"""Phase 2 Menu Management, Media Pipeline & Static WebP Route (API-026..API-031)."""

from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import AppError, success_response
from app.core.rbac import Role, require_feature_flag, require_venue_role
from app.core.validation import clean_optional_text, clean_text
from app.core.valkey_client import (
    check_and_store_idempotency,
    delete_ephemeral_json,
    evict_public_menu_cache,
    get_ephemeral_json,
    set_ephemeral_json,
)
from app.db.base import get_db, uuid7
from app.db.models import (
    Menu,
    MenuCategory,
    MenuItem,
    MenuMediaAsset,
    Venue,
)
from app.schemas.menus_qr import (
    ALLOWED_ALLERGENS,
    ALLOWED_DIETARY_TAGS,
    BulkItemActionRequest,
    BulkItemAvailabilityRequest,
    CreateCategoryRequest,
    CreateMenuItemRequest,
    CreateMenuRequest,
    CsvImportCommitRequest,
    ItemAvailabilityRequest,
    ReorderIdsRequest,
    UpdateCategoryRequest,
    UpdateMenuItemRequest,
    UpdateMenuRequest,
    UpdateMenuSettingsRequest,
)
from app.services.audit import write_audit_log
from app.services.media import (
    MAX_MEDIA_BYTES,
    delete_media_files,
    transcode_to_webp,
    write_media_files_atomic,
)

router = APIRouter(tags=["menus-admin"])

_FILENAME_RE_SEG = r"^[a-f0-9]{32}(_thumb)?\.webp$"
_SKU_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")
MAX_CSV_IMPORT_BYTES = 2 * 1024 * 1024
MAX_CSV_IMPORT_ROWS = 2000


def _csv_safe(val: object) -> str:
    s = "" if val is None else str(val)
    if s.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


def _csv_unquote_safe(val: str | None) -> str:
    s = (val or "").strip()
    if len(s) >= 2 and s[0] == "'" and s[1] in ("=", "+", "-", "@", "\t", "\r"):
        return s[1:]
    return s


def _clean_sku(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    sku = raw.strip().upper()
    if not _SKU_RE.match(sku):
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "SKU must be 1-64 alphanumeric, dash, or underscore characters",
            {"sku": "invalid SKU format"},
        )
    return sku


def _clean_translations(raw: dict[str, dict[str, str]] | None) -> dict[str, dict[str, str]]:
    if not raw:
        return {}
    out: dict[str, dict[str, str]] = {}
    for lang, fields in raw.items():
        if lang not in ("en", "hi") or not isinstance(fields, dict):
            continue
        cleaned_lang: dict[str, str] = {}
        name_val = clean_optional_text(fields.get("name"), max_len=120, field=f"translations.{lang}.name")
        desc_val = clean_optional_text(
            fields.get("description"), max_len=500, field=f"translations.{lang}.description"
        )
        if name_val:
            cleaned_lang["name"] = name_val
        if desc_val:
            cleaned_lang["description"] = desc_val
        if cleaned_lang:
            out[lang] = cleaned_lang
    return out


def _media_urls(asset: MenuMediaAsset | None) -> tuple[str | None, str | None]:
    if asset is None:
        return None, None
    return f"/media/menu/{asset.storage_key}", f"/media/menu/{asset.thumb_storage_key}"


def _menu_dict(m: Menu, category_count: int = 0, item_count: int = 0) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "venue_id": str(m.venue_id),
        "name": m.name,
        "description": m.description,
        "translations_json": m.translations_json or {},
        "status": m.status,
        "is_active": m.is_active,
        "is_default": m.is_default,
        "schedule_json": m.schedule_json,
        "sort_order": m.sort_order,
        "category_count": category_count,
        "item_count": item_count,
        "created_at": m.created_at.isoformat(),
        "updated_at": m.updated_at.isoformat(),
    }


def _category_dict(c: MenuCategory, item_count: int = 0) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "venue_id": str(c.venue_id),
        "menu_id": str(c.menu_id),
        "name": c.name,
        "description": c.description,
        "translations_json": c.translations_json or {},
        "is_active": c.is_active,
        "sort_order": c.sort_order,
        "item_count": item_count,
    }


def _item_dict(item: MenuItem, asset: MenuMediaAsset | None = None) -> dict[str, Any]:
    full_url, thumb_url = _media_urls(asset)
    return {
        "id": str(item.id),
        "venue_id": str(item.venue_id),
        "category_id": str(item.category_id),
        "sku": item.sku,
        "name": item.name,
        "description": item.description,
        "translations_json": item.translations_json or {},
        "price_minor_units": item.price_minor_units,
        "compare_at_price_minor_units": item.compare_at_price_minor_units,
        "image_asset_id": str(item.image_asset_id) if item.image_asset_id else None,
        "image_url": full_url,
        "thumb_url": thumb_url,
        "image_alt": item.image_alt,
        "is_available": item.is_available,
        "unavailable_until": item.unavailable_until.isoformat() if item.unavailable_until else None,
        "is_featured": item.is_featured,
        "dietary_tags": item.dietary_tags or [],
        "allergens": item.allergens or [],
        "variants_json": item.variants_json or [],
        "prep_time_minutes": item.prep_time_minutes,
        "calories_kcal": item.calories_kcal,
        "sort_order": item.sort_order,
        "version": item.version,
        "updated_at": item.updated_at.isoformat(),
    }


async def _bump_menu_revision(db: AsyncSession, venue_id: uuid.UUID) -> None:
    await db.execute(
        update(Venue).where(Venue.id == venue_id).values(menu_revision=Venue.menu_revision + 1)
    )


# ---------------------------------------------------------------------------
# Menus & Settings (API-026, API-027)
# ---------------------------------------------------------------------------


@router.get("/api/v1/venues/{venue_id}/menus")
async def list_menus(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-026 (list): Return all non-deleted menus + venue menu settings."""
    venue = (
        await db.execute(
            select(Venue).where(
                Venue.id == venue_id,
                Venue.organization_id == actor.organization_id,
                Venue.deleted_at.is_(None),
            )
        )
    ).scalar_one()

    menus = (
        (
            await db.execute(
                select(Menu)
                .where(
                    Menu.venue_id == venue_id,
                    Menu.organization_id == actor.organization_id,
                    Menu.deleted_at.is_(None),
                )
                .order_by(Menu.sort_order.asc(), Menu.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    cats = (
        (
            await db.execute(
                select(MenuCategory).where(
                    MenuCategory.venue_id == venue_id,
                    MenuCategory.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    items = (
        (
            await db.execute(
                select(MenuItem.category_id).where(
                    MenuItem.venue_id == venue_id,
                    MenuItem.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )

    cat_to_menu = {c.id: c.menu_id for c in cats}
    cat_counts: dict[uuid.UUID, int] = {}
    for c in cats:
        cat_counts[c.menu_id] = cat_counts.get(c.menu_id, 0) + 1
    item_counts: dict[uuid.UUID, int] = {}
    for cid in items:
        mid = cat_to_menu.get(cid)
        if mid is not None:
            item_counts[mid] = item_counts.get(mid, 0) + 1

    return success_response(
        {
            "venue_settings": {
                "currency_code": venue.currency_code,
                "menu_public_enabled": venue.menu_public_enabled,
                "show_unavailable_items_public": venue.show_unavailable_items_public,
                "logo_storage_key": venue.logo_storage_key,
                "logo_url": f"/media/menu/{venue.logo_storage_key}"
                if venue.logo_storage_key
                else None,
                "menu_tagline": venue.menu_tagline,
                "menu_revision": venue.menu_revision,
                "qr_grace_days": venue.qr_grace_days,
                "allow_host_menu_availability": venue.allow_host_menu_availability,
            },
            "items": [
                _menu_dict(m, cat_counts.get(m.id, 0), item_counts.get(m.id, 0)) for m in menus
            ],
        }
    )


@router.post("/api/v1/venues/{venue_id}/menus", status_code=201)
async def create_menu(
    venue_id: uuid.UUID,
    body: CreateMenuRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-026 (create): Create a menu (DRAFT or PUBLISHED)."""
    name = clean_text(body.name, max_len=100, field="name")
    desc = clean_optional_text(body.description, max_len=300, field="description")

    if body.status == "PUBLISHED":
        raise AppError(
            422,
            "MENU_NOT_PUBLISHABLE",
            "Create menu as DRAFT first and add at least one active category and item before publishing",
        )

    dup = (
        await db.execute(
            select(Menu.id).where(
                Menu.venue_id == venue_id,
                Menu.deleted_at.is_(None),
                func.lower(Menu.name) == name.lower(),
            )
        )
    ).scalar_one_or_none()
    if dup is not None:
        raise AppError(
            409,
            "DUPLICATE_MENU_NAME",
            f"Menu '{name}' already exists",
            {"name": "duplicate menu name"},
        )

    if body.is_default:
        await db.execute(
            update(Menu)
            .where(Menu.venue_id == venue_id, Menu.deleted_at.is_(None))
            .values(is_default=False)
        )

    m = Menu(
        id=uuid7(),
        organization_id=actor.organization_id,
        venue_id=venue_id,
        name=name,
        description=desc,
        translations_json=_clean_translations(body.translations_json),
        status=body.status,
        is_active=body.is_active,
        is_default=body.is_default,
        schedule_json=body.schedule_json.model_dump() if body.schedule_json else None,
        sort_order=body.sort_order,
    )
    db.add(m)
    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="MENU_CREATED",
        target_type="menu",
        target_id=m.id,
        after_json={"name": m.name, "status": m.status},
        request=request,
    )
    await db.commit()
    await db.refresh(m)
    await evict_public_menu_cache(str(venue_id))
    return success_response(_menu_dict(m), status_code=201)


