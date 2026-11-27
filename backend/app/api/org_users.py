"""Organization user management, invites, session revocation, and audit logs (API-021)."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import AppError, success_response
from app.core.rbac import Role, require_org_role
from app.core.security import generate_opaque_token
from app.core.valkey_client import (
    check_and_store_idempotency,
    check_rate_limit,
    mark_user_revoked,
)
from app.db.base import get_db, uuid7
from app.db.models import AuditLog, RefreshToken, User, Venue
from app.schemas.auth import InviteUserRequest, UpdateUserRequest
from app.services.audit import write_audit_log
from app.services.email import send_email_if_configured

router = APIRouter(prefix="/api/v1/org", tags=["org-admin"])


def _csv_safe(val: object) -> str:
    s = "" if val is None else str(val)
    if s.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


@router.get("/users")
async def list_org_users(
    user: Annotated[User, Depends(require_org_role({Role.OWNER, Role.MANAGER}))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> JSONResponse:
    """List organization users with pagination and MANAGER venue/role scoping."""
    q = select(User).where(User.organization_id == user.organization_id)
    if user.role == Role.MANAGER:
        q = q.where(User.role.in_(["HOST", "STAFF", "VIEWER"]))
    if search:
        pat = f"%{search.strip()}%"
        q = q.where((User.email.ilike(pat)) | (User.full_name.ilike(pat)))

    all_rows = (await db.execute(q.order_by(User.created_at.desc()))).scalars().all()
    if user.role == Role.MANAGER:
        mgr_venues = set(user.assigned_venue_ids or [])
        all_rows = [u for u in all_rows if set(u.assigned_venue_ids or []).intersection(mgr_venues)]

    total = len(all_rows)
    start = (page - 1) * page_size
    items = [
        {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "assigned_venue_ids": [str(v) for v in (u.assigned_venue_ids or [])],
            "is_active": u.is_active,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "created_at": u.created_at.isoformat(),
        }
        for u in all_rows[start : start + page_size]
    ]
    return success_response({"items": items, "total": total, "page": page, "page_size": page_size})


@router.post("/users/invite", status_code=201)
async def invite_user(
    body: InviteUserRequest,
    request: Request,
    actor: Annotated[User, Depends(require_org_role({Role.OWNER, Role.MANAGER}))],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Invite a new user scoped to role and assigned venues (48h single-use link)."""
    if idempotency_key:
        cached = await check_and_store_idempotency(f"invite:{actor.id}:{idempotency_key}")
        if cached is not None:
            return success_response(cached, status_code=201)

    ok, retry = await check_rate_limit(f"invite:actor:{actor.id}", 20, 86400, fail_closed=False)
    if not ok:
        raise AppError(
            429, "RATE_LIMITED", "Daily invite limit reached", headers={"Retry-After": str(retry)}
        )

    if actor.role == Role.MANAGER:
        if body.role in {"OWNER", "MANAGER"}:
            raise AppError(403, "AUTH_FORBIDDEN", "Managers cannot invite OWNER or MANAGER users")
        allowed_venues = set(actor.assigned_venue_ids or [])
        if not body.venue_ids or not set(body.venue_ids).issubset(allowed_venues):
            raise AppError(403, "AUTH_FORBIDDEN", "Managers can only invite to assigned venues")

    # Verify all requested venue_ids belong to actor's organization
    if body.venue_ids:
        found = (
            (
                await db.execute(
                    select(Venue.id).where(
                        Venue.organization_id == actor.organization_id,
                        Venue.id.in_(body.venue_ids),
                        Venue.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        if len(found) != len(set(body.venue_ids)):
            raise AppError(
                400,
                "VALIDATION_ERROR",
                "One or more venue_ids are invalid",
                {"venue_ids": "invalid venue"},
            )

    email_norm = body.email.lower().strip()
    existing = (await db.execute(select(User).where(User.email == email_norm))).scalar_one_or_none()
    if existing is not None:
        raise AppError(409, "VERSION_CONFLICT", "User with this email already exists")

    raw_token, token_h = generate_opaque_token()
    expires_at = datetime.now(UTC) + timedelta(hours=48)
    inv_row = RefreshToken(
        id=uuid7(),
        organization_id=actor.organization_id,
        user_id=None,
        token_type="INVITE",
        token_family_id=uuid7(),
        token_hash=token_h,
        metadata_json={
            "email": email_norm,
            "role": body.role,
            "venue_ids": [str(v) for v in body.venue_ids],
            "invited_by": str(actor.id),
        },
        expires_at=expires_at,
    )
    db.add(inv_row)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        actor_user_id=actor.id,
        action="USER_INVITED",
        target_type="invitation",
        target_id=inv_row.id,
        after_json={
            "email": email_norm,
            "role": body.role,
            "venue_ids": [str(v) for v in body.venue_ids],
        },
        request=request,
    )
    await db.commit()

    settings = get_settings()
    invite_url = f"{settings.public_app_url.rstrip('/')}/register?token={raw_token}"
    email_sent = await send_email_if_configured(
        email_norm,
        f"You're invited to TablePulse ({body.role})",
        (
            f"You have been invited to join TablePulse as {body.role}.\n\n"
            f"Complete your registration (valid for 48 hours): {invite_url}\n"
        ),
    )
    payload = {
        "invitation_id": str(inv_row.id),
        "email": email_norm,
        "role": body.role,
        "expires_at": expires_at.isoformat(),
        "email_sent": email_sent,
        "invite_url": invite_url if not email_sent else None,
        "token": raw_token if (settings.app_env != "production" and not email_sent) else None,
    }
    if idempotency_key:
        await check_and_store_idempotency(f"invite:{actor.id}:{idempotency_key}", payload)
    return success_response(payload, status_code=201)


@router.patch("/users/{target_user_id}")
async def update_org_user(
    target_user_id: uuid.UUID,
    body: UpdateUserRequest,
    request: Request,
    actor: Annotated[User, Depends(require_org_role({Role.OWNER, Role.MANAGER}))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Update user role, venue assignments, or active state with Last-Owner protection."""
    res = await db.execute(
        select(User).where(
            User.id == target_user_id,
            User.organization_id == actor.organization_id,
        )
    )
    target = res.scalar_one_or_none()
    if target is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "User not found")

    if actor.role == Role.MANAGER:
        if target.role in {"OWNER", "MANAGER"} or (body.role and body.role in {"OWNER", "MANAGER"}):
            raise AppError(403, "AUTH_FORBIDDEN", "Managers cannot modify OWNER or MANAGER roles")
        mgr_venues = set(actor.assigned_venue_ids or [])
        if not set(target.assigned_venue_ids or []).intersection(mgr_venues):
            raise AppError(403, "AUTH_FORBIDDEN", "User outside manager venue scope")

    # Last-OWNER protection check before mutation (also guarded by DB trigger)
    demoting_owner = (
        target.role == "OWNER"
        and target.is_active
        and ((body.role is not None and body.role != "OWNER") or (body.is_active is False))
    )
    if demoting_owner:
        other_owners = (
            await db.execute(
                select(func.count())
                .select_from(User)
                .where(
                    User.organization_id == actor.organization_id,
                    User.role == "OWNER",
                    User.is_active.is_(True),
                    User.id != target.id,
                )
            )
        ).scalar_one()
        if int(other_owners) == 0:
            raise AppError(
                409,
                "LAST_OWNER_PROTECTED",
                "At least one active OWNER is required per organization",
            )

    before = {
        "role": target.role,
        "assigned_venue_ids": [str(v) for v in (target.assigned_venue_ids or [])],
        "is_active": target.is_active,
        "full_name": target.full_name,
    }

    if body.role is not None:
        target.role = body.role
    if body.assigned_venue_ids is not None:
        if body.assigned_venue_ids:
            valid_venues = set(
                (
                    await db.execute(
                        select(Venue.id).where(
                            Venue.organization_id == actor.organization_id,
                            Venue.deleted_at.is_(None),
                            Venue.id.in_(body.assigned_venue_ids),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if valid_venues != set(body.assigned_venue_ids):
                raise AppError(
                    403,
                    "AUTH_FORBIDDEN",
                    "One or more assigned venues do not belong to your organization",
                )
            if actor.role == Role.MANAGER and not set(body.assigned_venue_ids).issubset(
                set(actor.assigned_venue_ids or [])
            ):
                raise AppError(
                    403,
                    "AUTH_FORBIDDEN",
                    "Managers can only assign venues within their own scope",
                )
        target.assigned_venue_ids = body.assigned_venue_ids
    if body.full_name is not None:
        target.full_name = body.full_name.strip()
    if body.is_active is not None:
        target.is_active = body.is_active
        if not body.is_active:
            now = datetime.now(UTC)
            await db.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == target.id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            await mark_user_revoked(str(target.id), int(now.timestamp()))

    after = {
        "role": target.role,
        "assigned_venue_ids": [str(v) for v in (target.assigned_venue_ids or [])],
        "is_active": target.is_active,
        "full_name": target.full_name,
    }
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        actor_user_id=actor.id,
        action="CHANGE_ROLE" if before["role"] != after["role"] else "UPDATE_USER",
        target_type="user",
        target_id=target.id,
        before_json=before,
        after_json=after,
        request=request,
    )
    await db.commit()
    return success_response({"id": str(target.id), **after})


@router.post("/users/{target_user_id}/revoke-sessions")
async def revoke_user_sessions(
    target_user_id: uuid.UUID,
    request: Request,
    actor: Annotated[User, Depends(require_org_role({Role.OWNER, Role.MANAGER}))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    res = await db.execute(
        select(User).where(
            User.id == target_user_id,
            User.organization_id == actor.organization_id,
        )
    )
    target = res.scalar_one_or_none()
    if target is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "User not found")
    if actor.role == Role.MANAGER:
        if target.role in {"OWNER", "MANAGER"}:
            raise AppError(
                403, "AUTH_FORBIDDEN", "Managers cannot revoke OWNER or MANAGER sessions"
            )
        mgr_venues = set(actor.assigned_venue_ids or [])
        if not set(target.assigned_venue_ids or []).intersection(mgr_venues):
            raise AppError(403, "AUTH_FORBIDDEN", "User outside manager venue scope")

    now = datetime.now(UTC)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == target.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await mark_user_revoked(str(target.id), int(now.timestamp()))
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        actor_user_id=actor.id,
        action="REVOKE_SESSIONS",
        target_type="user",
        target_id=target.id,
        request=request,
    )
    await db.commit()
    return success_response({"revoked": True, "user_id": str(target.id)})


@router.post("/users/{target_user_id}/reset-link")
async def create_admin_reset_link(
    target_user_id: uuid.UUID,
    request: Request,
    actor: Annotated[User, Depends(require_org_role({Role.OWNER}))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Air-gapped self-hosted helper: OWNER generates a 30-min one-time reset link."""
    res = await db.execute(
        select(User).where(
            User.id == target_user_id,
            User.organization_id == actor.organization_id,
        )
    )
    target = res.scalar_one_or_none()
    if target is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "User not found")

    raw_token, token_h = generate_opaque_token()
    expires_at = datetime.now(UTC) + timedelta(minutes=30)
    db.add(
        RefreshToken(
            id=uuid7(),
            organization_id=actor.organization_id,
            user_id=target.id,
            token_type="PASSWORD_RESET",
            token_family_id=uuid7(),
            token_hash=token_h,
            expires_at=expires_at,
        )
    )
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        actor_user_id=actor.id,
        action="ADMIN_RESET_LINK_ISSUED",
        target_type="user",
        target_id=target.id,
        request=request,
    )
    await db.commit()
    url = f"{get_settings().public_app_url.rstrip('/')}/reset-password?token={raw_token}"
    email_sent = await send_email_if_configured(
        target.email,
        "TablePulse password reset",
        (
            "An organization administrator initiated a password reset for your TablePulse account.\n\n"
            f"Reset your password (valid for 30 minutes): {url}\n"
        ),
    )
    return success_response(
        {"reset_url": url, "email_sent": email_sent, "expires_at": expires_at.isoformat()}
    )


@router.get("/audit-logs")
async def list_audit_logs(
    actor: Annotated[User, Depends(require_org_role(capability="audit_logs.view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    action: Annotated[str | None, Query(max_length=64)] = None,
    actor_user_id: Annotated[uuid.UUID | None, Query()] = None,
    format: Annotated[str, Query(pattern="^(json|csv)$")] = "json",
) -> Response:
    """Paginated immutable audit logs; OWNER sees entire org, MANAGER sees assigned venues."""
    q = select(AuditLog).where(AuditLog.organization_id == actor.organization_id)
    if actor.role == Role.MANAGER:
        q = q.where(AuditLog.venue_id.in_(actor.assigned_venue_ids or []))
    if action:
        q = q.where(AuditLog.action == action)
    if actor_user_id:
        q = q.where(AuditLog.actor_user_id == actor_user_id)

    q = q.order_by(AuditLog.created_at.desc())
    rows = (await db.execute(q)).scalars().all()

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "id",
                "created_at",
                "action",
                "target_type",
                "target_id",
                "actor_user_id",
                "venue_id",
                "ip_address",
            ]
        )
        for r in rows[:5000]:
            writer.writerow(
                [
                    _csv_safe(r.id),
                    _csv_safe(r.created_at.isoformat()),
                    _csv_safe(r.action),
                    _csv_safe(r.target_type),
                    _csv_safe(r.target_id),
                    _csv_safe(r.actor_user_id),
                    _csv_safe(r.venue_id),
                    _csv_safe(r.ip_address),
                ]
            )
        return Response(
            content=buf.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="tablepulse-audit-logs.csv"'},
        )

    total = len(rows)
    start = (page - 1) * page_size
    items = [
        {
            "id": str(r.id),
            "organization_id": str(r.organization_id),
            "venue_id": str(r.venue_id) if r.venue_id else None,
            "actor_user_id": str(r.actor_user_id) if r.actor_user_id else None,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": str(r.target_id) if r.target_id else None,
            "before_json": r.before_json,
            "after_json": r.after_json,
            "ip_address": str(r.ip_address) if r.ip_address else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows[start : start + page_size]
    ]
    return success_response({"items": items, "total": total, "page": page, "page_size": page_size})
