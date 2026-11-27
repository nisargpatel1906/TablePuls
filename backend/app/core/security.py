"""Cryptographic, password hashing, JWT, TOTP, and AES-256-GCM helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from zxcvbn import zxcvbn

from app.config import get_settings
from app.core.errors import AppError

_ARGON2 = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

_COMMON_BREACHED = {
    "password1234",
    "123456789012",
    "qwertyuiop12",
    "letmein12345",
    "tablepulse123",
    "admin1234567",
}


def validate_password_strength(password: str) -> None:
    """Enforce >= 12 chars, non-breached, and zxcvbn >= 3 (docs/03 & docs/08)."""
    if len(password) < 12:
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "Password does not meet security policy",
            {"password": "must be at least 12 characters long"},
        )
    if password.lower() in _COMMON_BREACHED:
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "Password does not meet security policy",
            {"password": "cannot use a commonly breached password"},
        )
    strength = zxcvbn(password)
    if int(strength["score"]) < 3:
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "Password is too weak",
            {"password": "choose a stronger passphrase (score >= 3)"},
        )


def hash_password(password: str) -> str:
    return _ARGON2.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bool(_ARGON2.verify(password_hash, password))
    except VerifyMismatchError:
        return False


def generate_opaque_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hex_digest)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    role: str,
    jti: str | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org_id": str(organization_id),
        "role": role,
        "token_type": "access",
        "jti": jti or str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "iat_ms": int(now.timestamp() * 1000),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AppError(401, "AUTH_UNAUTHORIZED", "Invalid or expired access token") from exc
    if payload.get("token_type") != "access":
        raise AppError(401, "AUTH_UNAUTHORIZED", "Invalid token type")
    return dict(payload)


def _derive_aes_key() -> bytes:
    raw = get_settings().data_key.strip()
    try:
        decoded = base64.b64decode(raw, validate=True)
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt_field(plaintext: str, aad: bytes = b"tablepulse-v1") -> bytes:
    """Encrypt sensitive field using AES-256-GCM (nonce || ciphertext)."""
    key = _derive_aes_key()
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), aad)
    return nonce + ct


def decrypt_field(blob: bytes, aad: bytes = b"tablepulse-v1") -> str:
    """Decrypt AES-256-GCM field encrypted by encrypt_field."""
    if len(blob) < 13:
        raise ValueError("Encrypted payload too short")
    key = _derive_aes_key()
    nonce, ct = blob[:12], blob[12:]
    pt = AESGCM(key).decrypt(nonce, ct, aad)
    return pt.decode("utf-8")


def verify_totp(secret_base32: str, code: str) -> bool:
    return bool(pyotp.TOTP(secret_base32).verify(code, valid_window=1))


def create_stream_token(
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    venue_id: uuid.UUID,
    camera_id: uuid.UUID,
    action: str = "read",
    ttl_seconds: int = 120,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "org_id": str(organization_id),
        "venue_id": str(venue_id),
        "camera_id": str(camera_id),
        "action": action,
        "token_type": "stream",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.mediamtx_hook_secret, algorithm="HS256")


def verify_stream_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.mediamtx_hook_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AppError(403, "AUTH_FORBIDDEN", "Invalid or expired stream token") from exc
    if payload.get("token_type") != "stream":
        raise AppError(403, "AUTH_FORBIDDEN", "Invalid stream token type")
    return dict(payload)


def sign_webhook_payload(secret: str, payload_bytes: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"
