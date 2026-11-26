# TablePulse Phase 2 — Database Schema Extensions & Relationships

## Quick Reference
- **Database Engine**: PostgreSQL 16 (100% standard PostgreSQL — no proprietary extensions required).
- **Migration Strategy**: Single forward-only Alembic migration (`002_phase2_tables_menu_qr.py`) that (1) adds nullable/defaulted columns to existing `venues` and `tables`, (2) creates 6 new tables (`#16`–`#21`), (3) enables PostgreSQL RLS on all 6 new tables, and (4) **backfills one `ACTIVE` `table_qr_codes` row for every existing non-deleted v1.0 table**.
- **Conventions Inherited from v1.0**: UUIDv7 primary keys, `TIMESTAMPTZ` UTC timestamps, `organization_id` + `venue_id` tenant columns on every venue-scoped table, explicit `ON DELETE` rules (no blind cascades).

---

## 1. Additive Changes to Existing v1.0 Tables (Backward-Compatible)

### 1.1 `venues` (Existing Table `#2`) — New Columns
| Column | Type | Nullability & Default | Constraints | Purpose |
|---|---|---|---|---|
| `currency_code` | `CHAR(3)` | `NOT NULL DEFAULT 'INR'` | `CHECK (currency_code ~ '^[A-Z]{3}$')` | ISO-4217 currency for formatting item prices (`INR`, `USD`, `EUR`). |
| `menu_public_enabled` | `BOOLEAN` | `NOT NULL DEFAULT true` | — | Master venue switch to temporarily unpublish QR digital menu. |
| `show_unavailable_items_public` | `BOOLEAN` | `NOT NULL DEFAULT true` | — | If `true`, sold-out items appear dimmed with "Unavailable" badge; if `false`, hidden from diners. |
| `logo_storage_key` | `TEXT` | `NULL` | — | Relative path to validated venue logo shown at top of `SCR-022`. |
| `menu_tagline` | `VARCHAR(160)` | `NULL` | — | Short subtitle shown under venue name on customer digital menu. |
| `menu_revision` | `BIGINT` | `NOT NULL DEFAULT 1` | `CHECK (menu_revision >= 1)` | Monotonic revision counter bumped atomically on any public menu/branding/QR change (ETag + cache invalidation). |
| `qr_grace_days` | `SMALLINT` | `NOT NULL DEFAULT 7` | `CHECK (qr_grace_days BETWEEN 0 AND 30)` | Default grace period when regenerating a table QR (`0` = immediate revocation). |

### 1.2 `tables` (Existing Table `#6`) — Column Changes
| Column | Change | Type & Default | Constraints | Purpose |
|---|---|---|---|---|
| `polygon_json` | **ALTER** | `JSONB NULL` (was `NOT NULL`) | `CHECK (polygon_json IS NULL OR jsonb_typeof(polygon_json) = 'array')` | Allows creating tables without camera calibration. |
| `floor_x`, `floor_y` | **ALTER** | `REAL NOT NULL DEFAULT 0.0` | — | Safe default when created from Table Management before placing on floor map. |
| `display_name` | **ADD** | `VARCHAR(80) NULL` | — | Optional friendly name (e.g., `"Window Booth 4"`); falls back to `table_code`. |
| `min_capacity` | **ADD** | `SMALLINT NOT NULL DEFAULT 1` | `CHECK (min_capacity >= 1 AND min_capacity <= seat_capacity)` | Minimum party size for seating/waitlist guidance. |
| `is_active` | **ADD** | `BOOLEAN NOT NULL DEFAULT true` | — | Temporarily disable a table (e.g., seasonal patio) without deleting history. |
| `is_combinable` | **ADD** | `BOOLEAN NOT NULL DEFAULT false` | — | Indicates table can be joined with adjacent tables for large parties. |
| `table_notes` | **ADD** | `VARCHAR(255) NULL` | — | Internal staff notes (NEVER exposed on public QR menu!). |
| `sort_order` | **ADD** | `INT NOT NULL DEFAULT 0` | — | Deterministic display ordering in `SCR-017` and `SCR-020`. |

---

## 2. New Phase 2 Tables (`#16`–`#21`)

