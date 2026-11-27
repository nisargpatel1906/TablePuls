"""Offline QR SVG/PNG/PDF generation (segno + Pillow + reportlab) and HMAC preview tokens."""

from __future__ import annotations

import hashlib
import hmac
import io
import time
import zipfile
from collections.abc import Sequence
from urllib.parse import urlparse

import segno
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4, A6, LETTER
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

from app.config import get_settings


def build_qr_url(token: str) -> str:
    """Strictly construct frozen `/m/{token}` contract from configured PUBLIC_APP_URL only."""
    base = get_settings().public_app_url.rstrip("/")
    return f"{base}/m/{token}"


def short_domain_label() -> str:
    parsed = urlparse(get_settings().public_app_url)
    return parsed.netloc or get_settings().public_app_url


def sign_qr_preview_token(qr_token: str, venue_id: str, ttl_seconds: int = 900) -> str:
    exp = int(time.time()) + ttl_seconds
    secret = get_settings().secret_key.encode("utf-8")
    msg = f"{qr_token}:{venue_id}:{exp}".encode()
    sig = hmac.new(secret, msg, hashlib.sha256).hexdigest()[:32]
    return f"{exp}.{sig}"


def verify_qr_preview_token(qr_token: str, venue_id: str, preview_param: str | None) -> bool:
    if not preview_param or "." not in preview_param:
        return False
    parts = preview_param.split(".", 1)
    try:
        exp = int(parts[0])
    except ValueError:
        return False
    if exp < int(time.time()):
        return False
    secret = get_settings().secret_key.encode("utf-8")
    msg = f"{qr_token}:{venue_id}:{exp}".encode()
    expected_sig = hmac.new(secret, msg, hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(parts[1], expected_sig)


def generate_qr_svg_bytes(url: str, *, scale: int = 8) -> bytes:
    qr = segno.make(url, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=scale, border=4, xmldecl=True, nl=False)
    return buf.getvalue()


def generate_qr_png_bytes(
    url: str,
    *,
    framed: bool = False,
    venue_name: str = "TablePulse",
    table_label: str = "Table",
    size_px: int = 1024,
) -> bytes:
    qr = segno.make(url, error="m")
    raw_buf = io.BytesIO()
    # Reserve padding for framed card layout
    target_qr = int(size_px * 0.62) if framed else size_px
    scale = max(4, target_qr // 37)
    qr.save(raw_buf, kind="png", scale=scale, border=4)
    raw_buf.seek(0)

    if not framed:
        with Image.open(raw_buf) as im:
            resized = im.convert("RGB").resize((size_px, size_px), Image.Resampling.NEAREST)
            out = io.BytesIO()
            resized.save(out, format="PNG")
            return out.getvalue()

    card = Image.new("RGB", (size_px, size_px), (255, 255, 255))
    draw = ImageDraw.Draw(card)
    font_lg = ImageFont.load_default(size=max(24, size_px // 24))
    font_md = ImageFont.load_default(size=max(18, size_px // 32))
    font_sm = ImageFont.load_default(size=max(14, size_px // 44))

    # Border
    pad = max(20, size_px // 32)
    draw.rounded_rectangle(
        [pad, pad, size_px - pad, size_px - pad],
        radius=max(18, size_px // 36),
        outline=(28, 28, 30),
        width=max(3, size_px // 256),
    )

    draw.text(
        (size_px // 2, int(size_px * 0.10)),
        venue_name[:32],
        fill=(28, 28, 30),
        font=font_lg,
        anchor="mm",
    )
    draw.text(
        (size_px // 2, int(size_px * 0.17)),
        table_label[:28],
        fill=(0, 98, 204),
        font=font_md,
        anchor="mm",
    )

    with Image.open(raw_buf) as im:
        qr_img = im.convert("RGB").resize((target_qr, target_qr), Image.Resampling.NEAREST)
        qr_x = (size_px - target_qr) // 2
        qr_y = int(size_px * 0.22)
        card.paste(qr_img, (qr_x, qr_y))

    draw.text(
        (size_px // 2, int(size_px * 0.88)),
        "Scan for Digital Menu",
        fill=(28, 28, 30),
        font=font_md,
        anchor="mm",
    )
    draw.text(
        (size_px // 2, int(size_px * 0.93)),
        short_domain_label(),
        fill=(99, 99, 102),
        font=font_sm,
        anchor="mm",
    )

    out = io.BytesIO()
    card.save(out, format="PNG")
    return out.getvalue()


def generate_qr_pdf_bytes(
    cards: Sequence[tuple[str, str, str]],
    *,
    venue_name: str,
    layout: str = "A4_4UP",
) -> bytes:
    """
    Generate multi-table cut-guided PDF tent-card sheet via reportlab.
    Each card tuple: (table_code, table_label, url).
    """
    page_size = LETTER if layout == "LETTER_4UP" else (A6 if layout == "A6_1UP" else A4)
    if layout == "A6_1UP":
        cols, rows = 1, 1
        margin_x = 8 * mm
        margin_y = 8 * mm
    elif layout == "A4_STICKER_12UP":
        cols, rows = 3, 4
        margin_x = 8 * mm
        margin_y = 8 * mm
    elif layout == "A4_6UP":
        cols, rows = 2, 3
        margin_x = 12 * mm
        margin_y = 12 * mm
    else:
        cols, rows = 2, 2
        margin_x = 12 * mm
        margin_y = 12 * mm
    per_page = cols * rows

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=page_size)
    page_w, page_h = page_size
    cell_w = (page_w - 2 * margin_x) / cols
    cell_h = (page_h - 2 * margin_y) / rows

    domain_hint = short_domain_label()
    safe_venue = venue_name.encode("latin-1", "replace").decode("latin-1")[:34]

    for idx, (_code, label, url) in enumerate(cards):
        if idx > 0 and idx % per_page == 0:
            c.showPage()
        slot = idx % per_page
        col_i = slot % cols
        row_i = slot // cols
        x0 = margin_x + col_i * cell_w
        y0 = page_h - margin_y - (row_i + 1) * cell_h

        # Cut-guide dashed rectangle
        c.saveState()
        c.setDash(4, 3)
        c.setStrokeColorRGB(0.6, 0.6, 0.65)
        c.rect(x0 + 3 * mm, y0 + 3 * mm, cell_w - 6 * mm, cell_h - 6 * mm)
        c.restoreState()

        cx = x0 + cell_w / 2.0
        safe_label = label.encode("latin-1", "replace").decode("latin-1")[:28]

        c.setFont("Helvetica-Bold", 11)
        c.setFillColorRGB(0.11, 0.11, 0.12)
        c.drawCentredString(cx, y0 + cell_h - 14 * mm, safe_venue)

        c.setFont("Helvetica-Bold", 13)
        c.setFillColorRGB(0.0, 0.38, 0.80)
        c.drawCentredString(cx, y0 + cell_h - 21 * mm, safe_label)

        qr_png = generate_qr_png_bytes(url, framed=False, size_px=512)
        qr_side = min(cell_w - 22 * mm, cell_h - 42 * mm)
        c.drawImage(
            ImageReader(io.BytesIO(qr_png)),
            cx - qr_side / 2.0,
            y0 + 18 * mm,
            width=qr_side,
            height=qr_side,
        )

        c.setFont("Helvetica-Bold", 9)
        c.setFillColorRGB(0.11, 0.11, 0.12)
        c.drawCentredString(cx, y0 + 12 * mm, "Scan for Menu")

        c.setFont("Helvetica", 7.5)
        c.setFillColorRGB(0.39, 0.39, 0.42)
        c.drawCentredString(cx, y0 + 7 * mm, domain_hint)

    c.save()
    return buf.getvalue()


def generate_qr_zip_bytes(
    cards: Sequence[tuple[str, str, str]],
    *,
    venue_name: str,
    fmt: str = "png",
    framed: bool = True,
) -> bytes:
    """Generate in-memory ZIP archive containing SVG and/or framed PNG QR files for selected tables."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for table_code, label, url in cards:
            safe_code = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in table_code)
            if fmt in ("svg", "both"):
                zf.writestr(f"qr-{safe_code}.svg", generate_qr_svg_bytes(url))
            if fmt in ("png", "both"):
                zf.writestr(
                    f"qr-{safe_code}.png",
                    generate_qr_png_bytes(
                        url,
                        framed=framed,
                        venue_name=venue_name,
                        table_label=label,
                        size_px=1024,
                    ),
                )
    return buf.getvalue()
