"""Initial TablePulse schema: 15 tables, native PG16 monthly range partitioning, RLS, triggers, and rollup view.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-25 00:00:00+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

RLS_TABLES = (
    "venues",
    "cameras",
    "tables",
    "alerts",
    "waitlist_entries",
    "ml_review_items",
    "audit_logs",
)


def upgrade() -> None:
    # 1. organizations
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 2. venues
    op.create_table(
        "venues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column(
            "operating_hours_json",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "allow_host_camera_view", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "guests_per_server_ratio", sa.Integer, nullable=False, server_default=sa.text("16")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "guests_per_server_ratio BETWEEN 4 AND 50", name="ck_venues_guests_per_server_ratio"
        ),
    )

    # 3. users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column(
            "assigned_venue_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("totp_secret_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("totp_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "role IN ('OWNER','MANAGER','HOST','STAFF','VIEWER')", name="ck_users_role"
        ),
    )

    # 4. refresh_tokens
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("token_type", sa.String(20), nullable=False, server_default="REFRESH"),
        sa.Column("token_family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "metadata_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "token_type IN ('REFRESH','INVITE','PASSWORD_RESET')", name="ck_refresh_tokens_type"
        ),
    )

    # 5. cameras
    op.create_table(
        "cameras",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "venue_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("venues.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("stream_type", sa.String(16), nullable=False),
        sa.Column("stream_url_encrypted", sa.LargeBinary, nullable=False),
        sa.Column("credentials_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("target_fps", sa.SmallInteger, nullable=False, server_default=sa.text("2")),
        sa.Column("face_blur_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(20), nullable=False, server_default="OFFLINE"),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "exclusion_polygons_json",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "stream_type IN ('RTSP','RTSPS','DEMO_MP4')", name="ck_cameras_stream_type"
        ),
        sa.CheckConstraint("target_fps BETWEEN 1 AND 5", name="ck_cameras_target_fps"),
        sa.CheckConstraint(
            "status IN ('ONLINE','RECONNECTING','OFFLINE','DISABLED')", name="ck_cameras_status"
        ),
    )

    # 6. tables
    op.create_table(
        "tables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "venue_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("venues.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "camera_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cameras.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("table_code", sa.String(20), nullable=False),
        sa.Column("section_name", sa.String(60), nullable=False, server_default="Main"),
        sa.Column("seat_capacity", sa.SmallInteger, nullable=False),
        sa.Column(
            "polygon_json", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("floor_x", sa.Float(precision=24), nullable=False, server_default=sa.text("0")),
        sa.Column("floor_y", sa.Float(precision=24), nullable=False, server_default=sa.text("0")),
        sa.Column("shape", sa.String(16), nullable=False, server_default="RECT"),
        sa.Column("current_state", sa.String(20), nullable=False, server_default="FREE"),
        sa.Column(
            "current_guest_count", sa.SmallInteger, nullable=False, server_default=sa.text("0")
        ),
        sa.Column("current_confidence", sa.Float(precision=24), nullable=True),
        sa.Column("occupied_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_staff_visit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("predicted_free_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("seat_capacity BETWEEN 1 AND 20", name="ck_tables_seat_capacity"),
        sa.CheckConstraint("shape IN ('RECT','CIRCLE','BOOTH')", name="ck_tables_shape"),
        sa.CheckConstraint(
            "current_state IN ('FREE','OCCUPIED','NEEDS_SERVICE','NEEDS_CLEANING','RESERVED','UNKNOWN')",
            name="ck_tables_current_state",
        ),
        sa.CheckConstraint("current_guest_count >= 0", name="ck_tables_guest_count_nonneg"),
    )
    op.create_index(
        "uq_tables_venue_code_active",
        "tables",
        ["venue_id", "table_code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_tables_venue_active",
        "tables",
        ["venue_id", "section_name"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 7. table_state_events
    op.create_table(
        "table_state_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("previous_state", sa.String(20), nullable=True),
        sa.Column("new_state", sa.String(20), nullable=False),
        sa.Column("guest_count", sa.SmallInteger, nullable=False),
        sa.Column("confidence", sa.Float(precision=24), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("source IN ('AI','MANUAL','SYSTEM')", name="ck_events_source"),
    )
    op.create_index(
        "idx_events_table_occurred", "table_state_events", ["table_id", sa.text("occurred_at DESC")]
    )

    # 8. occupancy_snapshots (Native PostgreSQL 16+ monthly RANGE partition)
    op.execute(
        """
        CREATE TABLE occupancy_snapshots (
            captured_at TIMESTAMPTZ NOT NULL,
            table_id UUID NOT NULL,
            organization_id UUID NOT NULL,
            venue_id UUID NOT NULL,
            section_name VARCHAR(60) NOT NULL,
            state VARCHAR(20) NOT NULL,
            guest_count SMALLINT NOT NULL,
            seat_capacity SMALLINT NOT NULL,
            sla_breached BOOLEAN NOT NULL DEFAULT false,
            PRIMARY KEY (captured_at, table_id)
        ) PARTITION BY RANGE (captured_at);
        """
    )
    op.execute(
        "CREATE INDEX idx_snapshots_venue_time ON occupancy_snapshots (venue_id, captured_at DESC);"
    )

    # Monthly partition helper + pre-created rolling monthly partitions (-2 to +14 months from now)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ensure_occupancy_partition(target_ts TIMESTAMPTZ)
        RETURNS VOID AS $$
        DECLARE
            start_month TIMESTAMPTZ := date_trunc('month', target_ts AT TIME ZONE 'UTC') AT TIME ZONE 'UTC';
            end_month TIMESTAMPTZ := start_month + INTERVAL '1 month';
            part_name TEXT := format('occupancy_snapshots_%s', to_char(start_month AT TIME ZONE 'UTC', 'YYYY_MM'));
        BEGIN
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS %I PARTITION OF occupancy_snapshots FOR VALUES FROM (%L) TO (%L)',
                part_name, start_month, end_month
            );
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            m INT;
        BEGIN
            FOR m IN -2..14 LOOP
                PERFORM ensure_occupancy_partition(now() + (m || ' month')::interval);
            END LOOP;
        END $$;
        """
    )

    # Hourly rollup view for SCR-010 analytics
    op.execute(
        """
        CREATE MATERIALIZED VIEW rollup_hourly_venue AS
        SELECT
            venue_id,
            organization_id,
            section_name,
            date_trunc('hour', captured_at) AS bucket_hour,
            COUNT(*) AS sample_count,
            ROUND(AVG(CASE WHEN state IN ('OCCUPIED','NEEDS_SERVICE') THEN 100.0 ELSE 0.0 END)::numeric, 2) AS avg_occupancy_pct,
            MAX(guest_count) AS peak_seated_guests,
            SUM(CASE WHEN sla_breached THEN 1 ELSE 0 END) AS sla_breach_count
        FROM occupancy_snapshots
        GROUP BY venue_id, organization_id, section_name, date_trunc('hour', captured_at);
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_rollup_hourly_venue ON rollup_hourly_venue (venue_id, section_name, bucket_hour);"
    )

    # 9. alerts
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tables.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "camera_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cameras.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("alert_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("dedup_key", sa.String(160), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "acknowledged_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "alert_type IN ('UNATTENDED_TABLE','NEEDS_CLEANING','CAMERA_OFFLINE','LOW_CONFIDENCE')",
            name="ck_alerts_type",
        ),
        sa.CheckConstraint("severity IN ('INFO','WARNING','CRITICAL')", name="ck_alerts_severity"),
        sa.CheckConstraint(
            "status IN ('ACTIVE','ACKNOWLEDGED','RESOLVED')", name="ck_alerts_status"
        ),
    )
    op.create_index(
        "uq_alerts_active_dedup",
        "alerts",
        ["dedup_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('ACTIVE','ACKNOWLEDGED')"),
    )
    op.create_index(
        "idx_alerts_venue_status_created",
        "alerts",
        ["venue_id", "status", sa.text("created_at DESC")],
    )

    # 10. waitlist_entries
    op.create_table(
        "waitlist_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("party_name", sa.String(80), nullable=False),
        sa.Column("party_size", sa.SmallInteger, nullable=False),
        sa.Column("phone_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("quoted_wait_minutes", sa.SmallInteger, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="WAITING"),
        sa.Column(
            "assigned_table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tables.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("seated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("party_size BETWEEN 1 AND 20", name="ck_waitlist_party_size"),
        sa.CheckConstraint(
            "status IN ('WAITING','SEATED','CANCELLED','NO_SHOW')", name="ck_waitlist_status"
        ),
    )
    op.create_index(
        "idx_waitlist_venue_status",
        "waitlist_entries",
        ["venue_id", "status", sa.text("joined_at ASC")],
    )

    # 11. ml_models
    op.create_table(
        "ml_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_role", sa.String(32), nullable=False),
        sa.Column("version", sa.String(64), nullable=False, unique=True),
        sa.Column("artifact_uri", sa.Text, nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("dataset_version", sa.String(64), nullable=False),
        sa.Column(
            "eval_metrics_json",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("gate_status", sa.String(20), nullable=False, server_default="NOT_MEASURED"),
        sa.Column("channel", sa.String(16), nullable=False, server_default="experimental"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "model_role IN ('DETECTOR','CLEANLINESS','TURNOVER_ETA')", name="ck_ml_models_role"
        ),
        sa.CheckConstraint(
            "gate_status IN ('NOT_MEASURED','PASS','FAIL')", name="ck_ml_models_gate_status"
        ),
        sa.CheckConstraint("channel IN ('experimental','stable')", name="ck_ml_models_channel"),
    )

    # 12. ml_review_items
    op.create_table(
        "ml_review_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_path", sa.Text, nullable=True),
        sa.Column("predicted_state", sa.String(20), nullable=False),
        sa.Column("predicted_guest_count", sa.SmallInteger, nullable=False),
        sa.Column("confidence", sa.Float(precision=24), nullable=False),
        sa.Column("trigger_reason", sa.String(32), nullable=False),
        sa.Column("review_status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("human_state", sa.String(20), nullable=True),
        sa.Column("human_guest_count", sa.SmallInteger, nullable=True),
        sa.Column(
            "issue_tags",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "trigger_reason IN ('LOW_CONFIDENCE','USER_FLAGGED','DISAGREEMENT')",
            name="ck_ml_review_trigger",
        ),
        sa.CheckConstraint(
            "review_status IN ('PENDING','REVIEWED','EXCLUDED')", name="ck_ml_review_status"
        ),
    )
    op.create_index(
        "idx_ml_review_venue_status",
        "ml_review_items",
        ["venue_id", "review_status", sa.text("created_at DESC")],
    )

    # 13. alert_rules
    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_name", sa.String(60), nullable=True),
        sa.Column(
            "unattended_service_sec", sa.Integer, nullable=False, server_default=sa.text("300")
        ),
        sa.Column(
            "cleaning_alert_delay_sec", sa.Integer, nullable=False, server_default=sa.text("120")
        ),
        sa.Column(
            "occupancy_debounce_sec", sa.Integer, nullable=False, server_default=sa.text("10")
        ),
        sa.Column(
            "departure_debounce_sec", sa.Integer, nullable=False, server_default=sa.text("20")
        ),
        sa.Column(
            "min_confidence", sa.Float(precision=24), nullable=False, server_default=sa.text("0.65")
        ),
        sa.Column(
            "require_bussing_confirmation",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("webhook_url_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("webhook_secret_encrypted", sa.LargeBinary, nullable=True),
        sa.Column(
            "quiet_hours_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "unattended_service_sec BETWEEN 60 AND 1800", name="ck_alert_rules_unattended"
        ),
        sa.CheckConstraint(
            "cleaning_alert_delay_sec BETWEEN 0 AND 900", name="ck_alert_rules_cleaning"
        ),
        sa.CheckConstraint(
            "occupancy_debounce_sec BETWEEN 3 AND 60", name="ck_alert_rules_occ_debounce"
        ),
        sa.CheckConstraint(
            "departure_debounce_sec BETWEEN 5 AND 120", name="ck_alert_rules_dep_debounce"
        ),
        sa.CheckConstraint("min_confidence BETWEEN 0.30 AND 0.95", name="ck_alert_rules_min_conf"),
    )

    # 14. audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("before_json", postgresql.JSONB, nullable=True),
        sa.Column("after_json", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", postgresql.INET, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "idx_audit_org_created", "audit_logs", ["organization_id", sa.text("created_at DESC")]
    )

    # 15. system_settings
    op.create_table(
        "system_settings",
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "ai_inference_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column("face_blur_enforced", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "snapshot_retention_days", sa.SmallInteger, nullable=False, server_default=sa.text("7")
        ),
        sa.Column(
            "analytics_retention_days",
            sa.SmallInteger,
            nullable=False,
            server_default=sa.text("365"),
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "snapshot_retention_days BETWEEN 0 AND 30", name="ck_system_settings_snapshot_retention"
        ),
        sa.CheckConstraint(
            "analytics_retention_days BETWEEN 30 AND 1095",
            name="ck_system_settings_analytics_retention",
        ),
    )

    # Last-OWNER protection trigger (docs/04 §5.5)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_last_owner_removal()
        RETURNS TRIGGER AS $$
        DECLARE
            remaining_owners INT;
        BEGIN
            IF OLD.role = 'OWNER' AND OLD.is_active = TRUE THEN
                IF TG_OP = 'DELETE' OR NEW.role <> 'OWNER' OR NEW.is_active = FALSE THEN
                    SELECT COUNT(*) INTO remaining_owners
                    FROM users
                    WHERE organization_id = OLD.organization_id
                      AND role = 'OWNER'
                      AND is_active = TRUE
                      AND id <> OLD.id;
                    IF remaining_owners = 0 THEN
                        RAISE EXCEPTION 'LAST_OWNER_PROTECTED: cannot remove or demote last active OWNER'
                            USING ERRCODE = 'P0001';
                    END IF;
                END IF;
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_last_owner_removal
        BEFORE UPDATE OR DELETE ON users
        FOR EACH ROW
        EXECUTE FUNCTION prevent_last_owner_removal();
        """
    )

    # PostgreSQL Row-Level Security (RLS) on multi-tenant tables (docs/04 §6)
    for tbl in RLS_TABLES:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{tbl} ON {tbl}
            USING (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
            WITH CHECK (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid);
            """
        )


def downgrade() -> None:
    for tbl in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{tbl} ON {tbl};")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP TRIGGER IF EXISTS trg_prevent_last_owner_removal ON users;")
    op.execute("DROP FUNCTION IF EXISTS prevent_last_owner_removal();")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS rollup_hourly_venue;")
    op.execute("DROP FUNCTION IF EXISTS ensure_occupancy_partition(TIMESTAMPTZ);")

    op.drop_table("system_settings")
    op.drop_table("audit_logs")
    op.drop_table("alert_rules")
    op.drop_table("ml_review_items")
    op.drop_table("ml_models")
    op.drop_table("waitlist_entries")
    op.drop_table("alerts")
    op.execute("DROP TABLE IF EXISTS occupancy_snapshots CASCADE;")
    op.drop_table("table_state_events")
    op.drop_table("tables")
    op.drop_table("cameras")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.drop_table("venues")
    op.drop_table("organizations")