### Table `#16`: `table_qr_codes`
Stores unique, revocable QR tokens bound 1-to-1 (for active tokens) to a restaurant table.
- `id UUID PRIMARY KEY`
- `organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT`
- `venue_id UUID NOT NULL REFERENCES venues(id) ON DELETE RESTRICT`
- `table_id UUID NOT NULL REFERENCES tables(id) ON DELETE RESTRICT`
- `token VARCHAR(32) NOT NULL UNIQUE` — 128-bit CSPRNG URL-safe base64url token (`secrets.token_urlsafe(16)`, 22 chars).
- `status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','GRACE','REVOKED','RETIRED'))`
- `grace_until TIMESTAMPTZ NULL` — Optional expiry when old QR enters `GRACE` during sticker swap (background job transitions `GRACE -> REVOKED` when `now() >= grace_until`).
- `scan_count BIGINT NOT NULL DEFAULT 0 CHECK (scan_count >= 0)`
- `last_scanned_at TIMESTAMPTZ NULL`
- `created_by UUID REFERENCES users(id) ON DELETE SET NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `revoked_at TIMESTAMPTZ NULL`
- `revoked_by UUID REFERENCES users(id) ON DELETE SET NULL`
- `revoked_reason VARCHAR(64) NULL` (`'REGENERATED'`, `'TABLE_DELETED'`, `'SECURITY_REVOKE'`)
- **Key Constraint**: Partial unique index `UNIQUE (table_id) WHERE status = 'ACTIVE'` — guarantees every table has at most one active QR code at any moment while retaining revoked token history for `410 Gone` handling.

### Table `#17`: `menus`
Supports multiple menus per venue (e.g., Main, Lunch, Drinks).
- `id UUID PRIMARY KEY`
- `organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT`
- `venue_id UUID NOT NULL REFERENCES venues(id) ON DELETE RESTRICT`
- `name VARCHAR(100) NOT NULL`
- `description VARCHAR(300) NULL`
- `status VARCHAR(16) NOT NULL DEFAULT 'PUBLISHED' CHECK (status IN ('DRAFT','PUBLISHED','ARCHIVED'))`
- `is_active BOOLEAN NOT NULL DEFAULT true`
- `is_default BOOLEAN NOT NULL DEFAULT false`
- `schedule_json JSONB NULL` — Versioned `v1` schema: `{ "v": 1, "windows": [{ "days": [1..7], "start": "11:30", "end": "15:00" }] }` (`NULL` = always active when `is_active=true`).
- `sort_order INT NOT NULL DEFAULT 0`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `deleted_at TIMESTAMPTZ NULL`
- **Constraint**: `UNIQUE (venue_id, lower(name)) WHERE deleted_at IS NULL`.

### Table `#18`: `menu_categories`
Ordered sections within a menu (e.g., Starters, Mains, Beverages).
- `id UUID PRIMARY KEY`
- `organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT`
- `venue_id UUID NOT NULL REFERENCES venues(id) ON DELETE RESTRICT`
- `menu_id UUID NOT NULL REFERENCES menus(id) ON DELETE RESTRICT`
- `name VARCHAR(100) NOT NULL`
- `description VARCHAR(300) NULL`
- `is_active BOOLEAN NOT NULL DEFAULT true`
- `sort_order INT NOT NULL DEFAULT 0`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `deleted_at TIMESTAMPTZ NULL`
- **Constraint**: `UNIQUE (menu_id, lower(name)) WHERE deleted_at IS NULL`.

### Table `#19`: `menu_items`
Individual food and beverage entries inside a category.
- `id UUID PRIMARY KEY`
- `organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT`
- `venue_id UUID NOT NULL REFERENCES venues(id) ON DELETE RESTRICT`
- `category_id UUID NOT NULL REFERENCES menu_categories(id) ON DELETE RESTRICT`
- `name VARCHAR(120) NOT NULL`
- `description VARCHAR(500) NULL`
- `price_minor_units BIGINT NOT NULL CHECK (price_minor_units >= 0 AND price_minor_units <= 100000000)`
- `compare_at_price_minor_units BIGINT NULL CHECK (compare_at_price_minor_units IS NULL OR compare_at_price_minor_units > price_minor_units)`
- `image_asset_id UUID NULL REFERENCES menu_media_assets(id) ON DELETE SET NULL`
- `image_alt VARCHAR(160) NULL`
- `is_available BOOLEAN NOT NULL DEFAULT true`
- `is_featured BOOLEAN NOT NULL DEFAULT false`
- `dietary_tags TEXT[] NOT NULL DEFAULT '{}'` (validated against enum: `VEG`, `NON_VEG`, `VEGAN`, `GLUTEN_FREE`, `DAIRY_FREE`, `NUT_FREE`, `SPICY_MILD`, `SPICY_MEDIUM`, `SPICY_HOT`, `CHEF_SPECIAL`)
- `allergens TEXT[] NOT NULL DEFAULT '{}'` (e.g., `NUTS`, `DAIRY`, `GLUTEN`, `SOY`, `SHELLFISH`, `EGGS`, `SESAME`)
- `variants_json JSONB NOT NULL DEFAULT '[]'` — Optional size/portion variants (max 8 entries: `[{ "name": "Half", "price_minor_units": 18000, "is_available": true }]`; validated server-side).
- `prep_time_minutes SMALLINT NULL CHECK (prep_time_minutes BETWEEN 1 AND 240)`
- `calories_kcal SMALLINT NULL CHECK (calories_kcal BETWEEN 0 AND 10000)`
- `sort_order INT NOT NULL DEFAULT 0`
- `version INT NOT NULL DEFAULT 1` (optimistic locking for concurrent edits)
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `deleted_at TIMESTAMPTZ NULL`

