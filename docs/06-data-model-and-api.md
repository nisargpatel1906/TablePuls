# TablePulse — Data Model & API Specification

## Quick Reference
- **Database**: PostgreSQL 16+ with native monthly range partitioning & RLS (`PROPOSED` — 100% OSI open source, no TimescaleDB TSL). All primary keys are UUIDv7 (`uuid`), timestamps are `TIMESTAMPTZ` (UTC).
- **Entities**: 15 tables (`organizations`, `venues`, `users`, `refresh_tokens`, `cameras`, `tables`, `table_state_events`, `occupancy_snapshots`, `alerts`, `waitlist_entries`, `ml_models`, `ml_review_items`, `alert_rules`, `audit_logs`, `system_settings`).
- **API Style**: Versioned REST (`/api/v1/...`) + WebSocket (`/api/v1/ws/venues/{venue_id}`) with 5s HTTP polling fallback.
- **Response Contract** (`DECIDED` — production readiness): Every endpoint returns `{ "success": true, "data": ... }` or `{ "success": false, "error": { "code", "message", "fields?" } }`.

---

## 1. Data Model Specification (15 Entities)

### 1.1 Entity Summary & Ownership
| # | Table Name | Purpose | PK | Owning Service | Soft Delete / Retention |
|---|---|---|---|---|---|
| 1 | `organizations` | Top-level tenant | `id (UUID)` | `api` | Soft delete (`deleted_at`) |
| 2 | `venues` | Restaurant branch/location | `id (UUID)` | `api` | Soft delete (`deleted_at`) |
| 3 | `users` | Staff & admin accounts | `id (UUID)` | `api` | Soft delete (`is_active=false`) |
| 4 | `refresh_tokens` | Rotating session tokens + invite/reset hashes | `id (UUID)` | `api` | Hard delete 30d after expiry |
| 5 | `cameras` | RTSP/demo camera configs | `id (UUID)` | `api` | Soft delete (`deleted_at`) |
| 6 | `tables` | Physical dining tables + polygon ROI + live state | `id (UUID)` | `api` (config) / `cv-worker` (live state via API) | Soft delete (`deleted_at`) |
| 7 | `table_state_events` | Immutable log of every table state change | `id (UUID)` | `api` | Retain 365 days |
| 8 | `occupancy_snapshots` | Native PG16 monthly range-partitioned table (1-min venue/table snapshots) | `(captured_at, table_id)` | `api` | Retain 365 days (drop expired monthly partitions cleanly) |
| 9 | `alerts` | Operational alerts (`UNATTENDED_TABLE`, `NEEDS_CLEANING`, etc.) | `id (UUID)` | `api` | Retain 90 days |
| 10 | `waitlist_entries` | Front-desk waiting parties | `id (UUID)` | `api` | Retain 90 days (PII scrubbed >30d) |
| 11 | `ml_models` | Registered CV/ETA model versions & benchmark JSON | `id (UUID)` | `api` | Immutable (never hard deleted) |
| 12 | `ml_review_items` | Low-confidence & flagged crops for human labeling | `id (UUID)` | `api` / `cv-worker` | Purge crop files after `snapshot_retention_days` (default 7d) |
| 13 | `alert_rules` | Venue/section alert thresholds & webhook targets | `id (UUID)` | `api` | Soft delete |
| 14 | `audit_logs` | Immutable security & override audit trail | `id (UUID)` | `api` | Append-only, retain 365 days |
| 15 | `system_settings` | Org-wide privacy, retention, and AI kill-switch flags | `organization_id (UUID)` | `api` | Never deleted |

### 1.2 Key Table Schemas, Constraints & Field Rules

