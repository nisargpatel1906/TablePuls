"""Stage 2 Verification: Auth, RBAC (5 roles), reuse detection, rate limiting, policy completeness, and DB audit."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import valkey_client
from app.core.logging import scrub_mapping, scrub_text
from app.db.base import reset_engine_cache
from app.db.models import Organization, Venue
from app.main import create_app


@pytest.fixture
async def client(clean_db: None) -> AsyncIterator[AsyncClient]:
    reset_engine_cache()
    valkey_client._local_rate_limits.clear()
    valkey_client._local_revocations.clear()
    # Clear Valkey rate-limit keys so repeated test runs start clean
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


async def _bootstrap(client: AsyncClient, email: str = "owner@example.com") -> tuple[str, str]:
    resp = await client.post(
        "/api/v1/auth/bootstrap",
        json={
            "organization_name": "Demo Bistro Group",
            "email": email,
            "full_name": "Alex Owner",
            "password": "CorrectHorseBattery99!",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["success"] is True
    return str(body["data"]["access_token"]), str(body["data"]["user"]["organization_id"])


@pytest.mark.asyncio
async def test_bootstrap_and_direct_db_verification(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Weak password -> 400 with unified error envelope
    bad = await client.post(
        "/api/v1/auth/bootstrap",
        json={
            "organization_name": "Demo",
            "email": "owner@example.com",
            "full_name": "Alex",
            "password": "short",
        },
    )
    assert bad.status_code == 400
    assert bad.json()["success"] is False
    assert bad.json()["error"]["code"] == "VALIDATION_ERROR"

    # Valid bootstrap -> 201
    token, org_id = await _bootstrap(client)
    assert token

    # Verify directly in PostgreSQL
    user_row = (
        await db_session.execute(
            text("SELECT role, password_hash FROM users WHERE email = 'owner@example.com'")
        )
    ).one()
    assert user_row[0] == "OWNER"
    assert user_row[1].startswith("$argon2id$")

    rt_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM refresh_tokens WHERE token_type = 'REFRESH'")
        )
    ).scalar_one()
    assert rt_count == 1

    audit_row = (
        await db_session.execute(
            text(
                "SELECT action, organization_id::text FROM audit_logs WHERE action = 'BOOTSTRAP_OWNER'"
            )
        )
    ).one()
    assert audit_row[1] == org_id

    # Second bootstrap must fail with 403
    second = await client.post(
        "/api/v1/auth/bootstrap",
        json={
            "organization_name": "Second Org",
            "email": "attacker@example.com",
            "full_name": "Bad Actor",
            "password": "CorrectHorseBattery99!",
        },
    )
    assert second.status_code == 403
    assert second.json()["error"]["code"] == "AUTH_FORBIDDEN"


@pytest.mark.asyncio
async def test_login_refresh_reuse_detection_and_logout(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _bootstrap(client)

    # Bad password -> generic 401
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "WrongPassword123!"},
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"

    # Valid login
    ok_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "CorrectHorseBattery99!"},
    )
    assert ok_login.status_code == 200
    old_cookie = ok_login.cookies.get("tp_refresh_token")
    assert old_cookie

    # Refresh rotation succeeds and issues a new cookie
    rot = await client.post("/api/v1/auth/refresh", cookies={"tp_refresh_token": old_cookie})
    assert rot.status_code == 200
    new_cookie = rot.cookies.get("tp_refresh_token")
    assert new_cookie and new_cookie != old_cookie
    new_access = rot.json()["data"]["access_token"]

    # Replay of already-revoked old_cookie -> 401 + entire family revoked in DB
    replay = await client.post("/api/v1/auth/refresh", cookies={"tp_refresh_token": old_cookie})
    assert replay.status_code == 401

    # Even the rotated new_cookie from the same family must now be rejected!
    after_replay = await client.post(
        "/api/v1/auth/refresh", cookies={"tp_refresh_token": new_cookie}
    )
    assert after_replay.status_code == 401

    reuse_audit = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM audit_logs WHERE action = 'REFRESH_REUSE_DETECTED'")
        )
    ).scalar_one()
    assert reuse_audit == 2

    # Logout revokes active access token
    out = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {new_access}"},
    )
    assert out.status_code == 200
    me_after = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access}"},
    )
    assert me_after.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limiting_429(client: AsyncClient) -> None:
    await _bootstrap(client)
    statuses = []
    for _ in range(11):
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "WrongPassword123!"},
        )
        statuses.append(r.status_code)
    assert 429 in statuses


@pytest.mark.asyncio
async def test_rbac_all_five_roles_invites_and_last_owner_protection(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner_token, org_id = await _bootstrap(client)

    # Create 2 venues directly for role scoping tests
    v1 = Venue(organization_id=uuid.UUID(org_id), name="Downtown", operating_hours_json={})
    v2 = Venue(organization_id=uuid.UUID(org_id), name="Uptown", operating_hours_json={})
    org_b = Organization(name="Other Restaurant Group")
    db_session.add_all([v1, v2, org_b])
    await db_session.commit()

    role_tokens: dict[str, str] = {"OWNER": owner_token}
    for role in ("MANAGER", "HOST", "STAFF", "VIEWER"):
        inv = await client.post(
            "/api/v1/org/users/invite",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "email": f"{role.lower()}@example.com",
                "role": role,
                "venue_ids": [str(v1.id)],
            },
        )
        assert inv.status_code == 201, inv.text
        raw_tok = inv.json()["data"]["token"]

        acc = await client.post(
            "/api/v1/auth/accept-invite",
            json={
                "token": raw_tok,
                "full_name": f"Test {role}",
                "password": "SecureRolePassword99!",
            },
        )
        assert acc.status_code == 201, acc.text
        role_tokens[role] = acc.json()["data"]["access_token"]

    # Unauthenticated -> 401
    assert (await client.get("/api/v1/org/users")).status_code == 401

    # HOST, STAFF, VIEWER -> 403 on /org/users and /org/audit-logs
    for r_name in ("HOST", "STAFF", "VIEWER"):
        hdr = {"Authorization": f"Bearer {role_tokens[r_name]}"}
        assert (await client.get("/api/v1/org/users", headers=hdr)).status_code == 403
        assert (await client.get("/api/v1/org/audit-logs", headers=hdr)).status_code == 403

    # MANAGER cannot invite OWNER/MANAGER or invite to unassigned v2
    mgr_hdr = {"Authorization": f"Bearer {role_tokens['MANAGER']}"}
    assert (
        await client.post(
            "/api/v1/org/users/invite",
            headers=mgr_hdr,
            json={"email": "newmgr@example.com", "role": "MANAGER", "venue_ids": [str(v1.id)]},
        )
    ).status_code == 403
    assert (
        await client.post(
            "/api/v1/org/users/invite",
            headers=mgr_hdr,
            json={"email": "v2host@example.com", "role": "HOST", "venue_ids": [str(v2.id)]},
        )
    ).status_code == 403

    # MANAGER can invite HOST to assigned v1
    mgr_ok = await client.post(
        "/api/v1/org/users/invite",
        headers=mgr_hdr,
        json={"email": "v1host2@example.com", "role": "HOST", "venue_ids": [str(v1.id)]},
    )
    assert mgr_ok.status_code == 201

    # Last-OWNER protection -> 409 LAST_OWNER_PROTECTED
    owner_uid = (
        await db_session.execute(
            text("SELECT id::text FROM users WHERE email = 'owner@example.com'")
        )
    ).scalar_one()
    demote = await client.patch(
        f"/api/v1/org/users/{owner_uid}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"role": "MANAGER"},
    )
    assert demote.status_code == 409
    assert demote.json()["error"]["code"] == "LAST_OWNER_PROTECTED"

    # Admin reset link + single-use reset flow
    reset_link_resp = await client.post(
        f"/api/v1/org/users/{owner_uid}/reset-link",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert reset_link_resp.status_code == 200
    reset_tok = reset_link_resp.json()["data"]["reset_url"].split("token=")[1]
    done_reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_tok, "new_password": "BrandNewOwnerPassword99!"},
    )
    assert done_reset.status_code == 200
    # Reusing reset token -> 400 TOKEN_EXPIRED
    reuse_reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_tok, "new_password": "AnotherNewPassword99!"},
    )
    assert reuse_reset.status_code == 400
    assert reuse_reset.json()["error"]["code"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_ws_ticket_and_policy_completeness_and_log_scrubber(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, _ = await _bootstrap(client)
    assert (await client.post("/api/v1/auth/ws-ticket")).status_code == 401
    ok_ticket = await client.post(
        "/api/v1/auth/ws-ticket",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok_ticket.status_code == 200
    assert ok_ticket.json()["data"]["expires_in"] == 60

    # Policy-completeness check (docs/04 §7)
    app = create_app()
    public_or_authn_only = {
        "/api/v1/health",
        "/api/v1/auth/bootstrap-status",
        "/api/v1/auth/bootstrap",
        "/api/v1/auth/login",
        "/api/v1/auth/demo-login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/invite-info",
        "/api/v1/auth/accept-invite",
        "/api/v1/auth/ws-ticket",
        "/api/v1/auth/me",
        "/api/v1/internal/media-auth",
        "/api/v1/public/menu/{qr_token}",
    }
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/v1/"):
            continue
        if path in public_or_authn_only:
            continue
        dependant = getattr(route, "dependant", None)
        deps = getattr(dependant, "dependencies", []) if dependant else []
        assert any(getattr(d.call, "_tp_rbac_protected", False) for d in deps), (
            f"Unprotected API route missing RBAC dependency: {path}"
        )

    # Fail-closed Phase 2 flags (missing => False) + extended matrix check
    for env_key in (
        "TABLE_ADVANCED_ENABLED",
        "QR_ENABLED",
        "PUBLIC_MENU_ENABLED",
        "MENU_IMAGES_ENABLED",
    ):
        monkeypatch.delenv(env_key, raising=False)
    from app.config import _parse_bool_env, get_settings
    from app.core.rbac import load_rbac_matrix

    get_settings.cache_clear()

    assert _parse_bool_env("TABLE_ADVANCED_ENABLED", False) is False
    assert _parse_bool_env("QR_ENABLED", False) is False
    assert _parse_bool_env("PUBLIC_MENU_ENABLED", False) is False
    assert _parse_bool_env("MENU_IMAGES_ENABLED", False) is False
    load_rbac_matrix.cache_clear()
    caps = load_rbac_matrix()["capabilities"]
    for p2_cap in (
        "tables.read",
        "tables.manage",
        "menu.read",
        "menu.manage",
        "menu.availability",
        "menu.currency_manage",
        "qr.read",
        "qr.manage",
    ):
        assert p2_cap in caps

    # Log scrubber canary test (docs/08 §10)
    canary = scrub_mapping(
        {
            "rtsp_url": "rtsp://camuser:TopSecretPass@192.168.1.55:554/stream1",
            "note": "Authorization: Bearer super_secret_jwt_abc",
            "password": "MyPassword123!",
            "msg": scrub_text("connect rtsp://admin:Pass123@10.0.0.2/live"),
        }
    )
    serialized = str(canary)
    assert "TopSecretPass" not in serialized
    assert "super_secret_jwt_abc" not in serialized
    assert "MyPassword123!" not in serialized
    assert "Pass123" not in serialized


@pytest.mark.asyncio
async def test_demo_login_gate_and_seed(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    forbidden = await client.post("/api/v1/auth/demo-login")
    assert forbidden.status_code == 403

    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    ok = await client.post("/api/v1/auth/demo-login")
    assert ok.status_code == 200
    body = ok.json()["data"]
    assert body["user"]["role"] == "MANAGER"
    assert len(body["user"]["assigned_venue_ids"]) >= 1
    assert ok.cookies.get("tp_refresh_token")

    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_bootstrap_status_reports_has_session_only_with_cookie(
    client: AsyncClient,
) -> None:
    unauth = await client.get("/api/v1/auth/bootstrap-status")
    assert unauth.status_code == 200
    assert unauth.json()["data"]["has_session"] is False

    token, _ = await _bootstrap(client)
    assert token
    authed = await client.get("/api/v1/auth/bootstrap-status")
    assert authed.status_code == 200
    assert authed.json()["data"]["has_session"] is True
    assert authed.json()["data"]["bootstrap_required"] is False
