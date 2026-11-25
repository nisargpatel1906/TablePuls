"""Venues, Cameras, Polygons, and MediaMTX auth endpoints (API-007..API-010, media-auth)."""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import parse_qs

import cv2
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
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
from app.core.ssrf import mask_stream_url, validate_rtsp_url
from app.core.valkey_client import publish_cv_control
from app.db.base import get_db, uuid7
from app.db.models import AlertRule, Camera, DiningTable, Venue
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
        "guests_per_server_ratio": v.guests_per_server_ratio,
        "created_at": v.created_at.isoformat(),
    }


def _camera_dict(c: Camera, table_count: int = 0) -> dict[str, Any]:
    raw_url = decrypt_field(c.stream_url_encrypted)
    masked = mask_stream_url(raw_url) if c.stream_type in {"RTSP", "RTSPS"} else raw_url
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
    actor: Annotated[Any, Depends(require_venue_role(capability="cameras.manage"))],
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
    """API-008 (create): Add RTSP/RTSPS or DEMO_MP4 camera with AES-256-GCM encryption."""
    settings = get_settings()
    if body.stream_type in {"RTSP", "RTSPS"}:
        stream_url = validate_rtsp_url(body.stream_url)
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
    if body.name is not None:
        cam.name = body.name.strip()
    if body.stream_type is not None:
        cam.stream_type = body.stream_type
    if body.stream_url is not None:
        url = (
            validate_rtsp_url(body.stream_url)
            if cam.stream_type in {"RTSP", "RTSPS"}
            else body.stream_url.strip()
        )
        cam.stream_url_encrypted = encrypt_field(url)
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

    raw_url = decrypt_field(cam.stream_url_encrypted)
    frame: Any = None
    if cam.stream_type == "DEMO_MP4":
        demo_path = Path(raw_url if Path(raw_url).exists() else get_settings().demo_video_path)
        if demo_path.exists():
            cap = cv2.VideoCapture(str(demo_path))
            ok, read_frame = cap.read()
            cap.release()
            if ok:
                frame = read_frame
        if frame is None:
            frame = generate_demo_floor_frame(1280, 720)
    else:
        validate_rtsp_url(raw_url)
        cap = cv2.VideoCapture(raw_url)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
        ok = False
        if cap.isOpened():
            ok, frame = cap.read()
        cap.release()
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
        blurred_jpeg = blur_faces_in_bgr(frame)
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
        }
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
    expected_path = f"cam-{claims['camera_id']}"
    if body.path and expected_path not in body.path:
        raise AppError(403, "AUTH_FORBIDDEN", "Stream token does not match requested camera path")

    return success_response({"authorized": True, "camera_id": claims["camera_id"]})
