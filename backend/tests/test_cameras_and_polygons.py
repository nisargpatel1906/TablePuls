"""Stage 3 Verification: Venues, Cameras, AES-GCM encryption, SSRF, polygons, and MediaMTX auth."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import valkey_client
from app.core.privacy import FaceBlurError, blur_faces_in_bgr
from app.db.base import reset_engine_cache
from app.main import create_app


@pytest.fixture
async def client(clean_db: None) -> AsyncIterator[AsyncClient]:
    reset_engine_cache()
    valkey_client._local_rate_limits.clear()
    valkey_client._local_revocations.clear()
    try:
        vk = valkey_client.get_valkey()
        keys = await vk.keys("tp:rl:*")
        if keys:
            await vk.delete(*keys)
    except Exception:
        pass

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    await valkey_client.close_valkey()
    reset_engine_cache()


async def _setup_owner_and_venue(client: AsyncClient) -> tuple[str, str]:
    boot = await client.post(
        "/api/v1/auth/bootstrap",
        json={
            "organization_name": "Stage 3 Bistro",
            "email": "owner3@example.com",
            "full_name": "Owner Three",
            "password": "CorrectHorseBattery99!",
        },
    )
    assert boot.status_code == 201
    token = boot.json()["data"]["access_token"]
    venue = await client.post(
        "/api/v1/venues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Main Branch", "timezone": "Asia/Kolkata"},
    )
    assert venue.status_code == 201
    return str(token), str(venue.json()["data"]["id"])


@pytest.mark.asyncio
async def test_camera_encryption_ssrf_and_demo_preview(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    from app.config import get_settings

    get_settings.cache_clear()

    token, venue_id = await _setup_owner_and_venue(client)
    hdr = {"Authorization": f"Bearer {token}"}

    # SSRF loopback rejection -> 400
    ssrf_bad = await client.post(
        f"/api/v1/venues/{venue_id}/cameras",
        headers=hdr,
        json={
            "name": "SSRF Cam",
            "stream_type": "RTSP",
            "stream_url": "rtsp://admin:secret@127.0.0.1:554/stream1",
        },
    )
    assert ssrf_bad.status_code == 400

    # Valid RTSP camera -> credentials encrypted in PostgreSQL and masked in API
    rtsp_ok = await client.post(
        f"/api/v1/venues/{venue_id}/cameras",
        headers=hdr,
        json={
            "name": "Ceiling Cam 1",
            "stream_type": "RTSP",
            "stream_url": "rtsp://camadmin:SuperSecretCam99@192.168.1.40:554/stream1",
            "username": "camadmin",
            "password": "SuperSecretCam99",
            "target_fps": 2,
        },
    )
    assert rtsp_ok.status_code == 201, rtsp_ok.text
    cam_data = rtsp_ok.json()["data"]
    assert "SuperSecretCam99" not in str(cam_data)
    assert "***@192.168.1.40:554" in cam_data["masked_stream_url"]

    # Verify ciphertext != plaintext directly in PostgreSQL
    raw_row = (
        await db_session.execute(
            text("SELECT stream_url_encrypted, credentials_encrypted FROM cameras WHERE id = :cid"),
            {"cid": uuid.UUID(cam_data["id"])},
        )
    ).one()
    assert b"SuperSecretCam99" not in bytes(raw_row[0])
    assert b"SuperSecretCam99" not in bytes(raw_row[1])

    # Demo MP4 camera test preview returns face-blurred JPEG >= 640x480
    demo_cam = await client.post(
        f"/api/v1/venues/{venue_id}/cameras",
        headers=hdr,
        json={
            "name": "Demo Floor Cam",
            "stream_type": "DEMO_MP4",
            "stream_url": "/app/data/demo/demo_floor.mp4",
            "target_fps": 2,
        },
    )
    assert demo_cam.status_code == 201
    demo_id = demo_cam.json()["data"]["id"]

    preview = await client.post(f"/api/v1/venues/{venue_id}/cameras/{demo_id}/test", headers=hdr)
    assert preview.status_code == 200
    pdata = preview.json()["data"]
    assert pdata["width"] >= 640
    assert pdata["height"] >= 480
    assert pdata["face_blurred"] is True
    assert len(pdata["preview_jpeg_base64"]) > 100

    # Blur failure must raise FaceBlurError (drop frame, never emit unblurred)
    import numpy as np

    with pytest.raises(FaceBlurError):
        blur_faces_in_bgr(np.zeros((0, 0, 3), dtype=np.uint8))


@pytest.mark.asyncio
async def test_polygons_validation_and_mediamtx_auth(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    from app.config import get_settings

    get_settings.cache_clear()
    token, venue_id = await _setup_owner_and_venue(client)
    hdr = {"Authorization": f"Bearer {token}"}

    cam = await client.post(
        f"/api/v1/venues/{venue_id}/cameras",
        headers=hdr,
        json={"name": "Cam A", "stream_type": "DEMO_MP4", "stream_url": "demo.mp4"},
    )
    cam_id = cam.json()["data"]["id"]

    # Self-intersecting bowtie polygon -> 400
    bowtie = await client.put(
        f"/api/v1/venues/{venue_id}/cameras/{cam_id}/polygons",
        headers=hdr,
        json={
            "tables": [
                {
                    "table_code": "T01",
                    "seat_capacity": 4,
                    "polygon_json": [
                        {"x": 0.1, "y": 0.1},
                        {"x": 0.4, "y": 0.4},
                        {"x": 0.4, "y": 0.1},
                        {"x": 0.1, "y": 0.4},
                    ],
                }
            ]
        },
    )
    assert bowtie.status_code == 400

    # Valid polygon save
    good = await client.put(
        f"/api/v1/venues/{venue_id}/cameras/{cam_id}/polygons",
        headers=hdr,
        json={
            "tables": [
                {
                    "table_code": "T01",
                    "section_name": "Main Hall",
                    "seat_capacity": 4,
                    "polygon_json": [
                        {"x": 0.1, "y": 0.1},
                        {"x": 0.3, "y": 0.1},
                        {"x": 0.3, "y": 0.3},
                        {"x": 0.1, "y": 0.3},
                    ],
                    "floor_x": 0.2,
                    "floor_y": 0.2,
                    "shape": "RECT",
                }
            ],
            "exclusion_polygons_json": [
                [
                    {"x": 0.8, "y": 0.8},
                    {"x": 0.9, "y": 0.8},
                    {"x": 0.9, "y": 0.9},
                ]
            ],
        },
    )
    assert good.status_code == 200
    saved_t = good.json()["data"]["tables"][0]
    assert saved_t["version"] == 1

    # Optimistic lock conflict on stale version -> 409
    # First bump version to 2
    bump = await client.put(
        f"/api/v1/venues/{venue_id}/cameras/{cam_id}/polygons",
        headers=hdr,
        json={
            "tables": [
                {
                    "id": saved_t["id"],
                    "table_code": "T01",
                    "seat_capacity": 4,
                    "polygon_json": saved_t["polygon_json"],
                    "version": 1,
                }
            ]
        },
    )
    assert bump.status_code == 200
    assert bump.json()["data"]["tables"][0]["version"] == 2

    stale = await client.put(
        f"/api/v1/venues/{venue_id}/cameras/{cam_id}/polygons",
        headers=hdr,
        json={
            "tables": [
                {
                    "id": saved_t["id"],
                    "table_code": "T01",
                    "seat_capacity": 4,
                    "polygon_json": saved_t["polygon_json"],
                    "version": 1,
                }
            ]
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"

    # MediaMTX stream token & auth hook
    tok_resp = await client.post(
        f"/api/v1/venues/{venue_id}/cameras/{cam_id}/stream-token",
        headers=hdr,
    )
    assert tok_resp.status_code == 200
    stream_token = tok_resp.json()["data"]["token"]

    # Unauthorized MediaMTX pull -> 403
    unauth = await client.post(
        "/api/v1/internal/media-auth",
        json={"action": "read", "path": f"cam-{cam_id}", "query": "token=bad_token"},
    )
    assert unauth.status_code == 403

    # Authorized MediaMTX pull -> 200
    auth_ok = await client.post(
        "/api/v1/internal/media-auth",
        json={"action": "read", "path": f"cam-{cam_id}", "query": f"token={stream_token}"},
    )
    assert auth_ok.status_code == 200

    # HOST blocked when allow_host_camera_view=false
    inv = await client.post(
        "/api/v1/org/users/invite",
        headers=hdr,
        json={"email": "host3@example.com", "role": "HOST", "venue_ids": [venue_id]},
    )
    acc = await client.post(
        "/api/v1/auth/accept-invite",
        json={
            "token": inv.json()["data"]["token"],
            "full_name": "Host Three",
            "password": "HostPassword123!",
        },
    )
    host_tok = acc.json()["data"]["access_token"]
    host_denied = await client.post(
        f"/api/v1/venues/{venue_id}/cameras/{cam_id}/stream-token",
        headers={"Authorization": f"Bearer {host_tok}"},
    )
    assert host_denied.status_code == 403
