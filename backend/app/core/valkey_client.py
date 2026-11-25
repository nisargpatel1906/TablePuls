"""Valkey (BSD-3 Redis-protocol) client with graceful degraded-mode fallbacks."""

from __future__ import annotations

import json
import time
from typing import Any

from valkey.asyncio import Valkey

from app.config import get_settings

_client: Valkey | None = None
_local_rate_limits: dict[str, list[float]] = {}
_local_revocations: dict[str, int] = {}


def get_valkey() -> Valkey:
    global _client
    if _client is None:
        _client = Valkey.from_url(
            get_settings().valkey_url,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
    return _client


async def close_valkey() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def ping_valkey() -> bool:
    try:
        return bool(await get_valkey().ping())
    except Exception:
        return False


async def check_rate_limit(
    key: str,
    limit: int,
    window_seconds: int,
    *,
    fail_closed: bool = False,
) -> tuple[bool, int]:
    """
    Sliding-window counter.
    Auth endpoints pass fail_closed=True using in-process fallback when Valkey is unreachable.
    Returns (allowed, retry_after_seconds).
    """
    now = int(time.time())
    bucket_key = f"tp:rl:{key}:{now // window_seconds}"
    try:
        client = get_valkey()
        count = await client.incr(bucket_key)
        if count == 1:
            await client.expire(bucket_key, window_seconds + 1)
        if int(count) > limit:
            ttl = await client.ttl(bucket_key)
            return False, max(1, int(ttl) if ttl and ttl > 0 else window_seconds)
        return True, 0
    except Exception:
        if not fail_closed:
            return True, 0
        # In-process fallback when Valkey is down so auth rate limiting stays fail-closed
        now_f = time.time()
        window_start = now_f - window_seconds
        history = [ts for ts in _local_rate_limits.get(key, []) if ts >= window_start]
        if len(history) >= limit:
            _local_rate_limits[key] = history
            retry = max(1, int(window_seconds - (now_f - history[0])))
            return False, retry
        history.append(now_f)
        _local_rate_limits[key] = history
        return True, 0


async def mark_user_revoked(user_id: str, revoked_at_ts: int) -> None:
    _local_revocations[user_id] = revoked_at_ts
    try:
        client = get_valkey()
        await client.set(f"tp:revoked:{user_id}", str(revoked_at_ts), ex=960)
        await client.publish(
            "tp:ws:events", json.dumps({"type": "user.revoked", "user_id": user_id})
        )
    except Exception:
        pass


async def is_user_revoked(user_id: str, token_iat: int) -> bool:
    local_ts = _local_revocations.get(user_id)
    if local_ts is not None and token_iat <= local_ts:
        return True
    try:
        val = await get_valkey().get(f"tp:revoked:{user_id}")
        if val is not None and token_iat <= int(val):
            return True
    except Exception:
        pass
    return False


async def set_kill_switch_cache(org_id: str, enabled: bool) -> None:
    try:
        client = get_valkey()
        val = "true" if enabled else "false"
        await client.set(f"tp:kill_switch:{org_id}", val)
        await client.set("tp:kill_switch:global", val)
        await client.publish(
            "tp:cv:control",
            json.dumps({"event": "kill_switch", "organization_id": org_id, "enabled": enabled}),
        )
    except Exception:
        pass


async def publish_cv_control(payload: dict[str, Any]) -> None:
    import contextlib

    with contextlib.suppress(Exception):
        await get_valkey().publish("tp:cv:control", json.dumps(payload))


async def check_and_store_idempotency(
    key: str,
    response_body: dict[str, Any] | None = None,
    ttl_seconds: int = 86400,
) -> dict[str, Any] | None:
    cache_key = f"tp:idem:{key}"
    try:
        client = get_valkey()
        if response_body is None:
            raw = await client.get(cache_key)
            return dict(json.loads(raw)) if raw else None
        await client.set(cache_key, json.dumps(response_body), ex=ttl_seconds)
    except Exception:
        return None
    return None