@router.patch("/api/v1/venues/{venue_id}/menus/{menu_id}")
async def update_menu(
    venue_id: uuid.UUID,
    menu_id: uuid.UUID,
    body: UpdateMenuRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-026 (update): Update menu metadata, schedule, or publish status."""
    m = (
        await db.execute(
            select(Menu).where(
                Menu.id == menu_id,
                Menu.venue_id == venue_id,
                Menu.organization_id == actor.organization_id,
                Menu.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if m is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Menu not found")

    if body.name is not None:
        new_name = clean_text(body.name, max_len=100, field="name")
        if new_name.lower() != m.name.lower():
            dup = (
                await db.execute(
                    select(Menu.id).where(
                        Menu.venue_id == venue_id,
                        Menu.deleted_at.is_(None),
                        Menu.id != menu_id,
                        func.lower(Menu.name) == new_name.lower(),
                    )
                )
            ).scalar_one_or_none()
            if dup is not None:
                raise AppError(
                    409,
                    "DUPLICATE_MENU_NAME",
                    f"Menu '{new_name}' already exists",
                    {"name": "duplicate menu name"},
                )
        m.name = new_name

    if body.description is not None:
        m.description = clean_optional_text(body.description, max_len=300, field="description")
    if body.translations_json is not None:
        m.translations_json = _clean_translations(body.translations_json)

    if body.status == "PUBLISHED" and m.status != "PUBLISHED":
        pub_item_cnt = (
            await db.execute(
                select(func.count())
                .select_from(MenuItem)
                .join(MenuCategory, MenuCategory.id == MenuItem.category_id)
                .where(
                    MenuCategory.menu_id == menu_id,
                    MenuCategory.deleted_at.is_(None),
                    MenuCategory.is_active.is_(True),
                    MenuItem.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        if pub_item_cnt < 1:
            raise AppError(
                422,
                "MENU_NOT_PUBLISHABLE",
                "Cannot publish menu without at least 1 active category containing 1 item",
            )

    prev_status = m.status
    if body.status is not None:
        m.status = body.status
    if body.is_active is not None:
        m.is_active = body.is_active
    if body.is_default is True:
        await db.execute(
            update(Menu)
            .where(Menu.venue_id == venue_id, Menu.id != menu_id, Menu.deleted_at.is_(None))
            .values(is_default=False)
        )
        m.is_default = True
    elif body.is_default is False:
        m.is_default = False
    if body.clear_schedule:
        m.schedule_json = None
    elif body.schedule_json is not None:
        m.schedule_json = body.schedule_json.model_dump()
    if body.sort_order is not None:
        m.sort_order = body.sort_order
    m.updated_at = datetime.now(UTC)

    await _bump_menu_revision(db, venue_id)
    action = (
        "MENU_PUBLISH_TOGGLED" if body.status and body.status != prev_status else "MENU_UPDATED"
    )
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action=action,
        target_type="menu",
        target_id=m.id,
        after_json={"name": m.name, "status": m.status, "is_active": m.is_active},
        request=request,
    )
    await db.commit()
    await db.refresh(m)
    await evict_public_menu_cache(str(venue_id))
    return success_response(_menu_dict(m))


@router.post("/api/v1/venues/{venue_id}/menus/{menu_id}/duplicate", status_code=201)
async def duplicate_menu(
    venue_id: uuid.UUID,
    menu_id: uuid.UUID,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Clone an entire menu with all categories and items into a DRAFT copy."""
    orig = (
        await db.execute(
            select(Menu).where(
                Menu.id == menu_id,
                Menu.venue_id == venue_id,
                Menu.organization_id == actor.organization_id,
                Menu.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if orig is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Menu not found")

    existing_names = {
        n.lower()
        for n in (
            await db.execute(
                select(Menu.name).where(Menu.venue_id == venue_id, Menu.deleted_at.is_(None))
            )
        )
        .scalars()
        .all()
    }
    copy_name = f"{orig.name[:93]} (Copy)"
    suffix_idx = 2
    while copy_name.lower() in existing_names:
        sfx = f" ({suffix_idx})"
        copy_name = f"{orig.name[: 100 - len(sfx)]}{sfx}"
        suffix_idx += 1

    clone = Menu(
        id=uuid7(),
        organization_id=actor.organization_id,
        venue_id=venue_id,
        name=copy_name,
        description=orig.description,
        translations_json=dict(orig.translations_json or {}),
        status="DRAFT",
        is_active=True,
        is_default=False,
        schedule_json=dict(orig.schedule_json) if orig.schedule_json else None,
        sort_order=orig.sort_order + 1,
    )
    db.add(clone)
    await db.flush()

    orig_cats = (
        (
            await db.execute(
                select(MenuCategory)
                .where(MenuCategory.menu_id == orig.id, MenuCategory.deleted_at.is_(None))
                .order_by(MenuCategory.sort_order.asc())
            )
        )
        .scalars()
        .all()
    )
    cat_map: dict[uuid.UUID, uuid.UUID] = {}
    for c in orig_cats:
        new_cid = uuid7()
        cat_map[c.id] = new_cid
        db.add(
            MenuCategory(
                id=new_cid,
                organization_id=actor.organization_id,
                venue_id=venue_id,
                menu_id=clone.id,
                name=c.name,
                description=c.description,
                translations_json=dict(c.translations_json or {}),
                is_active=c.is_active,
                sort_order=c.sort_order,
            )
        )
    await db.flush()

    item_count = 0
    if cat_map:
        orig_items = (
            (
                await db.execute(
                    select(MenuItem)
                    .where(
                        MenuItem.category_id.in_(list(cat_map.keys())),
                        MenuItem.deleted_at.is_(None),
                    )
                    .order_by(MenuItem.sort_order.asc())
                )
            )
            .scalars()
            .all()
        )
        for it in orig_items:
            db.add(
                MenuItem(
                    id=uuid7(),
                    organization_id=actor.organization_id,
                    venue_id=venue_id,
                    category_id=cat_map[it.category_id],
                    sku=None,
                    name=it.name,
                    description=it.description,
                    translations_json=dict(it.translations_json or {}),
                    price_minor_units=it.price_minor_units,
                    compare_at_price_minor_units=it.compare_at_price_minor_units,
                    image_asset_id=it.image_asset_id,
                    image_alt=it.image_alt,
                    is_available=it.is_available,
                    is_featured=it.is_featured,
                    dietary_tags=list(it.dietary_tags or []),
                    allergens=list(it.allergens or []),
                    variants_json=list(it.variants_json or []),
                    prep_time_minutes=it.prep_time_minutes,
                    calories_kcal=it.calories_kcal,
                    sort_order=it.sort_order,
                )
            )
            item_count += 1

    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="MENU_DUPLICATED",
        target_type="menu",
        target_id=clone.id,
        after_json={"source_menu_id": str(orig.id), "name": clone.name, "items": item_count},
        request=request,
    )
    await db.commit()
    await db.refresh(clone)
    await evict_public_menu_cache(str(venue_id))
    return success_response(_menu_dict(clone, len(cat_map), item_count), status_code=201)


@router.delete("/api/v1/venues/{venue_id}/menus/{menu_id}")
async def delete_menu(
    venue_id: uuid.UUID,
    menu_id: uuid.UUID,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-026 (delete): Atomically soft-delete menu and cascade soft-delete categories & items."""
    m = (
        await db.execute(
            select(Menu).where(
                Menu.id == menu_id,
                Menu.venue_id == venue_id,
                Menu.organization_id == actor.organization_id,
                Menu.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if m is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Menu not found")

    now = datetime.now(UTC)
    cat_ids = (
        (
            await db.execute(
                select(MenuCategory.id).where(
                    MenuCategory.menu_id == menu_id, MenuCategory.deleted_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    if cat_ids:
        await db.execute(
            update(MenuItem)
            .where(MenuItem.category_id.in_(cat_ids), MenuItem.deleted_at.is_(None))
            .values(deleted_at=now, updated_at=now)
        )
        await db.execute(
            update(MenuCategory)
            .where(MenuCategory.id.in_(cat_ids))
            .values(deleted_at=now, updated_at=now)
        )
    m.deleted_at = now
    m.updated_at = now

    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="MENU_DELETED",
        target_type="menu",
        target_id=m.id,
        before_json={"name": m.name},
        after_json={"deleted_at": now.isoformat()},
        request=request,
    )
    await db.commit()
    await evict_public_menu_cache(str(venue_id))
    return success_response({"deleted": True, "menu_id": str(menu_id)})


@router.patch("/api/v1/venues/{venue_id}/menu-settings")
async def update_menu_settings(
    venue_id: uuid.UUID,
    body: UpdateMenuSettingsRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-027: Update venue branding, publish switch, host-86 toggle, and OWNER-only currency lock."""
    venue = (
        await db.execute(
            select(Venue).where(
                Venue.id == venue_id,
                Venue.organization_id == actor.organization_id,
                Venue.deleted_at.is_(None),
            )
        )
    ).scalar_one()

    if body.currency_code is not None and body.currency_code != venue.currency_code:
        if Role(actor.role) != Role.OWNER:
            raise AppError(403, "AUTH_FORBIDDEN", "Only OWNER may change venue currency_code")
        priced_count = (
            await db.execute(
                select(func.count())
                .select_from(MenuItem)
                .where(
                    MenuItem.venue_id == venue_id,
                    MenuItem.deleted_at.is_(None),
                    MenuItem.price_minor_units > 0,
                )
            )
        ).scalar_one()
        if priced_count > 0 and not body.currency_override_confirm:
            raise AppError(
                409,
                "CURRENCY_LOCKED",
                "Currency change blocked while priced items exist; confirm currency_override_confirm=true to proceed",
                {"currency_code": "priced items exist"},
            )
        venue.currency_code = body.currency_code

    if body.menu_public_enabled is not None:
        venue.menu_public_enabled = body.menu_public_enabled
    if body.show_unavailable_items_public is not None:
        venue.show_unavailable_items_public = body.show_unavailable_items_public
    if body.menu_tagline is not None:
        venue.menu_tagline = clean_optional_text(
            body.menu_tagline, max_len=160, field="menu_tagline"
        )
    if body.logo_storage_key is not None:
        venue.logo_storage_key = clean_optional_text(
            body.logo_storage_key, max_len=512, field="logo_storage_key"
        )
    if body.allow_host_menu_availability is not None:
        venue.allow_host_menu_availability = body.allow_host_menu_availability
    if body.qr_grace_days is not None:
        venue.qr_grace_days = body.qr_grace_days

    venue.menu_revision += 1
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="MENU_PUBLISH_TOGGLED" if body.menu_public_enabled is not None else "MENU_UPDATED",
        target_type="venue",
        target_id=venue_id,
        after_json={
            "currency_code": venue.currency_code,
            "menu_public_enabled": venue.menu_public_enabled,
            "show_unavailable_items_public": venue.show_unavailable_items_public,
            "allow_host_menu_availability": venue.allow_host_menu_availability,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(venue)
    await evict_public_menu_cache(str(venue_id))
    return success_response(
        {
            "currency_code": venue.currency_code,
            "menu_public_enabled": venue.menu_public_enabled,
            "show_unavailable_items_public": venue.show_unavailable_items_public,
            "logo_storage_key": venue.logo_storage_key,
            "logo_url": f"/media/menu/{venue.logo_storage_key}" if venue.logo_storage_key else None,
            "menu_tagline": venue.menu_tagline,
            "menu_revision": venue.menu_revision,
            "qr_grace_days": venue.qr_grace_days,
            "allow_host_menu_availability": venue.allow_host_menu_availability,
        }
    )


# ---------------------------------------------------------------------------
# Menu Categories (API-028)
# ---------------------------------------------------------------------------


@router.get("/api/v1/venues/{venue_id}/menus/{menu_id}/categories")
async def list_categories(
    venue_id: uuid.UUID,
    menu_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-028 (list): Ordered categories inside a menu."""
    cats = (
        (
            await db.execute(
                select(MenuCategory)
                .where(
                    MenuCategory.venue_id == venue_id,
                    MenuCategory.menu_id == menu_id,
                    MenuCategory.organization_id == actor.organization_id,
                    MenuCategory.deleted_at.is_(None),
                )
                .order_by(MenuCategory.sort_order.asc(), MenuCategory.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    counts_rows = (
        await db.execute(
            select(MenuItem.category_id, func.count())
            .where(MenuItem.venue_id == venue_id, MenuItem.deleted_at.is_(None))
            .group_by(MenuItem.category_id)
        )
    ).all()
    counts = {row[0]: int(row[1]) for row in counts_rows}
    return success_response({"items": [_category_dict(c, counts.get(c.id, 0)) for c in cats]})


@router.post("/api/v1/venues/{venue_id}/menus/{menu_id}/categories", status_code=201)
async def create_category(
    venue_id: uuid.UUID,
    menu_id: uuid.UUID,
    body: CreateCategoryRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-028 (create): Add ordered category inside a menu."""
    menu = (
        await db.execute(
            select(Menu).where(
                Menu.id == menu_id,
                Menu.venue_id == venue_id,
                Menu.organization_id == actor.organization_id,
                Menu.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if menu is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Menu not found")

    name = clean_text(body.name, max_len=100, field="name")
    desc = clean_optional_text(body.description, max_len=300, field="description")
    dup = (
        await db.execute(
            select(MenuCategory.id).where(
                MenuCategory.menu_id == menu_id,
                MenuCategory.deleted_at.is_(None),
                func.lower(MenuCategory.name) == name.lower(),
            )
        )
    ).scalar_one_or_none()
    if dup is not None:
        raise AppError(
            409,
            "DUPLICATE_CATEGORY_NAME",
            f"Category '{name}' already exists in this menu",
            {"name": "duplicate category name"},
        )

    cat = MenuCategory(
        id=uuid7(),
        organization_id=actor.organization_id,
        venue_id=venue_id,
        menu_id=menu_id,
        name=name,
        description=desc,
        translations_json=_clean_translations(body.translations_json),
        is_active=body.is_active,
        sort_order=body.sort_order,
    )
    db.add(cat)
    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="CATEGORY_CREATED",
        target_type="menu_category",
        target_id=cat.id,
        after_json={"menu_id": str(menu_id), "name": cat.name},
        request=request,
    )
    await db.commit()
    await db.refresh(cat)
    await evict_public_menu_cache(str(venue_id))
    return success_response(_category_dict(cat), status_code=201)


@router.patch("/api/v1/venues/{venue_id}/menus/{menu_id}/categories/reorder")
async def reorder_categories(
    venue_id: uuid.UUID,
    menu_id: uuid.UUID,
    body: ReorderIdsRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-028 (reorder): Atomically update category sort_order."""
    cats = (
        (
            await db.execute(
                select(MenuCategory).where(
                    MenuCategory.venue_id == venue_id,
                    MenuCategory.menu_id == menu_id,
                    MenuCategory.organization_id == actor.organization_id,
                    MenuCategory.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    by_id = {c.id: c for c in cats}
    for idx, cid in enumerate(body.ids):
        if cid in by_id:
            by_id[cid].sort_order = idx
    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="CATEGORY_REORDERED",
        target_type="menu",
        target_id=menu_id,
        after_json={"ordered_ids": [str(i) for i in body.ids]},
        request=request,
    )
    await db.commit()
    await evict_public_menu_cache(str(venue_id))
    return success_response({"reordered": len(body.ids)})


@router.patch("/api/v1/venues/{venue_id}/categories/{category_id}")
async def update_category(
    venue_id: uuid.UUID,
    category_id: uuid.UUID,
    body: UpdateCategoryRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-028 (update): Rename, toggle active, or update category sort_order."""
    cat = (
        await db.execute(
            select(MenuCategory).where(
                MenuCategory.id == category_id,
                MenuCategory.venue_id == venue_id,
                MenuCategory.organization_id == actor.organization_id,
                MenuCategory.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if cat is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Category not found")

    if body.name is not None:
        new_name = clean_text(body.name, max_len=100, field="name")
        if new_name.lower() != cat.name.lower():
            dup = (
                await db.execute(
                    select(MenuCategory.id).where(
                        MenuCategory.menu_id == cat.menu_id,
                        MenuCategory.deleted_at.is_(None),
                        MenuCategory.id != category_id,
                        func.lower(MenuCategory.name) == new_name.lower(),
                    )
                )
            ).scalar_one_or_none()
            if dup is not None:
                raise AppError(
                    409,
                    "DUPLICATE_CATEGORY_NAME",
                    f"Category '{new_name}' already exists",
                    {"name": "duplicate category name"},
                )
        cat.name = new_name
    if body.description is not None:
        cat.description = clean_optional_text(body.description, max_len=300, field="description")
    if body.translations_json is not None:
        cat.translations_json = _clean_translations(body.translations_json)
    if body.is_active is not None:
        cat.is_active = body.is_active
    if body.sort_order is not None:
        cat.sort_order = body.sort_order
    cat.updated_at = datetime.now(UTC)

    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="CATEGORY_UPDATED",
        target_type="menu_category",
        target_id=cat.id,
        after_json={"name": cat.name, "is_active": cat.is_active},
        request=request,
    )
    await db.commit()
    await db.refresh(cat)
    await evict_public_menu_cache(str(venue_id))
    return success_response(_category_dict(cat))


@router.delete("/api/v1/venues/{venue_id}/categories/{category_id}")
async def delete_category(
    venue_id: uuid.UUID,
    category_id: uuid.UUID,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    cascade: Annotated[bool, Query()] = False,
) -> JSONResponse:
    """API-028 (delete): Require cascade=true if category still contains active items (E-22)."""
    cat = (
        await db.execute(
            select(MenuCategory).where(
                MenuCategory.id == category_id,
                MenuCategory.venue_id == venue_id,
                MenuCategory.organization_id == actor.organization_id,
                MenuCategory.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if cat is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Category not found")

    item_count = (
        await db.execute(
            select(func.count())
            .select_from(MenuItem)
            .where(MenuItem.category_id == category_id, MenuItem.deleted_at.is_(None))
        )
    ).scalar_one()
    if item_count > 0 and not cascade:
        raise AppError(
            409,
            "CATEGORY_NOT_EMPTY",
            f"Category '{cat.name}' contains {item_count} item(s). Confirm cascade=true to archive both.",
            {"category_id": str(category_id)},
        )

    now = datetime.now(UTC)
    if item_count > 0:
        await db.execute(
            update(MenuItem)
            .where(MenuItem.category_id == category_id, MenuItem.deleted_at.is_(None))
            .values(deleted_at=now, updated_at=now)
        )
    cat.deleted_at = now
    cat.updated_at = now

    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="CATEGORY_DELETED",
        target_type="menu_category",
        target_id=cat.id,
        after_json={"name": cat.name, "cascaded_items": int(item_count)},
        request=request,
    )
    await db.commit()
    await evict_public_menu_cache(str(venue_id))
    return success_response({"deleted": True, "cascaded_items": int(item_count)})


# ---------------------------------------------------------------------------
# Menu Items & Quick-86 (API-029, API-030)
# ---------------------------------------------------------------------------


@router.get("/api/v1/venues/{venue_id}/menu-items")
async def list_menu_items(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    menu_id: Annotated[uuid.UUID | None, Query()] = None,
    category_id: Annotated[uuid.UUID | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    available: Annotated[str, Query(pattern="^(all|available|unavailable)$")] = "all",
    dietary_tag: Annotated[str | None, Query(max_length=32)] = None,
    format: Annotated[str, Query(pattern="^(json|csv)$")] = "json",
) -> Response:
    """API-029 (list): Filterable item list or UTF-8 BOM formula-safe CSV export."""
    q = select(MenuItem).where(
        MenuItem.venue_id == venue_id,
        MenuItem.organization_id == actor.organization_id,
        MenuItem.deleted_at.is_(None),
    )
    if category_id is not None:
        q = q.where(MenuItem.category_id == category_id)
    elif menu_id is not None:
        cat_ids = (
            (
                await db.execute(
                    select(MenuCategory.id).where(
                        MenuCategory.menu_id == menu_id, MenuCategory.deleted_at.is_(None)
                    )
                )
            )
            .scalars()
            .all()
        )
        q = q.where(MenuItem.category_id.in_(cat_ids)) if cat_ids else q.where(False)  # type: ignore[arg-type]

    rows = (
        (await db.execute(q.order_by(MenuItem.sort_order.asc(), MenuItem.created_at.asc())))
        .scalars()
        .all()
    )

    now = datetime.now(UTC)
    restored_any = False
    for r in rows:
        if not r.is_available and r.unavailable_until is not None and r.unavailable_until <= now:
            r.is_available = True
            r.unavailable_until = None
            r.updated_at = now
            restored_any = True
    if restored_any:
        await _bump_menu_revision(db, venue_id)
        await db.commit()
        await evict_public_menu_cache(str(venue_id))

    asset_ids = [r.image_asset_id for r in rows if r.image_asset_id is not None]
    assets_by_id: dict[uuid.UUID, MenuMediaAsset] = {}
    if asset_ids:
        a_rows = (
            (await db.execute(select(MenuMediaAsset).where(MenuMediaAsset.id.in_(asset_ids))))
            .scalars()
            .all()
        )
        assets_by_id = {a.id: a for a in a_rows}

    search_q = search.strip().lower() if search else None
    tag_u = dietary_tag.strip().upper() if dietary_tag else None
    filtered: list[MenuItem] = []
    for r in rows:
        if available == "available" and not r.is_available:
            continue
        if available == "unavailable" and r.is_available:
            continue
        if tag_u and tag_u not in (r.dietary_tags or []):
            continue
        if search_q:
            hay = f"{r.name} {r.description or ''} {r.sku or ''}".lower()
            if search_q not in hay:
                continue
        filtered.append(r)

    if format == "csv":
        cat_rows = (
            (await db.execute(select(MenuCategory).where(MenuCategory.venue_id == venue_id)))
            .scalars()
            .all()
        )
        menu_rows = (
            (await db.execute(select(Menu).where(Menu.venue_id == venue_id))).scalars().all()
        )
        cat_by_id = {c.id: c for c in cat_rows}
        menu_by_id = {m.id: m for m in menu_rows}

        buf = io.StringIO()
        buf.write("\ufeff")
        writer = csv.writer(buf)
        writer.writerow(
            [
                "id",
                "name",
                "description",
                "price_minor_units",
                "is_available",
                "dietary_tags",
                "sku",
                "category_name",
                "menu_name",
                "compare_at_price_minor_units",
                "allergens",
                "is_featured",
                "prep_time_minutes",
                "calories_kcal",
                "name_hi",
                "description_hi",
            ]
        )
        for r in filtered:
            cat_obj = cat_by_id.get(r.category_id)
            menu_obj = menu_by_id.get(cat_obj.menu_id) if cat_obj else None
            hi_tr = (r.translations_json or {}).get("hi", {})
            writer.writerow(
                [
                    _csv_safe(r.id),
                    _csv_safe(r.name),
                    _csv_safe(r.description),
                    r.price_minor_units,
                    r.is_available,
                    _csv_safe(",".join(r.dietary_tags or [])),
                    _csv_safe(r.sku or ""),
                    _csv_safe(cat_obj.name if cat_obj else ""),
                    _csv_safe(menu_obj.name if menu_obj else ""),
                    "" if r.compare_at_price_minor_units is None else r.compare_at_price_minor_units,
                    _csv_safe(",".join(r.allergens or [])),
                    r.is_featured,
                    "" if r.prep_time_minutes is None else r.prep_time_minutes,
                    "" if r.calories_kcal is None else r.calories_kcal,
                    _csv_safe(hi_tr.get("name", "")),
                    _csv_safe(hi_tr.get("description", "")),
                ]
            )
        return Response(
            content=buf.getvalue().encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="menu-items.csv"'},
        )

    return success_response(
        {
            "items": [
                _item_dict(r, assets_by_id.get(r.image_asset_id) if r.image_asset_id else None)
                for r in filtered
            ],
            "total": len(filtered),
        }
    )


@router.post("/api/v1/venues/{venue_id}/menu-items", status_code=201)
async def create_menu_item(
    venue_id: uuid.UUID,
    body: CreateMenuItemRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """API-029 (create): Create item inside same-venue category."""
    if idempotency_key:
        cached = await check_and_store_idempotency(f"menu-item:{venue_id}:{idempotency_key}")
        if cached is not None:
            return success_response(cached, status_code=201)

    cat = (
        await db.execute(
            select(MenuCategory).where(
                MenuCategory.id == body.category_id,
                MenuCategory.venue_id == venue_id,
                MenuCategory.organization_id == actor.organization_id,
                MenuCategory.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if cat is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Category not found in venue")

    asset: MenuMediaAsset | None = None
    if body.image_asset_id is not None:
        asset = (
            await db.execute(
                select(MenuMediaAsset).where(
                    MenuMediaAsset.id == body.image_asset_id,
                    MenuMediaAsset.venue_id == venue_id,
                    MenuMediaAsset.organization_id == actor.organization_id,
                )
            )
        ).scalar_one_or_none()
        if asset is None:
            raise AppError(404, "RESOURCE_NOT_FOUND", "Referenced media asset not found")

    name = clean_text(body.name, max_len=120, field="name")
    desc = clean_optional_text(body.description, max_len=500, field="description")
    img_alt = clean_optional_text(body.image_alt, max_len=160, field="image_alt")
    sku_clean = _clean_sku(body.sku)
    if sku_clean:
        sku_dup = (
            await db.execute(
                select(MenuItem.id).where(
                    MenuItem.venue_id == venue_id,
                    MenuItem.deleted_at.is_(None),
                    func.lower(MenuItem.sku) == sku_clean.lower(),
                )
            )
        ).scalar_one_or_none()
        if sku_dup is not None:
            raise AppError(
                409,
                "DUPLICATE_SKU",
                f"SKU '{sku_clean}' already exists in this venue",
                {"sku": "duplicate SKU"},
            )

    variants = [
        {
            "name": clean_text(v.name, max_len=60, field="variant.name"),
            "price_minor_units": v.price_minor_units,
            "is_available": v.is_available,
        }
        for v in body.variants_json
    ]

    item = MenuItem(
        id=uuid7(),
        organization_id=actor.organization_id,
        venue_id=venue_id,
        category_id=body.category_id,
        sku=sku_clean,
        name=name,
        description=desc,
        translations_json=_clean_translations(body.translations_json),
        price_minor_units=body.price_minor_units,
        compare_at_price_minor_units=body.compare_at_price_minor_units,
        image_asset_id=body.image_asset_id,
        image_alt=img_alt,
        is_available=body.is_available,
        is_featured=body.is_featured,
        dietary_tags=body.dietary_tags,
        allergens=body.allergens,
        variants_json=variants,
        prep_time_minutes=body.prep_time_minutes,
        calories_kcal=body.calories_kcal,
        sort_order=body.sort_order,
    )
    db.add(item)
    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="MENU_ITEM_CREATED",
        target_type="menu_item",
        target_id=item.id,
        after_json={
            "name": item.name,
            "price_minor_units": item.price_minor_units,
            "category_id": str(item.category_id),
        },
        request=request,
    )
    await db.commit()
    await db.refresh(item)
    await evict_public_menu_cache(str(venue_id))

    payload = _item_dict(item, asset)
    if idempotency_key:
        await check_and_store_idempotency(f"menu-item:{venue_id}:{idempotency_key}", payload)
    return success_response(payload, status_code=201)


@router.patch("/api/v1/venues/{venue_id}/menu-items/reorder")
async def reorder_menu_items(
    venue_id: uuid.UUID,
    body: ReorderIdsRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-029 (reorder): Update item sort_order atomically."""
    items = (
        (
            await db.execute(
                select(MenuItem).where(
                    MenuItem.venue_id == venue_id,
                    MenuItem.organization_id == actor.organization_id,
                    MenuItem.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    by_id = {i.id: i for i in items}
    for idx, iid in enumerate(body.ids):
        if iid in by_id:
            by_id[iid].sort_order = idx
    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="MENU_ITEM_UPDATED",
        target_type="venue",
        target_id=venue_id,
        after_json={"reordered_items": len(body.ids)},
        request=request,
    )
    await db.commit()
    await evict_public_menu_cache(str(venue_id))
    return success_response({"reordered": len(body.ids)})


@router.patch("/api/v1/venues/{venue_id}/menu-items/bulk-availability")
async def bulk_item_availability(
    venue_id: uuid.UUID,
    body: BulkItemAvailabilityRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.availability"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-030 (bulk Quick-86): Toggle availability across selected items & evict cache."""
    now = datetime.now(UTC)
    res = await db.execute(
        update(MenuItem)
        .where(
            MenuItem.venue_id == venue_id,
            MenuItem.organization_id == actor.organization_id,
            MenuItem.deleted_at.is_(None),
            MenuItem.id.in_(body.item_ids),
        )
        .values(is_available=body.is_available, unavailable_until=None, updated_at=now)
    )
    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="MENU_ITEM_AVAILABILITY_CHANGED",
        target_type="venue",
        target_id=venue_id,
        after_json={"count": len(body.item_ids), "is_available": body.is_available},
        request=request,
    )
    await db.commit()
    await evict_public_menu_cache(str(venue_id))
    return success_response({"updated_count": int(getattr(res, "rowcount", 0) or 0)})


@router.post("/api/v1/venues/{venue_id}/menu-items/bulk-action")
async def bulk_item_action(
    venue_id: uuid.UUID,
    body: BulkItemActionRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Bulk delete or move menu items across categories atomically."""
    now = datetime.now(UTC)
    if body.action == "move":
        if body.target_category_id is None:
            raise AppError(
                400,
                "VALIDATION_ERROR",
                "target_category_id is required when action is 'move'",
                {"target_category_id": "required"},
            )
        cat = (
            await db.execute(
                select(MenuCategory.id).where(
                    MenuCategory.id == body.target_category_id,
                    MenuCategory.venue_id == venue_id,
                    MenuCategory.organization_id == actor.organization_id,
                    MenuCategory.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if cat is None:
            raise AppError(404, "RESOURCE_NOT_FOUND", "Target category not found in venue")
        res = await db.execute(
            update(MenuItem)
            .where(
                MenuItem.venue_id == venue_id,
                MenuItem.organization_id == actor.organization_id,
                MenuItem.deleted_at.is_(None),
                MenuItem.id.in_(body.item_ids),
            )
            .values(category_id=body.target_category_id, updated_at=now)
        )
        affected = int(getattr(res, "rowcount", 0) or 0)
    else:
        res = await db.execute(
            update(MenuItem)
            .where(
                MenuItem.venue_id == venue_id,
                MenuItem.organization_id == actor.organization_id,
                MenuItem.deleted_at.is_(None),
                MenuItem.id.in_(body.item_ids),
            )
            .values(deleted_at=now, updated_at=now)
        )
        affected = int(getattr(res, "rowcount", 0) or 0)

    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="MENU_ITEMS_BULK_UPDATED",
        target_type="venue",
        target_id=venue_id,
        after_json={"action": body.action, "affected": affected},
        request=request,
    )
    await db.commit()
    await evict_public_menu_cache(str(venue_id))
    return success_response({"action": body.action, "affected": affected})


@router.get("/api/v1/venues/{venue_id}/menus/import/template")
async def download_menu_csv_template(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
) -> Response:
    """Download UTF-8 BOM formula-safe CSV template for bulk menu item import."""
    _ = venue_id, actor
    buf = io.StringIO()
    buf.write("\ufeff")
    w = csv.writer(buf)
    w.writerow(
        [
            "sku",
            "category_name",
            "name",
            "description",
            "price_minor_units",
            "compare_at_price_minor_units",
            "dietary_tags",
            "allergens",
            "is_available",
            "is_featured",
            "prep_time_minutes",
            "calories_kcal",
            "name_hi",
            "description_hi",
        ]
    )
    w.writerow(
        [
            "STARTER-01",
            "Starters",
            "Paneer Tikka",
            "Chargrilled cottage cheese with spices",
            28900,
            32900,
            "VEG,GLUTEN_FREE",
            "DAIRY",
            "true",
            "true",
            15,
            340,
            "पनीर टिक्का",
            "मसालेदार ग्रिल्ड पनीर",
        ]
    )
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="menu-import-template.csv"'},
    )


def _parse_bool_cell(raw: str | None, default: bool = True) -> bool:
    s = (raw or "").strip().lower()
    if not s:
        return default
    if s in ("true", "1", "yes", "y"):
        return True
    if s in ("false", "0", "no", "n"):
        return False
    raise ValueError(f"Invalid boolean '{raw}'")


@router.post("/api/v1/venues/{venue_id}/menus/import/preview")
async def preview_menu_csv_import(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
    menu_id: Annotated[uuid.UUID, Query(...)],
    mode: Annotated[Literal["create_only", "upsert_by_sku"], Query()] = "create_only",
) -> JSONResponse:
    """Validate uploaded CSV (<=2 MB, <=2000 rows) and stage preview for 15 minutes."""
    menu = (
        await db.execute(
            select(Menu).where(
                Menu.id == menu_id,
                Menu.venue_id == venue_id,
                Menu.organization_id == actor.organization_id,
                Menu.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if menu is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Target menu not found")

    raw_bytes = await file.read(MAX_CSV_IMPORT_BYTES + 1)
    if len(raw_bytes) > MAX_CSV_IMPORT_BYTES:
        raise AppError(
            413,
            "PAYLOAD_TOO_LARGE",
            "CSV file exceeds 2 MB import limit",
        )
    try:
        text_csv = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AppError(400, "VALIDATION_ERROR", "CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text_csv))
    if not reader.fieldnames or "name" not in reader.fieldnames or "price_minor_units" not in reader.fieldnames:
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "CSV must include 'name', 'category_name', and 'price_minor_units' columns",
        )

    existing_items = (
        (
            await db.execute(
                select(MenuItem).where(
                    MenuItem.venue_id == venue_id,
                    MenuItem.deleted_at.is_(None),
                    MenuItem.sku.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    existing_skus = {str(it.sku).upper(): str(it.id) for it in existing_items if it.sku}

    parsed_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    ui_rows: list[dict[str, Any]] = []
    seen_skus_in_file: set[str] = set()
    total_rows = 0
    will_create = 0
    will_update = 0

    def _record_row_error(
        r_num: int, raw_row: dict[str, Any], col: str, msg: str
    ) -> None:
        errors.append({"row": r_num, "column": col, "message": msg})
        if len(ui_rows) < 100:
            ui_rows.append(
                {
                    "row_number": r_num,
                    "sku": _csv_unquote_safe(raw_row.get("sku")).upper() or None,
                    "category_name": _csv_unquote_safe(raw_row.get("category_name"))[:100] or "—",
                    "name": _csv_unquote_safe(raw_row.get("name"))[:120] or "—",
                    "action": "error",
                    "errors": [f"{col}: {msg}"],
                }
            )

    for row_num, row in enumerate(reader, start=2):
        total_rows += 1
        if total_rows > MAX_CSV_IMPORT_ROWS:
            raise AppError(
                400,
                "VALIDATION_ERROR",
                f"CSV exceeds maximum {MAX_CSV_IMPORT_ROWS} rows per import",
            )
        cat_name = _csv_unquote_safe(row.get("category_name")) or "Imported"
        if "category_name" in (reader.fieldnames or []) and not _csv_unquote_safe(
            row.get("category_name")
        ):
            _record_row_error(row_num, row, "category_name", "Missing category_name")
            continue

        item_name = _csv_unquote_safe(row.get("name"))
        if not item_name or len(item_name) > 120:
            _record_row_error(row_num, row, "name", "Name must be 1-120 chars")
            continue

        try:
            price = int((row.get("price_minor_units") or "").strip())
            if price < 0 or price > 100_000_000:
                raise ValueError("price out of range")
        except Exception:
            _record_row_error(
                row_num, row, "price_minor_units", "Invalid integer minor units (0..100000000)"
            )
            continue

        comp_raw = (row.get("compare_at_price_minor_units") or "").strip()
        comp_price: int | None = None
        if comp_raw:
            try:
                comp_price = int(comp_raw)
                if comp_price <= price or comp_price > 100_000_000:
                    raise ValueError("compare price must exceed price")
            except Exception:
                _record_row_error(
                    row_num,
                    row,
                    "compare_at_price_minor_units",
                    "Compare price must be an integer greater than price_minor_units",
                )
                continue

        sku_val = _csv_unquote_safe(row.get("sku")).upper() or None
        if sku_val is not None:
            if not _SKU_RE.match(sku_val):
                _record_row_error(row_num, row, "sku", "Invalid SKU format")
                continue
            if sku_val in seen_skus_in_file:
                _record_row_error(row_num, row, "sku", f"Duplicate SKU '{sku_val}' in CSV")
                continue
            seen_skus_in_file.add(sku_val)

        if sku_val and sku_val in existing_skus and mode == "create_only":
            _record_row_error(
                row_num,
                row,
                "sku",
                f"SKU '{sku_val}' already exists (use upsert_by_sku mode)",
            )
            continue

        tags: list[str] = []
        tag_err = False
        for t_raw in (row.get("dietary_tags") or "").split(","):
            t_clean = t_raw.strip().upper()
            if not t_clean:
                continue
            if t_clean not in ALLOWED_DIETARY_TAGS:
                _record_row_error(
                    row_num, row, "dietary_tags", f"Unsupported dietary tag '{t_clean}'"
                )
                tag_err = True
                break
            if t_clean not in tags:
                tags.append(t_clean)
        if tag_err:
            continue

        allergens: list[str] = []
        all_err = False
        for a_raw in (row.get("allergens") or "").split(","):
            a_clean = a_raw.strip().upper()
            if not a_clean:
                continue
            if a_clean not in ALLOWED_ALLERGENS:
                _record_row_error(
                    row_num, row, "allergens", f"Unsupported allergen '{a_clean}'"
                )
                all_err = True
                break
            if a_clean not in allergens:
                allergens.append(a_clean)
        if all_err:
            continue

        try:
            is_avail = _parse_bool_cell(row.get("is_available"), True)
            is_feat = _parse_bool_cell(row.get("is_featured"), False)
        except ValueError as exc:
            _record_row_error(row_num, row, "is_available", str(exc))
            continue

        prep_raw = (row.get("prep_time_minutes") or "").strip()
        cal_raw = (row.get("calories_kcal") or "").strip()
        prep_val = int(prep_raw) if prep_raw.isdigit() else None
        cal_val = int(cal_raw) if cal_raw.isdigit() else None
        if prep_val is not None and not (1 <= prep_val <= 240):
            _record_row_error(row_num, row, "prep_time_minutes", "Must be 1..240 minutes")
            continue
        if cal_val is not None and not (0 <= cal_val <= 10000):
            _record_row_error(row_num, row, "calories_kcal", "Must be 0..10000 kcal")
            continue

        desc_val = _csv_unquote_safe(row.get("description"))[:500] or None
        name_hi = _csv_unquote_safe(row.get("name_hi"))[:120]
        desc_hi = _csv_unquote_safe(row.get("description_hi"))[:500]
        tr: dict[str, dict[str, str]] = {}
        if name_hi or desc_hi:
            tr["hi"] = {}
            if name_hi:
                tr["hi"]["name"] = name_hi
            if desc_hi:
                tr["hi"]["description"] = desc_hi

        op = "update" if (sku_val and sku_val in existing_skus and mode == "upsert_by_sku") else "create"
        if op == "update":
            will_update += 1
        else:
            will_create += 1

        if len(ui_rows) < 100:
            ui_rows.append(
                {
                    "row_number": row_num,
                    "sku": sku_val,
                    "category_name": cat_name[:100],
                    "name": item_name,
                    "action": op,
                    "errors": [],
                }
            )
        parsed_rows.append(
            {
                "row": row_num,
                "op": op,
                "target_item_id": existing_skus.get(sku_val) if sku_val else None,
                "sku": sku_val,
                "category_name": cat_name[:100],
                "name": item_name,
                "description": desc_val,
                "price_minor_units": price,
                "compare_at_price_minor_units": comp_price,
                "dietary_tags": tags,
                "allergens": allergens,
                "is_available": is_avail,
                "is_featured": is_feat,
                "prep_time_minutes": prep_val,
                "calories_kcal": cal_val,
                "translations_json": tr,
            }
        )

    import_id = str(uuid7())
    staging = {
        "organization_id": str(actor.organization_id),
        "venue_id": str(venue_id),
        "menu_id": str(menu_id),
        "mode": mode,
        "rows": parsed_rows,
        "errors": errors,
    }
    await set_ephemeral_json(f"tp:csv_import:{venue_id}:{import_id}", staging, ttl_seconds=900)

    return success_response(
        {
            "import_id": import_id,
            "expires_in": 900,
            "mode": mode,
            "total_rows": total_rows,
            "valid_rows": len(parsed_rows),
            "invalid_rows": len(errors),
            "will_create": will_create,
            "will_update": will_update,
            "errors": errors[:50],
            "rows": ui_rows,
            "preview_sample": [
                {
                    "row": r["row"],
                    "op": r["op"],
                    "sku": r["sku"],
                    "category_name": r["category_name"],
                    "name": r["name"],
                    "price_minor_units": r["price_minor_units"],
                }
                for r in parsed_rows[:10]
            ],
        }
    )


@router.post("/api/v1/venues/{venue_id}/menus/import/{import_id}/commit")
async def commit_menu_csv_import(
    venue_id: uuid.UUID,
    import_id: str,
    body: CsvImportCommitRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Commit validated CSV import preview rows (supports all_or_nothing and skip_invalid)."""
    key = f"tp:csv_import:{venue_id}:{import_id}"
    staged = await get_ephemeral_json(key)
    if staged is None or staged.get("organization_id") != str(actor.organization_id):
        raise AppError(
            410,
            "IMPORT_EXPIRED",
            "CSV import preview has expired or was already committed",
        )

    if body.strategy == "all_or_nothing" and staged.get("errors"):
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "CSV contains invalid rows; fix errors or commit with strategy='skip_invalid'",
        )

    menu_id = uuid.UUID(str(staged["menu_id"]))
    existing_cats = (
        (
            await db.execute(
                select(MenuCategory).where(
                    MenuCategory.menu_id == menu_id,
                    MenuCategory.venue_id == venue_id,
                    MenuCategory.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    cats_by_lower = {c.name.lower(): c for c in existing_cats}
    next_cat_sort = max((c.sort_order for c in existing_cats), default=0) + 1

    created_count = 0
    updated_count = 0
    now = datetime.now(UTC)

    for idx, r in enumerate(staged.get("rows", [])):
        cname = str(r["category_name"])
        cat_obj = cats_by_lower.get(cname.lower())
        if cat_obj is None:
            cat_obj = MenuCategory(
                id=uuid7(),
                organization_id=actor.organization_id,
                venue_id=venue_id,
                menu_id=menu_id,
                name=clean_text(cname, max_len=100, field="category_name"),
                sort_order=next_cat_sort,
                is_active=True,
            )
            next_cat_sort += 1
            db.add(cat_obj)
            await db.flush()
            cats_by_lower[cname.lower()] = cat_obj

        if r["op"] == "update" and r.get("target_item_id"):
            item_obj = (
                await db.execute(
                    select(MenuItem).where(
                        MenuItem.id == uuid.UUID(str(r["target_item_id"])),
                        MenuItem.venue_id == venue_id,
                        MenuItem.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if item_obj is not None:
                item_obj.category_id = cat_obj.id
                item_obj.name = clean_text(r["name"], max_len=120, field="name")
                item_obj.description = r["description"]
                item_obj.price_minor_units = int(r["price_minor_units"])
                item_obj.compare_at_price_minor_units = r["compare_at_price_minor_units"]
                item_obj.dietary_tags = list(r["dietary_tags"])
                item_obj.allergens = list(r["allergens"])
                item_obj.is_available = bool(r["is_available"])
                item_obj.is_featured = bool(r["is_featured"])
                item_obj.prep_time_minutes = r["prep_time_minutes"]
                item_obj.calories_kcal = r["calories_kcal"]
                if r.get("translations_json"):
                    merged = dict(item_obj.translations_json or {})
                    merged.update(r["translations_json"])
                    item_obj.translations_json = merged
                item_obj.version += 1
                item_obj.updated_at = now
                updated_count += 1
                continue

        db.add(
            MenuItem(
                id=uuid7(),
                organization_id=actor.organization_id,
                venue_id=venue_id,
                category_id=cat_obj.id,
                sku=r["sku"],
                name=clean_text(r["name"], max_len=120, field="name"),
                description=r["description"],
                translations_json=r.get("translations_json") or {},
                price_minor_units=int(r["price_minor_units"]),
                compare_at_price_minor_units=r["compare_at_price_minor_units"],
                is_available=bool(r["is_available"]),
                is_featured=bool(r["is_featured"]),
                dietary_tags=list(r["dietary_tags"]),
                allergens=list(r["allergens"]),
                prep_time_minutes=r["prep_time_minutes"],
                calories_kcal=r["calories_kcal"],
                sort_order=idx,
            )
        )
        created_count += 1

    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="MENU_CSV_IMPORTED",
        target_type="menu",
        target_id=menu_id,
        after_json={
            "strategy": body.strategy,
            "created": created_count,
            "updated": updated_count,
            "skipped_errors": len(staged.get("errors", [])),
        },
        request=request,
    )
    await db.commit()
    await delete_ephemeral_json(key)
    await evict_public_menu_cache(str(venue_id))
    return success_response(
        {
            "created": created_count,
            "updated": updated_count,
            "skipped_errors": len(staged.get("errors", [])),
        }
    )


@router.patch("/api/v1/venues/{venue_id}/menu-items/{item_id}")
async def update_menu_item(
    venue_id: uuid.UUID,
    item_id: uuid.UUID,
    body: UpdateMenuItemRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-029 (update): Optimistic-locked full item update."""
    item = (
        await db.execute(
            select(MenuItem).where(
                MenuItem.id == item_id,
                MenuItem.venue_id == venue_id,
                MenuItem.organization_id == actor.organization_id,
                MenuItem.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Menu item not found")

    if body.version is not None and item.version != body.version:
        raise AppError(409, "VERSION_CONFLICT", "Item modified concurrently; reload and retry")

    if body.category_id is not None and body.category_id != item.category_id:
        cat = (
            await db.execute(
                select(MenuCategory.id).where(
                    MenuCategory.id == body.category_id,
                    MenuCategory.venue_id == venue_id,
                    MenuCategory.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if cat is None:
            raise AppError(404, "RESOURCE_NOT_FOUND", "Target category not found")
        item.category_id = body.category_id

    if body.clear_sku:
        item.sku = None
    elif body.sku is not None:
        sku_clean = _clean_sku(body.sku)
        if sku_clean and sku_clean.lower() != (item.sku or "").lower():
            sku_dup = (
                await db.execute(
                    select(MenuItem.id).where(
                        MenuItem.venue_id == venue_id,
                        MenuItem.deleted_at.is_(None),
                        MenuItem.id != item_id,
                        func.lower(MenuItem.sku) == sku_clean.lower(),
                    )
                )
            ).scalar_one_or_none()
            if sku_dup is not None:
                raise AppError(
                    409,
                    "DUPLICATE_SKU",
                    f"SKU '{sku_clean}' already exists in this venue",
                    {"sku": "duplicate SKU"},
                )
        item.sku = sku_clean
    if body.name is not None:
        item.name = clean_text(body.name, max_len=120, field="name")
    if body.description is not None:
        item.description = clean_optional_text(body.description, max_len=500, field="description")
    if body.translations_json is not None:
        item.translations_json = _clean_translations(body.translations_json)
    if body.price_minor_units is not None:
        item.price_minor_units = body.price_minor_units
    if body.clear_compare_at_price:
        item.compare_at_price_minor_units = None
    elif body.compare_at_price_minor_units is not None:
        item.compare_at_price_minor_units = body.compare_at_price_minor_units

    if (
        item.compare_at_price_minor_units is not None
        and item.compare_at_price_minor_units <= item.price_minor_units
    ):
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "compare_at_price_minor_units must exceed price_minor_units",
            {"compare_at_price_minor_units": "must exceed price_minor_units"},
        )

    asset: MenuMediaAsset | None = None
    if body.clear_image:
        item.image_asset_id = None
    elif body.image_asset_id is not None:
        asset = (
            await db.execute(
                select(MenuMediaAsset).where(
                    MenuMediaAsset.id == body.image_asset_id,
                    MenuMediaAsset.venue_id == venue_id,
                    MenuMediaAsset.organization_id == actor.organization_id,
                )
            )
        ).scalar_one_or_none()
        if asset is None:
            raise AppError(404, "RESOURCE_NOT_FOUND", "Media asset not found")
        item.image_asset_id = body.image_asset_id
    elif item.image_asset_id is not None:
        asset = (
            await db.execute(select(MenuMediaAsset).where(MenuMediaAsset.id == item.image_asset_id))
        ).scalar_one_or_none()

    if body.image_alt is not None:
        item.image_alt = clean_optional_text(body.image_alt, max_len=160, field="image_alt")
    if body.is_available is not None:
        item.is_available = body.is_available
    if body.is_featured is not None:
        item.is_featured = body.is_featured
    if body.dietary_tags is not None:
        item.dietary_tags = body.dietary_tags
    if body.allergens is not None:
        item.allergens = body.allergens
    if body.variants_json is not None:
        item.variants_json = [
            {
                "name": clean_text(v.name, max_len=60, field="variant.name"),
                "price_minor_units": v.price_minor_units,
                "is_available": v.is_available,
            }
            for v in body.variants_json
        ]
    if body.prep_time_minutes is not None:
        item.prep_time_minutes = body.prep_time_minutes
    if body.calories_kcal is not None:
        item.calories_kcal = body.calories_kcal
    if body.sort_order is not None:
        item.sort_order = body.sort_order

    item.version += 1
    item.updated_at = datetime.now(UTC)
    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="MENU_ITEM_UPDATED",
        target_type="menu_item",
        target_id=item.id,
        after_json={"name": item.name, "price_minor_units": item.price_minor_units},
        request=request,
    )
    await db.commit()
    await db.refresh(item)
    await evict_public_menu_cache(str(venue_id))
    return success_response(_item_dict(item, asset))


@router.delete("/api/v1/venues/{venue_id}/menu-items/{item_id}")
async def delete_menu_item(
    venue_id: uuid.UUID,
    item_id: uuid.UUID,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-029 (delete): Soft-delete menu item."""
    item = (
        await db.execute(
            select(MenuItem).where(
                MenuItem.id == item_id,
                MenuItem.venue_id == venue_id,
                MenuItem.organization_id == actor.organization_id,
                MenuItem.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Menu item not found")

    now = datetime.now(UTC)
    item.deleted_at = now
    item.updated_at = now
    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="MENU_ITEM_DELETED",
        target_type="menu_item",
        target_id=item.id,
        before_json={"name": item.name},
        after_json={"deleted_at": now.isoformat()},
        request=request,
    )
    await db.commit()
    await evict_public_menu_cache(str(venue_id))
    return success_response({"deleted": True, "item_id": str(item_id)})


@router.post("/api/v1/venues/{venue_id}/menu-items/{item_id}/duplicate", status_code=201)
async def duplicate_menu_item(
    venue_id: uuid.UUID,
    item_id: uuid.UUID,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-029 (duplicate): Clone item cleanly with ` (Copy)` suffix."""
    orig = (
        await db.execute(
            select(MenuItem).where(
                MenuItem.id == item_id,
                MenuItem.venue_id == venue_id,
                MenuItem.organization_id == actor.organization_id,
                MenuItem.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if orig is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Menu item not found")

    copy_name = f"{orig.name[:113]} (Copy)"
    clone = MenuItem(
        id=uuid7(),
        organization_id=actor.organization_id,
        venue_id=venue_id,
        category_id=orig.category_id,
        sku=None,
        name=copy_name,
        description=orig.description,
        translations_json=dict(orig.translations_json or {}),
        price_minor_units=orig.price_minor_units,
        compare_at_price_minor_units=orig.compare_at_price_minor_units,
        image_asset_id=orig.image_asset_id,
        image_alt=orig.image_alt,
        is_available=orig.is_available,
        is_featured=orig.is_featured,
        dietary_tags=list(orig.dietary_tags or []),
        allergens=list(orig.allergens or []),
        variants_json=list(orig.variants_json or []),
        prep_time_minutes=orig.prep_time_minutes,
        calories_kcal=orig.calories_kcal,
        sort_order=orig.sort_order + 1,
    )
    db.add(clone)
    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="MENU_ITEM_CREATED",
        target_type="menu_item",
        target_id=clone.id,
        after_json={"cloned_from": str(orig.id), "name": clone.name},
        request=request,
    )
    await db.commit()
    await db.refresh(clone)

    asset: MenuMediaAsset | None = None
    if clone.image_asset_id is not None:
        asset = (
            await db.execute(
                select(MenuMediaAsset).where(MenuMediaAsset.id == clone.image_asset_id)
            )
        ).scalar_one_or_none()
    await evict_public_menu_cache(str(venue_id))
    return success_response(_item_dict(clone, asset), status_code=201)


@router.patch("/api/v1/venues/{venue_id}/menu-items/{item_id}/availability")
async def toggle_item_availability(
    venue_id: uuid.UUID,
    item_id: uuid.UUID,
    body: ItemAvailabilityRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.availability"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-030 (Quick 86): 1-tap toggle of item availability & immediate public cache eviction."""
    item = (
        await db.execute(
            select(MenuItem).where(
                MenuItem.id == item_id,
                MenuItem.venue_id == venue_id,
                MenuItem.organization_id == actor.organization_id,
                MenuItem.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Menu item not found")

    if body.unavailable_until is not None:
        now = datetime.now(UTC)
        until = (
            body.unavailable_until.replace(tzinfo=UTC)
            if body.unavailable_until.tzinfo is None
            else body.unavailable_until
        )
        if until <= now or (until - now).days > 30:
            raise AppError(
                400,
                "VALIDATION_ERROR",
                "unavailable_until must be in the future and at most 30 days ahead",
                {"unavailable_until": "must be 0..30 days in future"},
            )
        item.unavailable_until = until
    else:
        item.unavailable_until = None

    prev = item.is_available
    item.is_available = body.is_available
    item.updated_at = datetime.now(UTC)
    await _bump_menu_revision(db, venue_id)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="MENU_ITEM_AVAILABILITY_CHANGED",
        target_type="menu_item",
        target_id=item.id,
        before_json={"is_available": prev},
        after_json={"is_available": item.is_available},
        request=request,
    )
    await db.commit()
    await evict_public_menu_cache(str(venue_id))
    return success_response({"id": str(item.id), "is_available": item.is_available})


# ---------------------------------------------------------------------------
# Media Pipeline Upload, Delete & Immutable Static WebP Serving (API-031)
# ---------------------------------------------------------------------------


@router.post("/api/v1/venues/{venue_id}/menu/media", status_code=201)
async def upload_menu_media(
    venue_id: uuid.UUID,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    _flag: Annotated[None, Depends(require_feature_flag("menu_images_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
) -> JSONResponse:
    """API-031: Magic-byte validated JPEG/PNG/WebP -> EXIF-stripped deduplicated WebP."""
    raw = await file.read(MAX_MEDIA_BYTES + 1)
    if len(raw) > MAX_MEDIA_BYTES:
        raise AppError(413, "PAYLOAD_TOO_LARGE", "Image exceeds 5 MB upload cap")

    full_bytes, thumb_bytes, out_w, out_h, sha256 = transcode_to_webp(raw)

    # Deduplicate per venue by raw SHA-256 (E-20)
    existing = (
        await db.execute(
            select(MenuMediaAsset).where(
                MenuMediaAsset.venue_id == venue_id,
                MenuMediaAsset.organization_id == actor.organization_id,
                MenuMediaAsset.sha256 == sha256,
                MenuMediaAsset.status == "READY",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        root = Path(get_settings().menu_media_dir).resolve()
        if (root / existing.storage_key).is_file() and (
            root / existing.thumb_storage_key
        ).is_file():
            return success_response(
                {
                    "id": str(existing.id),
                    "storage_key": existing.storage_key,
                    "thumb_storage_key": existing.thumb_storage_key,
                    "image_url": f"/media/menu/{existing.storage_key}",
                    "thumb_url": f"/media/menu/{existing.thumb_storage_key}",
                    "byte_size": existing.byte_size,
                    "width_px": existing.width_px,
                    "height_px": existing.height_px,
                    "deduplicated": True,
                },
                status_code=201,
            )

    storage_key, thumb_key = write_media_files_atomic(venue_id, full_bytes, thumb_bytes)
    asset = MenuMediaAsset(
        id=uuid7(),
        organization_id=actor.organization_id,
        venue_id=venue_id,
        storage_key=storage_key,
        thumb_storage_key=thumb_key,
        mime_type="image/webp",
        byte_size=len(full_bytes),
        width_px=out_w,
        height_px=out_h,
        sha256=sha256,
        status="READY",
        uploaded_by=actor.id,
    )
    db.add(asset)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="MENU_MEDIA_UPLOADED",
        target_type="menu_media_asset",
        target_id=asset.id,
        after_json={"byte_size": asset.byte_size, "sha256": sha256},
        request=request,
    )
    await db.commit()
    await db.refresh(asset)
    return success_response(
        {
            "id": str(asset.id),
            "storage_key": asset.storage_key,
            "thumb_storage_key": asset.thumb_storage_key,
            "image_url": f"/media/menu/{asset.storage_key}",
            "thumb_url": f"/media/menu/{asset.thumb_storage_key}",
            "byte_size": asset.byte_size,
            "width_px": asset.width_px,
            "height_px": asset.height_px,
            "deduplicated": False,
        },
        status_code=201,
    )


@router.delete("/api/v1/venues/{venue_id}/menu/media/{asset_id}")
async def delete_menu_media(
    venue_id: uuid.UUID,
    asset_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    detach: Annotated[bool, Query()] = False,
) -> JSONResponse:
    """API-031 (delete): Block with 409 MEDIA_IN_USE if linked to active items unless detach=true (E-21)."""
    asset = (
        await db.execute(
            select(MenuMediaAsset).where(
                MenuMediaAsset.id == asset_id,
                MenuMediaAsset.venue_id == venue_id,
                MenuMediaAsset.organization_id == actor.organization_id,
            )
        )
    ).scalar_one_or_none()
    if asset is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Media asset not found")

    in_use_cnt = (
        await db.execute(
            select(func.count())
            .select_from(MenuItem)
            .where(MenuItem.image_asset_id == asset_id, MenuItem.deleted_at.is_(None))
        )
    ).scalar_one()
    if in_use_cnt > 0 and not detach:
        raise AppError(
            409,
            "MEDIA_IN_USE",
            f"Image is used by {in_use_cnt} menu item(s); pass detach=true to clear references and delete",
        )

    if in_use_cnt > 0:
        await db.execute(
            update(MenuItem).where(MenuItem.image_asset_id == asset_id).values(image_asset_id=None)
        )
        await _bump_menu_revision(db, venue_id)

    storage_key, thumb_key = asset.storage_key, asset.thumb_storage_key
    await db.delete(asset)
    await db.commit()
    delete_media_files(storage_key, thumb_key)
    await evict_public_menu_cache(str(venue_id))
    return success_response({"deleted": True, "detached_items": int(in_use_cnt)})


@router.get("/media/menu/{venue_id}/{filename}")
async def serve_menu_media_webp(venue_id: uuid.UUID, filename: str) -> FileResponse:
    """Serve transcoded WebP media directly in local/dev with strict sandbox headers (no traversal)."""
    import re

    if not re.match(_FILENAME_RE_SEG, filename):
        raise AppError(404, "RESOURCE_NOT_FOUND", "Media file not found")
    root = Path(get_settings().menu_media_dir).resolve()
    cand = (root / str(venue_id) / filename).resolve()
    if not cand.is_relative_to(root) or not cand.is_file():
        raise AppError(404, "RESOURCE_NOT_FOUND", "Media file not found")
    return FileResponse(
        cand,
        media_type="image/webp",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )
