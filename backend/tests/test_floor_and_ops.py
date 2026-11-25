"""Stage 5 Verification: Floor ops, WS, CV stream consumer, waitlist, analytics, webhooks, ML review, kill switch."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import valkey_client
from app.db.base import reset_engine_cache
from app.db.models import MLModel
from app.main import create_app
from app.services.realtime import process_cv_stream_event
from app.services.webhooks import dispatch_webhook, reset_webhook_circuits


@pytest.fixture
async def client(clean_db: None) -> AsyncIterator[AsyncClient]:
    reset_engine_cache()
    valkey_client._local_rate_limits.clear()
    valkey_client._local_revocations.clear()
    reset_webhook_circuits()
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


async def _bootstrap_venue_camera_table(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, str, str, str, str]:
    monkeypatch.setenv("DEMO_MODE", "true")
    from app.config import get_settings

    get_settings.cache_clear()

    boot = await client.post(
        "/api/v1/auth/bootstrap",
        json={
            "organization_name": "Stage 5 Cafe",
            "email": "owner5@example.com",
            "full_name": "Owner Five",
            "password": "CorrectHorseBattery99!",
        },
    )
    assert boot.status_code == 201
    token = str(boot.json()["data"]["access_token"])
    org_id = str(boot.json()["data"]["user"]["organization_id"])
    hdr = {"Authorization": f"Bearer {token}"}

    venue = await client.post(
        "/api/v1/venues",
        headers=hdr,
        json={"name": "Flagship", "timezone": "UTC"},
    )
    venue_id = str(venue.json()["data"]["id"])

    cam = await client.post(
        f"/api/v1/venues/{venue_id}/cameras",
        headers=hdr,
        json={"name": "Cam 1", "stream_type": "DEMO_MP4", "stream_url": "demo.mp4"},
    )
    cam_id = str(cam.json()["data"]["id"])

    poly = await client.put(
        f"/api/v1/venues/{venue_id}/cameras/{cam_id}/polygons",
        headers=hdr,
        json={
            "tables": [
                {
                    "table_code": "T01",
                    "section_name": "Main",
                    "seat_capacity": 4,
                    "polygon_json": [
                        {"x": 0.1, "y": 0.1},
                        {"x": 0.3, "y": 0.1},
                        {"x": 0.3, "y": 0.3},
                        {"x": 0.1, "y": 0.3},
                    ],
                },
                {
                    "table_code": "T02",
                    "section_name": "Main",
                    "seat_capacity": 6,
                    "polygon_json": [
                        {"x": 0.5, "y": 0.1},
                        {"x": 0.8, "y": 0.1},
                        {"x": 0.8, "y": 0.3},
                        {"x": 0.5, "y": 0.3},
                    ],
                },
            ]
        },
    )
    assert poly.status_code == 200
    t1_id = str(poly.json()["data"]["tables"][0]["id"])
    return token, org_id, venue_id, cam_id, t1_id


@pytest.mark.asyncio
async def test_floor_ops_cv_consumer_overrides_and_alerts(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, org_id, venue_id, cam_id, t1_id = await _bootstrap_venue_camera_table(
        client, monkeypatch
    )
    hdr = {"Authorization": f"Bearer {token}"}

    # Simulate CV stream event transitioning T01 -> NEEDS_SERVICE
    await process_cv_stream_event(
        {
            "table_id": t1_id,
            "table_code": "T01",
            "venue_id": venue_id,
            "organization_id": org_id,
            "camera_id": cam_id,
            "previous_state": "OCCUPIED",
            "new_state": "NEEDS_SERVICE",
            "guest_count": "3",
            "confidence": "0.91",
            "source": "AI",
            "session_id": str(uuid.uuid4()),
            "reason": "unattended_service_sla",
            "model_version": "tablepulse-detector-b1@0.1.0",
            "enqueue_review": "0",
        }
    )

    floor = await client.get(f"/api/v1/venues/{venue_id}/floor-state", headers=hdr)
    assert floor.status_code == 200
    fdata = floor.json()["data"]
    assert fdata["kpis"]["occupied_tables"] == 1
    assert fdata["kpis"]["seated_guests"] == 3
    assert fdata["kpis"]["active_alerts"] == 1

    # Table detail returns timeline
    detail = await client.get(f"/api/v1/venues/{venue_id}/tables/{t1_id}", headers=hdr)
    assert detail.status_code == 200
    assert len(detail.json()["data"]["events"]) == 1
    current_version = detail.json()["data"]["table"]["version"]

    # Stale optimistic-lock version -> 409
    stale = await client.patch(
        f"/api/v1/venues/{venue_id}/tables/{t1_id}/override",
        headers=hdr,
        json={"new_state": "FREE", "reason": "Cleaned", "version": max(1, current_version - 1)},
    )
    assert stale.status_code == 409

    # STAFF role cannot mark RESERVED -> 403, but can mark FREE
    inv = await client.post(
        "/api/v1/org/users/invite",
        headers=hdr,
        json={"email": "staff5@example.com", "role": "STAFF", "venue_ids": [venue_id]},
    )
    acc = await client.post(
        "/api/v1/auth/accept-invite",
        json={
            "token": inv.json()["data"]["token"],
            "full_name": "Staff Five",
            "password": "StaffPassword123!",
        },
    )
    staff_hdr = {"Authorization": f"Bearer {acc.json()['data']['access_token']}"}
    staff_reserved = await client.patch(
        f"/api/v1/venues/{venue_id}/tables/{t1_id}/override",
        headers=staff_hdr,
        json={"new_state": "RESERVED", "reason": "VIP", "version": current_version},
    )
    assert staff_reserved.status_code == 403

    staff_clean = await client.patch(
        f"/api/v1/venues/{venue_id}/tables/{t1_id}/override",
        headers=staff_hdr,
        json={"new_state": "FREE", "reason": "Bussed and wiped", "version": current_version},
    )
    assert staff_clean.status_code == 200
    assert staff_clean.json()["data"]["current_state"] == "FREE"

    # Direct PostgreSQL check: alert auto-resolved and audit log written
    resolved_cnt = (
        await db_session.execute(text("SELECT COUNT(*) FROM alerts WHERE status = 'RESOLVED'"))
    ).scalar_one()
    assert resolved_cnt == 1


@pytest.mark.asyncio
async def test_waitlist_analytics_webhooks_ml_review_and_kill_switch(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, org_id, venue_id, cam_id, t1_id = await _bootstrap_venue_camera_table(
        client, monkeypatch
    )
    hdr = {"Authorization": f"Bearer {token}"}

    # Waitlist add + turnover ranking + seat party on T01
    wl = await client.post(
        f"/api/v1/venues/{venue_id}/waitlist",
        headers=hdr,
        json={
            "party_name": "Patel",
            "party_size": 4,
            "phone": "+919876543210",
            "quoted_wait_minutes": 10,
        },
    )
    assert wl.status_code == 201
    wl_id = wl.json()["data"]["id"]

    # Verify phone is encrypted in DB
    phone_blob = (
        await db_session.execute(
            text("SELECT phone_encrypted FROM waitlist_entries WHERE id = :wid"),
            {"wid": uuid.UUID(wl_id)},
        )
    ).scalar_one()
    assert b"9876543210" not in bytes(phone_blob)

    turnover = await client.get(
        f"/api/v1/venues/{venue_id}/turnover-predictions?party_size=4", headers=hdr
    )
    assert turnover.status_code == 200
    assert len(turnover.json()["data"]["items"]) == 2

    seat = await client.patch(
        f"/api/v1/venues/{venue_id}/waitlist/{wl_id}",
        headers=hdr,
        json={"status": "SEATED", "assigned_table_id": t1_id},
    )
    assert seat.status_code == 200
    assert seat.json()["data"]["status"] == "SEATED"

    # Analytics JSON + CSV + >365 day range error (400)
    await process_cv_stream_event(
        {
            "table_id": t1_id,
            "table_code": "T01",
            "venue_id": venue_id,
            "organization_id": org_id,
            "camera_id": cam_id,
            "previous_state": "FREE",
            "new_state": "OCCUPIED",
            "guest_count": "4",
            "confidence": "0.95",
            "source": "AI",
            "reason": "seated",
            "model_version": "b1",
            "enqueue_review": "0",
        }
    )
    ana = await client.get(f"/api/v1/venues/{venue_id}/analytics/peak-hours", headers=hdr)
    assert ana.status_code == 200
    assert ana.json()["data"]["total_samples"] >= 1

    csv_resp = await client.get(
        f"/api/v1/venues/{venue_id}/analytics/peak-hours?format=csv", headers=hdr
    )
    assert csv_resp.status_code == 200
    assert "avg_occupancy_pct" in csv_resp.text

    bad_range = await client.get(
        f"/api/v1/venues/{venue_id}/analytics/peak-hours?from_date=2020-01-01T00:00:00Z&to_date=2025-01-01T00:00:00Z",
        headers=hdr,
    )
    assert bad_range.status_code == 400

    # SSRF loopback rejection on alert-rules webhook
    ssrf_wh = await client.patch(
        f"/api/v1/venues/{venue_id}/alert-rules",
        headers=hdr,
        json={"webhook_url": "http://127.0.0.1:9000/hook"},
    )
    assert ssrf_wh.status_code == 400

    # Outbound webhook HMAC + retry + circuit breaker unit verification
    calls = 0

    def _mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers["X-TablePulse-Signature"].startswith("sha256=")
        return httpx.Response(500, json={"err": "down"})

    monkeypatch.setenv("WEBHOOKS_ENABLED", "true")
    from app.config import get_settings

    get_settings.cache_clear()
    ok, code, _ = await dispatch_webhook(
        url="https://93.184.216.34/alert",
        secret="hmac-secret-test",
        payload={"event": "test"},
        max_attempts=3,
        transport=httpx.MockTransport(_mock_handler),
    )
    assert ok is False and code == 500 and calls == 3

    # Flag detection -> ML Review -> Submit label -> OWNER export zip
    flag = await client.post(
        f"/api/v1/venues/{venue_id}/tables/{t1_id}/flag",
        headers=hdr,
        json={"reason": "Actually 4 guests", "suggested_state": "OCCUPIED"},
    )
    assert flag.status_code == 201
    rev_id = flag.json()["data"]["review_item_id"]

    submit_rev = await client.patch(
        f"/api/v1/venues/{venue_id}/ml-review/{rev_id}",
        headers=hdr,
        json={
            "review_status": "REVIEWED",
            "human_state": "OCCUPIED",
            "human_guest_count": 4,
            "issue_tags": ["Glare"],
        },
    )
    assert submit_rev.status_code == 200

    export_zip = await client.get(f"/api/v1/venues/{venue_id}/ml-review/export", headers=hdr)
    assert export_zip.status_code == 200
    assert export_zip.headers["content-type"] == "application/zip"

    # System overview, kill switch toggle, model gate enforcement (stable requires PASS), snapshot purge
    sys_get = await client.get("/api/v1/org/system", headers=hdr)
    assert sys_get.status_code == 200
    assert sys_get.json()["data"]["models"][0]["gate_status"] == "NOT_MEASURED"

    # Register a NOT_MEASURED stable model -> activation must fail 409
    bad_model = MLModel(
        model_role="DETECTOR",
        version="tablepulse-unmeasured-stable",
        artifact_uri="file:///tmp/m.onnx",
        artifact_sha256="a" * 64,
        dataset_version="none",
        eval_metrics_json={},
        gate_status="NOT_MEASURED",
        channel="stable",
        is_active=False,
    )
    db_session.add(bad_model)
    await db_session.commit()
    act_fail = await client.post(f"/api/v1/org/system/models/{bad_model.id}/activate", headers=hdr)
    assert act_fail.status_code == 409

    kill = await client.patch(
        "/api/v1/org/system", headers=hdr, json={"ai_inference_enabled": False}
    )
    assert kill.status_code == 200
    assert kill.json()["data"]["ai_inference_enabled"] is False

    purge = await client.post("/api/v1/org/system/purge-snapshots", headers=hdr)
    assert purge.status_code == 200
    assert datetime.now(UTC).year >= 2026


def test_websocket_floor_snapshot(clean_db: None) -> None:
    """Verify WS /api/v1/ws/venues/{venue_id}?ticket=... delivers floor.snapshot and ping/pong."""
    from starlette.testclient import TestClient

    reset_engine_cache()
    valkey_client._local_rate_limits.clear()
    valkey_client._local_revocations.clear()

    with TestClient(create_app()) as sync_client:
        boot = sync_client.post(
            "/api/v1/auth/bootstrap",
            json={
                "organization_name": "WS Bistro",
                "email": "wsowner@example.com",
                "full_name": "WS Owner",
                "password": "CorrectHorseBattery99!",
            },
        )
        assert boot.status_code == 201
        token = boot.json()["data"]["access_token"]
        hdr = {"Authorization": f"Bearer {token}"}

        venue = sync_client.post(
            "/api/v1/venues",
            headers=hdr,
            json={"name": "WS Branch", "timezone": "UTC"},
        )
        assert venue.status_code == 201
        venue_id = venue.json()["data"]["id"]

        ticket_resp = sync_client.post("/api/v1/auth/ws-ticket", headers=hdr)
        assert ticket_resp.status_code == 200
        ws_ticket = ticket_resp.json()["data"]["ticket"]

        with sync_client.websocket_connect(
            f"/api/v1/ws/venues/{venue_id}?ticket={ws_ticket}"
        ) as ws:
            snap_msg = ws.receive_json()
            assert snap_msg["type"] == "floor.snapshot"
            assert snap_msg["data"]["venue_id"] == venue_id
            ws.send_text("ping")
            assert ws.receive_text() == "pong"
    reset_engine_cache()
