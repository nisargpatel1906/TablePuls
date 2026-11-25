"""Pytest configuration and shared PostgreSQL / Valkey fixtures."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Ensure test defaults exist before app imports
os.environ.setdefault("TABLEPULSE_ENV", "test")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault(
    "TABLEPULSE_SECRET_KEY",
    "test_only_secret_key_0123456789abcdef0123456789abcdef0123456789",
)
os.environ.setdefault(
    "TABLEPULSE_DATA_KEY",
    "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
)
os.environ.setdefault(
    "MEDIAMTX_HOOK_SECRET",
    "test_mediamtx_hook_secret_0123456789abcdef0123456789abcdef",
)


def get_test_db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://tablepulse:change_me_postgres_password@localhost:5432/tablepulse",
    )


@pytest.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(get_test_db_url(), pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def clean_db(db_engine: AsyncEngine) -> AsyncIterator[None]:
    """Clean all application tables before/after integration tests."""
    tables = [
        "audit_logs",
        "alert_rules",
        "ml_review_items",
        "ml_models",
        "waitlist_entries",
        "alerts",
        "occupancy_snapshots",
        "table_state_events",
        "tables",
        "cameras",
        "refresh_tokens",
        "users",
        "venues",
        "system_settings",
        "organizations",
    ]
    async with db_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    yield
