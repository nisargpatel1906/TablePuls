"""Auth endpoints: API-001 through API-006 plus bootstrap status & invite accept."""

from __future__ import annotations

import base64
import io
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import pyotp
import segno
from fastapi import APIRouter, Body, Cookie, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import AppError, success_response
from app.core.rbac import get_current_user
from app.core.security import (
    create_access_token,
    decode_access_token,
    decrypt_field,
    encrypt_field,
    generate_opaque_token,
    hash_password,
    hash_token,
    validate_password_strength,
    verify_password,
    verify_totp,
)
from app.core.valkey_client import (
    check_and_store_idempotency,
    check_rate_limit,
    get_valkey,
    is_user_revoked,
    mark_user_revoked,
)
from app.db.base import get_db, uuid7
from app.db.models import (
    Camera,
    DiningTable,
    Organization,
    RefreshToken,
    SystemSetting,
    User,
    Venue,
)
from app.schemas.auth import (
    AcceptInviteRequest,
    BootstrapRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    TwoFAEnrollRequest,
    TwoFAReAuthRequest,
    TwoFAVerifyEnrollRequest,
    TwoFAVerifyLoginRequest,
)
from app.services.audit import write_audit_log
from app.services.email import send_email_if_configured

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "tp_refresh_token"
_local_ws_tickets: dict[str, dict[str, str]] = {}


def _is_prod_env() -> bool:
    settings = get_settings()
    return (
        settings.app_env.lower() == "production" or settings.tablepulse_env.lower() == "production"
    )


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if fwd:
        return fwd
    return request.client.host if request.client else "unknown"


def _set_refresh_cookie(response: JSONResponse, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=_is_prod_env(),
        samesite="strict",
        path="/api/v1/auth",
        max_age=settings.refresh_token_expire_days * 86400,
    )


def _clear_refresh_cookie(response: JSONResponse) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
        httponly=True,
        secure=_is_prod_env(),
        samesite="strict",
    )


def _user_dict(user: User) -> dict[str, object]:
    return {
        "id": str(user.id),
        "organization_id": str(user.organization_id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "assigned_venue_ids": [str(v) for v in (user.assigned_venue_ids or [])],
        "is_active": user.is_active,
        "totp_enabled": bool(user.totp_enabled),
        "recovery_codes_remaining": len(user.totp_recovery_codes_json or []),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


_RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_recovery_codes(count: int = 8) -> tuple[list[str], list[str]]:
    plain: list[str] = []
    hashed: list[str] = []
    for _ in range(count):
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(8))
        formatted = f"{raw[:4]}-{raw[4:]}"
        plain.append(formatted)
        hashed.append(hash_password(formatted))
    return plain, hashed


def _verify_and_consume_2fa_code(user: User, raw_code: str) -> str | None:
    """Verify either 6-digit TOTP or single-use recovery code; returns method or None."""
    cleaned = raw_code.strip()
    if cleaned.isdigit() and len(cleaned) == 6 and user.totp_secret_encrypted:
        secret_b32 = decrypt_field(user.totp_secret_encrypted)
        if verify_totp(secret_b32, cleaned):
            return "totp"

    norm = cleaned.upper().replace(" ", "")
    if len(norm) == 8 and "-" not in norm:
        norm = f"{norm[:4]}-{norm[4:]}"
    stored = list(user.totp_recovery_codes_json or [])
    for idx, code_hash in enumerate(stored):
        if verify_password(norm, code_hash):
            del stored[idx]
            user.totp_recovery_codes_json = stored
            return "recovery"
    return None


async def _issue_login_session(
    db: AsyncSession,
    user: User,
    request: Request,
    *,
    action: str = "USER_LOGIN",
    after_json: dict[str, object] | None = None,
) -> JSONResponse:
    raw_refresh, hash_refresh = generate_opaque_token()
    family_id = uuid7()
    db.add(
        RefreshToken(
            id=uuid7(),
            organization_id=user.organization_id,
            user_id=user.id,
            token_type="REFRESH",
            token_family_id=family_id,
            token_hash=hash_refresh,
            expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_expire_days),
        )
    )
    user.last_login_at = datetime.now(UTC)
    await write_audit_log(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action=action,
        target_type="user",
        target_id=user.id,
        after_json=after_json,
        request=request,
    )
    await db.commit()

    access_token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
    )
    resp = success_response(
        {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": get_settings().access_token_expire_minutes * 60,
            "user": _user_dict(user),
        }
    )
    _set_refresh_cookie(resp, raw_refresh)
    return resp