- **`venues`**: `id UUID PK`, `organization_id UUID NOT NULL FK(organizations.id) ON DELETE RESTRICT`, `name VARCHAR(120) NOT NULL`, `timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'`, `operating_hours_json JSONB NOT NULL`, `allow_host_camera_view BOOLEAN NOT NULL DEFAULT false`, `guests_per_server_ratio INT NOT NULL DEFAULT 16 CHECK (guests_per_server_ratio BETWEEN 4 AND 50)`, `created_at TIMESTAMPTZ`, `deleted_at TIMESTAMPTZ`.
- **`users`**: `id UUID PK`, `organization_id UUID NOT NULL FK`, `email VARCHAR(255) NOT NULL UNIQUE`, `full_name VARCHAR(120) NOT NULL`, `password_hash TEXT NOT NULL`, `role VARCHAR(20) NOT NULL CHECK (role IN ('OWNER','MANAGER','HOST','STAFF','VIEWER'))`, `assigned_venue_ids UUID[] NOT NULL DEFAULT '{}'`, `is_active BOOLEAN NOT NULL DEFAULT true`, `last_login_at TIMESTAMPTZ`, `created_at TIMESTAMPTZ`.
- **`cameras`**: `id UUID PK`, `organization_id UUID NOT NULL`, `venue_id UUID NOT NULL FK(venues.id) ON DELETE RESTRICT`, `name VARCHAR(100) NOT NULL`, `stream_type VARCHAR(16) NOT NULL CHECK (stream_type IN ('RTSP','RTSPS','DEMO_MP4'))`, `stream_url_encrypted BYTEA NOT NULL`, `credentials_encrypted BYTEA`, `target_fps SMALLINT NOT NULL DEFAULT 2 CHECK (target_fps BETWEEN 1 AND 5)`, `face_blur_enabled BOOLEAN NOT NULL DEFAULT true`, `status VARCHAR(20) NOT NULL DEFAULT 'OFFLINE' CHECK (status IN ('ONLINE','RECONNECTING','OFFLINE','DISABLED'))`, `last_heartbeat_at TIMESTAMPTZ`, `exclusion_polygons_json JSONB NOT NULL DEFAULT '[]'`.
- **`tables`**: `id UUID PK`, `organization_id UUID NOT NULL`, `venue_id UUID NOT NULL FK(venues.id) ON DELETE RESTRICT`, `camera_id UUID FK(cameras.id) ON DELETE SET NULL`, `table_code VARCHAR(20) NOT NULL`, `section_name VARCHAR(60) NOT NULL DEFAULT 'Main'`, `seat_capacity SMALLINT NOT NULL CHECK (seat_capacity BETWEEN 1 AND 20)`, `polygon_json JSONB NOT NULL` (schema version `v1`: array of `{x: 0..1, y: 0..1}`, min 3 vertices), `floor_x REAL NOT NULL`, `floor_y REAL NOT NULL`, `shape VARCHAR(16) NOT NULL DEFAULT 'RECT' CHECK (shape IN ('RECT','CIRCLE','BOOTH'))`, `current_state VARCHAR(20) NOT NULL DEFAULT 'FREE' CHECK (current_state IN ('FREE','OCCUPIED','NEEDS_SERVICE','NEEDS_CLEANING','RESERVED','UNKNOWN'))`, `current_guest_count SMALLINT NOT NULL DEFAULT 0 CHECK (current_guest_count >= 0)`, `current_confidence REAL`, `occupied_since TIMESTAMPTZ`, `last_staff_visit_at TIMESTAMPTZ`, `active_session_id UUID`, `predicted_free_at TIMESTAMPTZ`, `version INT NOT NULL DEFAULT 1` (optimistic locking). **Constraint**: `UNIQUE (venue_id, table_code) WHERE deleted_at IS NULL`.
- **`table_state_events`**: `id UUID PK`, `organization_id UUID NOT NULL`, `venue_id UUID NOT NULL`, `table_id UUID NOT NULL FK(tables.id) ON DELETE CASCADE`, `session_id UUID`, `previous_state VARCHAR(20)`, `new_state VARCHAR(20) NOT NULL`, `guest_count SMALLINT NOT NULL`, `confidence REAL`, `source VARCHAR(16) NOT NULL CHECK (source IN ('AI','MANUAL','SYSTEM'))`, `actor_user_id UUID FK(users.id) ON DELETE SET NULL`, `reason TEXT`, `model_version VARCHAR(64)`, `occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
- **`occupancy_snapshots`** *(Native PostgreSQL 16 `PARTITION BY RANGE (captured_at)` monthly partitions + scheduled hourly rollup query)*: `captured_at TIMESTAMPTZ NOT NULL`, `organization_id UUID NOT NULL`, `venue_id UUID NOT NULL`, `table_id UUID NOT NULL`, `section_name VARCHAR(60) NOT NULL`, `state VARCHAR(20) NOT NULL`, `guest_count SMALLINT NOT NULL`, `seat_capacity SMALLINT NOT NULL`, `sla_breached BOOLEAN NOT NULL DEFAULT false`.
- **`alerts`**: `id UUID PK`, `organization_id UUID NOT NULL`, `venue_id UUID NOT NULL`, `table_id UUID FK(tables.id) ON DELETE SET NULL`, `camera_id UUID FK(cameras.id) ON DELETE SET NULL`, `alert_type VARCHAR(32) NOT NULL CHECK (alert_type IN ('UNATTENDED_TABLE','NEEDS_CLEANING','CAMERA_OFFLINE','LOW_CONFIDENCE'))`, `severity VARCHAR(16) NOT NULL CHECK (severity IN ('INFO','WARNING','CRITICAL'))`, `status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','ACKNOWLEDGED','RESOLVED'))`, `dedup_key VARCHAR(160) NOT NULL`, `message TEXT NOT NULL`, `created_at TIMESTAMPTZ NOT NULL`, `acknowledged_by UUID FK(users.id)`, `acknowledged_at TIMESTAMPTZ`, `resolved_at TIMESTAMPTZ`. **Constraint**: Partial unique index `UNIQUE (dedup_key) WHERE status IN ('ACTIVE','ACKNOWLEDGED')`.
- **`waitlist_entries`**: `id UUID PK`, `organization_id UUID NOT NULL`, `venue_id UUID NOT NULL`, `party_name VARCHAR(80) NOT NULL`, `party_size SMALLINT NOT NULL CHECK (party_size BETWEEN 1 AND 20)`, `quoted_wait_minutes SMALLINT`, `status VARCHAR(16) NOT NULL DEFAULT 'WAITING' CHECK (status IN ('WAITING','SEATED','CANCELLED','NO_SHOW'))`, `assigned_table_id UUID FK(tables.id) ON DELETE SET NULL`, `notes VARCHAR(255)`, `joined_at TIMESTAMPTZ NOT NULL`, `seated_at TIMESTAMPTZ`.
- **`ml_models`**: `id UUID PK`, `model_role VARCHAR(32) NOT NULL CHECK (model_role IN ('DETECTOR','CLEANLINESS','TURNOVER_ETA'))`, `version VARCHAR(64) NOT NULL UNIQUE`, `artifact_uri TEXT NOT NULL`, `artifact_sha256 CHAR(64) NOT NULL`, `dataset_version VARCHAR(64) NOT NULL`, `eval_metrics_json JSONB NOT NULL`, `gate_status VARCHAR(20) NOT NULL DEFAULT 'NOT_MEASURED' CHECK (gate_status IN ('NOT_MEASURED','PASS','FAIL'))`, `channel VARCHAR(16) NOT NULL DEFAULT 'experimental' CHECK (channel IN ('experimental','stable'))`, `is_active BOOLEAN NOT NULL DEFAULT false`, `created_at TIMESTAMPTZ NOT NULL`.
- **`ml_review_items`**: `id UUID PK`, `organization_id UUID NOT NULL`, `venue_id UUID NOT NULL`, `table_id UUID NOT NULL`, `camera_id UUID NOT NULL`, `snapshot_path TEXT`, `predicted_state VARCHAR(20) NOT NULL`, `predicted_guest_count SMALLINT NOT NULL`, `confidence REAL NOT NULL`, `trigger_reason VARCHAR(32) NOT NULL CHECK (trigger_reason IN ('LOW_CONFIDENCE','USER_FLAGGED','DISAGREEMENT'))`, `review_status VARCHAR(16) NOT NULL DEFAULT 'PENDING' CHECK (review_status IN ('PENDING','REVIEWED','EXCLUDED'))`, `human_state VARCHAR(20)`, `human_guest_count SMALLINT`, `issue_tags TEXT[] DEFAULT '{}'`, `reviewed_by UUID FK(users.id)`, `created_at TIMESTAMPTZ NOT NULL`, `reviewed_at TIMESTAMPTZ`.
- **`alert_rules`**: `id UUID PK`, `organization_id UUID NOT NULL`, `venue_id UUID NOT NULL`, `section_name VARCHAR(60)` (null = venue default), `unattended_service_sec INT NOT NULL DEFAULT 300 CHECK (unattended_service_sec BETWEEN 60 AND 1800)`, `cleaning_alert_delay_sec INT NOT NULL DEFAULT 120 CHECK (cleaning_alert_delay_sec BETWEEN 0 AND 900)`, `occupancy_debounce_sec INT NOT NULL DEFAULT 10 CHECK (occupancy_debounce_sec BETWEEN 3 AND 60)`, `departure_debounce_sec INT NOT NULL DEFAULT 20 CHECK (departure_debounce_sec BETWEEN 5 AND 120)`, `min_confidence REAL NOT NULL DEFAULT 0.65 CHECK (min_confidence BETWEEN 0.30 AND 0.95)`, `require_bussing_confirmation BOOLEAN NOT NULL DEFAULT false`, `webhook_url_encrypted BYTEA`, `webhook_secret_encrypted BYTEA`, `quiet_hours_enabled BOOLEAN NOT NULL DEFAULT true`.
- **`audit_logs`**: `id UUID PK`, `organization_id UUID NOT NULL`, `venue_id UUID`, `actor_user_id UUID`, `action VARCHAR(64) NOT NULL`, `target_type VARCHAR(32) NOT NULL`, `target_id UUID`, `before_json JSONB`, `after_json JSONB`, `ip_address INET`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
- **`system_settings`**: `organization_id UUID PK FK(organizations.id)`, `ai_inference_enabled BOOLEAN NOT NULL DEFAULT true`, `face_blur_enforced BOOLEAN NOT NULL DEFAULT true`, `snapshot_retention_days SMALLINT NOT NULL DEFAULT 7 CHECK (snapshot_retention_days BETWEEN 0 AND 30)`, `analytics_retention_days SMALLINT NOT NULL DEFAULT 365 CHECK (analytics_retention_days BETWEEN 30 AND 1095)`, `updated_by UUID`, `updated_at TIMESTAMPTZ`.

