# TablePulse Phase 2 — Advanced Table Management Specification

## Quick Reference
- **Purpose**: Gives `OWNER` and `MANAGER` full, flexible lifecycle control over restaurant tables (add, bulk-create, edit, rename, configure, deactivate, soft-delete) independent of CCTV camera calibration (`DECIDED`).
- **Primary Screen**: `SCR-017` (Table Management & Configuration), seamlessly synced with existing `SCR-005` (Live Floor Map) and `SCR-013` (Polygon Calibration Editor).
- **Functional Requirements Covered**: `FR-025`, `FR-026`, `FR-027`, `FR-028`.

---

## 1. Core Capabilities & Business Rules

### 1.1 Individual Table CRUD (`FR-025`)
- **Create Table**: `OWNER` or `MANAGER` creates a table with:
  - `table_code` (required, 1–20 chars, alphanumeric + hyphen/underscore, unique per venue among non-deleted tables, e.g., `T01`, `PATIO-3`, `BAR-2`).
  - `display_name` (optional, max 80 chars, e.g., `"Corner Window Booth"` — shown to guests on QR menu if set, else `Table {table_code}`).
  - `section_name` (required, e.g., `Main Hall`, `Patio`, `Rooftop`, `Bar`).
  - `min_capacity` (default `1`) and `seat_capacity` (`1–20`, must satisfy `min_capacity <= seat_capacity`).
  - `shape` (`RECT`, `CIRCLE`, `BOOTH`), `is_combinable` (boolean), `table_notes` (optional internal staff notes, max 255 chars).
  - **Automatic QR Provisioning**: Inside the exact same PostgreSQL transaction, the backend inserts a new `table_qr_codes` row with a unique 128-bit CSPRNG `token` (`status='ACTIVE'`).
- **Edit & Rename**:
  - Changing `table_code` or `display_name` updates the table in place **without breaking its existing printed QR code** (because QR codes bind to `table_id` via opaque `token`, not `table_code`!).
  - Uses optimistic locking (`version`) to prevent concurrent edit conflicts (`409 VERSION_CONFLICT`).

### 1.2 Bulk Table Count Adjustment (`FR-026`)
- **Bulk Add Tables**: Allows increasing total table count in seconds (e.g., opening a new patio section or seasonal expansion):
  - Inputs: `prefix` (e.g., `P`), `start_number` (e.g., `1`), `count` (`1–50` per request), `zero_pad` (e.g., `2` -> `P01..P10`), `section_name`, `seat_capacity`, `shape`.
  - Pre-validates every generated `table_code` for collisions before inserting; if any code collides, returns `409 DUPLICATE_TABLE_CODE` listing the conflicting codes (atomic all-or-nothing transaction).
  - Auto-generates a unique QR code for every bulk-created table.
- **Bulk Section / Active-Status Update**: Select multiple tables in `SCR-017` to move them to another section or deactivate/reactivate them together (e.g., close `Patio` tables during monsoon/winter without losing their polygons or QR codes).

### 1.3 Safe Deactivation & Deletion (`FR-027`)
- **Deactivate (`is_active = false`)**:
  - Hides the table from active floor capacity denominators (`total_tables`, `total_seats`) on `SCR-005` and waitlist matching on `SCR-009`.
  - Retains camera polygon and QR code intact for easy reactivation; scanning an inactive table's QR displays a clean "Table currently unavailable" state.
- **Soft Delete (`deleted_at = now()`)**:
  - **Active Session Guard**: If `current_state IN ('OCCUPIED','NEEDS_SERVICE')` OR the table is assigned to an active `waitlist_entries` row, `DELETE` returns `409 TABLE_IN_USE` unless the caller explicitly passes `?force=true` (confirmed via modal in UI).
  - Atomically: (1) sets `tables.deleted_at = now()`, (2) sets `tables.is_active = false`, (3) revokes its active `table_qr_codes` row (`status='REVOKED'`, `revoked_reason='TABLE_DELETED'`), (4) resolves any open alerts for that table, (5) publishes `roi.updated` to `cv-worker` if `camera_id IS NOT NULL`, and (6) writes an immutable `audit_logs` entry.
  - Preserves all historical `table_state_events` and `occupancy_snapshots` for `SCR-010` analytics.

### 1.4 Synchronization with Existing v1.0 Modules (`FR-028`)
- **`SCR-005` (Live Floor Map)**: Newly created tables appear immediately via WebSocket `table.created` / `floor.config_updated`; tables without a camera show a subtle "Manual Mode (No Camera)" indicator rather than `UNKNOWN`.
- **`SCR-013` (Polygon Editor)**: Lists uncalibrated tables in a "Pending Camera Mapping" sidebar so managers can bind polygons to tables created in `SCR-017` in one click instead of re-typing table metadata.
- **`cv-worker`**: Ignores tables where `is_active = false` or `deleted_at IS NOT NULL` or `polygon_json IS NULL`.

---

## 2. Validation Rules & Edge Cases
| Scenario | Rule / Expected Behavior |
|---|---|
| Re-using a `table_code` after soft-deletion | Allowed (`UNIQUE (venue_id, table_code) WHERE deleted_at IS NULL`); new table gets a brand-new `table_id` and brand-new QR `token`. |
| Decreasing `seat_capacity` below current `min_capacity` | Rejected with `400 VALIDATION_ERROR` (`fields: { min_capacity: "cannot exceed seat_capacity" }`). |
| Bulk add `count > 50` | Rejected with `400 VALIDATION_ERROR` (prevents accidental mass creation). |
| Venue has 0 active tables | `SCR-005` displays empty-floor state with CTA to `SCR-017`; `capacity_pct` returns `0` (never division-by-zero `NaN`). |
| Deleting a table linked to a camera | Unlinks polygon from `cv-worker` immediately; does NOT delete the camera. |


---

## 3. Floor API & Vision Worker Compatibility Rules
- **Uncalibrated / Non-CCTV Tables (`unmonitored_tables`)**: Tables created with `polygon_json IS NULL` or `camera_id IS NULL` are returned in an additive `unmonitored_tables` list on `GET /api/v1/venues/{v}/floor-state` and excluded from vision occupancy % denominators so Phase 1 HUD metrics remain accurate.
- **Vision Worker Safety**: `cv-worker` strictly queries `WHERE is_active = true AND deleted_at IS NULL AND camera_id IS NOT NULL AND polygon_json IS NOT NULL`.
- **Archived Label Reuse**: Because uniqueness is enforced via partial index `UNIQUE (venue_id, table_code) WHERE deleted_at IS NULL`, soft-deleting a retired table frees its `table_code` for reuse while keeping historical `table_state_events` intact.
