"""Phase 2 Public Menu API tests (API-035, isolation, schema allowlist, caching, ETag, privacy)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.valkey_client import (
    _local_public_menu_cache,
    _local_public_qr_cache,
    _local_rate_limits,
)
from app.db.base import get_session_factory
from app.main import create_app


@pytest.mark.asyncio
async def test_public_menu_allowlist_etag_86_grace_and_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TABLE_ADVANCED_ENABLED", "true")
    monkeypatch.setenv("QR_ENABLED", "true")
    monkeypatch.setenv("PUBLIC_MENU_ENABLED", "true")
    monkeypatch.setenv("MENU_IMAGES_ENABLED", "true")

    from app.config import get_settings

    get_settings.cache_clear()
    _local_public_menu_cache.clear()
    _local_public_qr_cache.clear()
    _local_rate_limits.clear()
    try:
        from app.core.valkey_client import get_valkey

        keys = await get_valkey().keys("tp:rl:pub_menu:*")
        if keys:
            await get_valkey().delete(*keys)
    except Exception:
        pass

    app = create_app()
    from httpx import ASGITransport

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post("/api/v1/auth/demo-login", json={"role": "OWNER"})
        assert login.status_code == 200
        owner_token = login.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {owner_token}"}

        # 1. Create venue
        v_resp = await client.post(
            "/api/v1/venues",
            headers=headers,
            json={"name": f"PubBistro {uuid.uuid4().hex[:6]}", "timezone": "Asia/Kolkata"},
        )
        assert v_resp.status_code == 201
        venue_id = v_resp.json()["data"]["id"]

        # 2. Create table -> gets auto-QR
        t_resp = await client.post(
            f"/api/v1/venues/{venue_id}/tables",
            headers=headers,
            json={"table_code": "M10", "section_name": "Main", "seat_capacity": 4},
        )
        assert t_resp.status_code == 201
        tbl = t_resp.json()["data"]
        table_id = tbl["id"]
        qr_token = tbl["qr_token"]
        assert qr_token

        # 3. Create menu (DRAFT), category, and 1 item, then PUBLISH
        m_resp = await client.post(
            f"/api/v1/venues/{venue_id}/menus",
            headers=headers,
            json={"name": "Dinner", "status": "DRAFT", "is_default": True},
        )
        assert m_resp.status_code == 201
        menu_id = m_resp.json()["data"]["id"]

        c_resp = await client.post(
            f"/api/v1/venues/{venue_id}/menus/{menu_id}/categories",
            headers=headers,
            json={"name": "Mains"},
        )
        assert c_resp.status_code == 201
        cat_id = c_resp.json()["data"]["id"]

        i1 = await client.post(
            f"/api/v1/venues/{venue_id}/menu-items",
            headers=headers,
            json={
                "category_id": cat_id,
                "name": "Paneer Butter Masala",
                "price_minor_units": 39500,
                "dietary_tags": ["VEG"],
                "allergens": ["DAIRY"],
                "is_available": True,
            },
        )
        assert i1.status_code == 201
        item1_id = i1.json()["data"]["id"]

        pub_menu = await client.patch(
            f"/api/v1/venues/{venue_id}/menus/{menu_id}",
            headers=headers,
            json={"status": "PUBLISHED"},
        )
        assert pub_menu.status_code == 200

        # 4. Completely unauthenticated client (no Authorization, no cookies) fetches /api/v1/public/menu/{qr_token}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as pub:
            res = await pub.get(f"/api/v1/public/menu/{qr_token}")
            assert res.status_code == 200
            assert "set-cookie" not in {k.lower() for k in res.headers}
            assert res.headers.get("x-robots-tag") == "noindex, nofollow"
            etag = res.headers.get("etag")
            assert etag

            body = res.json()
            assert body["success"] is True
            data = body["data"]
            assert set(data.keys()) == {
                "venue",
                "table",
                "menu_public_enabled",
                "show_unavailable_items",
                "preview_mode",
                "menu_revision",
                "menus",
            }
            assert set(data["venue"].keys()) == {
                "name",
                "tagline",
                "logo_url",
                "currency_code",
                "timezone",
            }
            assert data["table"] == {"label": "Table M10"}
            # Ensure zero internal IDs/PII leak anywhere in JSON string
            raw_text = res.text
            assert venue_id not in raw_text
            assert "organization_id" not in raw_text
            assert "rtsp" not in raw_text.lower()
            assert len(data["menus"]) == 1
            assert data["menus"][0]["categories"][0]["items"][0]["name"] == "Paneer Butter Masala"

            # ETag 304 check
            not_mod = await pub.get(
                f"/api/v1/public/menu/{qr_token}",
                headers={"If-None-Match": etag},
            )
            assert not_mod.status_code == 304

            # Invalid token => 404
            missing = await pub.get("/api/v1/public/menu/invalid-nonexistent-token-123456")
            assert missing.status_code == 404
            assert missing.json()["error"]["code"] == "QR_CODE_NOT_FOUND"

        # 5. Quick-86 reflects promptly (cache evicted + ETag changes)
        t86 = await client.patch(
            f"/api/v1/venues/{venue_id}/menu-items/{item1_id}/availability",
            headers=headers,
            json={"is_available": False},
        )
        assert t86.status_code == 200
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as pub:
            res2 = await pub.get(f"/api/v1/public/menu/{qr_token}")
            assert res2.status_code == 200
            assert res2.headers.get("etag") != etag
            assert res2.json()["data"]["menus"][0]["categories"][0]["items"][0]["is_available"] is False

            # Hide sold-out setting omits item completely
            upd_cfg = await client.patch(
                f"/api/v1/venues/{venue_id}/menu-settings",
                headers=headers,
                json={"show_unavailable_items_public": False},
            )
            assert upd_cfg.status_code == 200
            res3 = await pub.get(f"/api/v1/public/menu/{qr_token}")
            assert res3.status_code == 200
            assert res3.json()["data"]["menus"][0]["categories"] == []

        # 6. Pause public menu + Preview link bypasses pause
        pause = await client.patch(
            f"/api/v1/venues/{venue_id}/menu-settings",
            headers=headers,
            json={"menu_public_enabled": False},
        )
        assert pause.status_code == 200
        pv = await client.post(
            f"/api/v1/venues/{venue_id}/tables/{table_id}/qr/preview-link",
            headers=headers,
        )
        assert pv.status_code == 200
        p_token = pv.json()["data"]["preview_url"].split("p=")[-1]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as pub:
            paused_res = await pub.get(f"/api/v1/public/menu/{qr_token}")
            assert paused_res.status_code == 200
            assert paused_res.json()["data"]["menu_public_enabled"] is False
            assert paused_res.json()["data"]["menus"] == []

            prev_res = await pub.get(f"/api/v1/public/menu/{qr_token}?p={p_token}")
            assert prev_res.status_code == 200
            assert prev_res.json()["data"]["preview_mode"] is True

        # 7. Degraded DB stale-while-error fallback (mock catalog query failure -> X-Stale: 1)
        await client.patch(
            f"/api/v1/venues/{venue_id}/menu-settings",
            headers=headers,
            json={"menu_public_enabled": True, "show_unavailable_items_public": True},
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as pub:
            # Warm cache with latest payload
            warm = await pub.get(f"/api/v1/public/menu/{qr_token}")
            assert warm.status_code == 200

            # Force cache miss on rev while breaking public_db.execute on catalog query -> X-Stale: 1
            from app.api import public_menu as pub_mod

            orig_get_cached = pub_mod.get_public_menu_cached

            async def force_miss_on_live(key: str):
                if ":latest:" in key:
                    return await orig_get_cached(key)
                return None

            monkeypatch.setattr(pub_mod, "get_public_menu_cached", force_miss_on_live)
            async with get_session_factory()() as db:
                await db.execute(text("SET LOCAL lock_timeout = '2s'"))

            async def broken_db():
                class BrokenSession:
                    async def execute(self, *_args, **_kwargs):
                        raise RuntimeError("simulated DB outage")

                yield BrokenSession()

            app.dependency_overrides[pub_mod.get_public_db] = broken_db
            stale_res = await pub.get(f"/api/v1/public/menu/{qr_token}")
            app.dependency_overrides.clear()
            assert stale_res.status_code == 200
            assert stale_res.headers.get("x-stale") == "1"

        # 8. QR Compromise rotation -> old QR returns 410 QR_CODE_REVOKED
        regen = await client.post(
            f"/api/v1/venues/{venue_id}/tables/{table_id}/qr/regenerate",
            headers=headers,
            json={"reason": "COMPROMISED"},
        )
        assert regen.status_code == 201
        new_token = regen.json()["data"]["token"]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as pub:
            old_res = await pub.get(f"/api/v1/public/menu/{qr_token}")
            assert old_res.status_code == 410
            assert old_res.json()["error"]["code"] == "QR_CODE_REVOKED"

            new_res = await pub.get(f"/api/v1/public/menu/{new_token}")
            assert new_res.status_code == 200

            # 9. Verify rate limit returns 429 + Retry-After cleanly
            for _ in range(60):
                await pub.get(f"/api/v1/public/menu/{new_token}")
            limited = await pub.get(f"/api/v1/public/menu/{new_token}")
            assert limited.status_code == 429
            assert "retry-after" in {k.lower() for k in limited.headers}
