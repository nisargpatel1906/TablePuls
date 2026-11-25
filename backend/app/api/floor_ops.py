"""Live Floor State, Table Detail, Manual Overrides, AI Flag, Alerts, and WebSocket (API-011..015)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import consume_ws_ticket
from app.core.errors import AppError, success_response
from app.core.rbac import Role, require_venue_role
from app.core.valkey_client import check_and_store_idempotency
from app.db.base import get_db, get_session_factory, uuid7
from app.db.models import (
    Alert,
    Camera,
    DiningTable,
    MLReviewItem,
    SystemSetting,
    TableStateEvent,
    Venue,
)
from app.schemas.floor_ops import FlagDetectionRequest, TableOverrideRequest, UpdateAlertRequest
from app.services.audit import write_audit_log
from app.services.realtime import ws_hub

router = APIRouter(tags=["floor-ops"])


def _table_dict(t: DiningTable) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "venue_id": str(t.venue_id),
        "camera_id": str(t.camera_id) if t.camera_id else None,
        "table_code": t.table_code,
        "section_name": t.section_name,
        "seat_capacity": t.seat_capacity,
        "polygon_json": t.polygon_json,
        "floor_x": t.floor_x,
        "floor_y": t.floor_y,
        "shape": t.shape,
        "current_state": t.current_state,
        "current_guest_count": t.current_guest_count,
        "current_confidence": t.current_confidence,
        "occupied_since": t.occupied_since.isoformat() if t.occupied_since else None,
        "last_staff_visit_at": t.last_staff_visit_at.isoformat() if t.last_staff_visit_at else None,
        "predicted_free_at": t.predicted_free_at.isoformat() if t.predicted_free_at else None,
        "version": t.version,
    }


def _alert_dict(a: Alert, table_code: str | None = None) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "venue_id": str(a.venue_id),
        "table_id": str(a.table_id) if a.table_id else None,
        "table_code": table_code,
        "camera_id": str(a.camera_id) if a.camera_id else None,
        "alert_type": a.alert_type,
        "severity": a.severity,
        "status": a.status,
        "message": a.message,
        "created_at": a.created_at.isoformat(),
        "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
    }


async def build_floor_snapshot(
    db: AsyncSession, venue_id: uuid.UUID, org_id: uuid.UUID
) -> dict[str, Any]:
    tables = (
        (
            await db.execute(
                select(DiningTable)
                .where(
                    DiningTable.venue_id == venue_id,
                    DiningTable.organization_id == org_id,
                    DiningTable.deleted_at.is_(None),
                )
                .order_by(DiningTable.table_code.asc())
            )
        )
        .scalars()
        .all()
    )
    alerts_count = (
        await db.execute(
            select(func.count())
            .select_from(Alert)
            .where(
                Alert.venue_id == venue_id,
                Alert.organization_id == org_id,
                Alert.status == "ACTIVE",
            )
        )
    ).scalar_one()
    cams = (
        (
            await db.execute(
                select(Camera).where(
                    Camera.venue_id == venue_id,
                    Camera.organization_id == org_id,
                    Camera.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    sys_set = (
        await db.execute(select(SystemSetting).where(SystemSetting.organization_id == org_id))
    ).scalar_one_or_none()

    total_tables = len(tables)
    occupied_tables = sum(1 for t in tables if t.current_state in {"OCCUPIED", "NEEDS_SERVICE"})
    total_seats = sum(t.seat_capacity for t in tables)
    seated_guests = sum(
        t.current_guest_count for t in tables if t.current_state in {"OCCUPIED", "NEEDS_SERVICE"}
    )
    capacity_pct = round((seated_guests / total_seats) * 100.0, 1) if total_seats > 0 else 0.0

    return {
        "venue_id": str(venue_id),
        "kpis": {
            "occupied_tables": occupied_tables,
            "total_tables": total_tables,
            "seated_guests": seated_guests,
            "total_seats": total_seats,
            "capacity_pct": capacity_pct,
            "active_alerts": int(alerts_count),
        },
        "ai_inference_enabled": bool(sys_set.ai_inference_enabled) if sys_set else False,
        "cameras_summary": {
            "total": len(cams),
            "online": sum(1 for c in cams if c.status == "ONLINE"),
            "offline": sum(1 for c in cams if c.status == "OFFLINE"),
        },
        "tables": [_table_dict(t) for t in tables],
    }


@router.get("/api/v1/venues/{venue_id}/floor-state")
async def get_floor_state(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="floor.view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-011: Full live floor state + KPIs (and 5s HTTP polling fallback)."""
    snap = await build_floor_snapshot(db, venue_id, actor.organization_id)
    return success_response(snap)


