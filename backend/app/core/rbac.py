"""Single-Source-of-Truth RBAC matrix loader, AuthN, and AuthZ dependencies."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, cast

import yaml
from fastapi import Depends, Request
from fastapi import Path as ApiPath
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.core.valkey_client import is_user_revoked
from app.db.base import get_db
from app.db.models import SystemSetting, User, Venue


class Role(StrEnum):
    OWNER = "OWNER"
    MANAGER = "MANAGER"
    HOST = "HOST"
    STAFF = "STAFF"
    VIEWER = "VIEWER"


_bearer_scheme = HTTPBearer(auto_error=False)


def _find_matrix_path() -> Path:
    candidates = [
        Path(__file__).resolve().parents[3] / "packages" / "rbac" / "matrix.yaml",
        Path("/app/packages/rbac/matrix.yaml"),
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("Cannot locate packages/rbac/matrix.yaml")


@lru_cache(maxsize=1)
def load_rbac_matrix() -> dict[str, Any]:
    path = _find_matrix_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "capabilities" not in data:
        raise ValueError("Invalid packages/rbac/matrix.yaml structure")
    return dict(data)


def roles_for_capability(capability: str) -> set[Role]:
    matrix = load_rbac_matrix()
    cap = matrix["capabilities"].get(capability)
    if cap is None:
        raise KeyError(f"Unknown RBAC capability: {capability}")
    return {Role(r) for r in cap.get("roles", [])}


def capability_conditional_host_attr(capability: str) -> str | None:
    matrix = load_rbac_matrix()
    cap = matrix["capabilities"].get(capability, {})
    cond = cap.get("conditional_roles", {}).get("HOST")
    if not cond:
        return None
    if "allow_host_menu_availability" in str(cond):
        return "allow_host_menu_availability"
    return "allow_host_camera_view"


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """AuthN layer: strictly validates Bearer JWT and active user state (401 on failure)."""
    if credentials is None or not credentials.credentials:
        raise AppError(401, "AUTH_UNAUTHORIZED", "Authentication required")

    payload = decode_access_token(credentials.credentials)
    try:
        user_id = uuid.UUID(str(payload["sub"]))
        org_id = uuid.UUID(str(payload["org_id"]))
    except (KeyError, ValueError) as exc:
        raise AppError(401, "AUTH_UNAUTHORIZED", "Malformed token claims") from exc

    if await is_user_revoked(str(user_id), int(payload.get("iat_ms") or int(payload.get("iat", 0)) * 1000)):
        raise AppError(401, "AUTH_UNAUTHORIZED", "Session has been revoked")

    res = await db.execute(select(User).where(User.id == user_id, User.organization_id == org_id))
    user = res.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppError(401, "AUTH_UNAUTHORIZED", "Account inactive or not found")

    request.state.user_id = str(user.id)
    request.state.org_id = str(user.organization_id)
    return user


def require_org_role(
    allowed_roles: set[Role] | None = None,
    *,
    capability: str | None = None,
) -> Callable[..., Awaitable[User]]:
    """AuthZ dependency for organization-level endpoints (403 on unauthorized role)."""
    resolved_roles = (
        roles_for_capability(capability) if capability is not None else (allowed_roles or set())
    )

    async def _dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if Role(user.role) not in resolved_roles:
            raise AppError(403, "AUTH_FORBIDDEN", "Insufficient organization permissions")
        return user

    cast(Any, _dependency)._tp_rbac_protected = True
    return _dependency


def require_venue_role(
    allowed_roles: set[Role] | None = None,
    *,
    capability: str | None = None,
) -> Callable[..., Awaitable[User]]:
    """AuthZ dependency enforcing org ownership, venue assignment, and role matrix (403)."""
    resolved_roles = (
        roles_for_capability(capability) if capability is not None else (allowed_roles or set())
    )
    cond_host_attr = (
        capability_conditional_host_attr(capability) if capability is not None else None
    )

    async def _dependency(
        venue_id: Annotated[uuid.UUID, ApiPath(...)],
        user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        user_role = Role(user.role)

        # Verify target venue exists inside authenticated user's organization (Zero Trust)
        res = await db.execute(
            select(Venue).where(
                Venue.id == venue_id,
                Venue.organization_id == user.organization_id,
                Venue.deleted_at.is_(None),
            )
        )
        venue = res.scalar_one_or_none()
        if venue is None:
            raise AppError(403, "AUTH_FORBIDDEN", "Venue access denied")

        if user_role != Role.OWNER and venue_id not in (user.assigned_venue_ids or []):
            raise AppError(403, "AUTH_FORBIDDEN", "User not assigned to this venue")

        if user_role in resolved_roles:
            if user_role == Role.MANAGER and capability in (
                "tables.manage",
                "menu.manage",
                "menu.media.upload",
            ):
                sys_set = (
                    await db.execute(
                        select(SystemSetting).where(
                            SystemSetting.organization_id == user.organization_id
                        )
                    )
                ).scalar_one_or_none()
                if sys_set is not None:
                    if capability == "tables.manage" and not sys_set.managers_can_manage_tables:
                        raise AppError(
                            403,
                            "POLICY_DISABLED",
                            "Organization policy restricts table management to OWNER",
                        )
                    if (
                        capability in ("menu.manage", "menu.media.upload")
                        and not sys_set.managers_can_manage_menu
                    ):
                        raise AppError(
                            403,
                            "POLICY_DISABLED",
                            "Organization policy restricts menu management to OWNER",
                        )
            return user

        if (
            cond_host_attr
            and user_role == Role.HOST
            and bool(getattr(venue, cond_host_attr, False))
        ):
            return user

        raise AppError(403, "AUTH_FORBIDDEN", "Insufficient venue permissions")

    cast(Any, _dependency)._tp_rbac_protected = True
    return _dependency


def require_feature_flag(flag_attr: str) -> Callable[..., Awaitable[None]]:
    """Fail-closed Phase 2 feature flag guard (missing or false => 503 FEATURE_DISABLED)."""

    async def _guard() -> None:
        if not bool(getattr(get_settings(), flag_attr, False)):
            raise AppError(
                503,
                "FEATURE_DISABLED",
                f"Feature '{flag_attr}' is currently disabled",
            )

    return _guard
