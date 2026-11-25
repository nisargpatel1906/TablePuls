"""Stage 1 Verification: 15 tables, constraints, PG16 partitioning, triggers, and RLS isolation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, User, Venue

EXPECTED_TABLES = {
    "organizations",
    "venues",
    "users",
    "refresh_tokens",
    "cameras",
    "tables",
    "table_state_events",
    "occupancy_snapshots",
    "alerts",
    "waitlist_entries",
    "ml_models",
    "ml_review_items",
    "alert_rules",
    "audit_logs",
    "system_settings",
}


@pytest.mark.asyncio
async def test_all_15_tables_and_indexes_exist(db_session: AsyncSession) -> None:
    res = await db_session.execute(
        text(
            "SELECT c.relname FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') "
            "AND c.relname NOT LIKE 'occupancy_snapshots_%'"
        )
    )
    found = {row[0] for row in res.fetchall()}
    assert EXPECTED_TABLES.issubset(found)

    # Verify occupancy_snapshots is natively range-partitioned
    part_res = await db_session.execute(
        text("SELECT relkind::text FROM pg_class WHERE relname = 'occupancy_snapshots'")
    )
    assert part_res.scalar_one() == "p"

    # Verify rollup_hourly_venue materialized view exists
    mv_res = await db_session.execute(
        text("SELECT matviewname FROM pg_matviews WHERE matviewname = 'rollup_hourly_venue'")
    )
    assert mv_res.scalar_one() == "rollup_hourly_venue"


@pytest.mark.asyncio
async def test_native_monthly_partition_routing(clean_db: None, db_session: AsyncSession) -> None:
    org_id = uuid.uuid4()
    venue_id = uuid.uuid4()
    table_id = uuid.uuid4()
    ts = datetime.now(UTC)

    await db_session.execute(text("SELECT ensure_occupancy_partition(:ts)"), {"ts": ts})
    await db_session.execute(
        text(
            """
            INSERT INTO occupancy_snapshots
                (captured_at, table_id, organization_id, venue_id, section_name, state, guest_count, seat_capacity, sla_breached)
            VALUES (:ts, :tid, :oid, :vid, 'Main', 'OCCUPIED', 3, 4, false)
            """
        ),
        {"ts": ts, "tid": table_id, "oid": org_id, "vid": venue_id},
    )
    await db_session.commit()

    part_name = f"occupancy_snapshots_{ts.strftime('%Y_%m')}"
    cnt = await db_session.execute(text(f"SELECT COUNT(*) FROM {part_name}"))
    assert cnt.scalar_one() == 1


@pytest.mark.asyncio
async def test_constraints_and_last_owner_trigger(clean_db: None, db_session: AsyncSession) -> None:
    org = Organization(name="Test Bistro")
    db_session.add(org)
    await db_session.flush()
    org_id = org.id

    owner = User(
        organization_id=org_id,
        email="owner@bistro.test",
        full_name="Owner One",
        password_hash="argon2id$placeholder",
        role="OWNER",
    )
    db_session.add(owner)
    await db_session.commit()

    # Demoting the last active OWNER must raise DB exception
    with pytest.raises(Exception, match="LAST_OWNER_PROTECTED"):
        await db_session.execute(
            text("UPDATE users SET role = 'MANAGER' WHERE id = :uid"),
            {"uid": owner.id},
        )
    await db_session.rollback()

    # Invalid venue ratio check constraint
    bad_venue = Venue(
        organization_id=org_id,
        name="Bad Ratio",
        operating_hours_json={},
        guests_per_server_ratio=1,  # violates BETWEEN 4 AND 50
    )
    db_session.add(bad_venue)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_rls_cross_org_isolation(clean_db: None, db_session: AsyncSession) -> None:
    org_a = Organization(name="Org A")
    org_b = Organization(name="Org B")
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    venue_a = Venue(organization_id=org_a.id, name="Venue A", operating_hours_json={})
    venue_b = Venue(organization_id=org_b.id, name="Venue B", operating_hours_json={})
    db_session.add_all([venue_a, venue_b])
    await db_session.commit()

    # Create non-superuser role for strict RLS enforcement test
    await db_session.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tp_rls_tester') THEN
                    CREATE ROLE tp_rls_tester NOLOGIN NOSUPERUSER NOBYPASSRLS;
                END IF;
            END $$;
            """
        )
    )
    await db_session.execute(text("GRANT USAGE ON SCHEMA public TO tp_rls_tester"))
    await db_session.execute(
        text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO tp_rls_tester")
    )
    await db_session.commit()

    await db_session.execute(text("SET LOCAL ROLE tp_rls_tester"))
    # Unset app.current_org_id -> fail-closed: 0 rows
    res_empty = await db_session.execute(text("SELECT id FROM venues"))
    assert res_empty.fetchall() == []

    # Set Org A -> only Venue A visible
    await db_session.execute(
        text("SELECT set_config('app.current_org_id', :oid, true)"),
        {"oid": str(org_a.id)},
    )
    res_a = await db_session.execute(text("SELECT id FROM venues"))
    ids_a = {row[0] for row in res_a.fetchall()}
    assert ids_a == {venue_a.id}

    # Attempt cross-org insert into Org B while scoped to Org A -> RLS WITH CHECK violation
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError):
        await db_session.execute(
            text(
                "INSERT INTO venues (id, organization_id, name, operating_hours_json) "
                "VALUES (:vid, :oid, 'Intruder', '{}'::jsonb)"
            ),
            {"vid": uuid.uuid4(), "oid": org_b.id},
        )
    await db_session.rollback()
