"""Server-validated Pillow WebP media pipeline with magic-byte checks, EXIF stripping, and SHA-256 deduplication."""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
import uuid
from pathlib import Path

from PIL import Image, ImageOps

from app.config import get_settings
from app.core.errors import AppError

Image.MAX_IMAGE_PIXELS = 25_000_000

MAX_MEDIA_BYTES = 5 * 1024 * 1024
MIN_DIM_PX = 200


def detect_allowed_image_format(raw: bytes) -> str | None:
    """Inspect magic bytes strictly (never trust Content-Type or filename)."""
    head = raw[:64].lstrip()
    head_l = head.lower()
    if head_l.startswith(b"<svg") or head_l.startswith(b"<?xml") or b"<script" in raw[:512].lower():
        return None
    if raw.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "WEBP"
    return None


def transcode_to_webp(raw: bytes) -> tuple[bytes, bytes, int, int, str]:
    """Validate, strip EXIF/ICC/XMP metadata, and encode 800px full + 320px thumb WebP."""
    if len(raw) == 0:
        raise AppError(400, "VALIDATION_ERROR", "Empty image upload")
    if len(raw) > MAX_MEDIA_BYTES:
        raise AppError(413, "PAYLOAD_TOO_LARGE", "Image upload exceeds 5 MB limit")

    fmt = detect_allowed_image_format(raw)
    if fmt is None:
        raise AppError(
            400,
            "UNSUPPORTED_MEDIA_TYPE",
            "Only valid JPEG, PNG, or WebP images are permitted",
        )

    sha256 = hashlib.sha256(raw).hexdigest()

    try:
        with Image.open(io.BytesIO(raw)) as opened:
            opened.verify()
        with Image.open(io.BytesIO(raw)) as img:
            img.load()
            width, height = img.size
            if width < MIN_DIM_PX or height < MIN_DIM_PX:
                raise AppError(
                    400,
                    "VALIDATION_ERROR",
                    f"Image dimensions must be at least {MIN_DIM_PX}x{MIN_DIM_PX} pixels",
                    {"file": f"minimum {MIN_DIM_PX}x{MIN_DIM_PX} px required"},
                )

            transposed = ImageOps.exif_transpose(img)
            mode = "RGBA" if transposed.mode in {"RGBA", "LA", "PA"} else "RGB"
            # Reconstruct pixel buffer cleanly so zero EXIF / ICC / XMP metadata carries over
            clean = Image.new(mode, transposed.size)
            clean.paste(transposed.convert(mode))

            full_img = clean.copy()
            full_img.thumbnail((800, 800), Image.Resampling.LANCZOS)
            full_buf = io.BytesIO()
            full_img.save(full_buf, format="WEBP", quality=82, method=4)
            full_bytes = full_buf.getvalue()

            thumb_img = ImageOps.fit(clean, (320, 320), Image.Resampling.LANCZOS)
            thumb_buf = io.BytesIO()
            thumb_img.save(thumb_buf, format="WEBP", quality=78, method=4)
            thumb_bytes = thumb_buf.getvalue()

            out_w, out_h = full_img.size
            return full_bytes, thumb_bytes, out_w, out_h, sha256
    except AppError:
        raise
    except Image.DecompressionBombError as exc:
        raise AppError(
            400,
            "UNSUPPORTED_MEDIA_TYPE",
            "Image pixel count exceeds safety limit (25 MP)",
        ) from exc
    except Exception as exc:
        raise AppError(
            400,
            "UNSUPPORTED_MEDIA_TYPE",
            "Invalid or corrupted image file",
        ) from exc


def write_media_files_atomic(
    venue_id: uuid.UUID, full_bytes: bytes, thumb_bytes: bytes
) -> tuple[str, str]:
    """Persist WebP assets atomically with restrictive file modes and clean temp cleanup."""
    root = Path(get_settings().menu_media_dir).resolve()
    venue_dir = root / str(venue_id)
    venue_dir.mkdir(parents=True, exist_ok=True)

    asset_uid = uuid.uuid4().hex
    full_name = f"{asset_uid}.webp"
    thumb_name = f"{asset_uid}_thumb.webp"
    full_path = venue_dir / full_name
    thumb_path = venue_dir / thumb_name

    for dest, payload in ((full_path, full_bytes), (thumb_path, thumb_bytes)):
        fd, tmp_name = tempfile.mkstemp(prefix=".tmp_", suffix=".webp", dir=str(venue_dir))
        try:
            os.chmod(tmp_name, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
            os.replace(tmp_name, dest)
            os.chmod(dest, 0o644)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    return f"{venue_id}/{full_name}", f"{venue_id}/{thumb_name}"


def delete_media_files(storage_key: str, thumb_storage_key: str) -> None:
    root = Path(get_settings().menu_media_dir).resolve()
    for key in (storage_key, thumb_storage_key):
        cand = (root / key).resolve()
        if cand.is_relative_to(root):
            cand.unlink(missing_ok=True)
