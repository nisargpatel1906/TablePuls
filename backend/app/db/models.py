"""SQLAlchemy 2.0 ORM models for all 15 TablePulse tables (docs/06-data-model-and-api.md)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, uuid7


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Venue(Base):
    __tablename__ = "venues"
    __table_args__ = (
        CheckConstraint(
            "guests_per_server_ratio BETWEEN 4 AND 50",
            name="ck_venues_guests_per_server_ratio",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="UTC")
    operating_hours_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    allow_host_camera_view: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    guests_per_server_ratio: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("16")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('OWNER','MANAGER','HOST','STAFF','VIEWER')",
            name="ck_users_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    assigned_venue_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=text("'{}'::uuid[]")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    totp_secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        CheckConstraint(
            "token_type IN ('REFRESH','INVITE','PASSWORD_RESET')",
            name="ck_refresh_tokens_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    token_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="REFRESH")
    token_family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Camera(Base):
    __tablename__ = "cameras"
    __table_args__ = (
        CheckConstraint(
            "stream_type IN ('RTSP','RTSPS','DEMO_MP4')",
            name="ck_cameras_stream_type",
        ),
        CheckConstraint("target_fps BETWEEN 1 AND 5", name="ck_cameras_target_fps"),
        CheckConstraint(
            "status IN ('ONLINE','RECONNECTING','OFFLINE','DISABLED')",
            name="ck_cameras_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venues.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    stream_type: Mapped[str] = mapped_column(String(16), nullable=False)
    stream_url_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    credentials_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    target_fps: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("2"))
    face_blur_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="OFFLINE")
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    exclusion_polygons_json: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DiningTable(Base):
    __tablename__ = "tables"
    __table_args__ = (
        CheckConstraint("seat_capacity BETWEEN 1 AND 20", name="ck_tables_seat_capacity"),
        CheckConstraint("shape IN ('RECT','CIRCLE','BOOTH')", name="ck_tables_shape"),
        CheckConstraint(
            "current_state IN ('FREE','OCCUPIED','NEEDS_SERVICE','NEEDS_CLEANING','RESERVED','UNKNOWN')",
            name="ck_tables_current_state",
        ),
        CheckConstraint("current_guest_count >= 0", name="ck_tables_guest_count_nonneg"),
        Index(
            "uq_tables_venue_code_active",
            "venue_id",
            "table_code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_tables_venue_active",
            "venue_id",
            "section_name",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venues.id", ondelete="RESTRICT"),
        nullable=False,
    )
    camera_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="SET NULL"),
        nullable=True,
    )
    table_code: Mapped[str] = mapped_column(String(20), nullable=False)
    section_name: Mapped[str] = mapped_column(String(60), nullable=False, server_default="Main")
    seat_capacity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    polygon_json: Mapped[list[dict[str, float]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    floor_x: Mapped[float] = mapped_column(
        Float(precision=24), nullable=False, server_default=text("0")
    )
    floor_y: Mapped[float] = mapped_column(
        Float(precision=24), nullable=False, server_default=text("0")
    )
    shape: Mapped[str] = mapped_column(String(16), nullable=False, server_default="RECT")
    current_state: Mapped[str] = mapped_column(String(20), nullable=False, server_default="FREE")
    current_guest_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    current_confidence: Mapped[float | None] = mapped_column(Float(precision=24), nullable=True)
    occupied_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_staff_visit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    active_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    predicted_free_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TableStateEvent(Base):
    __tablename__ = "table_state_events"
    __table_args__ = (
        CheckConstraint("source IN ('AI','MANUAL','SYSTEM')", name="ck_events_source"),
        Index("idx_events_table_occurred", "table_id", text("occurred_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tables.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    previous_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_state: Mapped[str] = mapped_column(String(20), nullable=False)
    guest_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float(precision=24), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OccupancySnapshot(Base):
    __tablename__ = "occupancy_snapshots"
    __table_args__ = (
        Index("idx_snapshots_venue_time", "venue_id", text("captured_at DESC")),
        {"postgresql_partition_by": "RANGE (captured_at)"},
    )

    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    table_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    section_name: Mapped[str] = mapped_column(String(60), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    guest_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    seat_capacity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sla_breached: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(
            "alert_type IN ('UNATTENDED_TABLE','NEEDS_CLEANING','CAMERA_OFFLINE','LOW_CONFIDENCE')",
            name="ck_alerts_type",
        ),
        CheckConstraint(
            "severity IN ('INFO','WARNING','CRITICAL')",
            name="ck_alerts_severity",
        ),
        CheckConstraint(
            "status IN ('ACTIVE','ACKNOWLEDGED','RESOLVED')",
            name="ck_alerts_status",
        ),
        Index(
            "uq_alerts_active_dedup",
            "dedup_key",
            unique=True,
            postgresql_where=text("status IN ('ACTIVE','ACKNOWLEDGED')"),
        ),
        Index("idx_alerts_venue_status_created", "venue_id", "status", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    table_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tables.id", ondelete="SET NULL"),
        nullable=True,
    )
    camera_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="SET NULL"),
        nullable=True,
    )
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ACTIVE")
    dedup_key: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"
    __table_args__ = (
        CheckConstraint("party_size BETWEEN 1 AND 20", name="ck_waitlist_party_size"),
        CheckConstraint(
            "status IN ('WAITING','SEATED','CANCELLED','NO_SHOW')",
            name="ck_waitlist_status",
        ),
        Index("idx_waitlist_venue_status", "venue_id", "status", text("joined_at ASC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    party_name: Mapped[str] = mapped_column(String(80), nullable=False)
    party_size: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    phone_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    quoted_wait_minutes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="WAITING")
    assigned_table_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tables.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    seated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MLModel(Base):
    __tablename__ = "ml_models"
    __table_args__ = (
        CheckConstraint(
            "model_role IN ('DETECTOR','CLEANLINESS','TURNOVER_ETA')",
            name="ck_ml_models_role",
        ),
        CheckConstraint(
            "gate_status IN ('NOT_MEASURED','PASS','FAIL')",
            name="ck_ml_models_gate_status",
        ),
        CheckConstraint(
            "channel IN ('experimental','stable')",
            name="ck_ml_models_channel",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    model_role: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    artifact_uri: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    eval_metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    gate_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="NOT_MEASURED"
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False, server_default="experimental")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MLReviewItem(Base):
    __tablename__ = "ml_review_items"
    __table_args__ = (
        CheckConstraint(
            "trigger_reason IN ('LOW_CONFIDENCE','USER_FLAGGED','DISAGREEMENT')",
            name="ck_ml_review_trigger",
        ),
        CheckConstraint(
            "review_status IN ('PENDING','REVIEWED','EXCLUDED')",
            name="ck_ml_review_status",
        ),
        Index("idx_ml_review_venue_status", "venue_id", "review_status", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    table_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    camera_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    snapshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    predicted_state: Mapped[str] = mapped_column(String(20), nullable=False)
    predicted_guest_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    confidence: Mapped[float] = mapped_column(Float(precision=24), nullable=False)
    trigger_reason: Mapped[str] = mapped_column(String(32), nullable=False)
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="PENDING")
    human_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    human_guest_count: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    issue_tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AlertRule(Base):
    __tablename__ = "alert_rules"
    __table_args__ = (
        CheckConstraint(
            "unattended_service_sec BETWEEN 60 AND 1800",
            name="ck_alert_rules_unattended",
        ),
        CheckConstraint(
            "cleaning_alert_delay_sec BETWEEN 0 AND 900",
            name="ck_alert_rules_cleaning",
        ),
        CheckConstraint(
            "occupancy_debounce_sec BETWEEN 3 AND 60",
            name="ck_alert_rules_occ_debounce",
        ),
        CheckConstraint(
            "departure_debounce_sec BETWEEN 5 AND 120",
            name="ck_alert_rules_dep_debounce",
        ),
        CheckConstraint(
            "min_confidence BETWEEN 0.30 AND 0.95",
            name="ck_alert_rules_min_conf",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    section_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    unattended_service_sec: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("300")
    )
    cleaning_alert_delay_sec: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("120")
    )
    occupancy_debounce_sec: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("10")
    )
    departure_debounce_sec: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("20")
    )
    min_confidence: Mapped[float] = mapped_column(
        Float(precision=24), nullable=False, server_default=text("0.65")
    )
    require_bussing_confirmation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    webhook_url_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    webhook_secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    quiet_hours_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("idx_audit_org_created", "organization_id", text("created_at DESC")),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    venue_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"
    __table_args__ = (
        CheckConstraint(
            "snapshot_retention_days BETWEEN 0 AND 30",
            name="ck_system_settings_snapshot_retention",
        ),
        CheckConstraint(
            "analytics_retention_days BETWEEN 30 AND 1095",
            name="ck_system_settings_analytics_retention",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    ai_inference_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    face_blur_enforced: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    snapshot_retention_days: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("7")
    )
    analytics_retention_days: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("365")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
