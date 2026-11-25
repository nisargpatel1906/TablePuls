"""Helpers for PostgreSQL 16+ monthly range partition management."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def ensure_occupancy_partition(session: AsyncSession, target_ts: datetime) -> None:
    """Ensure the monthly partition for target_ts exists before inserting snapshots."""
    await session.execute(
        text("SELECT ensure_occupancy_partition(:ts)"),
        {"ts": target_ts},
    )


async def refresh_hourly_rollup(session: AsyncSession) -> None:
    """Refresh rollup_hourly_venue materialized view."""
    await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY rollup_hourly_venue"))
