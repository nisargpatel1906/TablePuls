"""Venues, Cameras, Polygons, and MediaMTX auth endpoints (API-007..API-010, media-auth)."""

from __future__ import annotations

import asyncio
import base64
import hmac
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import parse_qs

import cv2
import numpy as np
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import AppError, success_response
from app.core.geometry import validate_normalized_polygon
from app.core.privacy import FaceBlurError, blur_faces_in_bgr, generate_demo_floor_frame
from app.core.rbac import Role, require_org_role, require_venue_role
from app.core.security import (
    create_stream_token,
    decrypt_field,
    encrypt_field,
    verify_stream_token,
)
from app.core.ssrf import mask_stream_url, validate_camera_stream_url
from app.core.valkey_client import publish_cv_control, set_kill_switch_cache
from app.db.base import get_db, uuid7
from app.db.models import AlertRule, Camera, DiningTable, SystemSetting, Venue
from app.schemas.venues_cameras import (
    BulkPolygonsRequest,
    CreateCameraRequest,
    CreateVenueRequest,
    MediaAuthHookRequest,
    UpdateCameraRequest,
    UpdateVenueRequest,
)
from app.services.audit import write_audit_log

router = APIRouter(tags=["venues-cameras"])


def _venue_dict(v: Venue) -> dict[str, Any]:
    return {
        "id": str(v.id),
        "organization_id": str(v.organization_id),
        "name": v.name,
        "timezone": v.timezone,
        "operating_hours_json": v.operating_hours_json,
        "allow_host_camera_view": v.allow_host_camera_view,
        "allow_host_menu_availability": v.allow_host_menu_availability,
        "guests_per_server_ratio": v.guests_per_server_ratio,
        "currency_code": v.currency_code,
        "menu_public_enabled": v.menu_public_enabled,
        "show_unavailable_items_public": v.show_unavailable_items_public,
        "menu_tagline": v.menu_tagline,
        "logo_storage_key": v.logo_storage_key,
        "menu_revision": v.menu_revision,
        "qr_grace_days": v.qr_grace_days,
        "created_at": v.created_at.isoformat(),
    }


def _camera_dict(c: Camera, table_count: int = 0) -> dict[str, Any]:
    raw_url = decrypt_field(c.stream_url_encrypted)
    masked = (
        mask_stream_url(raw_url)
        if c.stream_type in {"RTSP", "RTSPS", "HLS", "HTTP_MJPEG", "RTMP"}
        else raw_url
    )
    return {
        "id": str(c.id),
        "venue_id": str(c.venue_id),
        "name": c.name,
        "stream_type": c.stream_type,
        "masked_stream_url": masked,
        "target_fps": c.target_fps,
        "face_blur_enabled": c.face_blur_enabled,
        "status": c.status,
        "last_heartbeat_at": c.last_heartbeat_at.isoformat() if c.last_heartbeat_at else None,
        "exclusion_polygons_json": c.exclusion_polygons_json or [],
        "mapped_table_count": table_count,
        "created_at": c.created_at.isoformat(),
    }