### 1.3 Required Indexes (Every Index Maps to a Named Query)
| Index | Table | Query / Screen |
|---|---|---|
| `idx_tables_venue_active` | `tables (venue_id, section_name) WHERE deleted_at IS NULL` | `SCR-005` Live Floor Map load |
| `idx_alerts_venue_status_created` | `alerts (venue_id, status, created_at DESC)` | `SCR-008` Active Alerts Queue |
| `idx_events_table_occurred` | `table_state_events (table_id, occurred_at DESC)` | `SCR-007` Table Detail Timeline |
| `idx_snapshots_venue_time` | `occupancy_snapshots (venue_id, captured_at DESC)` | `SCR-010` Peak Hours Analytics |
| `idx_waitlist_venue_status` | `waitlist_entries (venue_id, status, joined_at ASC)` | `SCR-009` Waitlist Queue |
| `idx_ml_review_venue_status` | `ml_review_items (venue_id, review_status, created_at DESC)` | `SCR-011` ML Review Queue |
| `idx_audit_org_created` | `audit_logs (organization_id, created_at DESC)` | `SCR-015` Audit Log viewer |

---

## 2. REST & WebSocket API Contract

### 2.1 Standard Response Envelopes & Status Codes (`DECIDED`)
```json
// Success (200 / 201)
{ "success": true, "data": { ... } }

// Error (400 / 401 / 403 / 404 / 409 / 422 / 429 / 500)
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable explanation",
    "fields": { "seat_capacity": "must be between 1 and 20" }
  }
}
```
- **Error Code Catalog**: `VALIDATION_ERROR` (400), `TOKEN_EXPIRED` (400), `AUTH_UNAUTHORIZED` (401), `AUTH_INVALID_CREDENTIALS` (401), `AUTH_FORBIDDEN` (403), `RESOURCE_NOT_FOUND` (404), `VERSION_CONFLICT` (409), `LAST_OWNER_PROTECTED` (409), `CAMERA_UNREACHABLE` (422), `RATE_LIMITED` (429), `INTERNAL_ERROR` (500 — never exposes stack traces).
- **Pagination**: `?page=1&page_size=25` (max `100`). Returns `{ items: [...], total, page, page_size }`.
- **Idempotency**: Write endpoints for invites, alerts, waitlist creation, and manual overrides accept `Idempotency-Key` header (stored in Valkey for 24h).
- **Rate Limits**: Auth endpoints `10 req/min/IP`; general API `120 req/min/user`; CSV/dataset export `5 req/min/user`. Exceeded limit returns `429` with `Retry-After` header.

