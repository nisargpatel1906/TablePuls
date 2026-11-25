"""SSRF protection and URL credential masking for cameras and outbound webhooks."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

from app.config import get_settings
from app.core.errors import AppError

_BLOCKED_METADATA_HOSTS = {
    "169.254.169.254",
    "metadata.google.internal",
    "metadata.goog",
}


def _is_forbidden_ip(ip_str: str, *, block_private: bool) -> bool:
    ip = ipaddress.ip_address(ip_str)
    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return True
    return bool(block_private and ip.is_private)


def validate_rtsp_url(raw_url: str) -> str:
    """Validate RTSP/RTSPS URL and block loopback/link-local/metadata SSRF targets."""
    parsed = urlparse(raw_url.strip())
    if parsed.scheme.lower() not in {"rtsp", "rtsps"}:
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "Invalid camera stream URL",
            {"stream_url": "must start with rtsp:// or rtsps://"},
        )
    if not parsed.hostname:
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "Invalid camera stream URL",
            {"stream_url": "missing hostname"},
        )
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host in _BLOCKED_METADATA_HOSTS:
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "Camera host is blocked by SSRF policy",
            {"stream_url": "loopback and metadata hosts are not allowed"},
        )
    try:
        ipaddress.ip_address(host)
        if _is_forbidden_ip(host, block_private=False):
            raise AppError(
                400,
                "VALIDATION_ERROR",
                "Camera IP is blocked by SSRF policy",
                {"stream_url": "loopback, link-local, and multicast IPs are forbidden"},
            )
    except ValueError:
        # Hostname: resolve if possible to catch loopback/metadata DNS tricks
        try:
            infos = socket.getaddrinfo(host, parsed.port or 554, type=socket.SOCK_STREAM)
            for info in infos:
                resolved_ip = str(info[4][0])
                if _is_forbidden_ip(resolved_ip, block_private=False):
                    raise AppError(
                        400,
                        "VALIDATION_ERROR",
                        "Camera hostname resolves to blocked IP",
                        {"stream_url": "resolved IP is forbidden by SSRF policy"},
                    )
        except socket.gaierror:
            # Allow unresolved LAN hostnames at config save time; test endpoint reports 422
            pass
    return raw_url.strip()


def validate_webhook_url(raw_url: str) -> str:
    """Validate HTTP/HTTPS webhook URL with strict SSRF checks (blocks private unless allowed)."""
    settings = get_settings()
    parsed = urlparse(raw_url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "Invalid webhook URL",
            {"webhook_url": "must be a valid http:// or https:// URL"},
        )
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host in _BLOCKED_METADATA_HOSTS:
        raise AppError(
            400,
            "VALIDATION_ERROR",
            "Webhook host is blocked by SSRF policy",
            {"webhook_url": "loopback and cloud metadata hosts are forbidden"},
        )
    block_private = not settings.allow_private_webhook_hosts
    try:
        ipaddress.ip_address(host)
        if _is_forbidden_ip(host, block_private=block_private):
            raise AppError(
                400,
                "VALIDATION_ERROR",
                "Webhook IP is blocked by SSRF policy",
                {"webhook_url": "private, loopback, and link-local IPs are forbidden"},
            )
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
            for info in infos:
                resolved_ip = str(info[4][0])
                if _is_forbidden_ip(resolved_ip, block_private=block_private):
                    raise AppError(
                        400,
                        "VALIDATION_ERROR",
                        "Webhook hostname resolves to blocked IP",
                        {"webhook_url": "resolved IP is forbidden by SSRF policy"},
                    )
        except socket.gaierror as exc:
            raise AppError(
                422,
                "CAMERA_UNREACHABLE",
                "Webhook host could not be resolved",
                {"webhook_url": str(exc)},
            ) from exc
    return raw_url.strip()


def mask_stream_url(raw_url: str) -> str:
    """Return RTSP URL with username/password replaced by ***."""
    parsed = urlparse(raw_url)
    if not parsed.scheme:
        return raw_url
    host_part = parsed.hostname or ""
    if parsed.port:
        host_part = f"{host_part}:{parsed.port}"
    netloc = f"***@{host_part}" if parsed.username or parsed.password else host_part
    return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, ""))
