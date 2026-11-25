"""Structured JSON logging with mandatory credential, token, and RTSP password scrubbing."""

from __future__ import annotations

import logging
import re
from typing import Any

import structlog

_RTSP_CRED_RE = re.compile(r"(rtsp[s]?://)([^/\s:@]+):([^/\s@]+)@", re.IGNORECASE)
_BEARER_RE = re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)
_SECRET_KEYS = {
    "password",
    "password_hash",
    "secret",
    "secret_key",
    "token",
    "refresh_token",
    "access_token",
    "authorization",
    "cookie",
    "rtsp_url",
    "stream_url",
    "credentials",
    "totp_code",
    "phone",
    "webhook_secret",
}


def scrub_text(value: str) -> str:
    """Scrub embedded RTSP credentials and Bearer tokens from any string."""
    scrubbed = _RTSP_CRED_RE.sub(r"\1***:***@", value)
    scrubbed = _BEARER_RE.sub(r"\1[REDACTED]", scrubbed)
    return scrubbed


def scrub_mapping(data: Any) -> Any:
    """Recursively scrub sensitive keys and RTSP URLs from structured log events."""
    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for k, v in data.items():
            if str(k).lower() in _SECRET_KEYS:
                out[k] = "[REDACTED]"
            else:
                out[k] = scrub_mapping(v)
        return out
    if isinstance(data, list):
        return [scrub_mapping(item) for item in data]
    if isinstance(data, str):
        return scrub_text(data)
    return data


def _scrub_processor(
    _logger: Any, _method_name: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    return dict(scrub_mapping(dict(event_dict)))


def configure_logging(service_name: str = "api") -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
            structlog.processors.add_log_level,
            _scrub_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.bind_contextvars(service=service_name)