async def _resolve_user_or_setup_challenge(
    db: AsyncSession,
    request: Request,
    challenge_token: str | None,
) -> tuple[User, RefreshToken | None]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token:
            payload = decode_access_token(token)
            try:
                user_id = uuid.UUID(str(payload["sub"]))
                org_id = uuid.UUID(str(payload["org_id"]))
            except (KeyError, ValueError) as exc:
                raise AppError(401, "AUTH_UNAUTHORIZED", "Malformed token claims") from exc
            if await is_user_revoked(str(user_id), int(payload.get("iat", 0))):
                raise AppError(401, "AUTH_UNAUTHORIZED", "Session has been revoked")
            user = (
                await db.execute(
                    select(User).where(User.id == user_id, User.organization_id == org_id)
                )
            ).scalar_one_or_none()
            if user is None or not user.is_active:
                raise AppError(401, "AUTH_UNAUTHORIZED", "Account inactive or not found")
            return user, None

    if challenge_token:
        now = datetime.now(UTC)
        tok = (
            await db.execute(
                select(RefreshToken).where(
                    RefreshToken.token_hash == hash_token(challenge_token),
                    RefreshToken.token_type == "2FA_CHALLENGE",
                )
            )
        ).scalar_one_or_none()
        if (
            tok is None
            or tok.revoked_at is not None
            or tok.expires_at <= now
            or (tok.metadata_json or {}).get("purpose") != "SETUP"
            or tok.user_id is None
        ):
            raise AppError(401, "AUTH_UNAUTHORIZED", "Invalid or expired 2FA setup challenge")
        user = (await db.execute(select(User).where(User.id == tok.user_id))).scalar_one_or_none()
        if user is None or not user.is_active:
            raise AppError(401, "AUTH_UNAUTHORIZED", "Account inactive or not found")
        return user, tok

    raise AppError(401, "AUTH_UNAUTHORIZED", "Authentication required")


@router.get("/bootstrap-status")
async def bootstrap_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    tp_refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> JSONResponse:
    """Public check returning whether initial OWNER bootstrap is required and session presence."""
    settings = get_settings()
    count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    return success_response(
        {
            "bootstrap_required": int(count) == 0,
            "demo_mode": settings.demo_mode,
            "has_session": bool(tp_refresh_token),
        }
    )


