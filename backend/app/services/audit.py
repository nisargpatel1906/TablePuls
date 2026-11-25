"""Immutable audit logging service."""

from __future__ import annotations

import ipaddress
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


async def write_audit_log(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None = None,
    venue_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    before_json: dict[str, Any] | None = None,
    after_json: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    ip_addr: str | None = None
    if request is not None and request.client is not None and request.client.host:
        try:
            ip_addr = str(ipaddress.ip_address(request.client.host))
        except ValueError:
            ip_addr = None

    entry = AuditLog(
        organization_id=organization_id,
        venue_id=venue_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before_json=before_json,
        after_json=after_json,
        ip_address=ip_addr,
    )
    db.add(entry)
    await db.flush()
    return entry
