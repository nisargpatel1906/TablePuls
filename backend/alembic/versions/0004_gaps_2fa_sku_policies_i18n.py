"""Alembic 0004: TOTP recovery codes, 2FA login challenge tokens, org policy toggles, SKU & EN/HI translations."""

from __future__ import annotations

from typing import Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: Final[str] = "0004_gaps_2fa_sku_policies_i18n"
down_revision: Final[str] = "0003_phase2_tables_menu_qr"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_refresh_tokens_type", "refresh_tokens", type_="check")
    op.create_check_constraint(
        "ck_refresh_tokens_type",
        "refresh_tokens",
        "token_type IN ('REFRESH','INVITE','PASSWORD_RESET','2FA_CHALLENGE')",
    )

    op.add_column(
        "users",
        sa.Column(
            "totp_recovery_codes_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    op.add_column(
        "system_settings",
        sa.Column(
            "require_2fa_roles",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    op.add_column(
        "system_settings",
        sa.Column(
            "managers_can_manage_tables",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "system_settings",
        sa.Column(
            "managers_can_manage_menu",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "system_settings",
        sa.Column(
            "admins_can_manage_tables",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "system_settings",
        sa.Column(
            "admins_can_manage_menu",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    op.add_column(
        "menus",
        sa.Column(
            "translations_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "menu_categories",
        sa.Column(
            "translations_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "menu_items",
        sa.Column("sku", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "menu_items",
        sa.Column(
            "translations_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_menu_items_venue_sku_active
        ON menu_items (venue_id, lower(sku))
        WHERE deleted_at IS NULL AND sku IS NOT NULL;
        """
    )

    op.execute("REVOKE ALL ON v_public_menu_catalog FROM tablepulse_public;")
    op.execute("DROP VIEW IF EXISTS v_public_menu_catalog;")
    op.execute(
        """
        CREATE OR REPLACE VIEW v_public_menu_catalog AS
        SELECT
            m.venue_id,
            m.id AS menu_id,
            m.name AS menu_name,
            m.description AS menu_description,
            m.translations_json AS menu_translations_json,
            m.schedule_json AS menu_schedule_json,
            m.is_default AS menu_is_default,
            m.sort_order AS menu_sort_order,
            c.id AS category_id,
            c.name AS category_name,
            c.description AS category_description,
            c.translations_json AS category_translations_json,
            c.sort_order AS category_sort_order,
            i.id AS item_id,
            i.sku,
            i.name AS item_name,
            i.description AS item_description,
            i.translations_json AS item_translations_json,
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
    op.execute("GRANT SELECT ON v_public_menu_catalog TO tablepulse_public;")


def downgrade() -> None:
    op.execute("REVOKE ALL ON v_public_menu_catalog FROM tablepulse_public;")
    op.execute("DROP VIEW IF EXISTS v_public_menu_catalog;")
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
    op.execute("GRANT SELECT ON v_public_menu_catalog TO tablepulse_public;")

    op.execute("DROP INDEX IF EXISTS uq_menu_items_venue_sku_active;")
    op.drop_column("menu_items", "translations_json")
    op.drop_column("menu_items", "sku")
    op.drop_column("menu_categories", "translations_json")
    op.drop_column("menus", "translations_json")

    op.drop_column("system_settings", "admins_can_manage_menu")
    op.drop_column("system_settings", "admins_can_manage_tables")
    op.drop_column("system_settings", "managers_can_manage_menu")
    op.drop_column("system_settings", "managers_can_manage_tables")
    op.drop_column("system_settings", "require_2fa_roles")

    op.drop_column("users", "totp_recovery_codes_json")

    op.drop_constraint("ck_refresh_tokens_type", "refresh_tokens", type_="check")
    op.execute("DELETE FROM refresh_tokens WHERE token_type = '2FA_CHALLENGE';")
    op.create_check_constraint(
        "ck_refresh_tokens_type",
        "refresh_tokens",
        "token_type IN ('REFRESH','INVITE','PASSWORD_RESET')",
    )