### 2.2 Core Endpoint Inventory

| ID | Method & Path | Purpose | Auth / Roles | Status Codes |
|---|---|---|---|---|
| `API-001` | `POST /api/v1/auth/bootstrap` | Create initial org + `OWNER` (only when 0 users exist) | Public (one-time) | 201, 400, 403 |
| `API-002` | `POST /api/v1/auth/login` | Email/password login -> access JWT + HttpOnly refresh cookie | Public | 200, 400, 401, 429 |
| `API-003` | `POST /api/v1/auth/refresh` | Rotate refresh cookie -> new access JWT | Refresh Cookie | 200, 401 |
| `API-004` | `POST /api/v1/auth/logout` | Revoke refresh token & clear cookie | Authenticated | 200 |
| `API-005` | `POST /api/v1/auth/forgot-password` & `/reset-password` | Password recovery flow | Public | 200, 400, 429 |
| `API-006` | `POST /api/v1/auth/ws-ticket` | Issue 60s single-use WebSocket ticket | Authenticated | 200, 401 |
| `API-007` | `GET/POST/PATCH /api/v1/venues` | List/create/update venues | `OWNER`, `MANAGER` (read all roles) | 200, 201, 400, 403 |
| `API-008` | `GET/POST/PATCH/DELETE /api/v1/venues/{v}/cameras` | Manage RTSP/Demo cameras | `OWNER`, `MANAGER` | 200, 201, 400, 403, 404 |
| `API-009` | `POST /api/v1/venues/{v}/cameras/{c}/test` | Capture test snapshot & validate RTSP | `OWNER`, `MANAGER` | 200, 403, 422 |
| `API-010` | `GET/PUT /api/v1/venues/{v}/cameras/{c}/polygons` | Bulk save table polygons & exclusion zones | `OWNER`, `MANAGER` | 200, 400, 403, 409 |
| `API-011` | `GET /api/v1/venues/{v}/floor-state` | Full live floor state + KPIs (also WS polling fallback) | All venue roles | 200, 403 |
| `API-012` | `GET /api/v1/venues/{v}/tables/{t}` | Single table detail + latest blurred crop + last 10 events | All venue roles | 200, 403, 404 |
| `API-013` | `PATCH /api/v1/venues/{v}/tables/{t}/override` | Manual state/guest override (`version` checked) | `OWNER`, `MANAGER`, `HOST`, `STAFF` (clean/served only) | 200, 400, 403, 409 |
| `API-014` | `POST /api/v1/venues/{v}/tables/{t}/flag` | Flag inaccurate AI detection -> `ml_review_items` | `OWNER`, `MANAGER`, `HOST`, `STAFF` | 201, 403 |
| `API-015` | `GET /api/v1/venues/{v}/alerts` & `PATCH /alerts/{a}` | List alerts; acknowledge or resolve alert | `OWNER`, `MANAGER`, `HOST`, `STAFF` | 200, 403, 404 |
| `API-016` | `GET/POST/PATCH /api/v1/venues/{v}/waitlist` | Manage waitlist + seat party on table | `OWNER`, `MANAGER`, `HOST` | 200, 201, 400, 403 |
| `API-017` | `GET /api/v1/venues/{v}/turnover-predictions` | Ranked next-available tables with ETA intervals | `OWNER`, `MANAGER`, `HOST` | 200, 403 |
| `API-018` | `GET /api/v1/venues/{v}/analytics/peak-hours` | Peak hours, heatmap, staffing curve & `?format=csv` | `OWNER`, `MANAGER`, `VIEWER` | 200, 400, 403 |
| `API-019` | `GET/PATCH /api/v1/venues/{v}/alert-rules` & `POST /test-webhook` | Manage alert thresholds & test webhook | `OWNER`, `MANAGER` | 200, 400, 403, 422 |
| `API-020` | `GET/PATCH /api/v1/venues/{v}/ml-review` & `GET /export` | Review uncertain crops & export anonymized zip | `OWNER`, `MANAGER` (export `OWNER` only) | 200, 403, 404 |
| `API-021` | `GET/POST/PATCH /api/v1/org/users` & `GET /org/audit-logs` | User invites, role changes, session revocation, audit log | `OWNER`, `MANAGER` (scoped) | 200, 201, 403, 409 |
| `API-022` | `GET/PATCH /api/v1/org/system` & `POST /models/{id}/activate` & `POST /purge-snapshots` | System health, kill switch, model switch, privacy purge | `OWNER` only | 200, 403, 409 |
| `API-023` | `GET /api/v1/health` | Liveness/readiness check (DB + Valkey + MediaMTX + CV worker heartbeat) | Public (minimal) / `OWNER` (detailed) | 200, 503 |

### 2.3 Real-Time WebSocket Contract (`WS /api/v1/ws/venues/{venue_id}?ticket=...`)
- **Events Emitted**:
  - `floor.snapshot`: Full floor state upon initial connect.
  - `table.state_changed`: `{ table_id, table_code, previous_state, new_state, guest_count, occupied_since, confidence, source, toast_message }`.
  - `alert.created` / `alert.updated`: `{ alert_id, table_code, alert_type, severity, status, message, created_at }`.
  - `camera.status_changed`: `{ camera_id, status, last_heartbeat_at }`.
  - `system.kill_switch_changed`: `{ ai_inference_enabled }`.
- **Polling Fallback**: If WebSocket fails 3 consecutive reconnect attempts, frontend polls `GET /api/v1/venues/{v}/floor-state` every `5000ms` until WS restores.
