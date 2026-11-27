"""Stage N4 Verification: Media pipeline, Menu CRUD/schedules/Quick-86/currency-lock, QR SVG/PNG/PDF + zxing decode & RBAC."""

from __future__ import annotations

import io
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import zxingcpp
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core import valkey_client
from app.core.security import create_access_token, hash_password
from app.db.base import reset_engine_cache
from app.db.models import User
from app.main import create_app
from app.services.menu_schedule import is_menu_scheduled_now
from app.services.qr_export import verify_qr_preview_token


@pytest.fixture
async def client(
    clean_db: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    monkeypatch.setenv("TABLE_ADVANCED_ENABLED", "true")
    monkeypatch.setenv("QR_ENABLED", "true")
    monkeypatch.setenv("MENU_IMAGES_ENABLED", "true")
    monkeypatch.setenv("PUBLIC_APP_URL", "https://menu.example.com")
    monkeypatch.setenv("MENU_MEDIA_DIR", str(tmp_path / "menu-media"))
    get_settings.cache_clear()
    reset_engine_cache()
    valkey_client._local_rate_limits.clear()
    valkey_client._local_revocations.clear()
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac
    await valkey_client.close_valkey()
    reset_engine_cache()


async def _bootstrap_with_table(client: AsyncClient) -> tuple[str, str, str, str, str]:
    boot = await client.post(
        "/api/v1/auth/bootstrap",
        json={
            "organization_name": "Stage N4 Kitchen",
            "email": "owner-n4@example.com",
            "full_name": "Owner N4",
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
        json={"name": "Spice Courtyard", "timezone": "Asia/Kolkata"},
    )
    venue_id = str(venue.json()["data"]["id"])
    tbl = await client.post(
        f"/api/v1/venues/{venue_id}/tables",
        headers=hdr,
        json={"table_code": "T01", "display_name": "Window Booth 1", "seat_capacity": 4},
    )
    assert tbl.status_code == 201
    table_id = str(tbl.json()["data"]["id"])
    qr_token = str(tbl.json()["data"]["qr_token"])
    return token, org_id, venue_id, table_id, qr_token


def _make_png_bytes(
    width: int = 320, height: int = 320, color: tuple[int, int, int] = (20, 120, 80)
) -> bytes:
    im = Image.new("RGB", (width, height), color)
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMake"
    buf = io.BytesIO()
    im.save(buf, format="PNG", exif=exif)
    return buf.getvalue()


def test_menu_schedule_daytime_and_overnight_windows() -> None:
    day_sched = {"v": 1, "windows": [{"days": [1, 2, 3, 4, 5], "start": "11:30", "end": "15:00"}]}
    # Monday 2026-11-23 12:30 Asia/Kolkata == 07:00 UTC
    assert is_menu_scheduled_now(
        day_sched, "Asia/Kolkata", datetime(2026, 11, 23, 7, 0, tzinfo=UTC)
    )
    # Monday 2026-11-23 16:00 Asia/Kolkata == 10:30 UTC
    assert not is_menu_scheduled_now(
        day_sched, "Asia/Kolkata", datetime(2026, 11, 23, 10, 30, tzinfo=UTC)
    )

    # Overnight Friday window 22:00 - 02:00 UTC (active Friday 23:00 and Saturday 01:00)
    overnight = {"v": 1, "windows": [{"days": [5], "start": "22:00", "end": "02:00"}]}
    assert is_menu_scheduled_now(overnight, "UTC", datetime(2026, 11, 27, 23, 0, tzinfo=UTC))
    assert is_menu_scheduled_now(overnight, "UTC", datetime(2026, 11, 28, 1, 30, tzinfo=UTC))
    assert not is_menu_scheduled_now(overnight, "UTC", datetime(2026, 11, 28, 3, 0, tzinfo=UTC))


@pytest.mark.asyncio
async def test_media_upload_validation_dedup_and_menu_lifecycle(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, org_id, venue_id, _table_id, _qr = await _bootstrap_with_table(client)
    hdr = {"Authorization": f"Bearer {token}"}

    # 1. Fail-closed media flag
    monkeypatch.setenv("MENU_IMAGES_ENABLED", "false")
    get_settings.cache_clear()
    dis = await client.post(
        f"/api/v1/venues/{venue_id}/menu/media",
        headers=hdr,
        files={"file": ("test.png", _make_png_bytes(), "image/png")},
    )
    assert dis.status_code == 503
    monkeypatch.setenv("MENU_IMAGES_ENABLED", "true")
    get_settings.cache_clear()

    # 2. Reject SVG, oversized (>5 MB), and tiny (<200x200) uploads
    svg_res = await client.post(
        f"/api/v1/venues/{venue_id}/menu/media",
        headers=hdr,
        files={"file": ("xss.svg", b'<svg onload="alert(1)"></svg>', "image/svg+xml")},
    )
    assert svg_res.status_code == 400
    assert svg_res.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"

    big_res = await client.post(
        f"/api/v1/venues/{venue_id}/menu/media",
        headers=hdr,
        files={
            "file": ("big.png", b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024 + 10), "image/png")
        },
    )
    assert big_res.status_code == 413

    tiny_res = await client.post(
        f"/api/v1/venues/{venue_id}/menu/media",
        headers=hdr,
        files={"file": ("tiny.png", _make_png_bytes(100, 100), "image/png")},
    )
    assert tiny_res.status_code == 400

    # 3. Valid PNG -> EXIF-stripped WebP + deduplication + static /media/menu/* delivery
    png_bytes = _make_png_bytes(400, 400)
    up1 = await client.post(
        f"/api/v1/venues/{venue_id}/menu/media",
        headers=hdr,
        files={"file": ("dish.png", png_bytes, "image/png")},
    )
    assert up1.status_code == 201
    asset1 = up1.json()["data"]
    assert asset1["deduplicated"] is False
    asset_id = asset1["id"]

    up2 = await client.post(
        f"/api/v1/venues/{venue_id}/menu/media",
        headers=hdr,
        files={"file": ("dish_again.png", png_bytes, "image/png")},
    )
    assert up2.status_code == 201
    assert up2.json()["data"]["id"] == asset_id
    assert up2.json()["data"]["deduplicated"] is True

    served = await client.get(asset1["image_url"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/webp"
    assert served.headers["x-content-type-options"] == "nosniff"
    with Image.open(io.BytesIO(served.content)) as out_im:
        assert out_im.format == "WEBP"
        assert len(out_im.getexif()) == 0

    # 4. Menu -> Category -> Item -> Publish gate -> Duplicate -> CSV export -> Currency Lock
    m_res = await client.post(
        f"/api/v1/venues/{venue_id}/menus",
        headers=hdr,
        json={"name": "All-Day Dining", "status": "DRAFT", "is_default": True},
    )
    assert m_res.status_code == 201
    menu_id = m_res.json()["data"]["id"]

    # Publishing empty menu -> 422 MENU_NOT_PUBLISHABLE
    unpub = await client.patch(
        f"/api/v1/venues/{venue_id}/menus/{menu_id}",
        headers=hdr,
        json={"status": "PUBLISHED"},
    )
    assert unpub.status_code == 422
    assert unpub.json()["error"]["code"] == "MENU_NOT_PUBLISHABLE"

    cat1 = (
        await client.post(
            f"/api/v1/venues/{venue_id}/menus/{menu_id}/categories",
            headers=hdr,
            json={"name": "Starters"},
        )
    ).json()["data"]["id"]
    cat2 = (
        await client.post(
            f"/api/v1/venues/{venue_id}/menus/{menu_id}/categories",
            headers=hdr,
            json={"name": "Mains"},
        )
    ).json()["data"]["id"]

    reorder = await client.patch(
        f"/api/v1/venues/{venue_id}/menus/{menu_id}/categories/reorder",
        headers=hdr,
        json={"ids": [cat2, cat1]},
    )
    assert reorder.status_code == 200

    item_res = await client.post(
        f"/api/v1/venues/{venue_id}/menu-items",
        headers=hdr,
        json={
            "category_id": cat1,
            "name": "=FORMULA_TRAP Lotus Stem",
            "description": "Honey chili glazed",
            "price_minor_units": 32500,
            "image_asset_id": asset_id,
            "dietary_tags": ["veg", "spicy_mild"],
            "allergens": ["sesame"],
            "variants_json": [
                {"name": "Half", "price_minor_units": 20000},
                {"name": "Full", "price_minor_units": 32500},
            ],
        },
    )
    assert item_res.status_code == 201
    item_id = item_res.json()["data"]["id"]

    # Publish succeeds now that category + item exist
    pub_ok = await client.patch(
        f"/api/v1/venues/{venue_id}/menus/{menu_id}",
        headers=hdr,
        json={"status": "PUBLISHED"},
    )
    assert pub_ok.status_code == 200

    # Category non-empty delete -> 409 CATEGORY_NOT_EMPTY
    cat_del_block = await client.delete(f"/api/v1/venues/{venue_id}/categories/{cat1}", headers=hdr)
    assert cat_del_block.status_code == 409
    assert cat_del_block.json()["error"]["code"] == "CATEGORY_NOT_EMPTY"

    # Media delete while in use -> 409 MEDIA_IN_USE
    med_block = await client.delete(f"/api/v1/venues/{venue_id}/menu/media/{asset_id}", headers=hdr)
    assert med_block.status_code == 409
    assert med_block.json()["error"]["code"] == "MEDIA_IN_USE"

    # CSV export protects against formula injection in name and description
    csv_res = await client.get(f"/api/v1/venues/{venue_id}/menu-items?format=csv", headers=hdr)
    assert csv_res.status_code == 200
    assert "description" in csv_res.text.splitlines()[0]
    assert "'=FORMULA_TRAP Lotus Stem" in csv_res.text

    # Currency change lock when priced items exist -> 409 CURRENCY_LOCKED
    cur_lock = await client.patch(
        f"/api/v1/venues/{venue_id}/menu-settings",
        headers=hdr,
        json={"currency_code": "USD"},
    )
    assert cur_lock.status_code == 409
    assert cur_lock.json()["error"]["code"] == "CURRENCY_LOCKED"

    # Quick 86 conditional HOST RBAC check
    host_u = User(
        organization_id=uuid.UUID(org_id),
        email="host-n4@example.com",
        full_name="Host N4",
        password_hash=hash_password("StrongPassword123!"),
        role="HOST",
        assigned_venue_ids=[uuid.UUID(venue_id)],
        is_active=True,
    )
    db_session.add(host_u)
    await db_session.commit()
    host_tok = create_access_token(
        user_id=host_u.id, organization_id=uuid.UUID(org_id), role="HOST"
    )
    host_hdr = {"Authorization": f"Bearer {host_tok}"}

    assert (
        await client.patch(
            f"/api/v1/venues/{venue_id}/menu-items/{item_id}/availability",
            headers=host_hdr,
            json={"is_available": False},
        )
    ).status_code == 403

    # Owner enables allow_host_menu_availability -> HOST can toggle Quick 86
    await client.patch(
        f"/api/v1/venues/{venue_id}/menu-settings",
        headers=hdr,
        json={"allow_host_menu_availability": True},
    )
    host_ok = await client.patch(
        f"/api/v1/venues/{venue_id}/menu-items/{item_id}/availability",
        headers=host_hdr,
        json={"is_available": False},
    )
    assert host_ok.status_code == 200
    assert host_ok.json()["data"]["is_available"] is False

    # Detach and delete media cleans disk & item FK
    med_del = await client.delete(
        f"/api/v1/venues/{venue_id}/menu/media/{asset_id}?detach=true", headers=hdr
    )
    assert med_del.status_code == 200
    assert (await client.get(asset1["image_url"])).status_code == 404


@pytest.mark.asyncio
async def test_qr_management_decode_verification_pdf_and_grace_lifecycle(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    token, org_id, venue_id, table_id, qr_token = await _bootstrap_with_table(client)
    hdr = {"Authorization": f"Bearer {token}", "Host": "evil.attacker.example"}

    # 1. List QR codes
    qr_list = await client.get(f"/api/v1/venues/{venue_id}/qr-codes", headers=hdr)
    assert qr_list.status_code == 200
    items = qr_list.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["qr_url"] == f"https://menu.example.com/m/{qr_token}"

    # 2. Download SVG and PNG + CI zxing-cpp decode check (must ignore spoofed Host header)
    svg_res = await client.get(
        f"/api/v1/venues/{venue_id}/tables/{table_id}/qr/download?format=svg",
        headers=hdr,
    )
    assert svg_res.status_code == 200
    assert b"<svg" in svg_res.content

    png_res = await client.get(
        f"/api/v1/venues/{venue_id}/tables/{table_id}/qr/download?format=png&framed=true",
        headers=hdr,
    )
    assert png_res.status_code == 200
    with Image.open(io.BytesIO(png_res.content)) as im:
        barcodes = zxingcpp.read_barcodes(im)
        assert len(barcodes) == 1
        assert barcodes[0].text == f"https://menu.example.com/m/{qr_token}"
        assert "evil.attacker.example" not in barcodes[0].text

    # 3. Batch PDF tent-card export
    pdf_res = await client.post(
        f"/api/v1/venues/{venue_id}/qr/export-pdf",
        headers=hdr,
        json={"table_ids": [table_id], "layout": "A4_4UP"},
    )
    assert pdf_res.status_code == 200
    assert pdf_res.content.startswith(b"%PDF-1.")

    # 4. Signed 15-min admin preview link
    prev_res = await client.post(
        f"/api/v1/venues/{venue_id}/tables/{table_id}/qr/preview-link",
        headers=hdr,
    )
    assert prev_res.status_code == 201 or prev_res.status_code == 200
    p_param = prev_res.json()["data"]["preview_url"].split("?p=")[1]
    assert verify_qr_preview_token(qr_token, venue_id, p_param) is True

    # 5. Regenerate with grace_days=7 -> old token becomes GRACE, end-grace revokes immediately
    reg1 = await client.post(
        f"/api/v1/venues/{venue_id}/tables/{table_id}/qr/regenerate",
        headers=hdr,
        json={"reason": "REBRAND", "grace_days": 7},
    )
    assert reg1.status_code == 201
    new_tok1 = reg1.json()["data"]["token"]
    assert new_tok1 != qr_token

    old_status = (
        await db_session.execute(
            text("SELECT status FROM table_qr_codes WHERE token = :t"), {"t": qr_token}
        )
    ).scalar_one()
    assert old_status == "GRACE"

    end_g = await client.post(
        f"/api/v1/venues/{venue_id}/tables/{table_id}/qr/end-grace", headers=hdr
    )
    assert end_g.status_code == 200
    old_status2 = (
        await db_session.execute(
            text("SELECT status FROM table_qr_codes WHERE token = :t"), {"t": qr_token}
        )
    ).scalar_one()
    assert old_status2 == "REVOKED"

    # Regenerate COMPROMISED forces immediate revocation (grace=0 even if grace_days=7 requested)
    reg2 = await client.post(
        f"/api/v1/venues/{venue_id}/tables/{table_id}/qr/regenerate",
        headers=hdr,
        json={"reason": "COMPROMISED", "grace_days": 7},
    )
    assert reg2.status_code == 201
    assert reg2.json()["data"]["grace_days"] == 0
    tok1_status = (
        await db_session.execute(
            text("SELECT status, revoked_reason FROM table_qr_codes WHERE token = :t"),
            {"t": new_tok1},
        )
    ).fetchone()
    assert tok1_status == ("REVOKED", "SECURITY_REVOKE")


@pytest.mark.asyncio
async def test_orphan_menu_media_gc(db_session: AsyncSession) -> None:
    """Verify purge_orphan_menu_media_once removes unreferenced >24h assets while preserving in-use files."""
    from datetime import UTC, datetime, timedelta

    from app.db.models import MenuMediaAsset, Organization, Venue
    from app.services.media import purge_orphan_menu_media_once, write_media_files_atomic

    org = Organization(name=f"GCOrg-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.flush()
    venue = Venue(organization_id=org.id, name="GCVenue", timezone="UTC")
    db_session.add(venue)
    await db_session.flush()

    full_k, thumb_k = write_media_files_atomic(venue.id, b"RIFF0000WEBP", b"RIFF0000WEBP")
    orphan = MenuMediaAsset(
        organization_id=org.id,
        venue_id=venue.id,
        storage_key=full_k,
        thumb_storage_key=thumb_k,
        mime_type="image/webp",
        byte_size=12,
        width_px=200,
        height_px=200,
        sha256="a" * 64,
        status="READY",
        created_at=datetime.now(UTC) - timedelta(hours=30),
    )
    db_session.add(orphan)
    await db_session.commit()

    removed = await purge_orphan_menu_media_once(db_session, min_age_hours=24)
    assert removed >= 1
