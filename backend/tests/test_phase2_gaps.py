"""Tests for Phase 2 Should items: CSV import round-trip, table duplicate/restore/purge, QR A6/Sticker/ZIP/stats, EN/HI & large menu paging."""

from __future__ import annotations

import io
import zipfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import get_settings
from app.core import valkey_client
from app.db.base import reset_engine_cache
from app.db.models import DiningTable, MenuItem, TableStateEvent
from app.main import create_app


@pytest.fixture
async def client(clean_db: None, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    for key in (
        "DEMO_MODE",
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
    valkey_client._local_ephemeral.clear()
    valkey_client._local_public_menu_cache.clear()
    valkey_client._local_public_qr_cache.clear()
    try:
        vk = valkey_client.get_valkey()
        for pat in ("tp:rl:*", "tp:pub:*", "tp:csv_import:*"):
            keys = await vk.keys(pat)
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


async def _owner_venue(client: AsyncClient) -> tuple[dict[str, str], str]:
    await client.post(
        "/api/v1/auth/bootstrap",
        json={
            "organization_name": "Gaps Bistro",
            "full_name": "Owner Gaps",
            "email": "gaps-owner@example.com",
            "password": "StrongPassword!123",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "gaps-owner@example.com", "password": "StrongPassword!123"},
    )
    hdrs = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    v_res = await client.post(
        "/api/v1/venues",
        headers=hdrs,
        json={"name": "Gaps Venue", "timezone": "Asia/Kolkata"},
    )
    return hdrs, v_res.json()["data"]["id"]


@pytest.mark.asyncio
async def test_table_duplicate_archived_restore_conflict_and_purge(
    client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    hdrs, venue_id = await _owner_venue(client)

    t1 = (
        await client.post(
            f"/api/v1/venues/{venue_id}/tables",
            headers=hdrs,
            json={"table_code": "P1", "display_name": "Patio One", "seat_capacity": 4},
        )
    ).json()["data"]

    # Duplicate P1 -> P1-COPY
    dup = await client.post(
        f"/api/v1/venues/{venue_id}/tables/{t1['id']}/duplicate",
        headers=hdrs,
    )
    assert dup.status_code == 201
    dup_tbl = dup.json()["data"]
    assert dup_tbl["table_code"] == "P1-COPY"
    assert dup_tbl["qr_token"] and dup_tbl["qr_token"] != t1["qr_token"]

    # Soft delete both P1 and P1-COPY
    assert (
        await client.delete(f"/api/v1/venues/{venue_id}/tables/{t1['id']}", headers=hdrs)
    ).status_code == 200
    assert (
        await client.delete(f"/api/v1/venues/{venue_id}/tables/{dup_tbl['id']}", headers=hdrs)
    ).status_code == 200

    # List archived
    arch = await client.get(
        f"/api/v1/venues/{venue_id}/tables?status=archived",
        headers=hdrs,
    )
    assert arch.status_code == 200
    assert arch.json()["data"]["total"] == 2

    # Create a new active P1 to trigger E-05 conflict on restore
    assert (
        await client.post(
            f"/api/v1/venues/{venue_id}/tables",
            headers=hdrs,
            json={"table_code": "P1", "seat_capacity": 2},
        )
    ).status_code == 201

    conflict_restore = await client.post(
        f"/api/v1/venues/{venue_id}/tables/{t1['id']}/restore",
        headers=hdrs,
    )
    assert conflict_restore.status_code == 409
    assert conflict_restore.json()["error"]["code"] == "DUPLICATE_TABLE_CODE"

    # Resolve conflict with new_table_code
    ok_restore = await client.post(
        f"/api/v1/venues/{venue_id}/tables/{t1['id']}/restore",
        headers=hdrs,
        json={"new_table_code": "P1-OLD"},
    )
    assert ok_restore.status_code == 200
    assert ok_restore.json()["data"]["table_code"] == "P1-OLD"

    # Zero-history archived P1-COPY can be purged
    purge_ok = await client.delete(
        f"/api/v1/venues/{venue_id}/tables/{dup_tbl['id']}/purge",
        headers=hdrs,
    )
    assert purge_ok.status_code == 200

    # Archived table with TableStateEvent history blocks purge (409 TABLE_HAS_HISTORY)
    t3 = (
        await client.post(
            f"/api/v1/venues/{venue_id}/tables",
            headers=hdrs,
            json={"table_code": "P9", "seat_capacity": 4},
        )
    ).json()["data"]
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        row = (await db.execute(select(DiningTable).where(DiningTable.id == t3["id"]))).scalar_one()
        db.add(
            TableStateEvent(
                organization_id=row.organization_id,
                venue_id=row.venue_id,
                table_id=row.id,
                previous_state="FREE",
                new_state="OCCUPIED",
                guest_count=2,
                source="MANUAL",
            )
        )
        await db.commit()
    await client.delete(
        f"/api/v1/venues/{venue_id}/tables/{t3['id']}",
        headers=hdrs,
    )
    purge_blocked = await client.delete(
        f"/api/v1/venues/{venue_id}/tables/{t3['id']}/purge",
        headers=hdrs,
    )
    assert purge_blocked.status_code == 409
    assert purge_blocked.json()["error"]["code"] == "TABLE_HAS_HISTORY"


@pytest.mark.asyncio
async def test_qr_a6_sticker_zip_stats_and_public_hardening(client: AsyncClient) -> None:
    hdrs, venue_id = await _owner_venue(client)
    t1 = (
        await client.post(
            f"/api/v1/venues/{venue_id}/tables",
            headers=hdrs,
            json={"table_code": "Q1", "seat_capacity": 4},
        )
    ).json()["data"]

    for layout in ("A6_1UP", "A4_STICKER_12UP"):
        pdf_res = await client.post(
            f"/api/v1/venues/{venue_id}/qr/export-pdf",
            headers=hdrs,
            json={"table_ids": [t1["id"]], "layout": layout},
        )
        assert pdf_res.status_code == 200
        assert pdf_res.content.startswith(b"%PDF")

    zip_res = await client.post(
        f"/api/v1/venues/{venue_id}/qr/export-zip",
        headers=hdrs,
        json={"table_ids": [t1["id"]], "format": "both", "framed": True},
    )
    assert zip_res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(zip_res.content)) as zf:
        names = set(zf.namelist())
        assert "qr-Q1.svg" in names
        assert "qr-Q1.png" in names

    # Malformed short QR token rejected cleanly with 404 before DB hit
    assert (await client.get("/api/v1/public/menu/short")).status_code == 404

    stats = await client.get(f"/api/v1/venues/{venue_id}/qr-codes/stats?days=30", headers=hdrs)
    assert stats.status_code == 200
    assert stats.json()["data"]["days"] == 30
    assert len(stats.json()["data"]["by_table"]) == 1


@pytest.mark.asyncio
async def test_menu_csv_import_roundtrip_duplicate_bulk_auto_restore_and_i18n(
    client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    hdrs, venue_id = await _owner_venue(client)

    menu = (
        await client.post(
            f"/api/v1/venues/{venue_id}/menus",
            headers=hdrs,
            json={
                "name": "All Day",
                "translations_json": {"hi": {"name": "पूरा दिन मेनू"}},
                "is_default": True,
            },
        )
    ).json()["data"]
    menu_id = menu["id"]

    # Template CSV
    tpl = await client.get(
        f"/api/v1/venues/{venue_id}/menus/import/template",
        headers=hdrs,
    )
    assert tpl.status_code == 200
    assert "sku,category_name,name" in tpl.text

    # Upload CSV preview (1 valid row with SKU + Hindi + formula-safe minus dish name, 1 invalid row)
    bad_csv = (
        "sku,category_name,name,description,price_minor_units,compare_at_price_minor_units,"
        "dietary_tags,allergens,is_available,is_featured,prep_time_minutes,calories_kcal,name_hi,description_hi\n"
        "SKU-001,Starters,'-50% Combo Chaat,Crisp street platter,24900,29900,\"VEG,SPICY_MILD\",DAIRY,true,true,12,420,कॉम्बो चाट,स्वादिष्ट\n"
        "BAD-002,,Missing Category,-5,0,UNKNOWN_TAG,,true,false,,,,,\n"
    )
    prev = await client.post(
        f"/api/v1/venues/{venue_id}/menus/import/preview?menu_id={menu_id}&mode=upsert_by_sku",
        headers=hdrs,
        files={"file": ("import.csv", bad_csv.encode("utf-8"), "text/csv")},
    )
    assert prev.status_code == 200
    pdata = prev.json()["data"]
    assert pdata["valid_rows"] == 1
    assert pdata["invalid_rows"] == 1
    assert len(pdata["rows"]) == 2
    assert pdata["rows"][0]["action"] == "create"
    assert pdata["rows"][1]["action"] == "error"
    assert len(pdata["rows"][1]["errors"]) >= 1
    import_id = pdata["import_id"]

    # all_or_nothing blocks when invalid_rows > 0
    block_commit = await client.post(
        f"/api/v1/venues/{venue_id}/menus/import/{import_id}/commit",
        headers=hdrs,
        json={"strategy": "all_or_nothing"},
    )
    assert block_commit.status_code == 400

    # skip_invalid commits valid rows cleanly
    ok_commit = await client.post(
        f"/api/v1/venues/{venue_id}/menus/import/{import_id}/commit",
        headers=hdrs,
        json={"strategy": "skip_invalid"},
    )
    assert ok_commit.status_code == 200
    assert ok_commit.json()["data"]["created"] == 1

    # Preview cannot be reused after commit -> 410 IMPORT_EXPIRED
    expired_retry = await client.post(
        f"/api/v1/venues/{venue_id}/menus/import/{import_id}/commit",
        headers=hdrs,
        json={"strategy": "skip_invalid"},
    )
    assert expired_retry.status_code == 410
    assert expired_retry.json()["error"]["code"] == "IMPORT_EXPIRED"

    # Export CSV -> formula safe & round-trips SKU + Hindi cleanly via upsert_by_sku
    exp = await client.get(
        f"/api/v1/venues/{venue_id}/menu-items?menu_id={menu_id}&format=csv",
        headers=hdrs,
    )
    assert exp.status_code == 200
    assert "'-50% Combo Chaat" in exp.text
    assert "SKU-001" in exp.text

    # Modify price & re-import with upsert_by_sku
    re_csv = exp.text.replace("24900", "27900")
    prev2 = await client.post(
        f"/api/v1/venues/{venue_id}/menus/import/preview?menu_id={menu_id}&mode=upsert_by_sku",
        headers=hdrs,
        files={"file": ("roundtrip.csv", re_csv.encode("utf-8"), "text/csv")},
    )
    assert prev2.status_code == 200
    assert prev2.json()["data"]["will_update"] == 1
    c2 = await client.post(
        f"/api/v1/venues/{venue_id}/menus/import/{prev2.json()['data']['import_id']}/commit",
        headers=hdrs,
        json={"strategy": "all_or_nothing"},
    )
    assert c2.status_code == 200
    assert c2.json()["data"]["updated"] == 1

    # Duplicate menu -> creates DRAFT copy
    dup_m = await client.post(
        f"/api/v1/venues/{venue_id}/menus/{menu_id}/duplicate",
        headers=hdrs,
    )
    assert dup_m.status_code == 201
    assert dup_m.json()["data"]["status"] == "DRAFT"
    assert dup_m.json()["data"]["item_count"] == 1

    # Publish original menu & verify localized ?lang=hi public endpoint
    t_qr = (
        await client.post(
            f"/api/v1/venues/{venue_id}/tables",
            headers=hdrs,
            json={"table_code": "G1", "seat_capacity": 4},
        )
    ).json()["data"]["qr_token"]
    assert (
        await client.patch(
            f"/api/v1/venues/{venue_id}/menus/{menu_id}",
            headers=hdrs,
            json={"status": "PUBLISHED"},
        )
    ).status_code == 200

    pub_hi = await client.get(f"/api/v1/public/menu/{t_qr}?lang=hi")
    assert pub_hi.status_code == 200
    assert pub_hi.headers.get("x-total-items") == "1"
    assert pub_hi.headers.get("x-has-more") == "false"
    pub_data = pub_hi.json()["data"]
    assert pub_data["menus"][0]["name"] == "पूरा दिन मेनू"
    assert pub_data["menus"][0]["categories"][0]["items"][0]["name"] == "कॉम्बो चाट"

    # unavailable_until auto-restore sync on admin list
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        it = (
            await db.execute(select(MenuItem).where(MenuItem.venue_id == venue_id, MenuItem.sku == "SKU-001"))
        ).scalar_one()
        it.is_available = False
        it.unavailable_until = datetime.now(UTC) - timedelta(minutes=5)
        await db.commit()

    listed = (
        await client.get(f"/api/v1/venues/{venue_id}/menu-items?menu_id={menu_id}", headers=hdrs)
    ).json()["data"]["items"]
    assert listed[0]["is_available"] is True
    assert listed[0]["unavailable_until"] is None

    # Bulk move & delete
    c_new = (
        await client.post(
            f"/api/v1/venues/{venue_id}/menus/{menu_id}/categories",
            headers=hdrs,
            json={"name": "Mains"},
        )
    ).json()["data"]["id"]
    mv = await client.post(
        f"/api/v1/venues/{venue_id}/menu-items/bulk-action",
        headers=hdrs,
        json={"action": "move", "item_ids": [listed[0]["id"]], "target_category_id": c_new},
    )
    assert mv.status_code == 200
    assert mv.json()["data"]["affected"] == 1
    dl = await client.post(
        f"/api/v1/venues/{venue_id}/menu-items/bulk-action",
        headers=hdrs,
        json={"action": "delete", "item_ids": [listed[0]["id"]]},
    )
    assert dl.status_code == 200
    assert dl.json()["data"]["affected"] == 1
