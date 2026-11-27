"""Tests for Mailpit/SMTP invite delivery and `tablepulse admin create-org` CLI."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from typer.testing import CliRunner

from app.cli import app as cli_app
from app.core import valkey_client
from app.db.base import reset_engine_cache
from app.db.models import AuditLog, Organization, SystemSetting, User, Venue
from app.main import create_app
from tests.conftest import get_test_db_url


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


@pytest.mark.asyncio
async def test_invite_user_calls_smtp_when_configured(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await client.post(
        "/api/v1/auth/bootstrap",
        json={
            "organization_name": "Org Mail Test",
            "full_name": "Owner One",
            "email": "owner-mail@example.com",
            "password": "StrongPassword!123",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner-mail@example.com", "password": "StrongPassword!123"},
    )
    token = login.json()["data"]["access_token"]

    sent: list[tuple[str, str, str]] = []

    async def _fake_send(to_email: str, subject: str, body: str) -> bool:
        sent.append((to_email, subject, body))
        return True

    monkeypatch.setattr("app.api.org_users.send_email_if_configured", _fake_send)
    resp = await client.post(
        "/api/v1/org/users/invite",
        json={"email": "host-mail@example.com", "role": "HOST", "venue_ids": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["email_sent"] is True
    assert data["invite_url"] is None
    assert len(sent) == 1
    assert sent[0][0] == "host-mail@example.com"
    assert "/register?token=" in sent[0][2]

    # When SMTP is not configured / fails, invite_url is returned for copy-paste fallback
    async def _no_send(to_email: str, subject: str, body: str) -> bool:
        return False

    monkeypatch.setattr("app.api.org_users.send_email_if_configured", _no_send)
    resp2 = await client.post(
        "/api/v1/org/users/invite",
        json={"email": "staff-mail@example.com", "role": "STAFF", "venue_ids": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 201
    data2 = resp2.json()["data"]
    assert data2["email_sent"] is False
    assert "/register?token=" in (data2["invite_url"] or "")


@pytest.mark.asyncio
async def test_cli_create_org_provisions_org_owner_venue_and_audit(
    clean_db: None,
    db_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _invoke(args: list[str]):
        engine = create_async_engine(get_test_db_url(), pool_pre_ping=True)
        local_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        class _DisposableFactory:
            def __call__(self):
                class _Ctx:
                    async def __aenter__(self):
                        self._sess = local_factory()
                        return await self._sess.__aenter__()

                    async def __aexit__(self, exc_type, exc, tb):
                        try:
                            return await self._sess.__aexit__(exc_type, exc, tb)
                        finally:
                            await engine.dispose()

                return _Ctx()

        monkeypatch.setattr("app.cli.get_session_factory", lambda: _DisposableFactory())
        return CliRunner().invoke(cli_app, args)

    res = await asyncio.to_thread(
        _invoke,
        [
            "admin",
            "create-org",
            "--org-name",
            "Second Bistro Group",
            "--owner-email",
            "owner-cli@example.com",
            "--owner-name",
            "Jordan Lee",
            "--owner-password",
            "CliStrongPass!987",
            "--venue-name",
            "Indiranagar Corner",
            "--timezone",
            "Asia/Kolkata",
            "--currency-code",
            "INR",
        ],
    )
    assert res.exit_code == 0, res.output
    assert "CliStrongPass!987" not in res.output
    payload = json.loads(res.stdout.strip().splitlines()[-1])
    assert payload["organization_id"]
    assert payload["owner_id"]
    assert payload["venue_id"]

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        org = (
            await db.execute(select(Organization).where(Organization.name == "Second Bistro Group"))
        ).scalar_one()
        owner = (
            await db.execute(select(User).where(User.email == "owner-cli@example.com"))
        ).scalar_one()
        assert owner.role == "OWNER"
        assert owner.organization_id == org.id
        setting = (
            await db.execute(select(SystemSetting).where(SystemSetting.organization_id == org.id))
        ).scalar_one()
        assert setting.face_blur_enforced is True
        venue = (
            await db.execute(select(Venue).where(Venue.organization_id == org.id))
        ).scalar_one()
        assert venue.name == "Indiranagar Corner"
        audit = (
            await db.execute(select(AuditLog).where(AuditLog.action == "CLI_CREATE_ORG"))
        ).scalar_one()
        assert audit.organization_id == org.id

    dup = await asyncio.to_thread(
        _invoke,
        [
            "admin",
            "create-org",
            "--org-name",
            "Third Org",
            "--owner-email",
            "owner-cli@example.com",
            "--owner-name",
            "Dup",
            "--owner-password",
            "CliStrongPass!987",
        ],
    )
    assert dup.exit_code != 0

    weak = await asyncio.to_thread(
        _invoke,
        [
            "admin",
            "create-org",
            "--org-name",
            "Third Org",
            "--owner-email",
            "new@example.com",
            "--owner-name",
            "Weak",
            "--owner-password",
            "short",
        ],
    )
    assert weak.exit_code != 0
