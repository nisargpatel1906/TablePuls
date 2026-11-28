"""Phase 2 Table QR Code Management, Regeneration, SVG/PNG/PDF Export & Preview APIs (API-032..API-034)."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, success_response
from app.core.rbac import Role, require_feature_flag, require_venue_role
from app.core.valkey_client import evict_public_menu_cache, evict_public_qr_cache
from app.db.base import get_db, uuid7
from app.db.models import DiningTable, QrScanDailyStat, TableQRCode, Venue
from app.schemas.tables_qr import ExportQRPdfRequest, ExportQRZipRequest, RegenerateQRRequest
from app.services.audit import write_audit_log
from app.services.qr_export import (
    build_qr_url,
    generate_qr_pdf_bytes,
    generate_qr_png_bytes,
    generate_qr_svg_bytes,
    generate_qr_zip_bytes,
    sign_qr_preview_token,
)

router = APIRouter(tags=["qr-admin"])


@router.get("/api/v1/venues/{venue_id}/qr-codes")
async def list_venue_qr_codes(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="qr.read"))],
    _flag: Annotated[None, Depends(require_feature_flag("qr_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    section: Annotated[str | None, Query(max_length=60)] = None,
    search: Annotated[str | None, Query(max_length=80)] = None,
    never_scanned_30d: Annotated[bool, Query()] = False,
) -> JSONResponse:
    """API-032: List active/non-deleted venue tables with active QR, grace state, and scan counts."""
    tables = (
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
    qrs = (
        (
            await db.execute(
                select(TableQRCode).where(
                    TableQRCode.venue_id == venue_id,
                    TableQRCode.organization_id == actor.organization_id,
                    TableQRCode.status.in_(["ACTIVE", "GRACE"]),
                )
            )
        )
        .scalars()
        .all()
    )
    active_qr: dict[uuid.UUID, TableQRCode] = {}
    grace_qr: dict[uuid.UUID, TableQRCode] = {}
    for q in qrs:
        if q.status == "ACTIVE":
            active_qr[q.table_id] = q
        elif q.status == "GRACE":
            grace_qr[q.table_id] = q

    since_7d = datetime.now(UTC).date() - timedelta(days=7)
    since_30d = datetime.now(UTC) - timedelta(days=30)
    stats_7d_rows = (
        await db.execute(
            select(QrScanDailyStat.table_id, func.sum(QrScanDailyStat.scan_count))
            .where(
                QrScanDailyStat.venue_id == venue_id,
                QrScanDailyStat.scan_date >= since_7d,
            )
            .group_by(QrScanDailyStat.table_id)
        )
    ).all()
    scans_7d = {row[0]: int(row[1] or 0) for row in stats_7d_rows}

    search_q = search.strip().lower() if search else None
    items: list[dict[str, Any]] = []
    for t in tables:
        if section and t.section_name != section:
            continue
        if search_q:
            hay = f"{t.table_code} {t.display_name or ''} {t.section_name}".lower()
            if search_q not in hay:
                continue
        aq = active_qr.get(t.id)
        gq = grace_qr.get(t.id)
        if (
            never_scanned_30d
            and aq is not None
            and aq.last_scanned_at is not None
            and aq.last_scanned_at >= since_30d
        ):
            continue
        label = t.display_name.strip() if t.display_name else f"Table {t.table_code}"
        items.append(
            {
                "table_id": str(t.id),
                "table_code": t.table_code,
                "table_label": label,
                "section_name": t.section_name,
                "is_active": t.is_active,
                "qr_id": str(aq.id) if aq else None,
                "token": aq.token if aq else None,
                "qr_url": build_qr_url(aq.token) if aq else None,
                "status": aq.status if aq else "MISSING",
                "scan_count": aq.scan_count if aq else 0,
                "scans_7d": scans_7d.get(t.id, 0),
                "last_scanned_at": aq.last_scanned_at.isoformat()
                if aq and aq.last_scanned_at
                else None,
                "grace_token_active": gq is not None,
                "grace_until": gq.grace_until.isoformat() if gq and gq.grace_until else None,
            }
        )
    return success_response({"items": items, "total": len(items)})


@router.post("/api/v1/venues/{venue_id}/tables/{table_id}/qr/regenerate", status_code=201)
async def regenerate_table_qr(
    venue_id: uuid.UUID,
    table_id: uuid.UUID,
    body: RegenerateQRRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="qr.manage"))],
    _flag: Annotated[None, Depends(require_feature_flag("qr_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-033 (regenerate): Rotate QR token atomically, handle optional grace window, evict Valkey."""
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

    venue = (await db.execute(select(Venue).where(Venue.id == venue_id))).scalar_one()
    now = datetime.now(UTC)
    grace_days = (
        0
        if body.reason == "COMPROMISED"
        else (body.grace_days if body.grace_days is not None else venue.qr_grace_days)
    )

    existing_rows = (
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
    evict_tokens = [r.token for r in existing_rows]

    # Revoke any older GRACE token immediately (never stack grace windows, E-09)
    for r in existing_rows:
        if r.status == "GRACE":
            r.status = "REVOKED"
            r.revoked_at = now
            r.revoked_by = actor.id
            r.revoked_reason = "REGENERATED"
        elif r.status == "ACTIVE":
            if grace_days > 0:
                r.status = "GRACE"
                r.grace_until = now + timedelta(days=grace_days)
                r.revoked_by = actor.id
                r.revoked_reason = "REGENERATED"
            else:
                r.status = "REVOKED"
                r.revoked_at = now
                r.revoked_by = actor.id
                r.revoked_reason = (
                    "SECURITY_REVOKE" if body.reason == "COMPROMISED" else "REGENERATED"
                )

    await db.flush()
    new_qr = TableQRCode(
        id=uuid7(),
        organization_id=actor.organization_id,
        venue_id=venue_id,
        table_id=table_id,
        token=secrets.token_urlsafe(16),
        status="ACTIVE",
        created_by=actor.id,
    )
    db.add(new_qr)
    await db.execute(
        update(Venue).where(Venue.id == venue_id).values(menu_revision=Venue.menu_revision + 1)
    )
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="QR_REGENERATED",
        target_type="table_qr_code",
        target_id=new_qr.id,
        after_json={
            "table_id": str(table_id),
            "reason": body.reason,
            "grace_days": grace_days,
            "token_prefix": new_qr.token[:4],
        },
        request=request,
    )
    await db.commit()
    await db.refresh(new_qr)

    for tok in evict_tokens:
        await evict_public_qr_cache(tok)
    await evict_public_menu_cache(str(venue_id))

    return success_response(
        {
            "table_id": str(table_id),
            "qr_id": str(new_qr.id),
            "token": new_qr.token,
            "qr_url": build_qr_url(new_qr.token),
            "grace_days": grace_days,
        },
        status_code=201,
    )


