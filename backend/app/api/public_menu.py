"""Public Read-Only Customer Digital Menu API (API-035).

Strict privacy & isolation guarantees:
- Zero AuthN cookie/JWT dependencies and zero Set-Cookie headers.
- Reads DB strictly through `get_public_db()` (`tablepulse_public` role on read-only views).
- Strict `PublicMenuResponse` (`extra="forbid"`) prevents leaking internal IDs or staff data.
- Privacy-safe debounced scan counting discards IP hashes via an ephemeral daily memory salt.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rbac import require_feature_flag
from app.core.valkey_client import (
    check_rate_limit,
    claim_public_scan_debounce,
    get_public_menu_cached,
    get_public_qr_cached,
    set_public_menu_cached,
    set_public_qr_cached,
)
from app.db.base import get_public_db, get_session_factory, uuid7
from app.schemas.public_menu import PublicMenuResponse
from app.services.menu_schedule import is_menu_scheduled_now
from app.services.qr_export import verify_qr_preview_token

router = APIRouter(tags=["public-menu"])

# Ephemeral daily salt held purely in memory (never written to DB/logs)
_scan_salt_date: date | None = None
_scan_salt_secret: str = ""
_background_tasks: set[asyncio.Task[None]] = set()


def _daily_scan_salt(today: date) -> str:
    global _scan_salt_date, _scan_salt_secret
    if _scan_salt_date != today or not _scan_salt_secret:
        _scan_salt_date = today
        _scan_salt_secret = secrets.token_hex(16)
    return _scan_salt_secret


async def _record_qr_scan_async(
    *,
    venue_id: str,
    table_id: str,
    qr_token: str,
    client_ip: str,
) -> None:
    try:
        today = datetime.now(UTC).date()
        salt = _daily_scan_salt(today)
        ip_hash = hashlib.sha256(f"{salt}:{client_ip}".encode()).hexdigest()[:24]
        dedup_key = f"tp:pub:scan_dedup:{today.isoformat()}:{ip_hash}:{qr_token}"
        should_count = await claim_public_scan_debounce(dedup_key, ttl_seconds=300)
        if not should_count:
            return

        now = datetime.now(UTC)
        async with get_session_factory()() as db:
            row = (
                await db.execute(
                    text(
                        """
                        UPDATE table_qr_codes
                        SET scan_count = scan_count + 1,
                            last_scanned_at = :now
                        WHERE token = :token
                          AND status IN ('ACTIVE', 'GRACE')
                        RETURNING organization_id, id
                        """
                    ),
                    {"token": qr_token, "now": now},
                )
            ).first()
            if row is None:
                await db.rollback()
                return
            org_id = str(row.organization_id)
            await db.execute(
                text(
                    """
                    INSERT INTO qr_scan_daily_stats
                        (id, organization_id, venue_id, table_id, scan_date, scan_count)
                    VALUES
                        (:id, :org_id, :venue_id, :table_id, :scan_date, 1)
                    ON CONFLICT (table_id, scan_date)
                    DO UPDATE SET scan_count = qr_scan_daily_stats.scan_count + 1
                    """
                ),
                {
                    "id": str(uuid7()),
                    "org_id": org_id,
                    "venue_id": venue_id,
                    "table_id": table_id,
                    "scan_date": today,
                },
            )
            await db.commit()
    except Exception:
        return


def _serialize_qr_binding(row: Any) -> dict[str, Any]:
    return {
        "token": row.token,
        "qr_status": row.qr_status,
        "grace_until": row.grace_until.isoformat() if row.grace_until else None,
        "revoked_reason": row.revoked_reason,
        "venue_id": str(row.venue_id),
        "table_id": str(row.table_id),
        "table_label": row.table_label,
        "table_is_active": bool(row.table_is_active),
        "table_deleted_at": row.table_deleted_at.isoformat() if row.table_deleted_at else None,
        "venue_deleted_at": row.venue_deleted_at.isoformat() if row.venue_deleted_at else None,
    }


def _build_menus_from_catalog_rows(
    catalog_rows: Sequence[Any],
    *,
    venue_timezone: str,
    show_unavailable: bool,
    now_utc: datetime,
) -> list[dict[str, Any]]:
    menus_map: dict[str, dict[str, Any]] = {}
    cats_map: dict[str, dict[str, Any]] = {}
    seen_items: set[str] = set()

    for r in catalog_rows:
        mid = str(r.menu_id)
        if mid not in menus_map:
            menus_map[mid] = {
                "id": mid,
                "name": r.menu_name,
                "description": r.menu_description,
                "schedule_json": r.menu_schedule_json,
                "is_default": bool(r.menu_is_default),
                "sort_order": int(r.menu_sort_order),
                "categories": [],
                "_cat_ids": set(),
            }
        m_obj = menus_map[mid]
        if r.category_id is None:
            continue
        cid = str(r.category_id)
        if cid not in cats_map:
            cats_map[cid] = {
                "id": cid,
                "name": r.category_name,
                "description": r.category_description,
                "sort_order": int(r.category_sort_order),
                "items": [],
            }
        if cid not in m_obj["_cat_ids"]:
            m_obj["_cat_ids"].add(cid)
            m_obj["categories"].append(cats_map[cid])

        if r.item_id is None:
            continue
        iid = str(r.item_id)
        if iid in seen_items:
            continue
        seen_items.add(iid)

        unavail_until = r.unavailable_until
        if isinstance(unavail_until, str):
            with contextlib.suppress(ValueError):
                unavail_until = datetime.fromisoformat(unavail_until)
        eff_available = bool(r.is_available) or (
            unavail_until is not None and unavail_until <= now_utc
        )
        if not eff_available and not show_unavailable:
            continue

        variants = []
        for v in r.variants_json or []:
            if isinstance(v, dict):
                variants.append(
                    {
                        "name": str(v.get("name", "")),
                        "price_minor_units": int(v.get("price_minor_units", 0)),
                        "is_available": bool(v.get("is_available", True)),
                    }
                )

        cats_map[cid]["items"].append(
            {
                "id": iid,
                "name": r.item_name,
                "description": r.item_description,
                "price_minor_units": int(r.price_minor_units),
                "compare_at_price_minor_units": (
                    int(r.compare_at_price_minor_units)
                    if r.compare_at_price_minor_units is not None
                    else None
                ),
                "image_url": f"/media/menu/{r.image_storage_key}" if r.image_storage_key else None,
                "thumb_url": f"/media/menu/{r.thumb_storage_key}" if r.thumb_storage_key else None,
                "image_alt": r.image_alt,
                "is_available": eff_available,
                "is_featured": bool(r.is_featured),
                "dietary_tags": list(r.dietary_tags or []),
                "allergens": list(r.allergens or []),
                "variants_json": variants,
                "prep_time_minutes": r.prep_time_minutes,
                "calories_kcal": r.calories_kcal,
            }
        )

    all_menus = sorted(menus_map.values(), key=lambda x: (x["sort_order"], x["name"]))
    scheduled = [
        m for m in all_menus if is_menu_scheduled_now(m["schedule_json"], venue_timezone, now_utc)
    ]
    selected = scheduled if scheduled else [m for m in all_menus if m["is_default"]]
    if not selected and all_menus:
        selected = all_menus

    cleaned_menus: list[dict[str, Any]] = []
    for m in selected:
        cleaned_cats = [
            {
                "id": c["id"],
                "name": c["name"],
                "description": c["description"],
                "items": c["items"],
            }
            for c in sorted(m["categories"], key=lambda x: (x["sort_order"], x["name"]))
            if c["items"]
        ]
        cleaned_menus.append(
            {
                "id": m["id"],
                "name": m["name"],
                "description": m["description"],
                "categories": cleaned_cats,
            }
        )
    return cleaned_menus


@router.get("/api/v1/public/menu/{qr_token}")
async def get_public_menu_by_qr(
    qr_token: str,
    request: Request,
    _flag: Annotated[None, Depends(require_feature_flag("public_menu_enabled"))],
    public_db: Annotated[AsyncSession, Depends(get_public_db)],
    p: Annotated[str | None, Query(max_length=128)] = None,
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
) -> Response:
    """API-035: Unauthenticated table QR -> digital menu endpoint (read-only least privilege)."""
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = await check_rate_limit(
        f"pub_menu:{client_ip}", limit=60, window_seconds=60, fail_closed=False
    )
    if not allowed:
        raise AppError(
            429,
            "RATE_LIMITED",
            "Too many menu requests from this client; please try again shortly",
            headers={"Retry-After": str(retry_after)},
        )

    now_utc = datetime.now(UTC)
    qr_data: dict[str, Any] | None = await get_public_qr_cached(qr_token)
    db_unavailable = False

    if qr_data is None:
        try:
            row = (
                await public_db.execute(
                    text("SELECT * FROM v_public_qr_resolution WHERE token = :token"),
                    {"token": qr_token},
                )
            ).first()
            if row is not None:
                qr_data = _serialize_qr_binding(row)
                if qr_data["qr_status"] in {"ACTIVE", "GRACE"}:
                    await set_public_qr_cached(qr_token, qr_data, ttl_seconds=300)
        except Exception:
            db_unavailable = True

    if qr_data is None:
        if db_unavailable:
            raise AppError(
                503,
                "SERVICE_UNAVAILABLE",
                "Menu service temporarily unavailable; please ask your server",
            )
        raise AppError(404, "QR_CODE_NOT_FOUND", "Table QR code was not found")

    if qr_data.get("venue_deleted_at"):
        raise AppError(404, "QR_CODE_NOT_FOUND", "Venue not found")

    qr_status = str(qr_data["qr_status"])
    grace_until_raw = qr_data.get("grace_until")
    grace_expired = False
    if qr_status == "GRACE":
        if not grace_until_raw:
            grace_expired = True
        else:
            grace_dt = datetime.fromisoformat(str(grace_until_raw))
            if grace_dt <= now_utc:
                grace_expired = True

    if qr_status == "REVOKED" or grace_expired:
        raise AppError(
            410,
            "QR_CODE_REVOKED",
            "This table QR sticker has been replaced. Please scan the updated code on your table.",
        )

    if not qr_data.get("table_is_active") or qr_data.get("table_deleted_at"):
        raise AppError(
            410,
            "TABLE_UNAVAILABLE",
            "This table is currently inactive. Please check with the host stand.",
        )

    venue_id = str(qr_data["venue_id"])
    table_id = str(qr_data["table_id"])
    preview_mode = bool(p and verify_qr_preview_token(qr_token, venue_id, p))

    # Venue-level cache key evicted immediately upon any menu/item/settings change
    cache_key = f"tp:pub:menu:{venue_id}:prev{int(preview_mode)}"
    latest_key = f"tp:pub:menu:latest:{venue_id}"
    payload_dict: dict[str, Any] | None = await get_public_menu_cached(cache_key)
    stale_served = False

    if payload_dict is None:
        try:
            venue_row = (
                await public_db.execute(
                    text(
                        """
                        SELECT
                            venue_name,
                            menu_tagline,
                            logo_storage_key,
                            currency_code,
                            timezone,
                            menu_public_enabled,
                            show_unavailable_items_public,
                            menu_revision
                        FROM v_public_qr_resolution
                        WHERE venue_id = :venue_id
                        LIMIT 1
                        """
                    ),
                    {"venue_id": uuid.UUID(venue_id)},
                )
            ).first()
            if venue_row is None:
                raise AppError(404, "QR_CODE_NOT_FOUND", "Venue not found")

            menu_public_enabled = bool(venue_row.menu_public_enabled)
            show_unavailable = bool(venue_row.show_unavailable_items_public)
            menu_revision = int(venue_row.menu_revision)
            menus_sections: list[dict[str, Any]] = []

            if menu_public_enabled or preview_mode:
                catalog_rows = (
                    await public_db.execute(
                        text(
                            """
                            SELECT *
                            FROM v_public_menu_catalog
                            WHERE venue_id = :venue_id
                            ORDER BY menu_sort_order ASC, category_sort_order ASC, item_sort_order ASC
                            """
                        ),
                        {"venue_id": uuid.UUID(venue_id)},
                    )
                ).all()
                menus_sections = _build_menus_from_catalog_rows(
                    catalog_rows,
                    venue_timezone=str(venue_row.timezone or "UTC"),
                    show_unavailable=show_unavailable,
                    now_utc=now_utc,
                )

            logo_key = venue_row.logo_storage_key
            raw_payload = {
                "venue": {
                    "name": str(venue_row.venue_name),
                    "tagline": venue_row.menu_tagline,
                    "logo_url": f"/media/menu/{logo_key}" if logo_key else None,
                    "currency_code": str(venue_row.currency_code),
                    "timezone": str(venue_row.timezone or "UTC"),
                },
                "table": {
                    "label": str(qr_data["table_label"]),
                },
                "menu_public_enabled": menu_public_enabled,
                "show_unavailable_items": show_unavailable,
                "preview_mode": preview_mode,
                "menu_revision": menu_revision,
                "menus": menus_sections,
            }
            validated = PublicMenuResponse.model_validate(raw_payload)
            payload_dict = validated.model_dump()
            await set_public_menu_cached(
                cache_key,
                payload_dict,
                ttl_seconds=60,
                latest_key=latest_key if not preview_mode else None,
                stale_ttl_seconds=86400,
            )
        except AppError:
            raise
        except Exception:
            stale = await get_public_menu_cached(latest_key)
            if stale is not None:
                payload_dict = dict(stale)
                stale_served = True
            else:
                raise AppError(
                    503,
                    "SERVICE_UNAVAILABLE",
                    "Menu catalog temporarily unavailable",
                ) from None

    payload_dict = dict(payload_dict)
    payload_dict["table"] = {"label": str(qr_data["table_label"])}
    payload_dict["preview_mode"] = preview_mode
    final_validated = PublicMenuResponse.model_validate(payload_dict)

    etag = f'W/"{venue_id}:{final_validated.menu_revision}:{int(preview_mode)}"'
    if if_none_match and if_none_match.strip() == etag:
        return Response(
            status_code=304,
            headers={
                "ETag": etag,
                "Cache-Control": "no-cache",
                "X-Robots-Tag": "noindex, nofollow",
            },
        )

    if not preview_mode and not stale_served:
        task = asyncio.create_task(
            _record_qr_scan_async(
                venue_id=venue_id,
                table_id=table_id,
                qr_token=qr_token,
                client_ip=client_ip,
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    headers = {
        "ETag": etag,
        "Cache-Control": "no-cache",
        "X-Robots-Tag": "noindex, nofollow",
    }
    if stale_served:
        headers["X-Stale"] = "1"

    return JSONResponse(
        status_code=200,
        content={"success": True, "data": final_validated.model_dump()},
        headers=headers,
    )
