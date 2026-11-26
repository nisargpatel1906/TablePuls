"""Stage N1 (Stage 9) Verification: Phase 2 schema, constraints, RLS, tablepulse_public isolation, and null-geometry safety."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core import valkey_client
from app.db.base import get_public_engine, reset_engine_cache
from app.db.models import (
    DiningTable,
    Menu,
    MenuCategory,
    MenuItem,
    Organization,
    TableQRCode,
    Venue,
)
from app.main import create_app

PHASE2_TABLES = {
    "table_qr_codes",
    "menus",
    "menu_categories",
    "menu_items",
    "menu_media_assets",
    "qr_scan_daily_stats",
}


@pytest.mark.asyncio
async def test_phase2_tables_views_and_columns_exist(db_session: AsyncSession) -> None:
    res = await db_session.execute(
        text(
            "SELECT c.relname FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')"
        )
    )
    found = {row[0] for row in res.fetchall()}
    assert PHASE2_TABLES.issubset(found)

    view_res = await db_session.execute(
        text("SELECT table_name FROM information_schema.views WHERE table_schema = 'public'")
    )
    views = {row[0] for row in view_res.fetchall()}
    assert {"v_public_qr_resolution", "v_public_menu_catalog"}.issubset(views)

    # Check tablepulse_public role exists without superuser or bypassrls
    role_res = await db_session.execute(
        text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'tablepulse_public'")
    )
    rol = role_res.fetchone()
    assert rol is not None
    assert rol[0] is False
    assert rol[1] is False


@pytest.mark.asyncio
async def test_phase2_constraints_and_nullable_polygon(
    clean_db: None, db_session: AsyncSession
) -> None:
    org = Organization(name="Phase 2 Bistro")
    db_session.add(org)
    await db_session.flush()
    org_id = org.id

    venue = Venue(
        organization_id=org_id,
        name="Patio Hall",
        operating_hours_json={},
        currency_code="INR",
    )
    db_session.add(venue)
    await db_session.flush()
    venue_id = venue.id

    # Valid non-camera table with NULL polygon_json
    unmapped = DiningTable(
        organization_id=org_id,
        venue_id=venue_id,
        camera_id=None,
        table_code="P01",
        display_name="Patio Table 1",
        section_name="Patio",
        min_capacity=2,
        seat_capacity=4,
        polygon_json=None,
        is_active=True,
    )
    db_session.add(unmapped)
    await db_session.commit()
    unmapped_id = unmapped.id

    # Invalid min_capacity > seat_capacity fails check constraint
    bad_tbl = DiningTable(
        organization_id=org_id,
        venue_id=venue_id,
        table_code="BAD1",
        section_name="Patio",
        min_capacity=6,
        seat_capacity=4,
        polygon_json=None,
    )
    db_session.add(bad_tbl)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()

    # Invalid negative price fails check constraint
    menu = Menu(organization_id=org_id, venue_id=venue_id, name="Main Menu")
    db_session.add(menu)
    await db_session.flush()
    cat = MenuCategory(organization_id=org_id, venue_id=venue_id, menu_id=menu.id, name="Starters")
    db_session.add(cat)
    await db_session.flush()
    bad_item = MenuItem(
        organization_id=org_id,
        venue_id=venue_id,
        category_id=cat.id,
        name="Negative Dish",
        price_minor_units=-100,
    )
    db_session.add(bad_item)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()

    # Duplicate ACTIVE QR token on same table fails partial unique index
    qr1 = TableQRCode(
        organization_id=org_id,
        venue_id=venue_id,
        table_id=unmapped_id,
        token="A" * 22,
        status="ACTIVE",
    )
    qr2 = TableQRCode(
        organization_id=org_id,
        venue_id=venue_id,
        table_id=unmapped_id,
        token="B" * 22,
        status="ACTIVE",
    )
    db_session.add(qr1)
    await db_session.flush()
    db_session.add(qr2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_phase2_rls_and_tablepulse_public_isolation(
    clean_db: None, db_session: AsyncSession
) -> None:
    org_a = Organization(name="Org Alpha")
    org_b = Organization(name="Org Beta")
    db_session.add_all([org_a, org_b])
    await db_session.flush()
    org_a_id = org_a.id
    org_b_id = org_b.id

    venue_a = Venue(organization_id=org_a_id, name="Venue Alpha", operating_hours_json={})
    venue_b = Venue(organization_id=org_b_id, name="Venue Beta", operating_hours_json={})
    db_session.add_all([venue_a, venue_b])
    await db_session.flush()
    venue_a_id = venue_a.id
    venue_b_id = venue_b.id

    menu_a = Menu(
        organization_id=org_a_id,
        venue_id=venue_a_id,
        name="Alpha Menu",
        status="PUBLISHED",
        is_active=True,
    )
    menu_draft = Menu(
        organization_id=org_a_id,
        venue_id=venue_a_id,
        name="Secret Draft Menu",
        status="DRAFT",
        is_active=True,
    )
    menu_b = Menu(
        organization_id=org_b_id,
        venue_id=venue_b_id,
        name="Beta Menu",
        status="PUBLISHED",
        is_active=True,
    )
    db_session.add_all([menu_a, menu_draft, menu_b])
    await db_session.flush()

    tbl_a = DiningTable(
        organization_id=org_a_id,
        venue_id=venue_a_id,
        table_code="A01",
        section_name="Main",
        seat_capacity=4,
        polygon_json=None,
        table_notes="VIP owner friend - DO NOT LEAK",
    )
    db_session.add(tbl_a)
    await db_session.flush()

    qr_a = TableQRCode(
        organization_id=org_a_id,
        venue_id=venue_a_id,
        table_id=tbl_a.id,
        token="ValidPublicToken_01234",
        status="ACTIVE",
    )
    db_session.add(qr_a)
    await db_session.commit()

    # Non-superuser RLS test
    await db_session.execute(
        text(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tp_rls_tester') THEN "
            "CREATE ROLE tp_rls_tester NOLOGIN NOSUPERUSER NOBYPASSRLS; END IF; END $$;"
        )
    )
    await db_session.execute(
        text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO tp_rls_tester")
    )
    await db_session.commit()

    await db_session.execute(text("SET LOCAL ROLE tp_rls_tester"))
    await db_session.execute(
        text("SELECT set_config('app.current_org_id', :oid, true)"),
        {"oid": str(org_a_id)},
    )
    visible_menus = (await db_session.execute(text("SELECT name FROM menus"))).scalars().all()
    assert set(visible_menus) == {"Alpha Menu", "Secret Draft Menu"}
    await db_session.rollback()

    # Least-privilege `tablepulse_public` role isolation test via real dedicated engine
    reset_engine_cache()
    pub_engine = get_public_engine()
    async with pub_engine.connect() as conn:
        qr_row = (
            await conn.execute(
                text("SELECT table_label, venue_name FROM v_public_qr_resolution WHERE token = :t"),
                {"t": "ValidPublicToken_01234"},
            )
        ).fetchone()
        assert qr_row is not None
        assert qr_row[0] == "Table A01"
        assert qr_row[1] == "Venue Alpha"

        # Published view never exposes DRAFT menus
        cat_rows = (
            await conn.execute(
                text("SELECT DISTINCT menu_name FROM v_public_menu_catalog WHERE venue_id = :vid"),
                {"vid": venue_a_id},
            )
        ).fetchall()
        assert [r[0] for r in cat_rows] == ["Alpha Menu"]

        # Reading base tables or writing MUST raise PostgreSQL permission denied
        for forbidden_sql in (
            "SELECT * FROM users",
            "SELECT * FROM cameras",
            "SELECT * FROM tables",
            "SELECT * FROM menus",
            "SELECT * FROM audit_logs",
        ):
            with pytest.raises(DBAPIError):
                await conn.execute(text(forbidden_sql))
            await conn.rollback()

    reset_engine_cache()


@pytest.mark.asyncio
async def test_unmonitored_tables_do_not_distort_floor_kpis_or_cv_cameras(
    clean_db: None, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    reset_engine_cache()

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        boot = await ac.post(
            "/api/v1/auth/bootstrap",
            json={
                "organization_name": "Split Floor Cafe",
                "email": "split@example.com",
                "full_name": "Split Owner",
                "password": "CorrectHorseBattery99!",
            },
        )
        assert boot.status_code == 201
        token = str(boot.json()["data"]["access_token"])
        hdr = {"Authorization": f"Bearer {token}"}
        venue_id = str(
            (
                await ac.post(
                    "/api/v1/venues",
                    headers=hdr,
                    json={"name": "Split Venue", "timezone": "UTC"},
                )
            ).json()["data"]["id"]
        )
        cam_id = str(
            (
                await ac.post(
                    f"/api/v1/venues/{venue_id}/cameras",
                    headers=hdr,
                    json={"name": "Cam 1", "stream_type": "DEMO_MP4", "stream_url": "demo.mp4"},
                )
            ).json()["data"]["id"]
        )
        # Add 1 monitored table via polygons endpoint
        poly = await ac.put(
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
                        "floor_x": 0.2,
                        "floor_y": 0.2,
                        "shape": "RECT",
                    }
                ],
                "exclusion_polygons_json": [],
            },
        )
        assert poly.status_code == 200

        # Insert 1 unmonitored patio table directly with NULL polygon_json + camera_id
        vid = uuid.UUID(venue_id)
        oid = uuid.UUID(str(boot.json()["data"]["user"]["organization_id"]))
        db_session.add(
            DiningTable(
                organization_id=oid,
                venue_id=vid,
                camera_id=None,
                table_code="P01",
                section_name="Patio",
                min_capacity=2,
                seat_capacity=6,
                polygon_json=None,
                is_active=True,
            )
        )
        await db_session.commit()

        # Verify floor-state puts T01 in `tables` (total_tables=1) and P01 in `unmonitored_tables`
        fs = await ac.get(f"/api/v1/venues/{venue_id}/floor-state", headers=hdr)
        assert fs.status_code == 200
        data = fs.json()["data"]
        assert data["kpis"]["total_tables"] == 1
        assert data["kpis"]["total_seats"] == 4
        assert [t["table_code"] for t in data["tables"]] == ["T01"]
        assert [t["table_code"] for t in data["unmonitored_tables"]] == ["P01"]
        assert data["unmonitored_tables"][0]["is_monitored"] is False

        # Verify /internal/cv-cameras excludes unmonitored P01
        cv_res = await ac.get(
            "/api/v1/internal/cv-cameras",
            headers={"X-Internal-Secret": get_settings().mediamtx_hook_secret},
        )
        assert cv_res.status_code == 200
        cams = cv_res.json()["data"]["cameras"]
        assert len(cams) == 1
        assert [t["table_code"] for t in cams[0]["tables"]] == ["T01"]

    await valkey_client.close_valkey()
    reset_engine_cache()