### Table `#20`: `menu_media_assets`
Tracks validated uploaded food photos and venue logos for storage quotas and orphan cleanup.
- `id UUID PRIMARY KEY`
- `organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT`
- `venue_id UUID NOT NULL REFERENCES venues(id) ON DELETE RESTRICT`
- `storage_key TEXT NOT NULL UNIQUE` (full WebP path)
- `thumb_storage_key TEXT NOT NULL UNIQUE` (320px WebP thumbnail path)
- `mime_type VARCHAR(32) NOT NULL CHECK (mime_type IN ('image/webp'))`
- `byte_size INT NOT NULL CHECK (byte_size > 0)`
- `width_px SMALLINT NOT NULL`
- `height_px SMALLINT NOT NULL`
- `sha256 CHAR(64) NOT NULL`
- `uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

### Table `#21`: `qr_scan_daily_stats`
Privacy-preserving daily scan aggregate per table (zero PII, zero IP/user-agent storage).
- `venue_id UUID NOT NULL REFERENCES venues(id) ON DELETE RESTRICT`
- `table_id UUID NOT NULL REFERENCES tables(id) ON DELETE RESTRICT`
- `scan_date DATE NOT NULL`
- `organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT`
- `scan_count INT NOT NULL DEFAULT 0 CHECK (scan_count >= 0)`
- **Primary Key**: `(venue_id, table_id, scan_date)`.

---

## 3. Relationships, Delete Behavior & Required Indexes

### 3.1 Delete Behavior Summary
- Every structural parent-child link (`menus -> menu_categories -> menu_items`, `tables -> table_qr_codes`) uses **`ON DELETE RESTRICT`** in SQL and **soft delete (`deleted_at`)** in application logic so historical analytics (`occupancy_snapshots`, `table_state_events`, `qr_scan_daily_stats`) and revoked QR audit records are never accidentally destroyed.
- Soft-deleting a `menu` cascades soft-delete (`deleted_at = now()`) to its `menu_categories` and `menu_items` inside a single DB transaction.
- Soft-deleting a `table` atomically marks its active `table_qr_codes` row `status='REVOKED', revoked_reason='TABLE_DELETED'`.

### 3.2 Required Indexes (Each Mapped to a Named Query)
| Index | Table & Columns | Query / Screen |
|---|---|---|
| `idx_qr_token_lookup` | `table_qr_codes (token)` (UNIQUE) | `API-035` Public QR Menu scan (`SCR-022`) |
| `idx_qr_table_active` | `table_qr_codes (table_id) WHERE status = 'ACTIVE'` (UNIQUE) | `SCR-017`, `SCR-020` Active QR lookup |
| `idx_menus_venue_sort` | `menus (venue_id, is_active, sort_order) WHERE deleted_at IS NULL` | `SCR-018`, `SCR-022` Active menus |
| `idx_categories_menu_sort` | `menu_categories (menu_id, is_active, sort_order) WHERE deleted_at IS NULL` | `SCR-018`, `SCR-022` Ordered categories |
| `idx_items_category_sort` | `menu_items (category_id, sort_order) WHERE deleted_at IS NULL` | `SCR-018`, `SCR-022` Ordered items |
| `idx_items_venue_available` | `menu_items (venue_id, is_available) WHERE deleted_at IS NULL` | `SCR-018` Quick 86 filter |
| `idx_qr_stats_venue_date` | `qr_scan_daily_stats (venue_id, scan_date DESC)` | `SCR-020` Scan summary |

### 3.3 Row-Level Security (RLS)
Enable PostgreSQL RLS on all 6 new tables (`table_qr_codes`, `menus`, `menu_categories`, `menu_items`, `menu_media_assets`, `qr_scan_daily_stats`) using `organization_id = current_setting('app.current_org_id', true)::uuid`. For the unauthenticated public QR endpoint (`API-035`), the backend resolves `organization_id` from `table_qr_codes` via a dedicated read-only lookup helper (or `SECURITY DEFINER` function returning only public fields) and sets `SET LOCAL app.current_org_id` before reading menu rows.


---

## 4. Read-Only Public Views & Least-Privilege DB Role (`tablepulse_public`)
Created in migration `002_phase2_tables_menu_qr.py`:
1. **`CREATE ROLE tablepulse_public LOGIN ...`** (separate connection pool credentials in `PUBLIC_DATABASE_URL`, no write privileges, no table-level `SELECT` on base tables).
2. **`v_public_qr_resolution`**: Exposes ONLY `token`, `status`, `grace_until`, `venue_id`, `table_id`, `table_label` (`COALESCE(display_name, 'Table ' || table_code)`), `table_is_active`, `table_deleted_at`, `venue_name`, `menu_tagline`, `logo_storage_key`, `currency_code`, `timezone`, `menu_public_enabled`, `show_unavailable_items_public`, `menu_revision`.
3. **`v_public_menu_catalog`**: Exposes ONLY published, active, non-deleted menus, categories, items (`id`, `name`, `description`, `price_minor_units`, `compare_at_price_minor_units`, `variants_json`, `is_available`, `is_featured`, `dietary_tags`, `allergens`, `prep_time_minutes`, `calories_kcal`, `sort_order`), and resolved WebP image/thumbnail storage keys.
4. `GRANT SELECT ON v_public_qr_resolution, v_public_menu_catalog TO tablepulse_public;`
