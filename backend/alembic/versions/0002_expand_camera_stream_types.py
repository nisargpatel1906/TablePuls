"""Expand cameras.stream_type check constraint to support HLS, HTTP_MJPEG, and RTMP.

Revision ID: 0002_expand_camera_stream_types
Revises: 0001_initial_schema
Create Date: 2026-11-25 20:15:00+00:00
"""

from __future__ import annotations

from alembic import op

revision: str = "0002_expand_camera_stream_types"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_cameras_stream_type", "cameras", type_="check")
    op.create_check_constraint(
        "ck_cameras_stream_type",
        "cameras",
        "stream_type IN ('RTSP','RTSPS','HLS','HTTP_MJPEG','RTMP','DEMO_MP4')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_cameras_stream_type", "cameras", type_="check")
    op.create_check_constraint(
        "ck_cameras_stream_type",
        "cameras",
        "stream_type IN ('RTSP','RTSPS','DEMO_MP4')",
    )