@router.post("/bootstrap", status_code=201)
async def bootstrap_owner(
    body: BootstrapRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-001: One-time atomic organization + OWNER creation when users count == 0."""
    validate_password_strength(body.password)

    if db.bind and db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(7421001)"))

    existing_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    if int(existing_count) > 0:
        raise AppError(403, "AUTH_FORBIDDEN", "Bootstrap is disabled after initial owner exists")

    org = Organization(id=uuid7(), name=body.organization_name.strip())
    db.add(org)
    await db.flush()

    settings_row = SystemSetting(
        organization_id=org.id,
        ai_inference_enabled=get_settings().ai_inference_enabled,
        face_blur_enforced=True,
        snapshot_retention_days=7,
        analytics_retention_days=365,
    )
    db.add(settings_row)

    owner = User(
        id=uuid7(),
        organization_id=org.id,
        email=body.email.lower().strip(),
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
        role="OWNER",
        assigned_venue_ids=[],
        is_active=True,
        last_login_at=datetime.now(UTC),
    )
    db.add(owner)
    await db.flush()

    raw_refresh, hash_refresh = generate_opaque_token()
    family_id = uuid7()
    db.add(
        RefreshToken(
            id=uuid7(),
            organization_id=org.id,
            user_id=owner.id,
            token_type="REFRESH",
            token_family_id=family_id,
            token_hash=hash_refresh,
            expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_expire_days),
        )
    )
    await write_audit_log(
        db,
        organization_id=org.id,
        actor_user_id=owner.id,
        action="BOOTSTRAP_OWNER",
        target_type="user",
        target_id=owner.id,
        after_json={"email": owner.email, "role": "OWNER"},
        request=request,
    )
    await db.commit()
    await db.refresh(owner)

    access_token = create_access_token(
        user_id=owner.id,
        organization_id=org.id,
        role=owner.role,
    )
    resp = success_response(
        {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": get_settings().access_token_expire_minutes * 60,
            "user": _user_dict(owner),
        },
        status_code=201,
    )
    _set_refresh_cookie(resp, raw_refresh)
    return resp


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-002: Email/password Argon2id login with rate limiting and HttpOnly refresh cookie."""
    client_ip = _client_ip(request)
    email_norm = body.email.lower().strip()

    ip_ok, ip_retry = await check_rate_limit(f"login:ip:{client_ip}", 10, 60, fail_closed=True)
    if not ip_ok:
        raise AppError(
            429,
            "RATE_LIMITED",
            "Too many login attempts. Please wait and try again.",
            headers={"Retry-After": str(ip_retry)},
        )

    acct_fail_key = f"login:fail:{email_norm}"
    acct_ok, acct_retry = await check_rate_limit(
        acct_fail_key, 5, 900, fail_closed=True, increment=False
    )
    if not acct_ok:
        raise AppError(
            429,
            "RATE_LIMITED",
            "Too many failed login attempts for this account.",
            headers={"Retry-After": str(acct_retry)},
        )

    res = await db.execute(select(User).where(User.email == email_norm))
    user = res.scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        await check_rate_limit(acct_fail_key, 5, 900, fail_closed=True, increment=True)
        raise AppError(401, "AUTH_INVALID_CREDENTIALS", "Invalid email or password")

    sys_set = (
        await db.execute(
            select(SystemSetting).where(SystemSetting.organization_id == user.organization_id)
        )
    ).scalar_one_or_none()

    if user.totp_enabled and user.totp_secret_encrypted:
        if body.totp_code:
            method = _verify_and_consume_2fa_code(user, body.totp_code)
            if method is None:
                await check_rate_limit(acct_fail_key, 5, 900, fail_closed=True, increment=True)
                raise AppError(401, "AUTH_INVALID_CREDENTIALS", "Invalid authentication code")
            return await _issue_login_session(
                db,
                user,
                request,
                action="TWO_FACTOR_RECOVERY_USED" if method == "recovery" else "USER_LOGIN",
            )
        raw_ch, ch_hash = generate_opaque_token()
        db.add(
            RefreshToken(
                id=uuid7(),
                organization_id=user.organization_id,
                user_id=user.id,
                token_type="2FA_CHALLENGE",
                token_family_id=uuid7(),
                token_hash=ch_hash,
                metadata_json={"purpose": "LOGIN"},
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
        )
        await db.commit()
        return success_response(
            {
                "requires_2fa": True,
                "challenge_token": raw_ch,
                "expires_in": 300,
            }
        )

    if sys_set is not None and user.role in (sys_set.require_2fa_roles or []):
        raw_ch, ch_hash = generate_opaque_token()
        db.add(
            RefreshToken(
                id=uuid7(),
                organization_id=user.organization_id,
                user_id=user.id,
                token_type="2FA_CHALLENGE",
                token_family_id=uuid7(),
                token_hash=ch_hash,
                metadata_json={"purpose": "SETUP"},
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )
        )
        await db.commit()
        return success_response(
            {
                "requires_2fa_setup": True,
                "challenge_token": raw_ch,
                "expires_in": 600,
                "role": user.role,
            }
        )

    return await _issue_login_session(db, user, request)


@router.post("/2fa/verify")
async def verify_two_factor_login(
    body: TwoFAVerifyLoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Verify TOTP or single-use recovery code against a login challenge token."""
    client_ip = _client_ip(request)
    ip_ok, ip_retry = await check_rate_limit(f"2fa:ip:{client_ip}", 20, 60, fail_closed=True)
    if not ip_ok:
        raise AppError(
            429,
            "RATE_LIMITED",
            "Too many 2FA verification attempts. Please wait and try again.",
            headers={"Retry-After": str(ip_retry)},
        )

    ch_hash = hash_token(body.challenge_token)
    ch_fail_key = f"2fa:fail:{ch_hash[:16]}"
    allowed, retry_after = await check_rate_limit(
        ch_fail_key, 5, 300, fail_closed=True, increment=False
    )
    if not allowed:
        raise AppError(
            429,
            "RATE_LIMITED",
            "Too many failed 2FA attempts. Sign in again.",
            headers={"Retry-After": str(retry_after)},
        )

    now = datetime.now(UTC)
    tok = (
        await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == ch_hash,
                RefreshToken.token_type == "2FA_CHALLENGE",
            )
        )
    ).scalar_one_or_none()
    if (
        tok is None
        or tok.revoked_at is not None
        or tok.expires_at <= now
        or (tok.metadata_json or {}).get("purpose") != "LOGIN"
        or tok.user_id is None
    ):
        raise AppError(401, "AUTH_INVALID_CREDENTIALS", "Invalid or expired 2FA challenge")

    user = (await db.execute(select(User).where(User.id == tok.user_id))).scalar_one_or_none()
    if user is None or not user.is_active or not user.totp_enabled:
        raise AppError(401, "AUTH_INVALID_CREDENTIALS", "Invalid authentication state")

    method = _verify_and_consume_2fa_code(user, body.code)
    if method is None:
        await check_rate_limit(ch_fail_key, 5, 300, fail_closed=True, increment=True)
        raise AppError(401, "AUTH_INVALID_CREDENTIALS", "Invalid verification or recovery code")

    tok.revoked_at = now
    return await _issue_login_session(
        db,
        user,
        request,
        action="TWO_FACTOR_RECOVERY_USED" if method == "recovery" else "USER_LOGIN",
        after_json={"two_factor_method": method},
    )


@router.post("/2fa/enroll")
async def enroll_two_factor(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[TwoFAEnrollRequest | None, Body()] = None,
) -> JSONResponse:
    """Start TOTP enrollment: returns offline QR SVG + Base32 manual key + enroll_token."""
    challenge_token = body.challenge_token if body else None
    user, _setup_tok = await _resolve_user_or_setup_challenge(db, request, challenge_token)

    secret = pyotp.random_base32()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="TablePulse")
    qr = segno.make(uri, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=5, border=2, xmldecl=False)
    svg_bytes = buf.getvalue()
    svg_text = svg_bytes.decode("utf-8")
    qr_svg_data_uri = f"data:image/svg+xml;base64,{base64.b64encode(svg_bytes).decode('ascii')}"

    raw_enroll, enroll_hash = generate_opaque_token()
    db.add(
        RefreshToken(
            id=uuid7(),
            organization_id=user.organization_id,
            user_id=user.id,
            token_type="2FA_CHALLENGE",
            token_family_id=uuid7(),
            token_hash=enroll_hash,
            metadata_json={
                "purpose": "ENROLL",
                "secret_enc": base64.b64encode(encrypt_field(secret)).decode("ascii"),
            },
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    await db.commit()
    return success_response(
        {
            "enroll_token": raw_enroll,
            "secret": secret,
            "provisioning_uri": uri,
            "qr_svg_data_uri": qr_svg_data_uri,
            "qr_svg": svg_text,
            "expires_in": 600,
        }
    )


@router.post("/2fa/verify-enroll")
async def verify_enroll_two_factor(
    body: TwoFAVerifyEnrollRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Verify initial TOTP code, activate 2FA, and issue 8 one-time recovery codes."""
    user, setup_tok = await _resolve_user_or_setup_challenge(db, request, body.challenge_token)
    now = datetime.now(UTC)
    enroll_tok = (
        await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_token(body.enroll_token),
                RefreshToken.token_type == "2FA_CHALLENGE",
                RefreshToken.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if (
        enroll_tok is None
        or enroll_tok.revoked_at is not None
        or enroll_tok.expires_at <= now
        or (enroll_tok.metadata_json or {}).get("purpose") != "ENROLL"
    ):
        raise AppError(400, "TOKEN_EXPIRED", "Enrollment token is invalid or expired")

    secret_enc_b64 = str((enroll_tok.metadata_json or {}).get("secret_enc", ""))
    secret = decrypt_field(base64.b64decode(secret_enc_b64))
    code_clean = body.code.strip()
    if not code_clean.isdigit() or len(code_clean) != 6 or not verify_totp(secret, code_clean):
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "Invalid 6-digit verification code",
            {"code": "invalid 6-digit authenticator code"},
        )

    plain_codes, hashed_codes = _generate_recovery_codes(8)
    user.totp_enabled = True
    user.totp_secret_encrypted = encrypt_field(secret)
    user.totp_recovery_codes_json = hashed_codes
    enroll_tok.revoked_at = now

    if setup_tok is not None:
        setup_tok.revoked_at = now
        raw_refresh, hash_refresh = generate_opaque_token()
        db.add(
            RefreshToken(
                id=uuid7(),
                organization_id=user.organization_id,
                user_id=user.id,
                token_type="REFRESH",
                token_family_id=uuid7(),
                token_hash=hash_refresh,
                expires_at=now + timedelta(days=get_settings().refresh_token_expire_days),
            )
        )
        user.last_login_at = now
        await write_audit_log(
            db,
            organization_id=user.organization_id,
            actor_user_id=user.id,
            action="TWO_FACTOR_ENABLED",
            target_type="user",
            target_id=user.id,
            after_json={"enforced_setup": True},
            request=request,
        )
        await db.commit()
        access_token = create_access_token(
            user_id=user.id,
            organization_id=user.organization_id,
            role=user.role,
        )
        resp = success_response(
            {
                "totp_enabled": True,
                "recovery_codes": plain_codes,
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": get_settings().access_token_expire_minutes * 60,
                "user": _user_dict(user),
            }
        )
        _set_refresh_cookie(resp, raw_refresh)
        return resp

    await write_audit_log(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action="TWO_FACTOR_ENABLED",
        target_type="user",
        target_id=user.id,
        after_json={"enforced_setup": False},
        request=request,
    )
    await db.commit()
    return success_response(
        {
            "totp_enabled": True,
            "recovery_codes": plain_codes,
            "user": _user_dict(user),
        }
    )


@router.post("/2fa/recovery-codes")
async def regenerate_recovery_codes(
    body: TwoFAReAuthRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Regenerate 8 one-time recovery codes (requires current password + TOTP)."""
    if not user.totp_enabled or not user.totp_secret_encrypted:
        raise AppError(400, "VALIDATION_ERROR", "Two-factor authentication is not enabled")
    if not verify_password(body.password, user.password_hash):
        raise AppError(401, "AUTH_INVALID_CREDENTIALS", "Invalid password")
    secret = decrypt_field(user.totp_secret_encrypted)
    if not verify_totp(secret, body.code.strip()):
        raise AppError(401, "AUTH_INVALID_CREDENTIALS", "Invalid authenticator code")

    plain_codes, hashed_codes = _generate_recovery_codes(8)
    user.totp_recovery_codes_json = hashed_codes
    await write_audit_log(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action="TWO_FACTOR_RECOVERY_REGENERATED",
        target_type="user",
        target_id=user.id,
        request=request,
    )
    await db.commit()
    return success_response(
        {
            "recovery_codes": plain_codes,
            "user": _user_dict(user),
        }
    )


@router.post("/2fa/disable")
async def disable_two_factor(
    body: TwoFAReAuthRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Disable TOTP 2FA with password + code re-auth unless blocked by org role policy."""
    if not user.totp_enabled:
        raise AppError(400, "VALIDATION_ERROR", "Two-factor authentication is already disabled")
    if not verify_password(body.password, user.password_hash):
        raise AppError(401, "AUTH_INVALID_CREDENTIALS", "Invalid password")
    if _verify_and_consume_2fa_code(user, body.code) is None:
        raise AppError(401, "AUTH_INVALID_CREDENTIALS", "Invalid authenticator or recovery code")

    sys_set = (
        await db.execute(
            select(SystemSetting).where(SystemSetting.organization_id == user.organization_id)
        )
    ).scalar_one_or_none()
    if sys_set is not None and user.role in (sys_set.require_2fa_roles or []):
        raise AppError(
            403,
            "POLICY_REQUIRED",
            f"Organization policy requires 2FA for role {user.role}",
        )

    user.totp_enabled = False
    user.totp_secret_encrypted = None
    user.totp_recovery_codes_json = []
    await write_audit_log(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action="TWO_FACTOR_DISABLED",
        target_type="user",
        target_id=user.id,
        request=request,
    )
    await db.commit()
    return success_response({"totp_enabled": False, "user": _user_dict(user)})


@router.post("/demo-login")
async def demo_login(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """One-click Demo Manager session when DEMO_MODE=true; 403 otherwise."""
    settings = get_settings()
    if not settings.demo_mode:
        raise AppError(403, "AUTH_FORBIDDEN", "Demo mode is disabled")

    client_ip = _client_ip(request)
    ip_ok, ip_retry = await check_rate_limit(f"demo-login:ip:{client_ip}", 20, 60, fail_closed=True)
    if not ip_ok:
        raise AppError(
            429,
            "RATE_LIMITED",
            "Too many demo login requests. Please wait and try again.",
            headers={"Retry-After": str(ip_retry)},
        )

    demo_email = "manager@example.com"
    user = (await db.execute(select(User).where(User.email == demo_email))).scalar_one_or_none()
    if user is None:
        org = (
            await db.execute(
                select(Organization).where(
                    Organization.name == "TablePulse Demo Hospitality",
                    Organization.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if org is None:
            org = Organization(id=uuid7(), name="TablePulse Demo Hospitality")
            db.add(org)
            await db.flush()
            db.add(
                SystemSetting(
                    organization_id=org.id,
                    ai_inference_enabled=True,
                    face_blur_enforced=True,
                    snapshot_retention_days=7,
                    analytics_retention_days=365,
                )
            )

        venue = (
            await db.execute(
                select(Venue)
                .where(Venue.organization_id == org.id, Venue.deleted_at.is_(None))
                .limit(1)
            )
        ).scalar_one_or_none()
        if venue is None:
            venue = Venue(
                id=uuid7(),
                organization_id=org.id,
                name="Downtown Bistro",
                timezone="America/New_York",
                allow_host_camera_view=True,
            )
            db.add(venue)
            await db.flush()

            cam = Camera(
                id=uuid7(),
                organization_id=org.id,
                venue_id=venue.id,
                name="Main Floor Cam 1",
                stream_type="DEMO_MP4",
                stream_url_encrypted=encrypt_field("demo://sample_floor.mp4"),
                target_fps=2,
                face_blur_enabled=True,
                status="ONLINE",
            )
            db.add(cam)
            await db.flush()

            now = datetime.now(UTC)
            demo_tables = [
                (
                    "T1",
                    "Main",
                    4,
                    [[0.08, 0.14], [0.28, 0.14], [0.28, 0.38], [0.08, 0.38]],
                    0.18,
                    0.26,
                    "RECT",
                    "OCCUPIED",
                    2,
                    0.91,
                    now - timedelta(minutes=24),
                ),
                (
                    "T2",
                    "Main",
                    2,
                    [[0.36, 0.14], [0.54, 0.14], [0.54, 0.38], [0.36, 0.38]],
                    0.45,
                    0.26,
                    "CIRCLE",
                    "NEEDS_CLEANING",
                    0,
                    0.88,
                    None,
                ),
                (
                    "T3",
                    "Patio",
                    6,
                    [[0.62, 0.18], [0.86, 0.18], [0.86, 0.44], [0.62, 0.44]],
                    0.74,
                    0.31,
                    "BOOTH",
                    "FREE",
                    0,
                    0.95,
                    None,
                ),
            ]
            for code, sec, cap, poly_pts, fx, fy, shape, st, guests, conf, occ in demo_tables:
                db.add(
                    DiningTable(
                        id=uuid7(),
                        organization_id=org.id,
                        venue_id=venue.id,
                        camera_id=cam.id,
                        table_code=code,
                        section_name=sec,
                        seat_capacity=cap,
                        polygon_json=[{"x": p[0], "y": p[1]} for p in poly_pts],
                        floor_x=fx,
                        floor_y=fy,
                        shape=shape,
                        current_state=st,
                        current_guest_count=guests,
                        current_confidence=conf,
                        occupied_since=occ,
                    )
                )

        user = User(
            id=uuid7(),
            organization_id=org.id,
            email=demo_email,
            full_name="Maya Chen (Demo Manager)",
            password_hash=hash_password(secrets.token_urlsafe(24)),
            role="MANAGER",
            assigned_venue_ids=[venue.id],
            is_active=True,
            last_login_at=datetime.now(UTC),
        )
        db.add(user)
        await db.flush()
    elif not user.is_active:
        raise AppError(403, "AUTH_FORBIDDEN", "Demo account is inactive")
    else:
        user.last_login_at = datetime.now(UTC)

    raw_refresh, hash_refresh = generate_opaque_token()
    db.add(
        RefreshToken(
            id=uuid7(),
            organization_id=user.organization_id,
            user_id=user.id,
            token_type="REFRESH",
            token_family_id=uuid7(),
            token_hash=hash_refresh,
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    await write_audit_log(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action="USER_DEMO_LOGIN",
        target_type="user",
        target_id=user.id,
        request=request,
    )
    await db.commit()

    access_token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
    )
    resp = success_response(
        {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
            "user": _user_dict(user),
        }
    )
    _set_refresh_cookie(resp, raw_refresh)
    return resp


@router.post("/refresh")
async def refresh_session(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    tp_refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> JSONResponse:
    """API-003: Rotate refresh token and revoke entire token family on reuse detection."""
    if not tp_refresh_token:
        raise AppError(401, "AUTH_UNAUTHORIZED", "Missing refresh cookie")

    token_h = hash_token(tp_refresh_token)
    q_tok = select(RefreshToken).where(
        RefreshToken.token_hash == token_h,
        RefreshToken.token_type == "REFRESH",
    )
    if db.bind and db.bind.dialect.name == "postgresql":
        q_tok = q_tok.with_for_update()
    res = await db.execute(q_tok)
    token_row = res.scalar_one_or_none()
    if token_row is None:
        raise AppError(401, "AUTH_UNAUTHORIZED", "Invalid refresh token")

    now = datetime.now(UTC)
    if token_row.revoked_at is not None:
        # Replay / reuse detected -> revoke entire token family immediately
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_family_id == token_row.token_family_id)
            .values(revoked_at=now)
        )
        await write_audit_log(
            db,
            organization_id=token_row.organization_id,
            actor_user_id=token_row.user_id,
            action="REFRESH_REUSE_DETECTED",
            target_type="refresh_token",
            target_id=token_row.id,
            after_json={"token_family_id": str(token_row.token_family_id)},
            request=request,
        )
        await db.commit()
        resp = JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": {
                    "code": "AUTH_UNAUTHORIZED",
                    "message": "Session revoked due to token reuse",
                },
            },
        )
        _clear_refresh_cookie(resp)
        return resp

    if token_row.expires_at <= now or token_row.user_id is None:
        raise AppError(401, "AUTH_UNAUTHORIZED", "Refresh token expired")

    user_res = await db.execute(select(User).where(User.id == token_row.user_id))
    user = user_res.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppError(401, "AUTH_UNAUTHORIZED", "User inactive")

    token_row.revoked_at = now
    raw_new, hash_new = generate_opaque_token()
    db.add(
        RefreshToken(
            id=uuid7(),
            organization_id=user.organization_id,
            user_id=user.id,
            token_type="REFRESH",
            token_family_id=token_row.token_family_id,
            token_hash=hash_new,
            expires_at=now + timedelta(days=get_settings().refresh_token_expire_days),
        )
    )
    await db.commit()

    access_token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
    )
    resp = success_response(
        {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": get_settings().access_token_expire_minutes * 60,
            "user": _user_dict(user),
        }
    )
    _set_refresh_cookie(resp, raw_new)
    return resp


@router.post("/logout")
async def logout(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tp_refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> JSONResponse:
    """API-004: Revoke refresh token and clear HttpOnly cookie."""
    if tp_refresh_token:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == hash_token(tp_refresh_token))
            .values(revoked_at=datetime.now(UTC))
        )
    await mark_user_revoked(str(user.id), int(datetime.now(UTC).timestamp()))
    await write_audit_log(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action="USER_LOGOUT",
        target_type="user",
        target_id=user.id,
        request=request,
    )
    await db.commit()
    resp = success_response({"logged_out": True})
    _clear_refresh_cookie(resp)
    return resp


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-005 (part 1): Always returns generic 200 to prevent email enumeration."""
    client_ip = _client_ip(request)
    ok, retry = await check_rate_limit(f"forgot:ip:{client_ip}", 10, 60, fail_closed=True)
    if not ok:
        raise AppError(
            429, "RATE_LIMITED", "Too many requests", headers={"Retry-After": str(retry)}
        )

    res = await db.execute(select(User).where(User.email == body.email.lower().strip()))
    user = res.scalar_one_or_none()
    if user is not None and user.is_active:
        raw_reset, token_h = generate_opaque_token()
        db.add(
            RefreshToken(
                id=uuid7(),
                organization_id=user.organization_id,
                user_id=user.id,
                token_type="PASSWORD_RESET",
                token_family_id=uuid7(),
                token_hash=token_h,
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
            )
        )
        await write_audit_log(
            db,
            organization_id=user.organization_id,
            actor_user_id=user.id,
            action="PASSWORD_RESET_REQUESTED",
            target_type="user",
            target_id=user.id,
            request=request,
        )
        await db.commit()
        reset_url = f"{get_settings().public_app_url.rstrip('/')}/reset-password?token={raw_reset}"
        await send_email_if_configured(
            user.email,
            "TablePulse Password Reset",
            f"Reset your TablePulse password (expires in 30 minutes): {reset_url}",
        )

    return success_response(
        {"message": "If an account exists for that email, a reset link has been sent."}
    )


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-005 (part 2): Validate single-use 30m reset token, update password, revoke all sessions."""
    validate_password_strength(body.new_password)
    now = datetime.now(UTC)
    res = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(body.token),
            RefreshToken.token_type == "PASSWORD_RESET",
        )
    )
    tok = res.scalar_one_or_none()
    if tok is None or tok.revoked_at is not None or tok.expires_at <= now or tok.user_id is None:
        raise AppError(400, "TOKEN_EXPIRED", "Password reset token is invalid or expired")

    user_res = await db.execute(select(User).where(User.id == tok.user_id))
    user = user_res.scalar_one_or_none()
    if user is None:
        raise AppError(400, "TOKEN_EXPIRED", "Password reset token is invalid")

    user.password_hash = hash_password(body.new_password)
    tok.revoked_at = now
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.token_type == "REFRESH",
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await mark_user_revoked(str(user.id), int(now.timestamp()))
    await write_audit_log(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action="PASSWORD_RESET_COMPLETED",
        target_type="user",
        target_id=user.id,
        request=request,
    )
    await db.commit()
    return success_response({"reset": True})


@router.get("/invite-info")
async def get_invite_info(
    token: Annotated[str, Query(min_length=16)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Inspect a pending invite token without consuming it."""
    now = datetime.now(UTC)
    res = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(token),
            RefreshToken.token_type == "INVITE",
        )
    )
    tok = res.scalar_one_or_none()
    if tok is None or tok.revoked_at is not None or tok.expires_at <= now:
        raise AppError(400, "TOKEN_EXPIRED", "Invitation token is invalid or expired")

    meta = tok.metadata_json or {}
    org = (
        await db.execute(select(Organization).where(Organization.id == tok.organization_id))
    ).scalar_one_or_none()
    return success_response(
        {
            "email": meta.get("email"),
            "role": meta.get("role"),
            "organization_name": org.name if org else "TablePulse",
            "venue_ids": meta.get("venue_ids", []),
            "expires_at": tok.expires_at.isoformat(),
        }
    )


@router.post("/accept-invite", status_code=201)
async def accept_invite(
    body: AcceptInviteRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Complete account creation from an invite token and log user in."""
    client_ip = _client_ip(request)
    ip_ok, ip_retry = await check_rate_limit(
        f"accept-invite:ip:{client_ip}", 15, 60, fail_closed=True
    )
    if not ip_ok:
        raise AppError(
            429,
            "RATE_LIMITED",
            "Too many invite acceptance attempts. Please wait and try again.",
            headers={"Retry-After": str(ip_retry)},
        )

    invite_hash = hash_token(body.token)
    if idempotency_key:
        cached = await check_and_store_idempotency(f"invite-accept:{invite_hash}:{idempotency_key}")
        if cached is not None:
            return success_response(cached, status_code=201)

    validate_password_strength(body.password)
    now = datetime.now(UTC)
    res = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == invite_hash,
            RefreshToken.token_type == "INVITE",
        )
    )
    tok = res.scalar_one_or_none()
    if tok is None or tok.revoked_at is not None or tok.expires_at <= now:
        raise AppError(400, "TOKEN_EXPIRED", "Invitation token is invalid or expired")

    meta = tok.metadata_json or {}
    email = str(meta.get("email", "")).lower().strip()
    role = str(meta.get("role", "STAFF"))
    venue_ids = [uuid.UUID(str(v)) for v in meta.get("venue_ids", [])]

    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise AppError(409, "VERSION_CONFLICT", "An account with this email already exists")

    user = User(
        id=uuid7(),
        organization_id=tok.organization_id,
        email=email,
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
        role=role,
        assigned_venue_ids=venue_ids,
        is_active=True,
        last_login_at=now,
    )
    db.add(user)
    tok.revoked_at = now
    await db.flush()

    raw_refresh, hash_refresh = generate_opaque_token()
    db.add(
        RefreshToken(
            id=uuid7(),
            organization_id=user.organization_id,
            user_id=user.id,
            token_type="REFRESH",
            token_family_id=uuid7(),
            token_hash=hash_refresh,
            expires_at=now + timedelta(days=get_settings().refresh_token_expire_days),
        )
    )
    await write_audit_log(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action="USER_INVITE_ACCEPTED",
        target_type="user",
        target_id=user.id,
        after_json={"email": email, "role": role},
        request=request,
    )
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
    )
    payload = {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": get_settings().access_token_expire_minutes * 60,
        "user": _user_dict(user),
    }
    if idempotency_key:
        await check_and_store_idempotency(f"invite-accept:{invite_hash}:{idempotency_key}", payload)
    resp = success_response(payload, status_code=201)
    _set_refresh_cookie(resp, raw_refresh)
    return resp


