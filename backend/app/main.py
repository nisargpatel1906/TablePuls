"""FastAPI entrypoint for TablePulse Backend."""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text

from app.api.admin_ops import purge_expired_snapshots_once
from app.api.admin_ops import router as admin_ops_router
from app.api.auth import router as auth_router
from app.api.floor_ops import router as floor_ops_router
from app.api.org_users import router as org_users_router
from app.api.venues_cameras import router as venues_cameras_router
from app.api.waitlist_analytics import router as waitlist_analytics_router
from app.config import get_settings
from app.core.errors import error_envelope, register_exception_handlers, success_response
from app.core.logging import configure_logging
from app.core.rbac import load_rbac_matrix
from app.core.valkey_client import close_valkey, ping_valkey
from app.db.base import get_engine, get_session_factory
from app.services.realtime import cv_stream_consumer_loop

HTTP_REQUESTS = Counter(
    "tp_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "tp_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)


async def _retention_cleanup_loop(stop_event: asyncio.Event) -> None:
    """Periodically purge expired face-blurred review crop snapshots per org retention policy."""
    factory = get_session_factory()
    while not stop_event.is_set():
        try:
            async with factory() as db:
                await purge_expired_snapshots_once(db)
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3600.0)
        except TimeoutError:
            continue


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.assert_production_safe()
    configure_logging("api")
    load_rbac_matrix()
    stop_event = asyncio.Event()
    consumer_task = None
    retention_task = None
    if settings.tablepulse_env != "test":
        consumer_task = asyncio.create_task(cv_stream_consumer_loop(stop_event))
        retention_task = asyncio.create_task(_retention_cleanup_loop(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        for t in (consumer_task, retention_task):
            if t is not None:
                t.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await t
        await close_valkey()
        await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    is_prod = settings.app_env.lower() == "production" or settings.tablepulse_env.lower() == "production"
    app = FastAPI(
        title="TablePulse API",
        version="1.0.0",
        docs_url=None if is_prod else "/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    )

    @app.middleware("http")
    async def observability_and_headers_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.perf_counter()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(service="api", request_id=req_id)

        try:
            response = await call_next(request)
        except Exception:
            response = JSONResponse(
                status_code=503,
                content=error_envelope("SERVICE_UNAVAILABLE", "Service temporarily unavailable"),
            )
        elapsed = time.perf_counter() - start
        path = request.url.path
        HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        HTTP_LATENCY.labels(request.method, path).observe(elapsed)

        response.headers["X-Request-ID"] = req_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        logger = structlog.get_logger("http")
        logger.info(
            "http_request",
            route=path,
            method=request.method,
            status=response.status_code,
            latency_ms=round(elapsed * 1000, 2),
            user_id=getattr(request.state, "user_id", None),
            org_id=getattr(request.state, "org_id", None),
        )
        return response

    register_exception_handlers(app)
    app.include_router(auth_router)
    app.include_router(org_users_router)
    app.include_router(venues_cameras_router)
    app.include_router(floor_ops_router)
    app.include_router(waitlist_analytics_router)
    app.include_router(admin_ops_router)

    @app.get("/api/v1/health")
    async def health_check() -> Response:
        db_ok = False
        try:
            async with asyncio.timeout(2.5), get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False
        valkey_ok = await ping_valkey()
        status_code = 200 if db_ok else 503
        return success_response(
            {
                "status": "ok" if (db_ok and valkey_ok) else ("degraded" if db_ok else "down"),
                "postgres": "ok" if db_ok else "down",
                "valkey": "ok" if valkey_ok else "down",
            },
            status_code=status_code,
        )

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
