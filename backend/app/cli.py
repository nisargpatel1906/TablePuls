"""TablePulse Admin CLI (`tablepulse admin ...`) per docs/08, docs/09, and AGENTS.md."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import func, select, update

from app.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    decrypt_field,
    encrypt_field,
    hash_password,
    validate_password_strength,
)
from app.core.valkey_client import mark_user_revoked
from app.db.base import get_session_factory, uuid7
from app.db.models import (
    AlertRule,
    AuditLog,
    Camera,
    Organization,
    RefreshToken,
    SystemSetting,
    User,
    Venue,
    WaitlistEntry,
)

app = typer.Typer(help="TablePulse CLI")
admin_app = typer.Typer(help="TablePulse administrative operations")
app.add_typer(admin_app, name="admin")


@admin_app.command("revoke-all")
def revoke_all() -> None:
    """Emergency incident command: revoke all active sessions across all users."""

    async def _run() -> int:
        now = datetime.now(UTC)
        factory = get_session_factory()
        async with factory() as db:
            users = (await db.execute(select(User.id))).scalars().all()
            await db.execute(
                update(RefreshToken).where(RefreshToken.revoked_at.is_(None)).values(revoked_at=now)
            )
            await db.commit()
            for uid in users:
                await mark_user_revoked(str(uid), int(now.timestamp()))
            return len(users)

    count = asyncio.run(_run())
    typer.echo(f"Revoked active sessions for {count} user(s).")


@admin_app.command("rotate-keys")
def rotate_keys(
    new_data_key: Annotated[str, typer.Option(help="New base64 32-byte AES-256-GCM key")],
) -> None:
    """Re-encrypt all S1/S2 database fields from current TABLEPULSE_DATA_KEY to new_data_key."""
    new_raw = base64.b64decode(new_data_key.strip(), validate=True)
    if len(new_raw) != 32:
        raise typer.BadParameter("new_data_key must decode to 32 bytes")

    def _re_encrypt(blob: bytes | None) -> bytes | None:
        if not blob:
            return blob
        pt = decrypt_field(blob)
        nonce = os.urandom(12)
        return nonce + AESGCM(new_raw).encrypt(nonce, pt.encode("utf-8"), b"tablepulse-v1")

    async def _run() -> int:
        factory = get_session_factory()
        updated = 0
        async with factory() as db:
            cams = (await db.execute(select(Camera))).scalars().all()
            for c in cams:
                c.stream_url_encrypted = (
                    _re_encrypt(c.stream_url_encrypted) or c.stream_url_encrypted
                )
                if c.credentials_encrypted:
                    c.credentials_encrypted = _re_encrypt(c.credentials_encrypted)
                updated += 1
            rules = (await db.execute(select(AlertRule))).scalars().all()
            for r in rules:
                if r.webhook_url_encrypted:
                    r.webhook_url_encrypted = _re_encrypt(r.webhook_url_encrypted)
                if r.webhook_secret_encrypted:
                    r.webhook_secret_encrypted = _re_encrypt(r.webhook_secret_encrypted)
                updated += 1
            wl = (await db.execute(select(WaitlistEntry))).scalars().all()
            for w in wl:
                if w.phone_encrypted:
                    w.phone_encrypted = _re_encrypt(w.phone_encrypted)
                updated += 1
            users = (await db.execute(select(User))).scalars().all()
            for u in users:
                if u.totp_secret_encrypted:
                    u.totp_secret_encrypted = _re_encrypt(u.totp_secret_encrypted)
                updated += 1
            await db.commit()
        return updated

    # Touch encrypt_field so ruff recognizes helper import parity
    _ = encrypt_field
    count = asyncio.run(_run())
    typer.echo(f"Re-encrypted {count} database record(s). Update TABLEPULSE_DATA_KEY in env now.")


@admin_app.command("backup")
def backup(
    output: Annotated[Path, typer.Option(help="Output pg_dump custom file")] = Path(
        "tablepulse_backup.dump"
    ),
) -> None:
    """Create a PostgreSQL custom-format backup via pg_dump."""
    db_url = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    subprocess.run(["pg_dump", "--format=custom", f"--file={output}", db_url], check=True)
    typer.echo(f"Backup written to {output}")


@admin_app.command("restore")
def restore(
    input_file: Annotated[Path, typer.Option(help="Input pg_dump custom file")],
) -> None:
    """Restore a PostgreSQL custom-format backup via pg_restore."""
    db_url = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    subprocess.run(
        ["pg_restore", "--clean", "--if-exists", f"--dbname={db_url}", str(input_file)], check=True
    )
    typer.echo(f"Restored backup from {input_file}")


@admin_app.command("create-org")
def create_org(
    org_name: Annotated[str, typer.Option("--org-name", help="Organization name")],
    owner_email: Annotated[str, typer.Option("--owner-email", help="Initial OWNER email address")],
    owner_name: Annotated[str, typer.Option("--owner-name", help="Initial OWNER full name")],
    owner_password: Annotated[
        str, typer.Option("--owner-password", help="Initial OWNER password (>=12 chars)")
    ],
    venue_name: Annotated[
        str | None, typer.Option("--venue-name", help="Optional initial venue name")
    ] = None,
    timezone: Annotated[str, typer.Option("--timezone", help="Initial venue timezone")] = "UTC",
    currency_code: Annotated[
        str, typer.Option("--currency-code", help="3-letter ISO currency code")
    ] = "INR",
) -> None:
    """Provision an isolated organization + OWNER (+ optional initial venue) for multi-org setups."""
    org_clean = org_name.strip()
    email_norm = owner_email.strip().lower()
    name_clean = owner_name.strip()
    curr = currency_code.strip().upper()

    if not org_clean:
        raise typer.BadParameter("org-name cannot be empty")
    if "@" not in email_norm or "." not in email_norm.split("@")[-1]:
        raise typer.BadParameter("owner-email must be a valid email address")
    if not name_clean:
        raise typer.BadParameter("owner-name cannot be empty")
    if len(curr) != 3 or not curr.isalpha():
        raise typer.BadParameter("currency-code must be a 3-letter ISO code")

    try:
        validate_password_strength(owner_password)
    except AppError as exc:
        raise typer.BadParameter(exc.message) from exc

    async def _run() -> dict[str, str | None]:
        factory = get_session_factory()
        async with factory() as db:
            existing_user = (
                await db.execute(select(User.id).where(User.email == email_norm))
            ).scalar_one_or_none()
            if existing_user is not None:
                raise typer.BadParameter(f"Email '{email_norm}' is already registered")

            existing_org = (
                await db.execute(
                    select(Organization.id).where(
                        func.lower(Organization.name) == org_clean.lower(),
                        Organization.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if existing_org is not None:
                raise typer.BadParameter(f"Organization '{org_clean}' already exists")

            org = Organization(id=uuid7(), name=org_clean)
            db.add(org)
            await db.flush()

            db.add(
                SystemSetting(
                    organization_id=org.id,
                    ai_inference_enabled=get_settings().ai_inference_enabled,
                    face_blur_enforced=True,
                    snapshot_retention_days=7,
                    analytics_retention_days=365,
                )
            )
            owner = User(
                id=uuid7(),
                organization_id=org.id,
                email=email_norm,
                full_name=name_clean,
                password_hash=hash_password(owner_password),
                role="OWNER",
                assigned_venue_ids=[],
                is_active=True,
            )
            db.add(owner)
            await db.flush()

            venue: Venue | None = None
            if venue_name and venue_name.strip():
                venue = Venue(
                    id=uuid7(),
                    organization_id=org.id,
                    name=venue_name.strip(),
                    timezone=timezone.strip() or "UTC",
                    currency_code=curr,
                )
                db.add(venue)
                await db.flush()
                db.add(
                    AlertRule(
                        id=uuid7(),
                        organization_id=org.id,
                        venue_id=venue.id,
                        section_name=None,
                    )
                )

            db.add(
                AuditLog(
                    id=uuid7(),
                    organization_id=org.id,
                    venue_id=venue.id if venue else None,
                    actor_user_id=owner.id,
                    action="CLI_CREATE_ORG",
                    target_type="organization",
                    target_id=org.id,
                    after_json={
                        "organization_name": org.name,
                        "owner_email": owner.email,
                        "venue_id": str(venue.id) if venue else None,
                    },
                )
            )
            await db.commit()
            return {
                "organization_id": str(org.id),
                "owner_id": str(owner.id),
                "venue_id": str(venue.id) if venue else None,
            }

    result = asyncio.run(_run())
    typer.echo(json.dumps(result))


if __name__ == "__main__":
    app()
