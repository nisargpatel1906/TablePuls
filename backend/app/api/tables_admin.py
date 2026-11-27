"""Phase 2 Advanced Table Management API (API-024..API-025)."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import AppError, success_response
from app.core.rbac import require_feature_flag, require_venue_role
from app.core.validation import (
    clean_optional_text,
    clean_text,
    normalize_bulk_prefix,
    normalize_table_code,
)
from app.core.valkey_client import (
    check_and_store_idempotency,
    evict_public_menu_cache,
    evict_public_qr_cache,
    publish_cv_control,
)
from app.db.base import get_db, uuid7
from app.db.models import (
    Alert,
    Camera,
    DiningTable,
    MLReviewItem,
    QrScanDailyStat,
    TableQRCode,
    TableStateEvent,
    Venue,
    WaitlistEntry,
)
from app.schemas.tables_qr import (
    BulkCreateTablesRequest,
    BulkUpdateTablesRequest,
    CreateTableRequest,
    RestoreTableRequest,
    UpdateTableRequest,
)
from app.services.audit import write_audit_log
from app.services.realtime import ws_hub

router = APIRouter(tags=["tables-admin"])

MAX_TABLES_PER_VENUE = 500


def _qr_url(token: str) -> str:
    base = get_settings().public_app_url.rstrip("/")
    return f"{base}/m/{token}"


def _admin_table_dict(t: DiningTable, qr: TableQRCode | None = None) -> dict[str, Any]:
    is_monitored = bool(
        t.camera_id is not None and t.polygon_json is not None and len(t.polygon_json) >= 3
    )
    return {
        "id": str(t.id),
        "venue_id": str(t.venue_id),
        "camera_id": str(t.camera_id) if t.camera_id else None,
        "table_code": t.table_code,
        "display_name": t.display_name,
        "section_name": t.section_name,
        "min_capacity": t.min_capacity,
        "seat_capacity": t.seat_capacity,
        "shape": t.shape,
        "is_active": t.is_active,
        "is_combinable": t.is_combinable,
        "table_notes": t.table_notes,
        "floor_x": t.floor_x,
        "floor_y": t.floor_y,
        "polygon_json": t.polygon_json,
        "sort_order": t.sort_order,
        "is_monitored": is_monitored,
        "current_state": t.current_state,
        "current_guest_count": t.current_guest_count,
        "version": t.version,
        "created_at": t.created_at.isoformat(),
        "deleted_at": t.deleted_at.isoformat() if t.deleted_at else None,
        "qr_token": qr.token if qr else None,
        "qr_url": _qr_url(qr.token) if qr else None,
        "qr_status": qr.status if qr else None,
        "qr_scan_count": qr.scan_count if qr else 0,
    }


@router.get("/api/v1/venues/{venue_id}/tables")
async def list_venue_tables(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="tables.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Annotated[str | None, Query(max_length=80)] = None,
    section: Annotated[str | None, Query(max_length=60)] = None,
    status: Annotated[str, Query(pattern="^(active|inactive|archived|all)$")] = "all",
    mapped: Annotated[str, Query(pattern="^(mapped|unmapped|all)$")] = "all",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> JSONResponse:
    """API-024 (list): List and filter venue tables alongside active QR status and summary KPIs."""
    non_deleted_rows = (
        (
            await db.execute(
                select(DiningTable)
                .where(
                    DiningTable.venue_id == venue_id,
                    DiningTable.organization_id == actor.organization_id,
                    DiningTable.deleted_at.is_(None),
                )
                .order_by(DiningTable.sort_order.asc(), DiningTable.table_code.asc())
            )
        )
        .scalars()
        .all()
    )
    if status == "archived":
        all_rows = (
            (
                await db.execute(
                    select(DiningTable)
                    .where(
                        DiningTable.venue_id == venue_id,
                        DiningTable.organization_id == actor.organization_id,
                        DiningTable.deleted_at.is_not(None),
                    )
                    .order_by(DiningTable.deleted_at.desc(), DiningTable.table_code.asc())
                )
            )
            .scalars()
            .all()
        )
    else:
        all_rows = non_deleted_rows

    qr_rows = (
        (
            await db.execute(
                select(TableQRCode).where(
                    TableQRCode.venue_id == venue_id,
                    TableQRCode.organization_id == actor.organization_id,
                    TableQRCode.status == "ACTIVE",
                )
            )
        )
        .scalars()
        .all()
    )
    qr_by_table = {q.table_id: q for q in qr_rows}

    total_active = sum(1 for t in non_deleted_rows if t.is_active)
    total_seats = sum(t.seat_capacity for t in non_deleted_rows if t.is_active)
    mapped_count = sum(
        1
        for t in non_deleted_rows
        if t.is_active and t.camera_id is not None and t.polygon_json and len(t.polygon_json) >= 3
    )
    inactive_count = sum(1 for t in non_deleted_rows if not t.is_active)
    sections = sorted({t.section_name for t in non_deleted_rows})

    filtered: list[DiningTable] = []
    search_q = search.strip().lower() if search else None
    for t in all_rows:
        if status == "active" and not t.is_active:
            continue
        if status == "inactive" and t.is_active:
            continue
        if section and t.section_name != section:
            continue
        is_mapped = bool(t.camera_id is not None and t.polygon_json and len(t.polygon_json) >= 3)
        if mapped == "mapped" and not is_mapped:
            continue
        if mapped == "unmapped" and is_mapped:
            continue
        if search_q:
            hay = f"{t.table_code} {t.display_name or ''} {t.section_name}".lower()
            if search_q not in hay:
                continue
        filtered.append(t)

    total = len(filtered)
    start = (page - 1) * page_size
    page_items = filtered[start : start + page_size]

    return success_response(
        {
            "items": [_admin_table_dict(t, qr_by_table.get(t.id)) for t in page_items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "summary": {
                "total_active": total_active,
                "total_seats": total_seats,
                "mapped_count": mapped_count,
                "inactive_count": inactive_count,
                "sections": sections,
            },
        }
    )


@router.post("/api/v1/venues/{venue_id}/tables", status_code=201)
async def create_table(
    venue_id: uuid.UUID,
    body: CreateTableRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="tables.manage"))],
    _flag: Annotated[None, Depends(require_feature_flag("table_advanced_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """API-024 (create): Create a standalone or camera-linked table with automatic 128-bit QR."""
    if idempotency_key:
        cached = await check_and_store_idempotency(f"table-create:{venue_id}:{idempotency_key}")
        if cached is not None:
            return success_response(cached, status_code=201)

    code = normalize_table_code(body.table_code)
    section = clean_text(body.section_name, max_len=60, field="section_name")
    display_name = clean_optional_text(body.display_name, max_len=80, field="display_name")
    table_notes = clean_optional_text(body.table_notes, max_len=255, field="table_notes")

    active_count = (
        await db.execute(
            select(func.count())
            .select_from(DiningTable)
            .where(
                DiningTable.venue_id == venue_id,
                DiningTable.organization_id == actor.organization_id,
                DiningTable.deleted_at.is_(None),
            )
        )
    ).scalar_one()
    if active_count >= MAX_TABLES_PER_VENUE:
        raise AppError(
            422,
            "LIMIT_EXCEEDED",
            f"Venue cannot exceed {MAX_TABLES_PER_VENUE} active tables",
        )

    dup = (
        await db.execute(
            select(DiningTable.id).where(
                DiningTable.venue_id == venue_id,
                DiningTable.deleted_at.is_(None),
                func.upper(DiningTable.table_code) == code,
            )
        )
    ).scalar_one_or_none()
    if dup is not None:
        raise AppError(
            409,
            "DUPLICATE_TABLE_CODE",
            f"Table code '{code}' already exists in this venue",
            {"table_code": "already in use"},
        )

    if body.camera_id is not None:
        cam = (
            await db.execute(
                select(Camera).where(
                    Camera.id == body.camera_id,
                    Camera.venue_id == venue_id,
                    Camera.organization_id == actor.organization_id,
                    Camera.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if cam is None:
            raise AppError(404, "RESOURCE_NOT_FOUND", "Target camera not found")

    tbl = DiningTable(
        id=uuid7(),
        organization_id=actor.organization_id,
        venue_id=venue_id,
        camera_id=body.camera_id,
        table_code=code,
        display_name=display_name,
        section_name=section,
        min_capacity=body.min_capacity,
        seat_capacity=body.seat_capacity,
        polygon_json=None,
        floor_x=body.floor_x,
        floor_y=body.floor_y,
        shape=body.shape,
        is_active=body.is_active,
        is_combinable=body.is_combinable,
        table_notes=table_notes,
        sort_order=body.sort_order,
    )
    db.add(tbl)
    await db.flush()

    qr = TableQRCode(
        id=uuid7(),
        organization_id=actor.organization_id,
        venue_id=venue_id,
        table_id=tbl.id,
        token=secrets.token_urlsafe(16),
        status="ACTIVE",
        created_by=actor.id,
    )
    db.add(qr)

    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="TABLE_CREATED",
        target_type="table",
        target_id=tbl.id,
        after_json={
            "table_code": tbl.table_code,
            "section_name": tbl.section_name,
            "min_capacity": tbl.min_capacity,
            "seat_capacity": tbl.seat_capacity,
            "is_active": tbl.is_active,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(tbl)
    await db.refresh(qr)

    payload = _admin_table_dict(tbl, qr)
    if idempotency_key:
        await check_and_store_idempotency(f"table-create:{venue_id}:{idempotency_key}", payload)
    await ws_hub.broadcast(str(venue_id), {"type": "table.created", "data": payload})
    return success_response(payload, status_code=201)


@router.post("/api/v1/venues/{venue_id}/tables/bulk", status_code=201)
async def bulk_create_tables(
    venue_id: uuid.UUID,
    body: BulkCreateTablesRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="tables.manage"))],
    _flag: Annotated[None, Depends(require_feature_flag("table_advanced_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """API-025 (bulk create): Atomically create 1-50 numbered tables with auto-provisioned QRs."""
    if idempotency_key:
        cached = await check_and_store_idempotency(f"table-bulk:{venue_id}:{idempotency_key}")
        if cached is not None:
            return success_response(cached, status_code=201)

    prefix = normalize_bulk_prefix(body.prefix)
    section = clean_text(body.section_name, max_len=60, field="section_name")

    codes: list[str] = []
    for i in range(body.count):
        num = body.start_number + i
        candidate = f"{prefix}{str(num).zfill(body.zero_pad)}"
        codes.append(normalize_table_code(candidate))

    existing_rows = (
        (
            await db.execute(
                select(DiningTable.table_code).where(
                    DiningTable.venue_id == venue_id,
                    DiningTable.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    if len(existing_rows) + len(codes) > MAX_TABLES_PER_VENUE:
        raise AppError(
            422,
            "LIMIT_EXCEEDED",
            f"Bulk add would exceed venue limit of {MAX_TABLES_PER_VENUE} tables",
        )

    existing_upper = {c.upper() for c in existing_rows}
    conflicts = [c for c in codes if c in existing_upper]
    if conflicts:
        raise AppError(
            409,
            "DUPLICATE_TABLE_CODE",
            f"Conflicting table codes already exist: {', '.join(conflicts[:10])}",
            {"table_code": ", ".join(conflicts)},
        )

    created_pairs: list[tuple[DiningTable, TableQRCode]] = []
    base_sort = len(existing_rows)
    for idx, code in enumerate(codes):
        tbl = DiningTable(
            id=uuid7(),
            organization_id=actor.organization_id,
            venue_id=venue_id,
            camera_id=None,
            table_code=code,
            display_name=None,
            section_name=section,
            min_capacity=body.min_capacity,
            seat_capacity=body.seat_capacity,
            polygon_json=None,
            floor_x=0.0,
            floor_y=0.0,
            shape=body.shape,
            is_active=True,
            is_combinable=body.is_combinable,
            sort_order=base_sort + idx,
        )
        db.add(tbl)
        await db.flush()
        qr = TableQRCode(
            id=uuid7(),
            organization_id=actor.organization_id,
            venue_id=venue_id,
            table_id=tbl.id,
            token=secrets.token_urlsafe(16),
            status="ACTIVE",
            created_by=actor.id,
        )
        db.add(qr)
        created_pairs.append((tbl, qr))

    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="TABLE_BULK_CREATED",
        target_type="venue",
        target_id=venue_id,
        after_json={"count": len(created_pairs), "codes": codes},
        request=request,
    )
    await db.commit()

    tables_out = [_admin_table_dict(t, q) for t, q in created_pairs]
    result = {"created_count": len(tables_out), "tables": tables_out}
    if idempotency_key:
        await check_and_store_idempotency(f"table-bulk:{venue_id}:{idempotency_key}", result)
    await ws_hub.broadcast(
        str(venue_id), {"type": "floor.config_updated", "data": {"created_count": len(tables_out)}}
    )
    return success_response(result, status_code=201)


@router.patch("/api/v1/venues/{venue_id}/tables/bulk")
async def bulk_update_tables(
    venue_id: uuid.UUID,
    body: BulkUpdateTablesRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="tables.manage"))],
    _flag: Annotated[None, Depends(require_feature_flag("table_advanced_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-025 (bulk update): Move selected tables to another section or toggle active status."""
    if body.section_name is None and body.is_active is None:
        raise AppError(400, "VALIDATION_ERROR", "Provide section_name or is_active to update")

    new_section = (
        clean_text(body.section_name, max_len=60, field="section_name")
        if body.section_name is not None
        else None
    )
    rows = (
        (
            await db.execute(
                select(DiningTable).where(
                    DiningTable.venue_id == venue_id,
                    DiningTable.organization_id == actor.organization_id,
                    DiningTable.deleted_at.is_(None),
                    DiningTable.id.in_(body.table_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    if len(rows) != len(set(body.table_ids)):
        raise AppError(404, "RESOURCE_NOT_FOUND", "One or more selected tables not found")

    qr_tokens: list[str] = []
    if body.is_active is not None:
        q_rows = (
            (
                await db.execute(
                    select(TableQRCode.token).where(
                        TableQRCode.table_id.in_([r.id for r in rows]),
                        TableQRCode.status.in_(["ACTIVE", "GRACE"]),
                    )
                )
            )
            .scalars()
            .all()
        )
        qr_tokens = list(q_rows)

    now = datetime.now(UTC)
    touched_cam = False
    for r in rows:
        if new_section is not None:
            r.section_name = new_section
        if body.is_active is not None:
            r.is_active = body.is_active
            if r.camera_id is not None:
                touched_cam = True
        r.version += 1

    if body.is_active is not None:
        await db.execute(
            update(Venue).where(Venue.id == venue_id).values(menu_revision=Venue.menu_revision + 1)
        )

    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="TABLE_UPDATED",
        target_type="venue",
        target_id=venue_id,
        after_json={
            "bulk_count": len(rows),
            "section_name": new_section,
            "is_active": body.is_active,
            "updated_at": now.isoformat(),
        },
        request=request,
    )
    await db.commit()

    for tok in qr_tokens:
        await evict_public_qr_cache(tok)
    if body.is_active is not None:
        await evict_public_menu_cache(str(venue_id))
    if touched_cam:
        await publish_cv_control({"event": "roi.updated", "venue_id": str(venue_id)})
    await ws_hub.broadcast(
        str(venue_id), {"type": "floor.config_updated", "data": {"updated_count": len(rows)}}
    )
    return success_response({"updated_count": len(rows)})


@router.patch("/api/v1/venues/{venue_id}/tables/{table_id}")
async def update_table(
    venue_id: uuid.UUID,
    table_id: uuid.UUID,
    body: UpdateTableRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="tables.manage"))],
    _flag: Annotated[None, Depends(require_feature_flag("table_advanced_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-024 (update): Rename, reconfigure, or deactivate a table cleanly without breaking its QR."""
    tbl = (
        await db.execute(
            select(DiningTable).where(
                DiningTable.id == table_id,
                DiningTable.venue_id == venue_id,
                DiningTable.organization_id == actor.organization_id,
                DiningTable.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if tbl is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Table not found")

    if body.version is not None and tbl.version != body.version:
        raise AppError(
            409, "VERSION_CONFLICT", "Table was modified concurrently; refresh and retry"
        )

    new_min = body.min_capacity if body.min_capacity is not None else tbl.min_capacity
    new_max = body.seat_capacity if body.seat_capacity is not None else tbl.seat_capacity
    if new_min > new_max:
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "min_capacity cannot exceed seat_capacity",
            {"min_capacity": "cannot exceed seat_capacity"},
        )

    before = {
        "table_code": tbl.table_code,
        "display_name": tbl.display_name,
        "section_name": tbl.section_name,
        "min_capacity": tbl.min_capacity,
        "seat_capacity": tbl.seat_capacity,
        "is_active": tbl.is_active,
    }

    if body.table_code is not None:
        code = normalize_table_code(body.table_code)
        if code != tbl.table_code.upper():
            dup = (
                await db.execute(
                    select(DiningTable.id).where(
                        DiningTable.venue_id == venue_id,
                        DiningTable.deleted_at.is_(None),
                        DiningTable.id != table_id,
                        func.upper(DiningTable.table_code) == code,
                    )
                )
            ).scalar_one_or_none()
            if dup is not None:
                raise AppError(
                    409,
                    "DUPLICATE_TABLE_CODE",
                    f"Table code '{code}' already exists in this venue",
                    {"table_code": "already in use"},
                )
        tbl.table_code = code

    if body.display_name is not None:
        tbl.display_name = clean_optional_text(body.display_name, max_len=80, field="display_name")
    if body.section_name is not None:
        tbl.section_name = clean_text(body.section_name, max_len=60, field="section_name")
    tbl.min_capacity = new_min
    tbl.seat_capacity = new_max
    if body.shape is not None:
        tbl.shape = body.shape
    if body.is_combinable is not None:
        tbl.is_combinable = body.is_combinable
    if body.table_notes is not None:
        tbl.table_notes = clean_optional_text(body.table_notes, max_len=255, field="table_notes")
    if body.floor_x is not None:
        tbl.floor_x = body.floor_x
    if body.floor_y is not None:
        tbl.floor_y = body.floor_y
    if body.sort_order is not None:
        tbl.sort_order = body.sort_order

    cam_changed = False
    if body.unlink_camera:
        tbl.camera_id = None
        tbl.polygon_json = None
        cam_changed = True
    elif body.camera_id is not None and body.camera_id != tbl.camera_id:
        cam = (
            await db.execute(
                select(Camera).where(
                    Camera.id == body.camera_id,
                    Camera.venue_id == venue_id,
                    Camera.organization_id == actor.organization_id,
                    Camera.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if cam is None:
            raise AppError(404, "RESOURCE_NOT_FOUND", "Target camera not found")
        tbl.camera_id = body.camera_id
        cam_changed = True

    deactivated = False
    if body.is_active is not None:
        deactivated = tbl.is_active and not body.is_active
        if body.is_active != tbl.is_active:
            cam_changed = cam_changed or (tbl.camera_id is not None)
        tbl.is_active = body.is_active

    tbl.version += 1

    public_meta_changed = (
        before["table_code"] != tbl.table_code
        or before["display_name"] != tbl.display_name
        or before["is_active"] != tbl.is_active
    )
    if public_meta_changed:
        await db.execute(
            update(Venue).where(Venue.id == venue_id).values(menu_revision=Venue.menu_revision + 1)
        )

    qr = (
        await db.execute(
            select(TableQRCode).where(
                TableQRCode.table_id == tbl.id,
                TableQRCode.status == "ACTIVE",
            )
        )
    ).scalar_one_or_none()

    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="TABLE_DEACTIVATED" if deactivated else "TABLE_UPDATED",
        target_type="table",
        target_id=tbl.id,
        before_json=before,
        after_json={
            "table_code": tbl.table_code,
            "display_name": tbl.display_name,
            "section_name": tbl.section_name,
            "min_capacity": tbl.min_capacity,
            "seat_capacity": tbl.seat_capacity,
            "is_active": tbl.is_active,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(tbl)

    if public_meta_changed and qr is not None:
        await evict_public_qr_cache(qr.token)
    if cam_changed:
        await publish_cv_control({"event": "roi.updated", "venue_id": str(venue_id)})
    payload = _admin_table_dict(tbl, qr)
    await ws_hub.broadcast(str(venue_id), {"type": "floor.config_updated", "data": payload})
    return success_response(payload)


@router.delete("/api/v1/venues/{venue_id}/tables/{table_id}")
async def delete_table(
    venue_id: uuid.UUID,
    table_id: uuid.UUID,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="tables.manage"))],
    _flag: Annotated[None, Depends(require_feature_flag("table_advanced_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    force: Annotated[bool, Query()] = False,
    reason: Annotated[str | None, Query(max_length=200)] = None,
) -> JSONResponse:
    """API-024 (delete): Soft-delete table, guard active sessions/waitlist, and revoke QR."""
    tbl = (
        await db.execute(
            select(DiningTable).where(
                DiningTable.id == table_id,
                DiningTable.venue_id == venue_id,
                DiningTable.organization_id == actor.organization_id,
                DiningTable.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if tbl is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Table not found")

    active_wl = (
        await db.execute(
            select(WaitlistEntry.id).where(
                WaitlistEntry.assigned_table_id == table_id,
                WaitlistEntry.status == "WAITING",
            )
        )
    ).scalar_one_or_none()
    in_use = tbl.current_state in {"OCCUPIED", "NEEDS_SERVICE", "NEEDS_CLEANING"} or (
        active_wl is not None
    )
    if in_use and not force:
        raise AppError(
            409,
            "TABLE_IN_USE",
            f"Table {tbl.table_code} is currently {tbl.current_state}. Pass force=true to archive.",
            {"table_id": str(table_id)},
        )

    now = datetime.now(UTC)
    had_cam = tbl.camera_id is not None
    clean_reason = clean_optional_text(reason, max_len=200, field="reason")

    q_rows = (
        (
            await db.execute(
                select(TableQRCode).where(
                    TableQRCode.table_id == table_id,
                    TableQRCode.status.in_(["ACTIVE", "GRACE"]),
                )
            )
        )
        .scalars()
        .all()
    )
    evict_tokens = [q.token for q in q_rows]
    for q in q_rows:
        q.status = "REVOKED"
        q.revoked_at = now
        q.revoked_by = actor.id
        q.revoked_reason = "TABLE_DELETED"

    tbl.deleted_at = now
    tbl.is_active = False
    tbl.version += 1

    await db.execute(
        update(Alert)
        .where(
            Alert.table_id == table_id,
            Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"]),
        )
        .values(status="RESOLVED", resolved_at=now)
    )
    await db.execute(
        update(Venue).where(Venue.id == venue_id).values(menu_revision=Venue.menu_revision + 1)
    )

    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="TABLE_DELETED",
        target_type="table",
        target_id=tbl.id,
        before_json={"table_code": tbl.table_code, "current_state": tbl.current_state},
        after_json={"deleted_at": now.isoformat(), "force": force, "reason": clean_reason},
        request=request,
    )
    await db.commit()

    for tok in evict_tokens:
        await evict_public_qr_cache(tok)
    if had_cam:
        await publish_cv_control({"event": "roi.updated", "venue_id": str(venue_id)})
    await ws_hub.broadcast(
        str(venue_id),
        {
            "type": "table.deleted",
            "data": {"table_id": str(table_id), "table_code": tbl.table_code},
        },
    )
    return success_response({"deleted": True, "table_id": str(table_id)})


@router.post("/api/v1/venues/{venue_id}/tables/{table_id}/duplicate", status_code=201)
async def duplicate_table(
    venue_id: uuid.UUID,
    table_id: uuid.UUID,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="tables.manage"))],
    _flag: Annotated[None, Depends(require_feature_flag("table_advanced_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Duplicate table configuration with next available code + fresh 128-bit QR."""
    orig = (
        await db.execute(
            select(DiningTable).where(
                DiningTable.id == table_id,
                DiningTable.venue_id == venue_id,
                DiningTable.organization_id == actor.organization_id,
                DiningTable.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if orig is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Table not found")

    existing_codes = {
        c.upper()
        for c in (
            await db.execute(
                select(DiningTable.table_code).where(
                    DiningTable.venue_id == venue_id,
                    DiningTable.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    }
    if len(existing_codes) >= MAX_TABLES_PER_VENUE:
        raise AppError(422, "LIMIT_EXCEEDED", "Maximum table limit reached for this venue")

    candidate = f"{orig.table_code[:14]}-COPY"
    idx = 2
    while candidate.upper() in existing_codes:
        suffix = f"-C{idx}"
        candidate = f"{orig.table_code[: 20 - len(suffix)]}{suffix}"
        idx += 1

    clone = DiningTable(
        id=uuid7(),
        organization_id=actor.organization_id,
        venue_id=venue_id,
        camera_id=None,
        table_code=candidate,
        display_name=f"{orig.display_name} (Copy)"[:80] if orig.display_name else None,
        section_name=orig.section_name,
        min_capacity=orig.min_capacity,
        seat_capacity=orig.seat_capacity,
        polygon_json=None,
        floor_x=min(0.95, max(0.05, orig.floor_x + 0.04)),
        floor_y=min(0.95, max(0.05, orig.floor_y + 0.04)),
        shape=orig.shape,
        is_active=orig.is_active,
        is_combinable=orig.is_combinable,
        table_notes=orig.table_notes,
        sort_order=orig.sort_order + 1,
    )
    db.add(clone)
    await db.flush()

    qr = TableQRCode(
        id=uuid7(),
        organization_id=actor.organization_id,
        venue_id=venue_id,
        table_id=clone.id,
        token=secrets.token_urlsafe(16),
        status="ACTIVE",
        created_by=actor.id,
    )
    db.add(qr)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="TABLE_DUPLICATED",
        target_type="table",
        target_id=clone.id,
        after_json={"source_table_id": str(orig.id), "table_code": clone.table_code},
        request=request,
    )
    await db.commit()
    await db.refresh(clone)
    await db.refresh(qr)
    payload = _admin_table_dict(clone, qr)
    await ws_hub.broadcast(str(venue_id), {"type": "table.created", "data": payload})
    return success_response(payload, status_code=201)


@router.post("/api/v1/venues/{venue_id}/tables/{table_id}/restore")
async def restore_archived_table(
    venue_id: uuid.UUID,
    table_id: uuid.UUID,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="tables.manage"))],
    _flag: Annotated[None, Depends(require_feature_flag("table_advanced_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: RestoreTableRequest | None = None,
) -> JSONResponse:
    """Restore an archived table (handles E-05 table_code conflicts with optional new_table_code)."""
    tbl = (
        await db.execute(
            select(DiningTable).where(
                DiningTable.id == table_id,
                DiningTable.venue_id == venue_id,
                DiningTable.organization_id == actor.organization_id,
                DiningTable.deleted_at.is_not(None),
            )
        )
    ).scalar_one_or_none()
    if tbl is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Archived table not found")

    target_code = (
        normalize_table_code(body.new_table_code)
        if body and body.new_table_code
        else tbl.table_code.upper()
    )
    conflict = (
        await db.execute(
            select(DiningTable.id).where(
                DiningTable.venue_id == venue_id,
                DiningTable.deleted_at.is_(None),
                DiningTable.id != table_id,
                func.upper(DiningTable.table_code) == target_code,
            )
        )
    ).scalar_one_or_none()
    if conflict is not None:
        raise AppError(
            409,
            "DUPLICATE_TABLE_CODE",
            f"Table code '{target_code}' is in use; provide a new_table_code to restore",
            {"new_table_code": "already in use"},
        )

    tbl.table_code = target_code
    tbl.deleted_at = None
    tbl.is_active = True
    tbl.current_state = "FREE"
    tbl.version += 1

    active_qr = (
        await db.execute(
            select(TableQRCode).where(
                TableQRCode.table_id == tbl.id,
                TableQRCode.status == "ACTIVE",
            )
        )
    ).scalar_one_or_none()
    if active_qr is None:
        active_qr = TableQRCode(
            id=uuid7(),
            organization_id=actor.organization_id,
            venue_id=venue_id,
            table_id=tbl.id,
            token=secrets.token_urlsafe(16),
            status="ACTIVE",
            created_by=actor.id,
        )
        db.add(active_qr)

    await db.execute(
        update(Venue).where(Venue.id == venue_id).values(menu_revision=Venue.menu_revision + 1)
    )
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="TABLE_RESTORED",
        target_type="table",
        target_id=tbl.id,
        after_json={"table_code": tbl.table_code},
        request=request,
    )
    await db.commit()
    await db.refresh(tbl)
    await db.refresh(active_qr)
    payload = _admin_table_dict(tbl, active_qr)
    await ws_hub.broadcast(str(venue_id), {"type": "table.created", "data": payload})
    return success_response(payload)


@router.delete("/api/v1/venues/{venue_id}/tables/{table_id}/purge")
async def purge_archived_table(
    venue_id: uuid.UUID,
    table_id: uuid.UUID,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="tables.manage"))],
    _flag: Annotated[None, Depends(require_feature_flag("table_advanced_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Permanently purge zero-history archived table; block with 409 TABLE_HAS_HISTORY otherwise (E-07)."""
    tbl = (
        await db.execute(
            select(DiningTable).where(
                DiningTable.id == table_id,
                DiningTable.venue_id == venue_id,
                DiningTable.organization_id == actor.organization_id,
                DiningTable.deleted_at.is_not(None),
            )
        )
    ).scalar_one_or_none()
    if tbl is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Archived table not found")

    has_history = False
    history_checks: list[tuple[Any, Any]] = [
        (TableStateEvent, TableStateEvent.table_id),
        (Alert, Alert.table_id),
        (WaitlistEntry, WaitlistEntry.assigned_table_id),
        (MLReviewItem, MLReviewItem.table_id),
        (QrScanDailyStat, QrScanDailyStat.table_id),
    ]
    for model_cls, col in history_checks:
        cnt = (
            await db.execute(select(func.count()).select_from(model_cls).where(col == table_id))
        ).scalar_one()
        if int(cnt or 0) > 0:
            has_history = True
            break

    if has_history:
        raise AppError(
            409,
            "TABLE_HAS_HISTORY",
            f"Table {tbl.table_code} has historical operational records and cannot be purged",
            {"table_id": str(table_id)},
        )

    qr_rows = (
        await db.execute(select(TableQRCode).where(TableQRCode.table_id == table_id))
    ).scalars().all()
    tokens = [q.token for q in qr_rows]
    for q in qr_rows:
        await db.delete(q)
    await db.flush()
    code_copy = tbl.table_code
    await db.delete(tbl)

    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="TABLE_PURGED",
        target_type="table",
        target_id=table_id,
        before_json={"table_code": code_copy},
        request=request,
    )
    await db.commit()
    for tok in tokens:
        await evict_public_qr_cache(tok)
    return success_response({"purged": True, "table_id": str(table_id)})