@router.post("/api/v1/venues/{venue_id}/tables/{table_id}/qr/end-grace")
async def end_qr_grace(
    venue_id: uuid.UUID,
    table_id: uuid.UUID,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="qr.manage"))],
    _flag: Annotated[None, Depends(require_feature_flag("qr_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-033 (end-grace): Immediately revoke any GRACE QR token for a table."""
    grace_rows = (
        (
            await db.execute(
                select(TableQRCode).where(
                    TableQRCode.venue_id == venue_id,
                    TableQRCode.table_id == table_id,
                    TableQRCode.organization_id == actor.organization_id,
                    TableQRCode.status == "GRACE",
                )
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    tokens = [r.token for r in grace_rows]
    for r in grace_rows:
        r.status = "REVOKED"
        r.revoked_at = now
        r.revoked_by = actor.id
        r.revoked_reason = "REGENERATED"

    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="QR_REVOKED",
        target_type="table",
        target_id=table_id,
        after_json={"ended_grace_count": len(grace_rows)},
        request=request,
    )
    await db.commit()
    for tok in tokens:
        await evict_public_qr_cache(tok)
    return success_response({"revoked_count": len(grace_rows)})


@router.post("/api/v1/venues/{venue_id}/tables/{table_id}/qr/preview-link")
async def create_qr_preview_link(
    venue_id: uuid.UUID,
    table_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="menu.manage"))],
    _flag: Annotated[None, Depends(require_feature_flag("qr_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-033 (preview-link): Signed 15-min admin preview URL rendering DRAFT + PUBLISHED menus."""
    qr = (
        await db.execute(
            select(TableQRCode).where(
                TableQRCode.venue_id == venue_id,
                TableQRCode.table_id == table_id,
                TableQRCode.organization_id == actor.organization_id,
                TableQRCode.status == "ACTIVE",
            )
        )
    ).scalar_one_or_none()
    if qr is None:
        raise AppError(404, "QR_CODE_NOT_FOUND", "No active QR code found for table")

    sig = sign_qr_preview_token(qr.token, str(venue_id), ttl_seconds=900)
    url = f"{build_qr_url(qr.token)}?p={sig}"
    return success_response({"preview_url": url, "expires_in": 900})


@router.get("/api/v1/venues/{venue_id}/tables/{table_id}/qr/download")
async def download_table_qr(
    venue_id: uuid.UUID,
    table_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="qr.read"))],
    _flag: Annotated[None, Depends(require_feature_flag("qr_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    format: Annotated[str, Query(pattern="^(svg|png)$")] = "svg",
    framed: Annotated[bool, Query()] = False,
    size: Annotated[int, Query(ge=128, le=2048)] = 1024,
) -> Response:
    """API-034 (single QR download): Offline SVG or 1024x1024 PNG card (OWNER/MANAGER/HOST)."""
    if Role(actor.role) == Role.VIEWER:
        raise AppError(403, "AUTH_FORBIDDEN", "VIEWER cannot download printable QR assets")

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

    qr = (
        await db.execute(
            select(TableQRCode).where(
                TableQRCode.table_id == table_id,
                TableQRCode.status == "ACTIVE",
            )
        )
    ).scalar_one_or_none()
    if qr is None:
        raise AppError(404, "QR_CODE_NOT_FOUND", "Active QR not found for table")

    venue = (await db.execute(select(Venue).where(Venue.id == venue_id))).scalar_one()
    url = build_qr_url(qr.token)
    label = tbl.display_name.strip() if tbl.display_name else f"Table {tbl.table_code}"

    if format == "svg":
        svg_bytes = generate_qr_svg_bytes(url)
        return Response(
            content=svg_bytes,
            media_type="image/svg+xml",
            headers={
                "Content-Disposition": f'attachment; filename="qr-{tbl.table_code}.svg"',
                "Cache-Control": "no-store",
            },
        )

    png_bytes = generate_qr_png_bytes(
        url,
        framed=framed,
        venue_name=venue.name,
        table_label=label,
        size_px=size,
    )
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="qr-{tbl.table_code}.png"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/api/v1/venues/{venue_id}/qr/export-pdf")
async def export_qr_pdf_batch(
    venue_id: uuid.UUID,
    body: ExportQRPdfRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="qr.read"))],
    _flag: Annotated[None, Depends(require_feature_flag("qr_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """API-034 (batch PDF): Cut-guided multi-table tent-card PDF sheet (max 100 tables)."""
    if Role(actor.role) == Role.VIEWER:
        raise AppError(403, "AUTH_FORBIDDEN", "VIEWER cannot export printable QR PDFs")

    venue = (await db.execute(select(Venue).where(Venue.id == venue_id))).scalar_one()
    rows = (
        await db.execute(
            select(DiningTable, TableQRCode)
            .join(TableQRCode, TableQRCode.table_id == DiningTable.id)
            .where(
                DiningTable.venue_id == venue_id,
                DiningTable.organization_id == actor.organization_id,
                DiningTable.deleted_at.is_(None),
                DiningTable.id.in_(body.table_ids),
                TableQRCode.status == "ACTIVE",
            )
            .order_by(DiningTable.sort_order.asc(), DiningTable.table_code.asc())
        )
    ).all()
    if not rows:
        raise AppError(404, "QR_CODE_NOT_FOUND", "No active QR codes found for selected tables")

    cards = [
        (
            tbl.table_code,
            tbl.display_name.strip() if tbl.display_name else f"Table {tbl.table_code}",
            build_qr_url(qr.token),
        )
        for tbl, qr in rows
    ]
    pdf_bytes = generate_qr_pdf_bytes(cards, venue_name=venue.name, layout=body.layout)

    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="QR_BATCH_PDF_EXPORTED",
        target_type="venue",
        target_id=venue_id,
        after_json={"table_count": len(cards), "layout": body.layout},
        request=request,
    )
    await db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="tablepulse-qr-cards-{body.layout.lower()}.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/api/v1/venues/{venue_id}/qr/export-zip")
async def export_qr_zip_batch(
    venue_id: uuid.UUID,
    body: ExportQRZipRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="qr.read"))],
    _flag: Annotated[None, Depends(require_feature_flag("qr_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """API-034 (batch ZIP): Download ZIP of SVG/PNG QR cards (max 100 tables)."""
    if Role(actor.role) == Role.VIEWER:
        raise AppError(403, "AUTH_FORBIDDEN", "VIEWER cannot export printable QR bundles")

    venue = (await db.execute(select(Venue).where(Venue.id == venue_id))).scalar_one()
    rows = (
        await db.execute(
            select(DiningTable, TableQRCode)
            .join(TableQRCode, TableQRCode.table_id == DiningTable.id)
            .where(
                DiningTable.venue_id == venue_id,
                DiningTable.organization_id == actor.organization_id,
                DiningTable.deleted_at.is_(None),
                DiningTable.id.in_(body.table_ids),
                TableQRCode.status == "ACTIVE",
            )
            .order_by(DiningTable.sort_order.asc(), DiningTable.table_code.asc())
        )
    ).all()
    if not rows:
        raise AppError(404, "QR_CODE_NOT_FOUND", "No active QR codes found for selected tables")

    cards = [
        (
            tbl.table_code,
            tbl.display_name.strip() if tbl.display_name else f"Table {tbl.table_code}",
            build_qr_url(qr.token),
        )
        for tbl, qr in rows
    ]
    zip_bytes = generate_qr_zip_bytes(
        cards,
        venue_name=venue.name,
        fmt=body.format,
        framed=body.framed,
    )
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="QR_BATCH_ZIP_EXPORTED",
        target_type="venue",
        target_id=venue_id,
        after_json={"table_count": len(cards), "format": body.format},
        request=request,
    )
    await db.commit()
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="tablepulse-qr-bundle-{body.format}.zip"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/api/v1/venues/{venue_id}/qr-codes/stats")
async def get_qr_scan_stats(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="qr.read"))],
    _flag: Annotated[None, Depends(require_feature_flag("qr_enabled"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> JSONResponse:
    """Aggregate anonymized QR scan statistics by day and table (zero PII)."""
    since_date = datetime.now(UTC).date() - timedelta(days=days - 1)
    daily_rows = (
        await db.execute(
            select(QrScanDailyStat.scan_date, func.sum(QrScanDailyStat.scan_count))
            .where(
                QrScanDailyStat.venue_id == venue_id,
                QrScanDailyStat.organization_id == actor.organization_id,
                QrScanDailyStat.scan_date >= since_date,
            )
            .group_by(QrScanDailyStat.scan_date)
            .order_by(QrScanDailyStat.scan_date.asc())
        )
    ).all()

    table_window_rows = (
        await db.execute(
            select(QrScanDailyStat.table_id, func.sum(QrScanDailyStat.scan_count))
            .where(
                QrScanDailyStat.venue_id == venue_id,
                QrScanDailyStat.organization_id == actor.organization_id,
                QrScanDailyStat.scan_date >= since_date,
            )
            .group_by(QrScanDailyStat.table_id)
        )
    ).all()
    win_by_table = {row[0]: int(row[1] or 0) for row in table_window_rows}

    tbl_qrs = (
        await db.execute(
            select(DiningTable, TableQRCode)
            .join(TableQRCode, TableQRCode.table_id == DiningTable.id)
            .where(
                DiningTable.venue_id == venue_id,
                DiningTable.organization_id == actor.organization_id,
                DiningTable.deleted_at.is_(None),
                TableQRCode.status == "ACTIVE",
            )
            .order_by(DiningTable.sort_order.asc(), DiningTable.table_code.asc())
        )
    ).all()

    per_table_rows: list[dict[str, Any]] = [
        {
            "table_id": str(t.id),
            "table_code": t.table_code,
            "section_name": t.section_name,
            "scans_total": int(q.scan_count),
            "scans_window": win_by_table.get(t.id, 0),
            "scan_count": win_by_table.get(t.id, 0),
        }
        for t, q in tbl_qrs
    ]
    per_table = sorted(
        per_table_rows,
        key=lambda p: (-int(p["scans_window"]), -int(p["scans_total"]), str(p["table_code"])),
    )
    return success_response(
        {
            "days": days,
            "total_scans_all_time": sum(p["scans_total"] for p in per_table),
            "total_scans_window": sum(int(r[1] or 0) for r in daily_rows),
            "daily": [
                {"date": r[0].isoformat(), "scans": int(r[1] or 0)} for r in daily_rows
            ],
            "by_table": per_table,
        }
    )


async def expire_grace_qr_codes_once(db: AsyncSession) -> int:
    """Transition expired GRACE QR tokens to REVOKED and evict their Valkey entries."""
    now = datetime.now(UTC)
    rows = (
        (
            await db.execute(
                select(TableQRCode).where(
                    TableQRCode.status == "GRACE",
                    TableQRCode.grace_until.is_not(None),
                    TableQRCode.grace_until <= now,
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return 0
    tokens = [r.token for r in rows]
    for r in rows:
        r.status = "REVOKED"
        r.revoked_at = now
    await db.commit()
    for tok in tokens:
        await evict_public_qr_cache(tok)
    return len(rows)
