"""Tests for full TOTP 2FA lifecycle, recovery codes, forced role 2FA, and org delegation policies."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pyotp
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import get_settings
from app.core import valkey_client
from app.db.base import reset_engine_cache
from app.db.models import AuditLog, RefreshToken, User
from app.main import create_app


@pytest.fixture
async def client(clean_db: None, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    for key in (
        "TABLE_ADVANCED_ENABLED",
        "QR_ENABLED",
        "PUBLIC_MENU_ENABLED",
        "MENU_IMAGES_ENABLED",
    ):
        monkeypatch.setenv(key, "true")
    get_settings.cache_clear()
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


async def _bootstrap_owner(client: AsyncClient) -> tuple[str, str]:
    r = await client.post(
        "/api/v1/auth/bootstrap",
        json={
            "organization_name": "Sec Bistro",
            "full_name": "Ada Owner",
            "email": "ada@example.com",
            "password": "StrongPassword!123",
        },
    )
    assert r.status_code == 201
    data = r.json()["data"]
    return data["access_token"], data["user"]["id"]


@pytest.mark.asyncio
async def test_totp_enrollment_login_recovery_regen_and_disable(
    client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    token, owner_id = await _bootstrap_owner(client)
    hdrs = {"Authorization": f"Bearer {token}"}

    # Unauthenticated cannot enroll or disable
    assert (await client.post("/api/v1/auth/2fa/enroll")).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/2fa/disable",
            json={"password": "StrongPassword!123", "code": "000000"},
        )
    ).status_code == 401

    # Enroll step 1 -> QR SVG + Base32 secret
    enr = await client.post("/api/v1/auth/2fa/enroll", headers=hdrs)
    assert enr.status_code == 200
    enr_data = enr.json()["data"]
    assert enr_data["qr_svg_data_uri"].startswith("data:image/svg+xml;base64,")
    assert "<svg" in enr_data["qr_svg"]
    assert "otpauth://totp/" in enr_data["provisioning_uri"]
    secret = enr_data["secret"]
    enroll_tok = enr_data["enroll_token"]

    # Wrong code fails cleanly with 400
    bad = await client.post(
        "/api/v1/auth/2fa/verify-enroll",
        json={"enroll_token": enroll_tok, "code": "000000"},
        headers=hdrs,
    )
    # Only assert error when 000000 isn't accidentally matching current TOTP
    if pyotp.TOTP(secret).now() != "000000":
        assert bad.status_code == 400

    # Valid code activates 2FA + returns 8 one-time recovery codes
    good_code = pyotp.TOTP(secret).now()
    ver = await client.post(
        "/api/v1/auth/2fa/verify-enroll",
        json={"enroll_token": enroll_tok, "code": good_code},
        headers=hdrs,
    )
    assert ver.status_code == 200
    ver_data = ver.json()["data"]
    assert ver_data["totp_enabled"] is True
    recovery_codes = ver_data["recovery_codes"]
    assert len(recovery_codes) == 8

    # Login without inline code returns two-step 2FA challenge (zero session yet)
    login1 = await client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "StrongPassword!123"},
    )
    assert login1.status_code == 200
    l1_data = login1.json()["data"]
    assert l1_data["requires_2fa"] is True
    assert "access_token" not in l1_data
    ch_tok = l1_data["challenge_token"]

    # Verify step 2 with TOTP succeeds + issues access token
    totp_now = pyotp.TOTP(secret).now()
    v_login = await client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_token": ch_tok, "code": totp_now},
    )
    assert v_login.status_code == 200
    assert v_login.json()["data"]["access_token"]
    assert v_login.json()["data"]["user"]["totp_enabled"] is True

    # Challenge token is single-use
    replay = await client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_token": ch_tok, "code": totp_now},
    )
    assert replay.status_code == 401

    # Verify recovery code login & single-use consumption
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "StrongPassword!123"},
    )
    ch_tok2 = login2.json()["data"]["challenge_token"]
    rc_used = recovery_codes[0]
    v_rec = await client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_token": ch_tok2, "code": rc_used},
    )
    assert v_rec.status_code == 200
    assert v_rec.json()["data"]["user"]["recovery_codes_remaining"] == 7

    # Same recovery code cannot be reused
    login3 = await client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "StrongPassword!123"},
    )
    ch_tok3 = login3.json()["data"]["challenge_token"]
    v_rec_reuse = await client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_token": ch_tok3, "code": rc_used},
    )
    assert v_rec_reuse.status_code == 401

    # Regenerate recovery codes requires valid password + TOTP
    bad_regen = await client.post(
        "/api/v1/auth/2fa/recovery-codes",
        json={"password": "WrongPassword!", "code": pyotp.TOTP(secret).now()},
        headers=hdrs,
    )
    assert bad_regen.status_code == 401

    regen = await client.post(
        "/api/v1/auth/2fa/recovery-codes",
        json={"password": "StrongPassword!123", "code": pyotp.TOTP(secret).now()},
        headers=hdrs,
    )
    assert regen.status_code == 200
    new_codes = regen.json()["data"]["recovery_codes"]
    assert len(new_codes) == 8
    assert new_codes[0] != recovery_codes[0]

    # Set org policy require_2fa_roles = ["OWNER"] -> disable is blocked (403 POLICY_REQUIRED)
    pol_resp = await client.patch(
        "/api/v1/org/system",
        json={"require_2fa_roles": ["OWNER", "MANAGER"]},
        headers=hdrs,
    )
    assert pol_resp.status_code == 200
    blocked_dis = await client.post(
        "/api/v1/auth/2fa/disable",
        json={"password": "StrongPassword!123", "code": pyotp.TOTP(secret).now()},
        headers=hdrs,
    )
    assert blocked_dis.status_code == 403
    assert blocked_dis.json()["error"]["code"] == "POLICY_REQUIRED"

    # Remove OWNER from policy -> disable succeeds + cleans secret/recovery codes
    await client.patch("/api/v1/org/system", json={"require_2fa_roles": ["MANAGER"]}, headers=hdrs)
    dis = await client.post(
        "/api/v1/auth/2fa/disable",
        json={"password": "StrongPassword!123", "code": pyotp.TOTP(secret).now()},
        headers=hdrs,
    )
    assert dis.status_code == 200
    assert dis.json()["data"]["totp_enabled"] is False

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        u = (await db.execute(select(User).where(User.id == owner_id))).scalar_one()
        assert u.totp_enabled is False
        assert u.totp_secret_encrypted is None
        assert u.totp_recovery_codes_json == []
        audits = (
            await db.execute(select(AuditLog.action).where(AuditLog.actor_user_id == owner_id))
        ).scalars().all()
        assert "TWO_FACTOR_ENABLED" in audits
        assert "TWO_FACTOR_RECOVERY_USED" in audits
        assert "TWO_FACTOR_RECOVERY_REGENERATED" in audits
        assert "TWO_FACTOR_DISABLED" in audits


@pytest.mark.asyncio
async def test_enforced_role_2fa_setup_and_org_policy_delegation(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, _ = await _bootstrap_owner(client)
    hdrs = {"Authorization": f"Bearer {token}"}

    v_resp = await client.post(
        "/api/v1/venues",
        json={"name": "Policy Venue", "timezone": "UTC"},
        headers=hdrs,
    )
    assert v_resp.status_code == 201
    venue_id = v_resp.json()["data"]["id"]

    # Create MANAGER via invite
    monkeypatch.setattr("app.api.org_users.send_email_if_configured", lambda *a, **k: _false())
    inv = await client.post(
        "/api/v1/org/users/invite",
        json={"email": "mgr-pol@example.com", "role": "MANAGER", "venue_ids": [venue_id]},
        headers=hdrs,
    )
    assert inv.status_code == 201
    inv_tok = inv.json()["data"]["invite_url"].split("token=")[1]
    acc = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": inv_tok, "full_name": "Pol Manager", "password": "ManagerPass!987"},
    )
    assert acc.status_code == 201
    mgr_tok = acc.json()["data"]["access_token"]
    mgr_hdrs = {"Authorization": f"Bearer {mgr_tok}"}

    # Require 2FA for MANAGER + restrict managers_can_manage_tables & managers_can_manage_menu
    upd = await client.patch(
        "/api/v1/org/system",
        json={
            "require_2fa_roles": ["MANAGER"],
            "managers_can_manage_tables": False,
            "managers_can_manage_menu": False,
            "admins_can_manage_tables": False,
            "admins_can_manage_menu": False,
        },
        headers=hdrs,
    )
    assert upd.status_code == 200

    # MANAGER blocked from table & menu management by org policy (403 POLICY_DISABLED)
    tbl_block = await client.post(
        f"/api/v1/venues/{venue_id}/tables",
        json={"table_code": "T9", "seat_capacity": 4},
        headers=mgr_hdrs,
    )
    assert tbl_block.status_code == 403
    assert tbl_block.json()["error"]["code"] == "POLICY_DISABLED"

    menu_block = await client.post(
        f"/api/v1/venues/{venue_id}/menus",
        json={"name": "Blocked Menu"},
        headers=mgr_hdrs,
    )
    assert menu_block.status_code == 403
    assert menu_block.json()["error"]["code"] == "POLICY_DISABLED"

    # OWNER still retains full management capability
    owner_ok = await client.post(
        f"/api/v1/venues/{venue_id}/tables",
        json={"table_code": "T1", "seat_capacity": 4},
        headers=hdrs,
    )
    assert owner_ok.status_code == 201

    # Re-enable policies -> MANAGER allowed again
    await client.patch(
        "/api/v1/org/system",
        json={"managers_can_manage_tables": True, "managers_can_manage_menu": True},
        headers=hdrs,
    )
    mgr_ok = await client.post(
        f"/api/v1/venues/{venue_id}/tables",
        json={"table_code": "T2", "seat_capacity": 4},
        headers=mgr_hdrs,
    )
    assert mgr_ok.status_code == 201

    # Forced 2FA enrollment during MANAGER login
    login_req = await client.post(
        "/api/v1/auth/login",
        json={"email": "mgr-pol@example.com", "password": "ManagerPass!987"},
    )
    assert login_req.status_code == 200
    lr_data = login_req.json()["data"]
    assert lr_data["requires_2fa_setup"] is True
    setup_tok = lr_data["challenge_token"]

    enr = await client.post("/api/v1/auth/2fa/enroll", json={"challenge_token": setup_tok})
    assert enr.status_code == 200
    secret = enr.json()["data"]["secret"]
    enroll_tok = enr.json()["data"]["enroll_token"]

    fin = await client.post(
        "/api/v1/auth/2fa/verify-enroll",
        json={
            "challenge_token": setup_tok,
            "enroll_token": enroll_tok,
            "code": pyotp.TOTP(secret).now(),
        },
    )
    assert fin.status_code == 200
    assert fin.json()["data"]["access_token"]
    assert fin.json()["data"]["user"]["totp_enabled"] is True
    assert len(fin.json()["data"]["recovery_codes"]) == 8

    # Check RefreshToken unused reference guard clean
    assert RefreshToken is not None


async def _false() -> bool:
    return False
