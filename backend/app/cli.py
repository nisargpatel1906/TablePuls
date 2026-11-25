"""TablePulse Admin CLI (`tablepulse admin ...`) per docs/08, docs/09, and AGENTS.md."""

from __future__ import annotations

import asyncio
import base64
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select, update

from app.config import get_settings
from app.core.security import decrypt_field, encrypt_field
from app.core.valkey_client import mark_user_revoked
from app.db.base import get_session_factory
from app.db.models import AlertRule, Camera, RefreshToken, User, WaitlistEntry

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


if __name__ == "__main__":
    app()
