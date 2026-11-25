"""WebSocket venue hub and Valkey Streams CV event consumer."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from fastapi import WebSocket
from sqlalchemy import select

from app.config import get_settings
from app.core.valkey_client import get_valkey
from app.db.base import get_session_factory, uuid7
from app.db.models import Alert, DiningTable, MLReviewItem, OccupancySnapshot, TableStateEvent
from app.db.partitions import ensure_occupancy_partition

logger = structlog.get_logger("realtime")


class VenueWSHub:
    """In-process WebSocket fan-out manager scoped by venue_id."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, venue_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(venue_id, set()).add(ws)

    def disconnect(self, venue_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(venue_id)
        if conns:
            conns.discard(ws)

    async def broadcast(self, venue_id: str, event: dict[str, Any]) -> None:
        conns = list(self._connections.get(venue_id, set()))
        if not conns:
            return
        msg = json.dumps(event)
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await asyncio.wait_for(ws.send_text(msg), timeout=2.0)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(venue_id, ws)

    async def broadcast_all(self, event: dict[str, Any]) -> None:
        for vid in list(self._connections.keys()):
            await self.broadcast(vid, event)


ws_hub = VenueWSHub()


async def process_cv_stream_event(fields: dict[str, Any]) -> None:
    """Persist a CV event from Valkey Stream tp:cv:events into PostgreSQL and broadcast via WS."""
    table_id = uuid.UUID(str(fields["table_id"]))
    venue_id = uuid.UUID(str(fields["venue_id"]))
    org_id = uuid.UUID(str(fields["organization_id"]))
    camera_id = uuid.UUID(str(fields["camera_id"]))
    new_state = str(fields["new_state"])
    prev_state = str(fields.get("previous_state") or "")
    guest_count = int(fields.get("guest_count", 0))
    confidence = float(fields.get("confidence", 0.0))
    source = str(fields.get("source", "AI"))
    reason = str(fields.get("reason", ""))
    model_version = str(fields.get("model_version", ""))
    session_id_raw = str(fields.get("session_id") or "")
    session_id = uuid.UUID(session_id_raw) if session_id_raw else None
    now = datetime.now(UTC)

    factory = get_session_factory()
    async with factory() as db:
        tbl = (
            await db.execute(select(DiningTable).where(DiningTable.id == table_id))
        ).scalar_one_or_none()
        if tbl is None or tbl.deleted_at is not None:
            return

        if tbl.current_state == "RESERVED":
            return

        tbl.current_state = new_state
        tbl.current_guest_count = guest_count
        tbl.current_confidence = confidence
        if new_state == "OCCUPIED" and tbl.occupied_since is None:
            tbl.occupied_since = now
        elif new_state == "FREE":
            tbl.occupied_since = None
            tbl.last_staff_visit_at = None
        tbl.active_session_id = session_id
        tbl.version += 1

        db.add(
            TableStateEvent(
                id=uuid7(),
                organization_id=org_id,
                venue_id=venue_id,
                table_id=table_id,
                session_id=session_id,
                previous_state=prev_state or None,
                new_state=new_state,
                guest_count=guest_count,
                confidence=confidence,
                source=source,
                reason=reason,
                model_version=model_version,
                occurred_at=now,
            )
        )

        await ensure_occupancy_partition(db, now)
        db.add(
            OccupancySnapshot(
                captured_at=now,
                table_id=table_id,
                organization_id=org_id,
                venue_id=venue_id,
                section_name=tbl.section_name,
                state=new_state,
                guest_count=guest_count,
                seat_capacity=tbl.seat_capacity,
                sla_breached=(new_state == "NEEDS_SERVICE"),
            )
        )

        # Create idempotent operational alert when needed
        created_alert: Alert | None = None
        if new_state in {"NEEDS_SERVICE", "NEEDS_CLEANING", "UNKNOWN"}:
            alert_type = (
                "UNATTENDED_TABLE"
                if new_state == "NEEDS_SERVICE"
                else ("NEEDS_CLEANING" if new_state == "NEEDS_CLEANING" else "LOW_CONFIDENCE")
            )
            dedup_key = f"{venue_id}:{table_id}:{session_id or 'none'}:{alert_type}"
            existing = (
                await db.execute(
                    select(Alert).where(
                        Alert.dedup_key == dedup_key,
                        Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"]),
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                sev = "CRITICAL" if alert_type == "UNATTENDED_TABLE" else "WARNING"
                msg = (
                    f"{tbl.table_code} waiting for service ({guest_count} guests)"
                    if alert_type == "UNATTENDED_TABLE"
                    else (
                        f"CCTV: Party left {tbl.table_code} — Needs Cleaning"
                        if alert_type == "NEEDS_CLEANING"
                        else f"{tbl.table_code} confidence low ({confidence:.0%}) — Review needed"
                    )
                )
                created_alert = Alert(
                    id=uuid7(),
                    organization_id=org_id,
                    venue_id=venue_id,
                    table_id=table_id,
                    camera_id=camera_id,
                    alert_type=alert_type,
                    severity=sev,
                    status="ACTIVE",
                    dedup_key=dedup_key,
                    message=msg,
                    created_at=now,
                )
                db.add(created_alert)

        if fields.get("enqueue_review") == "1":
            snap_path: str | None = None
            b64_crop = fields.get("blurred_crop_b64")
            if b64_crop and get_settings().review_crops_enabled:
                raw_bytes = base64.b64decode(str(b64_crop))
                if raw_bytes.startswith(b"\xff\xd8\xff"):
                    snap_dir = Path(get_settings().snapshot_storage_dir) / str(org_id)
                    snap_dir.mkdir(parents=True, exist_ok=True)
                    fpath = snap_dir / f"{uuid7()}.jpg"
                    fpath.write_bytes(raw_bytes)
                    snap_path = str(fpath)
            db.add(
                MLReviewItem(
                    id=uuid7(),
                    organization_id=org_id,
                    venue_id=venue_id,
                    table_id=table_id,
                    camera_id=camera_id,
                    snapshot_path=snap_path,
                    predicted_state=new_state,
                    predicted_guest_count=guest_count,
                    confidence=confidence,
                    trigger_reason="LOW_CONFIDENCE",
                )
            )

        await db.commit()

    await ws_hub.broadcast(
        str(venue_id),
        {
            "type": "table.state_changed",
            "data": {
                "table_id": str(table_id),
                "table_code": str(fields.get("table_code", "")),
                "previous_state": prev_state,
                "new_state": new_state,
                "guest_count": guest_count,
                "occupied_since": now.isoformat() if new_state == "OCCUPIED" else None,
                "confidence": confidence,
                "source": source,
                "toast_message": f"{fields.get('table_code', '')} -> {new_state}",
            },
        },
    )
    if created_alert is not None:
        await ws_hub.broadcast(
            str(venue_id),
            {
                "type": "alert.created",
                "data": {
                    "alert_id": str(created_alert.id),
                    "table_code": str(fields.get("table_code", "")),
                    "alert_type": created_alert.alert_type,
                    "severity": created_alert.severity,
                    "status": created_alert.status,
                    "message": created_alert.message,
                    "created_at": created_alert.created_at.isoformat(),
                },
            },
        )


async def cv_stream_consumer_loop(stop_event: asyncio.Event) -> None:
    """Background consumer reading tp:cv:events Valkey Stream with consumer group."""
    stream_name = "tp:cv:events"
    group_name = "tp-api-group"
    consumer_name = f"api-{uuid.uuid4().hex[:8]}"
    while not stop_event.is_set():
        try:
            vk = get_valkey()
            with contextlib.suppress(Exception):
                await vk.xgroup_create(stream_name, group_name, id="0", mkstream=True)
            entries = await vk.xreadgroup(
                group_name, consumer_name, {stream_name: ">"}, count=20, block=1000
            )
            for _stream, messages in entries or []:
                for msg_id, fields in messages:
                    try:
                        await process_cv_stream_event(fields)
                    except Exception as exc:
                        logger.warning("cv_event_process_error", error=str(exc))
                    await vk.xack(stream_name, group_name, msg_id)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(2.0)