@router.get("/api/v1/venues/{venue_id}/tables/{table_id}")
async def get_table_detail(
    venue_id: uuid.UUID,
    table_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="floor.view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-012: Single table detail, latest blurred crop reference, and last 10 events."""
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

    events = (
        (
            await db.execute(
                select(TableStateEvent)
                .where(TableStateEvent.table_id == table_id)
                .order_by(TableStateEvent.occurred_at.desc())
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    latest_review = (
        await db.execute(
            select(MLReviewItem)
            .where(MLReviewItem.table_id == table_id, MLReviewItem.snapshot_path.is_not(None))
            .order_by(MLReviewItem.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return success_response(
        {
            "table": _table_dict(tbl),
            "latest_snapshot_available": latest_review is not None,
            "events": [
                {
                    "id": str(e.id),
                    "previous_state": e.previous_state,
                    "new_state": e.new_state,
                    "guest_count": e.guest_count,
                    "confidence": e.confidence,
                    "source": e.source,
                    "reason": e.reason,
                    "occurred_at": e.occurred_at.isoformat(),
                }
                for e in events
            ],
        }
    )


@router.patch("/api/v1/venues/{venue_id}/tables/{table_id}/override")
async def override_table_state(
    venue_id: uuid.UUID,
    table_id: uuid.UUID,
    body: TableOverrideRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="tables.mark_clean_or_served"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """API-013: Manual table override with optimistic lock (409) and STAFF scope restriction."""
    if idempotency_key:
        cached = await check_and_store_idempotency(f"override:{table_id}:{idempotency_key}")
        if cached is not None:
            return success_response(cached)

    # STAFF may only mark clean (FREE) or mark service attended (OCCUPIED with mark_service_attended)
    if actor.role == Role.STAFF and not (
        body.new_state == "FREE" or (body.new_state == "OCCUPIED" and body.mark_service_attended)
    ):
        raise AppError(
            403,
            "AUTH_FORBIDDEN",
            "STAFF may only mark tables clean (FREE) or mark service attended",
        )

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

    if tbl.version != body.version:
        raise AppError(
            409,
            "VERSION_CONFLICT",
            f"Table {tbl.table_code} was updated by another user; please refresh",
        )

    now = datetime.now(UTC)
    prev_state = tbl.current_state
    before = {"state": prev_state, "guest_count": tbl.current_guest_count, "version": tbl.version}

    tbl.current_state = body.new_state
    if body.new_state == "FREE":
        tbl.current_guest_count = 0
        tbl.occupied_since = None
        tbl.last_staff_visit_at = None
        tbl.active_session_id = None
    elif body.new_state == "OCCUPIED":
        if tbl.occupied_since is None:
            tbl.occupied_since = now
        if body.mark_service_attended:
            tbl.last_staff_visit_at = now
        if body.guest_count is not None:
            tbl.current_guest_count = body.guest_count
        elif tbl.current_guest_count == 0:
            tbl.current_guest_count = 1
    elif body.new_state == "RESERVED":
        tbl.current_guest_count = 0
        tbl.occupied_since = None
    elif body.guest_count is not None:
        tbl.current_guest_count = body.guest_count

    tbl.version += 1

    db.add(
        TableStateEvent(
            id=uuid7(),
            organization_id=actor.organization_id,
            venue_id=venue_id,
            table_id=table_id,
            session_id=tbl.active_session_id,
            previous_state=prev_state,
            new_state=body.new_state,
            guest_count=tbl.current_guest_count,
            confidence=1.0,
            source="MANUAL",
            actor_user_id=actor.id,
            reason=body.reason.strip(),
            occurred_at=now,
        )
    )

    # Auto-resolve matching active alerts when table is marked FREE or service attended
    if body.new_state == "FREE" or body.mark_service_attended:
        await db.execute(
            update(Alert)
            .where(
                Alert.table_id == table_id,
                Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"]),
            )
            .values(status="RESOLVED", resolved_at=now)
        )

    after = _table_dict(tbl)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="OVERRIDE_TABLE",
        target_type="table",
        target_id=table_id,
        before_json=before,
        after_json={
            "state": tbl.current_state,
            "guest_count": tbl.current_guest_count,
            "reason": body.reason,
        },
        request=request,
    )
    await db.commit()

    await ws_hub.broadcast(
        str(venue_id),
        {
            "type": "table.state_changed",
            "data": {
                "table_id": str(tbl.id),
                "table_code": tbl.table_code,
                "previous_state": prev_state,
                "new_state": tbl.current_state,
                "guest_count": tbl.current_guest_count,
                "occupied_since": tbl.occupied_since.isoformat() if tbl.occupied_since else None,
                "confidence": 1.0,
                "source": "MANUAL",
                "toast_message": f"{tbl.table_code} manually set to {tbl.current_state}",
            },
        },
    )
    if idempotency_key:
        await check_and_store_idempotency(f"override:{table_id}:{idempotency_key}", after)
    return success_response(after)


@router.post("/api/v1/venues/{venue_id}/tables/{table_id}/flag", status_code=201)
async def flag_table_detection(
    venue_id: uuid.UUID,
    table_id: uuid.UUID,
    body: FlagDetectionRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="tables.flag_ai"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-014: Flag inaccurate AI detection -> ml_review_items."""
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

    item = MLReviewItem(
        id=uuid7(),
        organization_id=actor.organization_id,
        venue_id=venue_id,
        table_id=table_id,
        camera_id=tbl.camera_id or uuid7(),
        predicted_state=tbl.current_state,
        predicted_guest_count=tbl.current_guest_count,
        confidence=tbl.current_confidence or 0.0,
        trigger_reason="USER_FLAGGED",
        human_state=body.suggested_state,
        issue_tags=[body.reason.strip()],
    )
    db.add(item)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="FLAG_AI_DETECTION",
        target_type="ml_review_item",
        target_id=item.id,
        after_json={"table_code": tbl.table_code, "reason": body.reason},
        request=request,
    )
    await db.commit()
    return success_response({"review_item_id": str(item.id), "status": "PENDING"}, status_code=201)


@router.get("/api/v1/venues/{venue_id}/alerts")
async def list_alerts(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="alerts.view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[str | None, Query()] = None,
    alert_type: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> JSONResponse:
    """API-015 (list): Paginated operational alerts queue."""
    q = select(Alert).where(
        Alert.venue_id == venue_id,
        Alert.organization_id == actor.organization_id,
    )
    if status:
        q = q.where(Alert.status == status)
    if alert_type:
        q = q.where(Alert.alert_type == alert_type)

    rows = (await db.execute(q.order_by(Alert.created_at.desc()))).scalars().all()
    tables = (
        await db.execute(
            select(DiningTable.id, DiningTable.table_code).where(DiningTable.venue_id == venue_id)
        )
    ).all()
    code_map = {tid: code for tid, code in tables}

    total = len(rows)
    start = (page - 1) * page_size
    items = [
        _alert_dict(a, code_map.get(a.table_id) if a.table_id else None)
        for a in rows[start : start + page_size]
    ]
    return success_response({"items": items, "total": total, "page": page, "page_size": page_size})


@router.patch("/api/v1/venues/{venue_id}/alerts/{alert_id}")
async def update_alert(
    venue_id: uuid.UUID,
    alert_id: uuid.UUID,
    body: UpdateAlertRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="alerts.resolve"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-015 (update): Acknowledge or resolve an operational alert."""
    alert = (
        await db.execute(
            select(Alert).where(
                Alert.id == alert_id,
                Alert.venue_id == venue_id,
                Alert.organization_id == actor.organization_id,
            )
        )
    ).scalar_one_or_none()
    if alert is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Alert not found")

    now = datetime.now(UTC)
    alert.status = body.status
    if body.status == "ACKNOWLEDGED":
        alert.acknowledged_by = actor.id
        alert.acknowledged_at = now
    else:
        if alert.acknowledged_by is None:
            alert.acknowledged_by = actor.id
            alert.acknowledged_at = now
        alert.resolved_at = now

    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="UPDATE_ALERT",
        target_type="alert",
        target_id=alert.id,
        after_json={"status": alert.status},
        request=request,
    )
    await db.commit()
    payload = _alert_dict(alert)
    await ws_hub.broadcast(str(venue_id), {"type": "alert.updated", "data": payload})
    return success_response(payload)


@router.websocket("/api/v1/ws/venues/{venue_id}")
async def venue_websocket(
    websocket: WebSocket,
    venue_id: uuid.UUID,
    ticket: Annotated[str, Query(min_length=8)],
) -> None:
    """Authenticated venue WebSocket emitting floor.snapshot and incremental live events."""
    claims = await consume_ws_ticket(ticket)
    if claims is None:
        await websocket.close(code=4401)
        return

    org_id = uuid.UUID(claims["organization_id"])
    role = claims["role"]
    assigned = {uuid.UUID(v) for v in claims.get("assigned_venue_ids", "").split(",") if v}

    factory = get_session_factory()
    async with factory() as db:
        venue = (
            await db.execute(
                select(Venue).where(
                    Venue.id == venue_id,
                    Venue.organization_id == org_id,
                    Venue.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if venue is None or (role != Role.OWNER and venue_id not in assigned):
            await websocket.close(code=4403)
            return
        snap = await build_floor_snapshot(db, venue_id, org_id)

    await ws_hub.connect(str(venue_id), websocket)
    try:
        await websocket.send_json({"type": "floor.snapshot", "data": snap})
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_hub.disconnect(str(venue_id), websocket)
    except Exception:
        ws_hub.disconnect(str(venue_id), websocket)