@router.get("/api/v1/venues")
async def list_venues(
    user: Annotated[
        Any,
        Depends(require_org_role({Role.OWNER, Role.MANAGER, Role.HOST, Role.STAFF, Role.VIEWER})),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-007 (list): Return venues belonging to the authenticated user's org/scope."""
    q = select(Venue).where(
        Venue.organization_id == user.organization_id,
        Venue.deleted_at.is_(None),
    )
    if user.role != Role.OWNER:
        q = q.where(Venue.id.in_(user.assigned_venue_ids or []))
    rows = (await db.execute(q.order_by(Venue.created_at.asc()))).scalars().all()
    return success_response({"items": [_venue_dict(v) for v in rows]})


@router.post("/api/v1/venues", status_code=201)
async def create_venue(
    body: CreateVenueRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_org_role({Role.OWNER, Role.MANAGER}))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-007 (create): Create a new venue and default alert_rules row."""
    venue = Venue(
        id=uuid7(),
        organization_id=actor.organization_id,
        name=body.name.strip(),
        timezone=body.timezone.strip(),
        operating_hours_json=body.operating_hours_json,
        allow_host_camera_view=body.allow_host_camera_view,
        guests_per_server_ratio=body.guests_per_server_ratio,
    )
    db.add(venue)
    await db.flush()

    # Create default venue-level alert_rules row
    db.add(
        AlertRule(
            id=uuid7(),
            organization_id=actor.organization_id,
            venue_id=venue.id,
            section_name=None,
        )
    )
    if actor.role != Role.OWNER and venue.id not in (actor.assigned_venue_ids or []):
        actor.assigned_venue_ids = [*list(actor.assigned_venue_ids or []), venue.id]

    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue.id,
        actor_user_id=actor.id,
        action="CREATE_VENUE",
        target_type="venue",
        target_id=venue.id,
        after_json={"name": venue.name, "timezone": venue.timezone},
        request=request,
    )
    await db.commit()
    await db.refresh(venue)
    return success_response(_venue_dict(venue), status_code=201)


@router.patch("/api/v1/venues/{venue_id}")
async def update_venue(
    venue_id: uuid.UUID,
    body: UpdateVenueRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="venues.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-007 (update): Update venue settings."""
    venue = (
        await db.execute(
            select(Venue).where(
                Venue.id == venue_id,
                Venue.organization_id == actor.organization_id,
                Venue.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if venue is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Venue not found")

    before = _venue_dict(venue)
    if body.name is not None:
        venue.name = body.name.strip()
    if body.timezone is not None:
        venue.timezone = body.timezone.strip()
    if body.operating_hours_json is not None:
        venue.operating_hours_json = body.operating_hours_json
    if body.allow_host_camera_view is not None:
        venue.allow_host_camera_view = body.allow_host_camera_view
    if body.guests_per_server_ratio is not None:
        venue.guests_per_server_ratio = body.guests_per_server_ratio

    after = _venue_dict(venue)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue.id,
        actor_user_id=actor.id,
        action="UPDATE_VENUE",
        target_type="venue",
        target_id=venue.id,
        before_json=before,
        after_json=after,
        request=request,
    )
    await db.commit()
    return success_response(after)


@router.get("/api/v1/venues/{venue_id}/cameras")
async def list_cameras(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="cameras.live.view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-008 (list): List venue cameras with masked URLs."""
    cams = (
        (
            await db.execute(
                select(Camera).where(
                    Camera.venue_id == venue_id,
                    Camera.organization_id == actor.organization_id,
                    Camera.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    tables = (
        (
            await db.execute(
                select(DiningTable).where(
                    DiningTable.venue_id == venue_id,
                    DiningTable.organization_id == actor.organization_id,
                    DiningTable.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    counts: dict[uuid.UUID, int] = {}
    for t in tables:
        if t.camera_id:
            counts[t.camera_id] = counts.get(t.camera_id, 0) + 1
    return success_response({"items": [_camera_dict(c, counts.get(c.id, 0)) for c in cams]})


@router.post("/api/v1/venues/{venue_id}/cameras", status_code=201)
async def create_camera(
    venue_id: uuid.UUID,
    body: CreateCameraRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="cameras.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-008 (create): Add RTSP/RTSPS/HLS/HTTP_MJPEG/RTMP or DEMO_MP4 camera with AES-256-GCM encryption."""
    settings = get_settings()
    if body.stream_type != "DEMO_MP4":
        stream_url = validate_camera_stream_url(body.stream_url, body.stream_type)
    else:
        if not settings.demo_mode:
            raise AppError(400, "VALIDATION_ERROR", "DEMO_MP4 cameras require DEMO_MODE=true")
        stream_url = body.stream_url.strip()

    creds_blob: bytes | None = None
    if body.username or body.password:
        creds_blob = encrypt_field(f"{body.username or ''}:{body.password or ''}")

    cam = Camera(
        id=uuid7(),
        organization_id=actor.organization_id,
        venue_id=venue_id,
        name=body.name.strip(),
        stream_type=body.stream_type,
        stream_url_encrypted=encrypt_field(stream_url),
        credentials_encrypted=creds_blob,
        target_fps=body.target_fps,
        face_blur_enabled=body.face_blur_enabled,
        status="ONLINE" if body.stream_type == "DEMO_MP4" else "OFFLINE",
    )
    db.add(cam)
    await db.flush()

    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="CREATE_CAMERA",
        target_type="camera",
        target_id=cam.id,
        after_json={
            "name": cam.name,
            "stream_type": cam.stream_type,
            "masked_stream_url": mask_stream_url(stream_url),
        },
        request=request,
    )
    await db.commit()
    await db.refresh(cam)
    await publish_cv_control(
        {"event": "camera_reload", "venue_id": str(venue_id), "camera_id": str(cam.id)}
    )
    return success_response(_camera_dict(cam), status_code=201)


@router.patch("/api/v1/venues/{venue_id}/cameras/{camera_id}")
async def update_camera(
    venue_id: uuid.UUID,
    camera_id: uuid.UUID,
    body: UpdateCameraRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="cameras.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-008 (update): Update camera settings without echoing credentials."""
    cam = (
        await db.execute(
            select(Camera).where(
                Camera.id == camera_id,
                Camera.venue_id == venue_id,
                Camera.organization_id == actor.organization_id,
                Camera.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if cam is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Camera not found")

    before = _camera_dict(cam)
    settings = get_settings()
    prev_type = cam.stream_type
    if body.name is not None:
        cam.name = body.name.strip()
    if body.stream_type is not None:
        if body.stream_type == "DEMO_MP4" and not settings.demo_mode:
            raise AppError(400, "VALIDATION_ERROR", "DEMO_MP4 cameras require DEMO_MODE=true")
        cam.stream_type = body.stream_type
    if body.stream_url is not None:
        url = (
            validate_camera_stream_url(body.stream_url, cam.stream_type)
            if cam.stream_type != "DEMO_MP4"
            else body.stream_url.strip()
        )
        cam.stream_url_encrypted = encrypt_field(url)
    elif prev_type != "DEMO_MP4" and cam.stream_type == "DEMO_MP4":
        # Prevent unmasked RTSP credential URL exposure after switching to DEMO_MP4
        cam.stream_url_encrypted = encrypt_field("demo://sample_floor.mp4")
    if body.username is not None or body.password is not None:
        cam.credentials_encrypted = encrypt_field(f"{body.username or ''}:{body.password or ''}")
    if body.target_fps is not None:
        cam.target_fps = body.target_fps
    if body.face_blur_enabled is not None:
        cam.face_blur_enabled = body.face_blur_enabled
    if body.status is not None:
        cam.status = body.status

    after = _camera_dict(cam)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="UPDATE_CAMERA",
        target_type="camera",
        target_id=cam.id,
        before_json=before,
        after_json=after,
        request=request,
    )
    await db.commit()
    await publish_cv_control(
        {"event": "camera_reload", "venue_id": str(venue_id), "camera_id": str(cam.id)}
    )
    return success_response(after)


@router.delete("/api/v1/venues/{venue_id}/cameras/{camera_id}")
async def delete_camera(
    venue_id: uuid.UUID,
    camera_id: uuid.UUID,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="cameras.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-008 (delete): Soft-delete camera and publish reload event."""
    cam = (
        await db.execute(
            select(Camera).where(
                Camera.id == camera_id,
                Camera.venue_id == venue_id,
                Camera.organization_id == actor.organization_id,
                Camera.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if cam is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Camera not found")

    cam.deleted_at = datetime.now(UTC)
    cam.status = "DISABLED"
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="DELETE_CAMERA",
        target_type="camera",
        target_id=cam.id,
        request=request,
    )
    await db.commit()
    await publish_cv_control(
        {"event": "camera_reload", "venue_id": str(venue_id), "camera_id": str(cam.id)}
    )
    return success_response({"deleted": True, "camera_id": str(camera_id)})


def _read_camera_frame_sync(
    stream_type: str, raw_url: str, fallback_demo_path: str
) -> tuple[bool, Any]:
    if stream_type == "DEMO_MP4":
        demo_root = Path(fallback_demo_path).resolve().parent
        demo_path = Path(fallback_demo_path)
        if raw_url and not raw_url.startswith("demo://"):
            cand = Path(raw_url).resolve()
            if cand.is_relative_to(demo_root) and cand.is_file():
                demo_path = cand
        if demo_path.exists():
            cap = cv2.VideoCapture(str(demo_path))
            ok, read_frame = cap.read()
            cap.release()
            if ok and read_frame is not None:
                return True, read_frame
        return True, generate_demo_floor_frame(1280, 720)

    cap = cv2.VideoCapture(raw_url)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
    ok = False
    frame: Any = None
    if cap.isOpened():
        ok, frame = cap.read()
    cap.release()
    return ok, frame


def _apply_exclusions_and_blur(frame: Any, exclusion_zones: list[Any] | None) -> bytes:
    out = frame.copy()
    h, w = out.shape[:2]
    for zone in exclusion_zones or []:
        if isinstance(zone, list) and len(zone) >= 3:
            pts = np.array(
                [
                    [
                        int(max(0, min(w - 1, float(p["x"]) * w))),
                        int(max(0, min(h - 1, float(p["y"]) * h))),
                    ]
                    for p in zone
                    if isinstance(p, dict) and "x" in p and "y" in p
                ],
                dtype=np.int32,
            )
            if len(pts) >= 3:
                cv2.fillPoly(out, [pts], (0, 0, 0))
    return blur_faces_in_bgr(out)


async def _capture_camera_preview(cam: Camera, db: AsyncSession) -> JSONResponse:
    raw_url = decrypt_field(cam.stream_url_encrypted)
    if cam.stream_type != "DEMO_MP4":
        validate_camera_stream_url(raw_url, cam.stream_type)

    ok, frame = await asyncio.to_thread(
        _read_camera_frame_sync,
        cam.stream_type,
        raw_url,
        get_settings().demo_video_path,
    )
    if not ok or frame is None:
        cam.status = "OFFLINE"
        await db.commit()
        raise AppError(
            422,
            "CAMERA_UNREACHABLE",
            "Failed to connect or decode frame from RTSP camera",
            {
                "diagnostic": "Verify host reachability, port 554, credentials, and H.264/H.265 stream"
            },
        )

    h, w = frame.shape[:2]
    if w < 640 or h < 480:
        raise AppError(
            422,
            "CAMERA_UNREACHABLE",
            f"Stream resolution {w}x{h} is below minimum 640x480",
        )

    try:
        blurred_jpeg = await asyncio.to_thread(
            _apply_exclusions_and_blur, frame, cam.exclusion_polygons_json
        )
    except FaceBlurError as exc:
        raise AppError(
            500, "INTERNAL_ERROR", f"Frame dropped due to privacy blur failure: {exc}"
        ) from exc

    cam.status = "ONLINE"
    cam.last_heartbeat_at = datetime.now(UTC)
    await db.commit()

    return success_response(
        {
            "camera_id": str(cam.id),
            "status": "ONLINE",
            "width": w,
            "height": h,
            "face_blurred": True,
            "preview_jpeg_base64": base64.b64encode(blurred_jpeg).decode("ascii"),
        }
    )


@router.get("/api/v1/venues/{venue_id}/cameras/{camera_id}/preview")
async def get_camera_preview(
    venue_id: uuid.UUID,
    camera_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="cameras.live.view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Blurred live preview snapshot for Live Camera Wall viewers (including conditional HOST)."""
    cam = (
        await db.execute(
            select(Camera).where(
                Camera.id == camera_id,
                Camera.venue_id == venue_id,
                Camera.organization_id == actor.organization_id,
                Camera.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if cam is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Camera not found")
    return await _capture_camera_preview(cam, db)


@router.post("/api/v1/venues/{venue_id}/cameras/{camera_id}/test")
async def test_camera_connection(
    venue_id: uuid.UUID,
    camera_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="cameras.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-009: Capture test frame (>=640x480), enforce face-blur-or-drop, return base64 JPEG."""
    cam = (
        await db.execute(
            select(Camera).where(
                Camera.id == camera_id,
                Camera.venue_id == venue_id,
                Camera.organization_id == actor.organization_id,
                Camera.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if cam is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Camera not found")
    return await _capture_camera_preview(cam, db)


@router.get("/api/v1/venues/{venue_id}/cameras/{camera_id}/polygons")
async def get_polygons(
    venue_id: uuid.UUID,
    camera_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="polygons.calibrate"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-010 (get): Retrieve table polygons and exclusion zones for calibration editor."""
    cam = (
        await db.execute(
            select(Camera).where(
                Camera.id == camera_id,
                Camera.venue_id == venue_id,
                Camera.organization_id == actor.organization_id,
                Camera.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if cam is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Camera not found")

    tables = (
        (
            await db.execute(
                select(DiningTable)
                .where(
                    DiningTable.venue_id == venue_id,
                    DiningTable.camera_id == camera_id,
                    DiningTable.deleted_at.is_(None),
                )
                .order_by(DiningTable.table_code.asc())
            )
        )
        .scalars()
        .all()
    )

    return success_response(
        {
            "camera_id": str(camera_id),
            "exclusion_polygons_json": cam.exclusion_polygons_json or [],
            "tables": [
                {
                    "id": str(t.id),
                    "table_code": t.table_code,
                    "section_name": t.section_name,
                    "seat_capacity": t.seat_capacity,
                    "polygon_json": t.polygon_json,
                    "floor_x": t.floor_x,
                    "floor_y": t.floor_y,
                    "shape": t.shape,
                    "version": t.version,
                }
                for t in tables
            ],
        }
    )


@router.put("/api/v1/venues/{venue_id}/cameras/{camera_id}/polygons")
async def save_polygons(
    venue_id: uuid.UUID,
    camera_id: uuid.UUID,
    body: BulkPolygonsRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="polygons.calibrate"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-010 (put): Atomically validate and save table polygons & exclusion zones."""
    cam = (
        await db.execute(
            select(Camera).where(
                Camera.id == camera_id,
                Camera.venue_id == venue_id,
                Camera.organization_id == actor.organization_id,
                Camera.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if cam is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Camera not found")

    # Validate exclusion zones
    for idx, ex_poly in enumerate(body.exclusion_polygons_json):
        pts = [{"x": p.x, "y": p.y} for p in ex_poly]
        err = validate_normalized_polygon(pts)
        if err:
            raise AppError(
                400,
                "VALIDATION_ERROR",
                "Invalid exclusion polygon",
                {f"exclusion_polygons_json.{idx}": err},
            )

    # Validate table polygons and check duplicate table_codes
    seen_codes: set[str] = set()
    for idx, tbl in enumerate(body.tables):
        code = tbl.table_code.strip().upper()
        if code in seen_codes:
            raise AppError(
                400,
                "VALIDATION_ERROR",
                f"Duplicate table_code '{code}'",
                {f"tables.{idx}.table_code": "table_code must be unique within venue"},
            )
        seen_codes.add(code)
        pts = [{"x": p.x, "y": p.y} for p in tbl.polygon_json]
        err = validate_normalized_polygon(pts)
        if err:
            raise AppError(
                400,
                "VALIDATION_ERROR",
                f"Invalid polygon for table {code}",
                {f"tables.{idx}.polygon_json": err},
            )

    # Load all active venue tables to detect cross-camera table_code collisions and optimistic locks
    venue_tables = (
        (
            await db.execute(
                select(DiningTable).where(
                    DiningTable.venue_id == venue_id,
                    DiningTable.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    by_id = {t.id: t for t in venue_tables}
    by_code_other_cam = {t.table_code.upper(): t for t in venue_tables if t.camera_id != camera_id}

    for tbl in body.tables:
        code = tbl.table_code.strip().upper()
        if code in by_code_other_cam:
            raise AppError(
                400,
                "VALIDATION_ERROR",
                f"Table code '{code}' already assigned to another camera in this venue",
                {"table_code": "duplicate table_code in venue"},
            )

    existing_cam_ids = {t.id for t in venue_tables if t.camera_id == camera_id}
    submitted_ids = {tbl.id for tbl in body.tables if tbl.id is not None}

    # Soft-delete removed tables on this camera
    now = datetime.now(UTC)
    for rem_id in existing_cam_ids - submitted_ids:
        by_id[rem_id].deleted_at = now

    saved_tables: list[DiningTable] = []
    for tbl in body.tables:
        code = tbl.table_code.strip().upper()
        poly_dicts = [{"x": p.x, "y": p.y} for p in tbl.polygon_json]
        if tbl.id is not None and tbl.id in by_id:
            row = by_id[tbl.id]
            if tbl.version is not None and row.version != tbl.version:
                raise AppError(
                    409,
                    "VERSION_CONFLICT",
                    f"Table {code} was modified concurrently",
                )
            row.table_code = code
            row.section_name = tbl.section_name.strip()
            row.seat_capacity = tbl.seat_capacity
            row.polygon_json = poly_dicts
            row.floor_x = tbl.floor_x
            row.floor_y = tbl.floor_y
            row.shape = tbl.shape
            row.camera_id = camera_id
            row.version += 1
            saved_tables.append(row)
        else:
            row = DiningTable(
                id=uuid7(),
                organization_id=actor.organization_id,
                venue_id=venue_id,
                camera_id=camera_id,
                table_code=code,
                section_name=tbl.section_name.strip(),
                seat_capacity=tbl.seat_capacity,
                polygon_json=poly_dicts,
                floor_x=tbl.floor_x,
                floor_y=tbl.floor_y,
                shape=tbl.shape,
            )
            db.add(row)
            saved_tables.append(row)

    cam.exclusion_polygons_json = [
        [{"x": p.x, "y": p.y} for p in poly] for poly in body.exclusion_polygons_json
    ]
    await db.flush()
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="SAVE_POLYGONS",
        target_type="camera",
        target_id=camera_id,
        after_json={
            "table_count": len(saved_tables),
            "exclusion_count": len(cam.exclusion_polygons_json),
        },
        request=request,
    )
    await db.commit()

    await publish_cv_control(
        {
            "event": "polygons_updated",
            "venue_id": str(venue_id),
            "camera_id": str(camera_id),
            "table_count": len(saved_tables),
        }
    )

    return success_response(
        {
            "camera_id": str(camera_id),
            "exclusion_polygons_json": cam.exclusion_polygons_json,
            "tables": [
                {
                    "id": str(t.id),
                    "table_code": t.table_code,
                    "section_name": t.section_name,
                    "seat_capacity": t.seat_capacity,
                    "polygon_json": t.polygon_json,
                    "floor_x": t.floor_x,
                    "floor_y": t.floor_y,
                    "shape": t.shape,
                    "version": t.version,
                }
                for t in saved_tables
            ],
        }
    )


@router.post("/api/v1/venues/{venue_id}/cameras/{camera_id}/stream-token")
async def issue_stream_token(
    venue_id: uuid.UUID,
    camera_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="cameras.live.view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Issue short-lived signed MediaMTX WHEP playback token."""
    cam = (
        await db.execute(
            select(Camera).where(
                Camera.id == camera_id,
                Camera.venue_id == venue_id,
                Camera.organization_id == actor.organization_id,
                Camera.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if cam is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Camera not found")

    token = create_stream_token(
        user_id=actor.id,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        camera_id=camera_id,
    )
    return success_response(
        {
            "token": token,
            "expires_in": 120,
            "whep_url": f"{get_settings().mediamtx_webrtc_public_url.rstrip('/')}/cam-{camera_id}/whep?token={token}",
            "mjpeg_url": f"/api/v1/venues/{venue_id}/cameras/{camera_id}/live-mjpeg?token={token}",
        }
    )


def _open_capture_sync(stream_type: str, raw_url: str, demo_path: str) -> cv2.VideoCapture | None:
    if stream_type == "DEMO_MP4":
        if Path(demo_path).exists():
            return cv2.VideoCapture(demo_path)
        return None
    cap = cv2.VideoCapture(raw_url)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


async def _mjpeg_frame_generator(
    request: Request,
    stream_type: str,
    raw_url: str,
    exclusion_zones: list[Any] | None,
    fps: int,
    demo_path: str,
) -> AsyncIterator[bytes]:
    interval = 1.0 / max(1, min(60, fps))
    cap: cv2.VideoCapture | None = None
    try:
        cap = await asyncio.to_thread(_open_capture_sync, stream_type, raw_url, demo_path)
        frame_idx = 0
        while not await request.is_disconnected():
            t0 = time.monotonic()
            frame: Any = None
            if cap is not None and cap.isOpened():
                ok, frame = await asyncio.to_thread(cap.read)
                if not ok or frame is None:
                    if stream_type == "DEMO_MP4":
                        await asyncio.to_thread(cap.set, cv2.CAP_PROP_POS_FRAMES, 0)
                        ok, frame = await asyncio.to_thread(cap.read)
                    if not ok or frame is None:
                        break
            elif stream_type == "DEMO_MP4":
                frame = generate_demo_floor_frame(1280, 720)
            else:
                break

            frame_idx += 1
            try:
                blurred = await asyncio.to_thread(
                    _apply_exclusions_and_blur, frame, exclusion_zones
                )
            except FaceBlurError:
                # Privacy rule: drop unblurred frames
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                + f"Content-Length: {len(blurred)}\r\n\r\n".encode("ascii")
                + blurred
                + b"\r\n"
            )
            elapsed = time.monotonic() - t0
            await asyncio.sleep(max(0.005, interval - elapsed))
    finally:
        if cap is not None:
            await asyncio.to_thread(cap.release)


@router.get("/api/v1/venues/{venue_id}/cameras/{camera_id}/live-mjpeg")
async def stream_live_mjpeg(
    venue_id: uuid.UUID,
    camera_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    token: str = Query(...),
    fps: int = Query(default=24, ge=1, le=60),
) -> StreamingResponse:
    """High-FPS (up to 60 FPS) face-blurred MJPEG live stream authorized via short-lived stream token."""
    claims = verify_stream_token(token)
    if str(claims.get("camera_id")) != str(camera_id) or str(claims.get("venue_id")) != str(
        venue_id
    ):
        raise AppError(403, "AUTH_FORBIDDEN", "Stream token does not match requested camera")

    cam = (
        await db.execute(
            select(Camera).where(
                Camera.id == camera_id,
                Camera.venue_id == venue_id,
                Camera.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if cam is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Camera not found")

    raw_url = decrypt_field(cam.stream_url_encrypted)
    stream_type = cam.stream_type
    exclusion_zones = cam.exclusion_polygons_json
    await db.close()
    if stream_type != "DEMO_MP4":
        validate_camera_stream_url(raw_url, stream_type)

    return StreamingResponse(
        _mjpeg_frame_generator(
            request=request,
            stream_type=stream_type,
            raw_url=raw_url,
            exclusion_zones=exclusion_zones,
            fps=fps,
            demo_path=get_settings().demo_video_path,
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/api/v1/internal/media-auth")
async def mediamtx_auth_hook(body: MediaAuthHookRequest) -> JSONResponse:
    """MediaMTX external HTTP authentication hook rejecting unauthorized stream pulls."""
    raw_token = body.token.strip()
    if not raw_token and body.query:
        qs = parse_qs(body.query.lstrip("?"))
        raw_token = (qs.get("token") or [""])[0]
    if not raw_token:
        raise AppError(403, "AUTH_FORBIDDEN", "Missing stream authorization token")

    claims = verify_stream_token(raw_token)
    token_action = str(claims.get("action", "read"))
    if body.action and body.action != token_action:
        raise AppError(403, "AUTH_FORBIDDEN", "Stream token not valid for requested action")
    expected_path = f"cam-{claims['camera_id']}"
    clean_path = body.path.strip("/")
    if not clean_path or (
        clean_path != expected_path and not clean_path.startswith(f"{expected_path}/")
    ):
        raise AppError(403, "AUTH_FORBIDDEN", "Stream token does not match requested camera path")

    return success_response({"authorized": True, "camera_id": claims["camera_id"]})


@router.get("/api/v1/internal/cv-cameras")
async def list_internal_cv_cameras(
    db: Annotated[AsyncSession, Depends(get_db)],
    x_internal_secret: Annotated[str | None, Header(alias="X-Internal-Secret")] = None,
) -> JSONResponse:
    """Internal CV-worker sync endpoint returning active cameras, ROIs, and org thresholds."""
    expected = get_settings().mediamtx_hook_secret
    if not x_internal_secret or not hmac.compare_digest(x_internal_secret, expected):
        raise AppError(403, "AUTH_FORBIDDEN", "Invalid internal worker secret")

    cams = (
        (
            await db.execute(
                select(Camera).where(Camera.deleted_at.is_(None), Camera.status != "DISABLED")
            )
        )
        .scalars()
        .all()
    )
    sys_rows = (await db.execute(select(SystemSetting))).scalars().all()
    org_ai = {s.organization_id: bool(s.ai_inference_enabled) for s in sys_rows}
    for org_id, enabled in org_ai.items():
        await set_kill_switch_cache(str(org_id), enabled)

    rules_rows = (
        (await db.execute(select(AlertRule).where(AlertRule.deleted_at.is_(None)))).scalars().all()
    )
    venue_rules: dict[uuid.UUID, AlertRule] = {}
    for r in rules_rows:
        if r.section_name is None or r.venue_id not in venue_rules:
            venue_rules[r.venue_id] = r

    tables_rows = (
        (
            await db.execute(
                select(DiningTable).where(
                    DiningTable.deleted_at.is_(None),
                    DiningTable.is_active.is_(True),
                    DiningTable.camera_id.is_not(None),
                    DiningTable.polygon_json.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    tables_by_cam: dict[uuid.UUID, list[DiningTable]] = {}
    for t in tables_rows:
        if t.camera_id is not None and t.polygon_json and len(t.polygon_json) >= 3:
            tables_by_cam.setdefault(t.camera_id, []).append(t)

    payload_cams: list[dict[str, Any]] = []
    for cam in cams:
        rule = venue_rules.get(cam.venue_id)
        cam_tables = tables_by_cam.get(cam.id, [])
        if not cam_tables:
            continue
        payload_cams.append(
            {
                "camera_id": str(cam.id),
                "venue_id": str(cam.venue_id),
                "organization_id": str(cam.organization_id),
                "stream_url": decrypt_field(cam.stream_url_encrypted),
                "stream_type": cam.stream_type,
                "target_fps": cam.target_fps,
                "face_blur_enabled": cam.face_blur_enabled,
                "ai_inference_enabled": org_ai.get(cam.organization_id, False),
                "exclusion_polygons_json": cam.exclusion_polygons_json or [],
                "tables": [
                    {
                        "table_id": str(t.id),
                        "table_code": t.table_code,
                        "venue_id": str(t.venue_id),
                        "organization_id": str(t.organization_id),
                        "polygon_json": t.polygon_json or [],
                        "rules": {
                            "occupancy_debounce_sec": rule.occupancy_debounce_sec if rule else 10,
                            "departure_debounce_sec": rule.departure_debounce_sec if rule else 20,
                            "unattended_service_sec": rule.unattended_service_sec if rule else 300,
                            "cleaning_alert_delay_sec": rule.cleaning_alert_delay_sec
                            if rule
                            else 120,
                            "min_confidence": rule.min_confidence if rule else 0.65,
                            "require_bussing_confirmation": (
                                rule.require_bussing_confirmation if rule else False
                            ),
                        },
                    }
                    for t in cam_tables
                ],
            }
        )
    return success_response({"cameras": payload_cams})
