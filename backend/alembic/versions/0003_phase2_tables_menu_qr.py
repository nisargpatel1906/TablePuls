"""Phase 2 schema extensions: venues/tables updates, 6 new tables (#16-#21), RLS, read-only public views & role, and QR backfill.

Revision ID: 0003_phase2_tables_menu_qr
Revises: 0002_expand_camera_stream_types
Create Date: 2026-11-26 00:00:00+00:00
"""

from __future__ import annotations

import os
import secrets
import time

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_phase2_tables_menu_qr"
down_revision: str | None = "0002_expand_camera_stream_types"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

PHASE2_RLS_TABLES = (
    "table_qr_codes",
    "menus",
    "menu_categories",
    "menu_items",
    "menu_media_assets",
    "qr_scan_daily_stats",
)


def _uuid7_str() -> str:
    import uuid

    timestamp_ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    rand_bytes = os.urandom(10)
    rand_a = int.from_bytes(rand_bytes[:2], "big") & 0x0FFF
    rand_b = int.from_bytes(rand_bytes[2:], "big") & 0x3FFFFFFFFFFFFFFF
    val = (timestamp_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0x2 << 62) | rand_b
    return str(uuid.UUID(int=val))


def upgrade() -> None:
    # 1. Additive columns on `venues`
    op.add_column(
        "venues",
        sa.Column(
            "allow_host_menu_availability",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "venues",
        sa.Column("currency_code", sa.CHAR(3), nullable=False, server_default=sa.text("'INR'")),
    )
    op.add_column(
        "venues",
        sa.Column(
            "menu_public_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")
        ),
    )
    op.add_column(
        "venues",
        sa.Column(
            "show_unavailable_items_public",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column("venues", sa.Column("logo_storage_key", sa.Text, nullable=True))
    op.add_column("venues", sa.Column("menu_tagline", sa.String(160), nullable=True))
    op.add_column(
        "venues",
        sa.Column("menu_revision", sa.BigInteger, nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "venues",
        sa.Column("qr_grace_days", sa.SmallInteger, nullable=False, server_default=sa.text("7")),
    )
    op.create_check_constraint("ck_venues_currency_code", "venues", "currency_code ~ '^[A-Z]{3}$'")
    op.create_check_constraint("ck_venues_menu_revision", "venues", "menu_revision >= 1")
    op.create_check_constraint(
        "ck_venues_qr_grace_days", "venues", "qr_grace_days BETWEEN 0 AND 30"
    )

    # 2. Additive & nullability updates on `tables`
    op.alter_column(
        "tables",
        "polygon_json",
        existing_type=postgresql.JSONB,
        nullable=True,
        server_default=None,
    )
    op.create_check_constraint(
        "ck_tables_polygon_json_type",
        "tables",
        "polygon_json IS NULL OR jsonb_typeof(polygon_json) = 'array'",
    )
    op.add_column("tables", sa.Column("display_name", sa.String(80), nullable=True))
    op.add_column(
        "tables",
        sa.Column("min_capacity", sa.SmallInteger, nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "tables",
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "tables",
        sa.Column("is_combinable", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.add_column("tables", sa.Column("table_notes", sa.String(255), nullable=True))
    op.add_column(
        "tables",
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    op.create_check_constraint(
        "ck_tables_min_capacity", "tables", "min_capacity >= 1 AND min_capacity <= seat_capacity"
    )

    # 3. #16 table_qr_codes
    op.create_table(
        "table_qr_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "venue_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("venues.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tables.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("token", sa.String(32), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scan_count", sa.BigInteger, nullable=False, server_default=sa.text("0")),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revoked_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("revoked_reason", sa.String(64), nullable=True),
        sa.CheckConstraint(
            "status IN ('ACTIVE','GRACE','REVOKED','RETIRED')",
            name="ck_table_qr_codes_status",
        ),
        sa.CheckConstraint("scan_count >= 0", name="ck_table_qr_codes_scan_count"),
    )
    op.create_index(
        "idx_qr_table_active",
        "table_qr_codes",
        ["table_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index("idx_qr_venue_table", "table_qr_codes", ["venue_id", "table_id"])

    # 4. #17 menus
    op.create_table(
        "menus",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "venue_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("venues.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="PUBLISHED"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("schedule_json", postgresql.JSONB, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('DRAFT','PUBLISHED','ARCHIVED')", name="ck_menus_status"),
    )
    op.create_index(
        "uq_menus_venue_name_active",
        "menus",
        ["venue_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_menus_venue_sort",
        "menus",
        ["venue_id", "is_active", "sort_order"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 5. #18 menu_categories
    op.create_table(
        "menu_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "venue_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("venues.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "menu_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("menus.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_categories_menu_name_active",
        "menu_categories",
        ["menu_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_categories_menu_sort",
        "menu_categories",
        ["menu_id", "is_active", "sort_order"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 6. #20 menu_media_assets (before #19 menu_items FK)
    op.create_table(
        "menu_media_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "venue_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("venues.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.Text, nullable=False, unique=True),
        sa.Column("thumb_storage_key", sa.Text, nullable=False, unique=True),
        sa.Column("mime_type", sa.String(32), nullable=False, server_default="image/webp"),
        sa.Column("byte_size", sa.Integer, nullable=False),
        sa.Column("width_px", sa.SmallInteger, nullable=False),
        sa.Column("height_px", sa.SmallInteger, nullable=False),
        sa.Column("sha256", sa.CHAR(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="READY"),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("mime_type IN ('image/webp')", name="ck_menu_media_mime_type"),
        sa.CheckConstraint("byte_size > 0", name="ck_menu_media_byte_size"),
        sa.CheckConstraint("status IN ('READY','FAILED')", name="ck_menu_media_status"),
    )
    op.create_index("idx_menu_media_venue_sha256", "menu_media_assets", ["venue_id", "sha256"])

    # 7. #19 menu_items
    op.create_table(
        "menu_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "venue_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("venues.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("menu_categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("price_minor_units", sa.BigInteger, nullable=False),
        sa.Column("compare_at_price_minor_units", sa.BigInteger, nullable=True),
        sa.Column(
            "image_asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("menu_media_assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("image_alt", sa.String(160), nullable=True),
        sa.Column("is_available", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("unavailable_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_featured", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column(
            "dietary_tags",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "allergens",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "variants_json",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("prep_time_minutes", sa.SmallInteger, nullable=True),
        sa.Column("calories_kcal", sa.SmallInteger, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "price_minor_units >= 0 AND price_minor_units <= 100000000",
            name="ck_menu_items_price",
        ),
        sa.CheckConstraint(
            "compare_at_price_minor_units IS NULL OR compare_at_price_minor_units > price_minor_units",
            name="ck_menu_items_compare_price",
        ),
        sa.CheckConstraint(
            "prep_time_minutes IS NULL OR prep_time_minutes BETWEEN 1 AND 240",
            name="ck_menu_items_prep_time",
        ),
        sa.CheckConstraint(
            "calories_kcal IS NULL OR calories_kcal BETWEEN 0 AND 10000",
            name="ck_menu_items_calories",
        ),
    )
    op.create_index(
        "idx_items_category_sort",
        "menu_items",
        ["category_id", "sort_order"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_items_venue_available",
        "menu_items",
        ["venue_id", "is_available"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 8. #21 qr_scan_daily_stats
    op.create_table(
        "qr_scan_daily_stats",
        sa.Column(
            "venue_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("venues.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tables.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("scan_date", sa.Date, primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("scan_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.CheckConstraint("scan_count >= 0", name="ck_qr_scan_stats_nonneg"),
    )
    op.create_index(
        "idx_qr_stats_venue_date",
        "qr_scan_daily_stats",
        ["venue_id", sa.text("scan_date DESC")],
    )

    # 9. Enable PostgreSQL Row-Level Security on all 6 Phase 2 tables
    for tbl in PHASE2_RLS_TABLES:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{tbl} ON {tbl}
            USING (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
            WITH CHECK (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid);
            """
        )

    # 10. Create read-only public views + least-privilege `tablepulse_public` role
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tablepulse_public') THEN
                CREATE ROLE tablepulse_public LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD 'tablepulse_public_readonly';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW v_public_qr_resolution AS
        SELECT
            q.token,
            q.status AS qr_status,
            q.grace_until,
            q.revoked_reason,
            q.venue_id,
            q.table_id,
            COALESCE(NULLIF(t.display_name, ''), 'Table ' || t.table_code) AS table_label,
            t.is_active AS table_is_active,
            t.deleted_at AS table_deleted_at,
            v.name AS venue_name,
            v.menu_tagline,
            v.logo_storage_key,
            v.currency_code,
            v.timezone,
            v.menu_public_enabled,
            v.show_unavailable_items_public,
            v.menu_revision,
            v.deleted_at AS venue_deleted_at
        FROM table_qr_codes q
        JOIN tables t ON t.id = q.table_id
        JOIN venues v ON v.id = q.venue_id;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW v_public_menu_catalog AS
        SELECT
            m.venue_id,
            m.id AS menu_id,
            m.name AS menu_name,
            m.description AS menu_description,
            m.schedule_json AS menu_schedule_json,
            m.is_default AS menu_is_default,
            m.sort_order AS menu_sort_order,
            c.id AS category_id,
            c.name AS category_name,
            c.description AS category_description,
            c.sort_order AS category_sort_order,
            i.id AS item_id,
            i.name AS item_name,
            i.description AS item_description,
            i.price_minor_units,
            i.compare_at_price_minor_units,
            i.variants_json,
            i.is_available,
            i.unavailable_until,
            i.is_featured,
            i.dietary_tags,
            i.allergens,
            i.prep_time_minutes,
            i.calories_kcal,
            i.image_alt,
            i.sort_order AS item_sort_order,
            a.storage_key AS image_storage_key,
            a.thumb_storage_key
        FROM menus m
        LEFT JOIN menu_categories c
            ON c.menu_id = m.id AND c.deleted_at IS NULL AND c.is_active = true
        LEFT JOIN menu_items i
            ON i.category_id = c.id AND i.deleted_at IS NULL
        LEFT JOIN menu_media_assets a
            ON a.id = i.image_asset_id AND a.status = 'READY'
        WHERE m.deleted_at IS NULL
          AND m.status = 'PUBLISHED'
          AND m.is_active = true;
        """
    )
    op.execute("REVOKE ALL ON SCHEMA public FROM tablepulse_public;")
    op.execute("GRANT USAGE ON SCHEMA public TO tablepulse_public;")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM tablepulse_public;")
    op.execute(
        "GRANT SELECT ON v_public_qr_resolution, v_public_menu_catalog TO tablepulse_public;"
    )

    # 11. Backfill one ACTIVE 128-bit CSPRNG QR token for every existing non-deleted v1.0 table
    conn = op.get_bind()
    existing_tables = conn.execute(
        sa.text(
            """
            SELECT t.id, t.organization_id, t.venue_id
            FROM tables t
            WHERE t.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM table_qr_codes q
                  WHERE q.table_id = t.id AND q.status = 'ACTIVE'
              )
            """
        )
    ).fetchall()
    for row in existing_tables:
        conn.execute(
            sa.text(
                """
                INSERT INTO table_qr_codes
                    (id, organization_id, venue_id, table_id, token, status, scan_count)
                VALUES
                    (:id, :org_id, :venue_id, :table_id, :token, 'ACTIVE', 0)
                """
            ),
            {
                "id": _uuid7_str(),
                "org_id": str(row.organization_id),
                "venue_id": str(row.venue_id),
                "table_id": str(row.id),
                "token": secrets.token_urlsafe(16),
            },
        )


def downgrade() -> None:
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM tablepulse_public;")
    op.execute("DROP VIEW IF EXISTS v_public_menu_catalog;")
    op.execute("DROP VIEW IF EXISTS v_public_qr_resolution;")

    for tbl in PHASE2_RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{tbl} ON {tbl};")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;")

    op.drop_index("idx_qr_stats_venue_date", table_name="qr_scan_daily_stats")
    op.drop_table("qr_scan_daily_stats")

    op.drop_index("idx_items_venue_available", table_name="menu_items")
    op.drop_index("idx_items_category_sort", table_name="menu_items")
    op.drop_table("menu_items")

    op.drop_index("idx_menu_media_venue_sha256", table_name="menu_media_assets")
    op.drop_table("menu_media_assets")

    op.drop_index("idx_categories_menu_sort", table_name="menu_categories")
    op.drop_index("uq_categories_menu_name_active", table_name="menu_categories")
    op.drop_table("menu_categories")

    op.drop_index("idx_menus_venue_sort", table_name="menus")
    op.drop_index("uq_menus_venue_name_active", table_name="menus")
    op.drop_table("menus")

    op.drop_index("idx_qr_venue_table", table_name="table_qr_codes")
    op.drop_index("idx_qr_table_active", table_name="table_qr_codes")
    op.drop_table("table_qr_codes")

    op.drop_constraint("ck_tables_min_capacity", "tables", type_="check")
    op.drop_column("tables", "sort_order")
    op.drop_column("tables", "table_notes")
    op.drop_column("tables", "is_combinable")
    op.drop_column("tables", "is_active")
    op.drop_column("tables", "min_capacity")
    op.drop_column("tables", "display_name")
    op.drop_constraint("ck_tables_polygon_json_type", "tables", type_="check")
    op.execute("UPDATE tables SET polygon_json = '[]'::jsonb WHERE polygon_json IS NULL;")
    op.alter_column(
        "tables",
        "polygon_json",
        existing_type=postgresql.JSONB,
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )

    op.drop_constraint("ck_venues_qr_grace_days", "venues", type_="check")
    op.drop_constraint("ck_venues_menu_revision", "venues", type_="check")
    op.drop_constraint("ck_venues_currency_code", "venues", type_="check")
    op.drop_column("venues", "qr_grace_days")
    op.drop_column("venues", "menu_revision")
    op.drop_column("venues", "menu_tagline")
    op.drop_column("venues", "logo_storage_key")
    op.drop_column("venues", "show_unavailable_items_public")
    op.drop_column("venues", "menu_public_enabled")
    op.drop_column("venues", "currency_code")
    op.drop_column("venues", "allow_host_menu_availability")
