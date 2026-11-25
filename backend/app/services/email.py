"""Optional SMTP email helper (only active when SMTP_HOST is configured)."""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

import structlog

from app.config import get_settings

logger = structlog.get_logger("email")


def _send_sync(to_email: str, subject: str, body: str) -> None:
    settings = get_settings()
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_user and settings.smtp_pass:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_pass)
        smtp.send_message(msg)


async def send_email_if_configured(to_email: str, subject: str, body: str) -> bool:
    """Send an email via SMTP when SMTP_HOST is configured; never raises to callers."""
    settings = get_settings()
    if not settings.smtp_host.strip():
        return False
    try:
        await asyncio.to_thread(_send_sync, to_email, subject, body)
        return True
    except Exception as exc:
        logger.warning("smtp_delivery_failed", error=str(exc))
        return False
