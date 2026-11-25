"""SSRF-safe outbound webhook dispatcher with HMAC-SHA256 signing, retries, and circuit breaker."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from app.config import get_settings
from app.core.security import sign_webhook_payload
from app.core.ssrf import validate_webhook_url

logger = structlog.get_logger("webhooks")


@dataclass(slots=True)
class CircuitState:
    consecutive_failures: int = 0
    total_failures: int = 0
    open_until_ts: float = 0.0
    disabled: bool = False


_circuits: dict[str, CircuitState] = {}


def reset_webhook_circuits() -> None:
    _circuits.clear()


async def dispatch_webhook(
    *,
    url: str,
    secret: str,
    payload: dict[str, Any],
    max_attempts: int = 3,
    transport: httpx.AsyncBaseTransport | None = None,
    bypass_kill_switch: bool = False,
) -> tuple[bool, int | None, str]:
    """
    Dispatch HMAC-signed JSON webhook with SSRF validation, 3x retry, and circuit breaker.
    Returns (success, http_status_code, detail).
    """
    if not bypass_kill_switch and not get_settings().webhooks_enabled:
        return False, None, "WEBHOOKS_ENABLED is false"

    validate_webhook_url(url)

    state = _circuits.setdefault(url, CircuitState())
    now = time.time()
    if state.disabled:
        return False, None, "Webhook circuit permanently disabled after repeated failures"
    if state.open_until_ts > now:
        return False, None, "Webhook circuit breaker open"

    body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = sign_webhook_payload(secret or "tablepulse-default-hmac", body_bytes)
    headers = {
        "Content-Type": "application/json",
        "X-TablePulse-Signature": sig,
    }

    last_status: int | None = None
    last_err = "unknown error"
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
        follow_redirects=False,
        transport=transport,
    ) as client:
        for attempt in range(max_attempts):
            try:
                resp = await client.post(url, content=body_bytes, headers=headers)
                last_status = resp.status_code
                if 200 <= resp.status_code < 300:
                    state.consecutive_failures = 0
                    return True, resp.status_code, "delivered"
                last_err = f"HTTP {resp.status_code}"
            except Exception as exc:
                last_err = str(exc)

            state.consecutive_failures += 1
            state.total_failures += 1
            if state.total_failures >= 50:
                state.disabled = True
                break
            if state.consecutive_failures >= 10:
                state.open_until_ts = time.time() + 600.0
                break
            if attempt + 1 < max_attempts:
                await asyncio.sleep(0.05 * (2**attempt))

    logger.warning("webhook_delivery_failed", status=last_status, detail=last_err)
    return False, last_status, last_err
