"""Stage N3 Verification: Advanced Table Management API (API-024..API-025), direct SQL checks, and RBAC."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core import valkey_client
from app.db.base import reset_engine_cache
from app.db.models import Alert, User
from app.main import create_app


@pytest.fixture
async def client(clean_db: None, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    monkeypatch.setenv("TABLE_ADVANCED_ENABLED", "true")
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    reset_engine_cache()
    valkey_client._local_rate_limits.clear()
    valkey_client._local_revocations.clear()
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac
    await valkey_client.close_valkey()
    reset_engine_cache()


async def _setup_org(
    client: AsyncClient, email: str = "owner-n3@example.com", org_name: str = "N3 Bistro"
) -> tuple[str, str, str]:
    boot = await client.post(
        "/api/v1/auth/bootstrap",
        json={
            "organization_name": org_name,
            "email": email,
            "full_name": "N3 Owner",
            "password": "CorrectHorseBattery99!",
        },
    )
    if boot.status_code == 201:
        token = str(boot.json()["data"]["access_token"])
        org_id = str(boot.json()["data"]["user"]["organization_id"])
    else:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "CorrectHorseBattery99!"},
        )
        token = str(login.json()["data"]["access_token"])
        org_id = str(login.json()["data"]["user"]["organization_id"])
    hdr = {"Authorization": f"Bearer {token}"}
    venue = await client.post(
        "/api/v1/venues",
        headers=hdr,
        json={"name": f"{org_name} Main", "timezone": "Asia/Kolkata"},
    )
    venue_id = str(venue.json()["data"]["id"])
    return token, venue_id, org_id


@pytest.mark.asyncio
async def test_tables_crud_bulk_optimistic_lock_and_db_audit(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, venue_id, org_id = await _setup_org(client)
    hdr = {"Authorization": f"Bearer {token}"}

    # 1. Fail-closed flag check
    monkeypatch.setenv("TABLE_ADVANCED_ENABLED", "false")
    get_settings.cache_clear()
    disabled_res = await client.post(
        f"/api/v1/venues/{venue_id}/tables",
        headers=hdr,
        json={"table_code": "T10", "section_name": "Main", "seat_capacity": 4},
    )
    assert disabled_res.status_code == 503
    assert disabled_res.json()["error"]["code"] == "FEATURE_DISABLED"

    monkeypatch.setenv("TABLE_ADVANCED_ENABLED", "true")
    get_settings.cache_clear()

    # 2. Bad inputs -> 400 VALIDATION_ERROR
    assert (
        await client.post(
            f"/api/v1/venues/{venue_id}/tables",
            headers=hdr,
            json={"table_code": "T10", "min_capacity": 6, "seat_capacity": 4},
        )
    ).status_code == 400
    assert (
        await client.post(
            f"/api/v1/venues/{venue_id}/tables",
            headers=hdr,
            json={"table_code": "bad code!", "seat_capacity": 4},
        )
    ).status_code == 400
    assert (
        await client.post(
            f"/api/v1/venues/{venue_id}/tables",
            headers=hdr,
            json={"table_code": "T10", "seat_capacity": 4, "unexpected_field": 1},
        )
    ).status_code == 400

    # 3. Valid individual create + Idempotency-Key + auto QR + direct SQL verification
    idem = str(uuid.uuid4())
    create_res = await client.post(
        f"/api/v1/venues/{venue_id}/tables",
        headers={**hdr, "Idempotency-Key": idem},
        json={
            "table_code": "p01",
            "display_name": "Corner Window 1",
            "section_name": "Patio",
            "min_capacity": 2,
            "seat_capacity": 4,
            "shape": "BOOTH",
            "is_combinable": True,
            "table_notes": "Near heater - internal note",
        },
    )
    assert create_res.status_code == 201
    t_data = create_res.json()["data"]
    assert t_data["table_code"] == "P01"
    assert len(t_data["qr_token"]) == 22
    table_id = t_data["id"]

    # Idempotency replay returns identical payload without creating a second table
    replay_res = await client.post(
        f"/api/v1/venues/{venue_id}/tables",
        headers={**hdr, "Idempotency-Key": idem},
        json={
            "table_code": "p01",
            "display_name": "Corner Window 1",
            "section_name": "Patio",
            "min_capacity": 2,
            "seat_capacity": 4,
            "shape": "BOOTH",
            "is_combinable": True,
            "table_notes": "Near heater - internal note",
        },
    )
    assert replay_res.status_code == 201
    assert replay_res.json()["data"]["id"] == table_id

    # Direct DB verification on tables, table_qr_codes, and audit_logs
    qr_db = (
        await db_session.execute(
            text("SELECT token, status FROM table_qr_codes WHERE table_id = :tid"),
            {"tid": uuid.UUID(table_id)},
        )
    ).fetchone()
    assert qr_db is not None
    assert qr_db[0] == t_data["qr_token"]
    assert qr_db[1] == "ACTIVE"

    audit_cnt = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) FROM audit_logs WHERE action = 'TABLE_CREATED' AND target_id = :tid"
            ),
            {"tid": uuid.UUID(table_id)},
        )
    ).scalar_one()
    assert audit_cnt == 1

    # 4. Duplicate table_code -> 409 DUPLICATE_TABLE_CODE
    dup_res = await client.post(
        f"/api/v1/venues/{venue_id}/tables",
        headers=hdr,
        json={"table_code": "P01", "seat_capacity": 2},
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["code"] == "DUPLICATE_TABLE_CODE"

    # 5. Rename preserves active QR token & checks optimistic locking
    upd_res = await client.patch(
        f"/api/v1/venues/{venue_id}/tables/{table_id}",
        headers=hdr,
        json={"table_code": "PAT-1", "display_name": "Sunny Patio 1", "version": 1},
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["data"]["table_code"] == "PAT-1"
    assert upd_res.json()["data"]["qr_token"] == t_data["qr_token"]
    assert upd_res.json()["data"]["version"] == 2

    stale_res = await client.patch(
        f"/api/v1/venues/{venue_id}/tables/{table_id}",
        headers=hdr,
        json={"display_name": "Stale", "version": 1},
    )
    assert stale_res.status_code == 409
    assert stale_res.json()["error"]["code"] == "VERSION_CONFLICT"

    # 6. Bulk create + collision all-or-nothing + bulk section/active toggle
    bulk_ok = await client.post(
        f"/api/v1/venues/{venue_id}/tables/bulk",
        headers=hdr,
        json={
            "prefix": "M",
            "start_number": 1,
            "count": 3,
            "zero_pad": 2,
            "section_name": "Main Hall",
            "min_capacity": 2,
            "seat_capacity": 4,
        },
    )
    assert bulk_ok.status_code == 201
    assert bulk_ok.json()["data"]["created_count"] == 3
    m_ids = [item["id"] for item in bulk_ok.json()["data"]["tables"]]

    # Collision on M03 -> 409 all-or-nothing (M04 NOT inserted)
    bulk_col = await client.post(
        f"/api/v1/venues/{venue_id}/tables/bulk",
        headers=hdr,
        json={"prefix": "M", "start_number": 3, "count": 2, "zero_pad": 2},
    )
    assert bulk_col.status_code == 409
    assert bulk_col.json()["error"]["code"] == "DUPLICATE_TABLE_CODE"
    m04 = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM tables WHERE venue_id = :vid AND table_code = 'M04'"),
            {"vid": uuid.UUID(venue_id)},
        )
    ).scalar_one()
    assert m04 == 0

    # Bulk deactivate + move section
    bulk_upd = await client.patch(
        f"/api/v1/venues/{venue_id}/tables/bulk",
        headers=hdr,
        json={"table_ids": m_ids[:2], "section_name": "VIP", "is_active": False},
    )
    assert bulk_upd.status_code == 200
    assert bulk_upd.json()["data"]["updated_count"] == 2

    # 7. Active-session delete guard -> 409 TABLE_IN_USE, force=true revokes QR & resolves alert
    await db_session.execute(
        text("UPDATE tables SET current_state = 'OCCUPIED' WHERE id = :tid"),
        {"tid": uuid.UUID(table_id)},
    )
    db_session.add(
        Alert(
            organization_id=uuid.UUID(org_id),
            venue_id=uuid.UUID(venue_id),
            table_id=uuid.UUID(table_id),
            alert_type="UNATTENDED_TABLE",
            severity="WARNING",
            status="ACTIVE",
            dedup_key=f"test-{table_id}",
            message="Test alert",
        )
    )
    await db_session.commit()

    blocked_del = await client.delete(
        f"/api/v1/venues/{venue_id}/tables/{table_id}",
        headers=hdr,
    )
    assert blocked_del.status_code == 409
    assert blocked_del.json()["error"]["code"] == "TABLE_IN_USE"

    forced_del = await client.delete(
        f"/api/v1/venues/{venue_id}/tables/{table_id}?force=true&reason=Closing+patio",
        headers=hdr,
    )
    assert forced_del.status_code == 200

    qr_after = (
        await db_session.execute(
            text("SELECT status, revoked_reason FROM table_qr_codes WHERE table_id = :tid"),
            {"tid": uuid.UUID(table_id)},
        )
    ).fetchone()
    assert qr_after == ("REVOKED", "TABLE_DELETED")

    alert_after = (
        await db_session.execute(
            text("SELECT status FROM alerts WHERE table_id = :tid"),
            {"tid": uuid.UUID(table_id)},
        )
    ).scalar_one()
    assert alert_after == "RESOLVED"

    # Reuse archived table_code PAT-1 succeeds with a fresh QR token!
    reused = await client.post(
        f"/api/v1/venues/{venue_id}/tables",
        headers=hdr,
        json={"table_code": "PAT-1", "seat_capacity": 4},
    )
    assert reused.status_code == 201
    assert reused.json()["data"]["id"] != table_id
    assert reused.json()["data"]["qr_token"] != t_data["qr_token"]


@pytest.mark.asyncio
async def test_tables_rbac_and_cross_tenant_isolation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner_tok, venue_id, org_id = await _setup_org(client, email="owner-rbac-n3@example.com")
    # Create HOST and STAFF inside same org
    from app.core.security import create_access_token, hash_password

    host_u = User(
        organization_id=uuid.UUID(org_id),
        email="host-n3@example.com",
        full_name="Host User",
        password_hash=hash_password("StrongPassword123!"),
        role="HOST",
        assigned_venue_ids=[uuid.UUID(venue_id)],
        is_active=True,
    )
    staff_u = User(
        organization_id=uuid.UUID(org_id),
        email="staff-n3@example.com",
        full_name="Staff User",
        password_hash=hash_password("StrongPassword123!"),
        role="STAFF",
        assigned_venue_ids=[uuid.UUID(venue_id)],
        is_active=True,
    )
    db_session.add_all([host_u, staff_u])
    await db_session.commit()

    host_tok = create_access_token(
        user_id=host_u.id, organization_id=uuid.UUID(org_id), role="HOST"
    )
    staff_tok = create_access_token(
        user_id=staff_u.id, organization_id=uuid.UUID(org_id), role="STAFF"
    )

    # Unauthenticated -> 401
    assert (await client.get(f"/api/v1/venues/{venue_id}/tables")).status_code == 401

    # HOST can read tables, cannot create/write -> 403
    assert (
        await client.get(
            f"/api/v1/venues/{venue_id}/tables",
            headers={"Authorization": f"Bearer {host_tok}"},
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/api/v1/venues/{venue_id}/tables",
            headers={"Authorization": f"Bearer {host_tok}"},
            json={"table_code": "H01", "seat_capacity": 4},
        )
    ).status_code == 403

    # STAFF cannot even read Table Admin endpoint -> 403
    assert (
        await client.get(
            f"/api/v1/venues/{venue_id}/tables",
            headers={"Authorization": f"Bearer {staff_tok}"},
        )
    ).status_code == 403

    # Cross-org / unknown venue -> 403 AUTH_FORBIDDEN
    other_vid = uuid.uuid4()
    assert (
        await client.get(
            f"/api/v1/venues/{other_vid}/tables",
            headers={"Authorization": f"Bearer {owner_tok}"},
        )
    ).status_code == 403
