"""Shared strict server-side input normalization and validation helpers."""

from __future__ import annotations

import re
import unicodedata

from app.core.errors import AppError

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TABLE_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
_QR_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{22}$")
_PREFIX_RE = re.compile(r"^[A-Za-z0-9_-]{1,10}$")


def clean_text(
    raw: str,
    *,
    max_len: int,
    field: str,
    allow_empty: bool = False,
) -> str:
    """NFC-normalize, reject C0 controls/lone surrogates, trim whitespace, and enforce max length."""
    try:
        raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise AppError(
            400,
            "VALIDATION_ERROR",
            f"Invalid Unicode characters in {field}",
            {field: "invalid unicode"},
        ) from exc

    normalized = unicodedata.normalize("NFC", raw)
    if _CONTROL_RE.search(normalized):
        raise AppError(
            400,
            "VALIDATION_ERROR",
            f"Control characters are not allowed in {field}",
            {field: "control characters forbidden"},
        )
    trimmed = normalized.strip()
    if not allow_empty and not trimmed:
        raise AppError(
            400,
            "VALIDATION_ERROR",
            f"{field} cannot be empty",
            {field: "required"},
        )
    if len(trimmed) > max_len:
        raise AppError(
            400,
            "VALIDATION_ERROR",
            f"{field} exceeds maximum length {max_len}",
            {field: f"max length {max_len}"},
        )
    return trimmed


def clean_optional_text(raw: str | None, *, max_len: int, field: str) -> str | None:
    if raw is None:
        return None
    cleaned = clean_text(raw, max_len=max_len, field=field, allow_empty=True)
    return cleaned or None


def normalize_table_code(raw: str, *, field: str = "table_code") -> str:
    cleaned = clean_text(raw, max_len=20, field=field).upper()
    if not _TABLE_CODE_RE.match(cleaned):
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "table_code must be 1-20 alphanumeric, hyphen, or underscore characters",
            {field: "invalid format (allowed: A-Z, 0-9, -, _)"},
        )
    return cleaned


def is_valid_qr_token(token: str) -> bool:
    return bool(_QR_TOKEN_RE.match(token))


def normalize_bulk_prefix(raw: str) -> str:
    cleaned = clean_text(raw, max_len=10, field="prefix").upper()
    if not _PREFIX_RE.match(cleaned):
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "prefix must be 1-10 alphanumeric, hyphen, or underscore characters",
            {"prefix": "invalid format"},
        )
    return cleaned
