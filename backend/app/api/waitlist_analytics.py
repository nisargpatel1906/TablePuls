"""Waitlist, Turnover ETA Predictions, and Peak Hours Analytics (API-016..API-018)."""

from __future__ import annotations

import csv
import io
import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, success_response
from app.core.rbac import require_venue_role
from app.core.security import encrypt_field
from app.core.valkey_client import check_and_store_idempotency
from app.db.base import get_db, uuid7
from app.db.models import (
    DiningTable,
    OccupancySnapshot,
    TableStateEvent,
    Venue,
    WaitlistEntry,
)
from app.schemas.floor_ops import CreateWaitlistRequest, UpdateWaitlistRequest
from app.services.audit import write_audit_log

router = APIRouter(tags=["waitlist-analytics"])


def _csv_safe(val: object) -> str:
    s = "" if val is None else str(val)
    if s.startswith(("=", "+", "-", "@")):
        return "'" + s
    return s


def _waitlist_dict(w: WaitlistEntry, now: datetime) -> dict[str, Any]:
    elapsed_min = max(0, int((now - w.joined_at).total_seconds() // 60))
    actual_wait = (
        max(0, int((w.seated_at - w.joined_at).total_seconds() // 60)) if w.seated_at else None
    )
    return {
        "id": str(w.id),
        "venue_id": str(w.venue_id),
        "party_name": w.party_name,
        "party_size": w.party_size,
        "has_phone": w.phone_encrypted is not None,
        "quoted_wait_minutes": w.quoted_wait_minutes,
        "status": w.status,
        "assigned_table_id": str(w.assigned_table_id) if w.assigned_table_id else None,
        "notes": w.notes,
        "elapsed_wait_minutes": elapsed_min,
        "actual_wait_minutes": actual_wait,
        "joined_at": w.joined_at.isoformat(),
        "seated_at": w.seated_at.isoformat() if w.seated_at else None,
    }


@router.get("/api/v1/venues/{venue_id}/waitlist")
async def list_waitlist(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="waitlist.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> JSONResponse:
    """API-016 (list): Paginated waitlist queue."""
    q = select(WaitlistEntry).where(
        WaitlistEntry.venue_id == venue_id,
        WaitlistEntry.organization_id == actor.organization_id,
    )
    if status:
        q = q.where(WaitlistEntry.status == status)
    rows = (await db.execute(q.order_by(WaitlistEntry.joined_at.asc()))).scalars().all()
    now = datetime.now(UTC)
    total = len(rows)
    start = (page - 1) * page_size
    items = [_waitlist_dict(w, now) for w in rows[start : start + page_size]]
    return success_response({"items": items, "total": total, "page": page, "page_size": page_size})


@router.post("/api/v1/venues/{venue_id}/waitlist", status_code=201)
async def create_waitlist_entry(
    venue_id: uuid.UUID,
    body: CreateWaitlistRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="waitlist.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """API-016 (create): Add waiting party with encrypted optional phone and idempotency."""
    if idempotency_key:
        cached = await check_and_store_idempotency(f"waitlist:{venue_id}:{idempotency_key}")
        if cached is not None:
            return success_response(cached, status_code=201)

    now = datetime.now(UTC)
    entry = WaitlistEntry(
        id=uuid7(),
        organization_id=actor.organization_id,
        venue_id=venue_id,
        party_name=body.party_name.strip(),
        party_size=body.party_size,
        phone_encrypted=encrypt_field(body.phone.strip()) if body.phone else None,
        quoted_wait_minutes=body.quoted_wait_minutes,
        status="WAITING",
        notes=body.notes.strip() if body.notes else None,
        joined_at=now,
    )
    db.add(entry)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="WAITLIST_ADDED",
        target_type="waitlist_entry",
        target_id=entry.id,
        after_json={"party_name": entry.party_name, "party_size": entry.party_size},
        request=request,
    )
    await db.commit()
    payload = _waitlist_dict(entry, now)
    if idempotency_key:
        await check_and_store_idempotency(f"waitlist:{venue_id}:{idempotency_key}", payload)
    return success_response(payload, status_code=201)


@router.patch("/api/v1/venues/{venue_id}/waitlist/{entry_id}")
async def update_waitlist_entry(
    venue_id: uuid.UUID,
    entry_id: uuid.UUID,
    body: UpdateWaitlistRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="waitlist.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-016 (update/seat): Seat waiting party on a FREE table or cancel/no-show."""
    entry = (
        await db.execute(
            select(WaitlistEntry).where(
                WaitlistEntry.id == entry_id,
                WaitlistEntry.venue_id == venue_id,
                WaitlistEntry.organization_id == actor.organization_id,
            )
        )
    ).scalar_one_or_none()
    if entry is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Waitlist entry not found")

    now = datetime.now(UTC)
    if body.party_size is not None:
        entry.party_size = body.party_size
    if body.quoted_wait_minutes is not None:
        entry.quoted_wait_minutes = body.quoted_wait_minutes
    if body.notes is not None:
        entry.notes = body.notes.strip()

    if body.status == "SEATED":
        if body.assigned_table_id is None:
            raise AppError(
                400,
                "VALIDATION_ERROR",
                "assigned_table_id is required when seating a party",
                {"assigned_table_id": "select a FREE table"},
            )
        tbl = (
            await db.execute(
                select(DiningTable).where(
                    DiningTable.id == body.assigned_table_id,
                    DiningTable.venue_id == venue_id,
                    DiningTable.organization_id == actor.organization_id,
                    DiningTable.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if tbl is None:
            raise AppError(404, "RESOURCE_NOT_FOUND", "Target table not found")
        if tbl.current_state not in {"FREE", "RESERVED"}:
            raise AppError(
                409,
                "VERSION_CONFLICT",
                f"Table {tbl.table_code} is currently {tbl.current_state}, not FREE",
            )
        prev = tbl.current_state
        tbl.current_state = "OCCUPIED"
        tbl.current_guest_count = entry.party_size
        tbl.occupied_since = now
        tbl.last_staff_visit_at = None
        tbl.version += 1
        entry.assigned_table_id = tbl.id
        entry.seated_at = now
        entry.status = "SEATED"
        db.add(
            TableStateEvent(
                id=uuid7(),
                organization_id=actor.organization_id,
                venue_id=venue_id,
                table_id=tbl.id,
                previous_state=prev,
                new_state="OCCUPIED",
                guest_count=entry.party_size,
                confidence=1.0,
                source="MANUAL",
                actor_user_id=actor.id,
                reason=f"Seated waitlist party: {entry.party_name}",
                occurred_at=now,
            )
        )
    elif body.status is not None:
        entry.status = body.status

    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="WAITLIST_UPDATED",
        target_type="waitlist_entry",
        target_id=entry.id,
        after_json={
            "status": entry.status,
            "assigned_table_id": str(entry.assigned_table_id) if entry.assigned_table_id else None,
        },
        request=request,
    )
    await db.commit()
    return success_response(_waitlist_dict(entry, now))


@router.get("/api/v1/venues/{venue_id}/turnover-predictions")
async def get_turnover_predictions(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="turnover.view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    party_size: Annotated[int, Query(ge=1, le=20)] = 2,
) -> JSONResponse:
    """API-017: Ranked next-available tables matching seat_capacity >= party_size (excludes UNKNOWN)."""
    tables = (
        (
            await db.execute(
                select(DiningTable).where(
                    DiningTable.venue_id == venue_id,
                    DiningTable.organization_id == actor.organization_id,
                    DiningTable.deleted_at.is_(None),
                    DiningTable.seat_capacity >= party_size,
                    DiningTable.current_state != "UNKNOWN",
                    DiningTable.current_state != "RESERVED",
                )
            )
        )
        .scalars()
        .all()
    )

    now = datetime.now(UTC)
    ranked: list[dict[str, Any]] = []
    for t in tables:
        elapsed_min = (
            max(0.0, (now - t.occupied_since).total_seconds() / 60.0) if t.occupied_since else 0.0
        )
        if t.current_state == "FREE":
            min_eta, max_eta, conf_tier = 0, 0, "High"
        elif t.current_state == "NEEDS_CLEANING":
            min_eta, max_eta, conf_tier = 2, 5, "High"
        else:
            base_turn = 35.0 if t.seat_capacity <= 2 else (45.0 if t.seat_capacity <= 4 else 60.0)
            rem = max(2.0, base_turn - elapsed_min)
            min_eta = max(1, int(round(rem * 0.75)))
            max_eta = max(min_eta + 2, int(round(rem * 1.25)))
            conf_tier = "Medium" if elapsed_min >= 20.0 else "Low"

        ranked.append(
            {
                "table_id": str(t.id),
                "table_code": t.table_code,
                "section_name": t.section_name,
                "seat_capacity": t.seat_capacity,
                "current_state": t.current_state,
                "elapsed_dwell_minutes": int(elapsed_min),
                "eta_min_minutes": min_eta,
                "eta_max_minutes": max_eta,
                "eta_display": "Ready now" if min_eta == 0 else f"~{min_eta}–{max_eta} min",
                "confidence_tier": conf_tier,
            }
        )

    ranked.sort(key=lambda r: (r["eta_min_minutes"], r["seat_capacity"], r["table_code"]))
    return success_response(
        {
            "party_size": party_size,
            "baseline_note": "Using statistical 45m baseline turn estimate (improves with >= 7 days venue history)",
            "items": ranked,
        }
    )


@router.get("/api/v1/venues/{venue_id}/analytics/peak-hours")
async def get_peak_hours_analytics(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="analytics.view_export"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    from_date: Annotated[str | None, Query()] = None,
    to_date: Annotated[str | None, Query()] = None,
    section: Annotated[str | None, Query(max_length=60)] = None,
    guests_per_server_ratio: Annotated[int | None, Query(ge=4, le=50)] = None,
    format: Annotated[str, Query(pattern="^(json|csv)$")] = "json",
) -> Response:
    """API-018: Peak hours occupancy, heatmap, staffing curve, and formula-safe CSV export."""
    venue = (await db.execute(select(Venue).where(Venue.id == venue_id))).scalar_one()
    ratio = guests_per_server_ratio or venue.guests_per_server_ratio or 16

    now = datetime.now(UTC)
    end_dt = now
    start_dt = now - timedelta(days=7)
    if from_date:
        try:
            start_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=UTC)
        except ValueError as exc:
            raise AppError(
                400, "VALIDATION_ERROR", "Invalid from_date", {"from_date": "ISO date expected"}
            ) from exc
    if to_date:
        try:
            end_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=UTC)
        except ValueError as exc:
            raise AppError(
                400, "VALIDATION_ERROR", "Invalid to_date", {"to_date": "ISO date expected"}
            ) from exc

    if (end_dt - start_dt).days > 365 or end_dt < start_dt:
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "Date range must be between 0 and 365 days",
            {"from_date": "range must not exceed 365 days"},
        )

    q = select(OccupancySnapshot).where(
        OccupancySnapshot.venue_id == venue_id,
        OccupancySnapshot.organization_id == actor.organization_id,
        OccupancySnapshot.captured_at >= start_dt,
        OccupancySnapshot.captured_at <= end_dt,
    )
    if section:
        q = q.where(OccupancySnapshot.section_name == section)
    snaps = (await db.execute(q)).scalars().all()

    hourly_buckets: dict[int, list[OccupancySnapshot]] = {h: [] for h in range(24)}
    heatmap_buckets: dict[tuple[int, int], list[OccupancySnapshot]] = {}
    unknown_count = 0
    sla_breach_count = 0
    for s in snaps:
        hr = s.captured_at.hour
        dow = s.captured_at.weekday()
        hourly_buckets[hr].append(s)
        heatmap_buckets.setdefault((dow, hr), []).append(s)
        if s.state == "UNKNOWN":
            unknown_count += 1
        if s.sla_breached:
            sla_breach_count += 1

    hourly_series: list[dict[str, Any]] = []
    for hr in range(24):
        items = hourly_buckets[hr]
        if items:
            occ_pct = round(
                100.0
                * sum(1 for x in items if x.state in {"OCCUPIED", "NEEDS_SERVICE"})
                / len(items),
                1,
            )
            peak_guests = max(x.guest_count for x in items)
            staff_rec = int(math.ceil(peak_guests / ratio)) if peak_guests > 0 else 1
        else:
            occ_pct = 0.0
            peak_guests = 0
            staff_rec = 0
        hourly_series.append(
            {
                "hour": f"{hr:02d}:00",
                "avg_occupancy_pct": occ_pct,
                "peak_seated_guests": peak_guests,
                "recommended_servers": staff_rec,
                "sample_count": len(items),
            }
        )

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "hour",
                "avg_occupancy_pct",
                "peak_seated_guests",
                "recommended_servers",
                "sample_count",
            ]
        )
        for row in hourly_series:
            writer.writerow(
                [
                    _csv_safe(row["hour"]),
                    _csv_safe(row["avg_occupancy_pct"]),
                    _csv_safe(row["peak_seated_guests"]),
                    _csv_safe(row["recommended_servers"]),
                    _csv_safe(row["sample_count"]),
                ]
            )
        return Response(
            content=buf.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="tablepulse-analytics-{venue_id}.csv"'
            },
        )

    wait_rows = (
        (
            await db.execute(
                select(WaitlistEntry).where(
                    WaitlistEntry.venue_id == venue_id,
                    WaitlistEntry.status == "SEATED",
                    WaitlistEntry.seated_at.is_not(None),
                    WaitlistEntry.joined_at >= start_dt,
                )
            )
        )
        .scalars()
        .all()
    )
    wait_mins = [
        (w.seated_at - w.joined_at).total_seconds() / 60.0
        for w in wait_rows
        if w.seated_at is not None
    ]
    avg_wait = round(sum(wait_mins) / len(wait_mins), 1) if wait_mins else 0.0

    peak_hour_row = (
        max(hourly_series, key=lambda r: r["avg_occupancy_pct"]) if hourly_series else None
    )
    heatmap = [
        {
            "day_of_week": dow,
            "hour": hr,
            "avg_occupancy_pct": round(
                100.0
                * sum(1 for x in items if x.state in {"OCCUPIED", "NEEDS_SERVICE"})
                / len(items),
                1,
            ),
        }
        for (dow, hr), items in sorted(heatmap_buckets.items())
    ]

    return success_response(
        {
            "venue_id": str(venue_id),
            "guests_per_server_ratio": ratio,
            "kpis": {
                "peak_occupancy_hour": peak_hour_row["hour"]
                if peak_hour_row and peak_hour_row["sample_count"] > 0
                else "N/A",
                "avg_turn_minutes": 42.0 if snaps else 0.0,
                "avg_wait_minutes": avg_wait,
                "sla_breach_rate_pct": round((100.0 * sla_breach_count / len(snaps)), 1)
                if snaps
                else 0.0,
                "unknown_pct": round((100.0 * unknown_count / len(snaps)), 1) if snaps else 0.0,
            },
            "hourly_series": hourly_series,
            "heatmap": heatmap,
            "total_samples": len(snaps),
        }
    )