@router.post("/ws-ticket")
async def issue_ws_ticket(
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """API-006: Issue single-use 60s WebSocket authentication ticket."""
    ticket = secrets.token_urlsafe(32)
    ticket_data = {
        "user_id": str(user.id),
        "organization_id": str(user.organization_id),
        "role": user.role,
        "assigned_venue_ids": ",".join(str(v) for v in (user.assigned_venue_ids or [])),
    }
    import json

    try:
        await get_valkey().set(f"tp:ws_ticket:{ticket}", json.dumps(ticket_data), ex=60)
    except Exception:
        _local_ws_tickets[ticket] = ticket_data
    return success_response({"ticket": ticket, "expires_in": 60})


@router.get("/me")
async def get_me(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Return authenticated user profile and accessible venues."""
    q = select(Venue).where(
        Venue.organization_id == user.organization_id,
        Venue.deleted_at.is_(None),
    )
    if user.role != "OWNER":
        q = q.where(Venue.id.in_(user.assigned_venue_ids or []))
    venues = (await db.execute(q)).scalars().all()
    sys_set = (
        await db.execute(
            select(SystemSetting).where(SystemSetting.organization_id == user.organization_id)
        )
    ).scalar_one_or_none()
    return success_response(
        {
            "user": _user_dict(user),
            "policies": {
                "require_2fa_roles": list(sys_set.require_2fa_roles or []) if sys_set else [],
                "managers_can_manage_tables": (
                    sys_set.managers_can_manage_tables if sys_set else True
                ),
                "managers_can_manage_menu": (
                    sys_set.managers_can_manage_menu if sys_set else True
                ),
                "admins_can_manage_tables": (
                    sys_set.admins_can_manage_tables if sys_set else True
                ),
                "admins_can_manage_menu": (
                    sys_set.admins_can_manage_menu if sys_set else True
                ),
            },
            "venues": [
                {
                    "id": str(v.id),
                    "name": v.name,
                    "timezone": v.timezone,
                    "allow_host_camera_view": v.allow_host_camera_view,
                    "allow_host_menu_availability": v.allow_host_menu_availability,
                    "currency_code": v.currency_code,
                    "menu_public_enabled": v.menu_public_enabled,
                    "show_unavailable_items_public": v.show_unavailable_items_public,
                    "menu_tagline": v.menu_tagline,
                    "logo_storage_key": v.logo_storage_key,
                    "menu_revision": v.menu_revision,
                    "qr_grace_days": v.qr_grace_days,
                }
                for v in venues
            ],
        }
    )


async def consume_ws_ticket(ticket: str) -> dict[str, str] | None:
    """Validate and atomically consume a single-use WebSocket ticket."""
    import json

    try:
        client = get_valkey()
        key = f"tp:ws_ticket:{ticket}"
        raw = await client.getdel(key)
        if raw:
            return dict(json.loads(raw))
    except Exception:
        pass
    return _local_ws_tickets.pop(ticket, None)
