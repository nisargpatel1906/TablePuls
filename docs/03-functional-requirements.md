# TablePulse — Functional Requirements & User Stories

## Quick Reference
- **Scope**: 24 numbered Functional Requirements (`FR-001` through `FR-024`) grouped across 7 capability domains, each with concrete user stories, acceptance criteria (Definition of Done), and explicit edge-case / error-state behavior.
- **Priority Tiers**: `P0` (Launch blocker — required for v1.0 MVP), `P1` (Important v1.0 polish), `P2` (`DEFERRED` post-MVP).
- **Consistency Rule**: Every `FR-XXX` traces to specific screens (`SCR-001`–`SCR-016`), API endpoints (`API-XXX`), and automated tests.

---

## 1. Authentication, Onboarding & Account Management

### `FR-001` — First-Run Owner Bootstrap & Onboarding (`P0`, `PROPOSED`)
- **User Story**: As a restaurant owner deploying TablePulse for the first time, I want a guided setup flow so I can create the admin account, connect a camera or demo video, and map my first tables in under 15 minutes.
- **Acceptance Criteria**:
  - When `users` table count is `0`, visiting `/` redirects to `/register?bootstrap=true` (`SCR-002`) to create the first `OWNER` account; once created, bootstrap registration is permanently disabled (`403`).
  - Owner is guided through `SCR-004` (Venue -> Camera/Demo -> Polygon -> Thresholds) and lands on `SCR-005` with live state updates.
  - **Edge Cases**: Invalid RTSP URL returns `400` with human-readable diagnostic; skipping camera setup still creates the venue and opens `SCR-005` in empty-camera state.

### `FR-002` — Email/Password Authentication & Session Lifecycle (`P0`, `PROPOSED`)
- **User Story**: As a staff member, I want to sign in securely and stay signed in across shifts without re-entering my password every few minutes.
- **Acceptance Criteria**:
  - `POST /api/v1/auth/login` verifies Argon2id password hash, returns a short-lived JWT access token (15 min) in JSON body and sets an `HttpOnly`, `Secure`, `SameSite=Strict` refresh token cookie (7 days).
  - Frontend stores access token in memory only (never `localStorage` or `sessionStorage`).
  - `POST /api/v1/auth/refresh` rotates the refresh token and revokes the previous token family on reuse detection.
  - `POST /api/v1/auth/logout` revokes the refresh token in DB and clears the cookie.
  - **Error States**: Failed logins increment per-IP and per-account rate-limit counters (5 failures/15 min -> `429 RATE_LIMITED`). Invalid credentials return generic `401 AUTH_INVALID_CREDENTIALS`.

### `FR-003` — Invite-Based User Onboarding & Password Recovery (`P0`, `PROPOSED`)
- **User Story**: As a manager, I want to invite hosts and servers via a time-limited link, and let users reset forgotten passwords securely.
- **Acceptance Criteria**:
  - `OWNER`/`MANAGER` creates an invite token (SHA-256 hashed in DB, 48-hour expiry, single-use) scoped to a venue and role.
  - Password reset tokens expire in 30 minutes, are single-use, and invalidate all active refresh tokens upon successful reset.
  - Password policy enforces minimum 12 characters; rejects common breached passwords.
  - **Error States**: Expired/used tokens display a clear recovery state in `SCR-002`/`SCR-003` and return `400 TOKEN_EXPIRED`.

---

## 2. Camera Ingestion & Floor Calibration

### `FR-004` — RTSP/ONVIF Camera Management & Demo Video Mode (`P0`, `DECIDED`)
- **User Story**: As a manager, I want to connect our existing CCTV security cameras via RTSP (or load a sample restaurant video) without buying proprietary hardware.
- **Acceptance Criteria**:
  - Supports `rtsp://` and `rtsps://` URLs plus local sample `.mp4` files (looping) when `DEMO_MODE=true`.
  - Camera credentials are encrypted at rest (AES-256-GCM) and never returned in API responses or logs.
  - **Test Connection** captures a single frame within 10s, verifies resolution (`>= 640x480`), and returns a face-blurred JPEG preview.
  - **Error States**: Unreachable host, auth failure, or unsupported codec returns structured `422 CAMERA_UNREACHABLE` with specific diagnostic code; offline cameras auto-retry with exponential backoff (5s -> 10s -> 30s -> 60s max).

### `FR-005` — Interactive Table Polygon & ROI Calibration (`P0`, `PROPOSED`)
- **User Story**: As a manager, I want to draw polygonal regions around each table on my camera feed and position them on a 2D floor map so the AI monitors the exact right areas.
- **Acceptance Criteria**:
  - Manager draws polygons (`>= 3` vertices, normalized `0.0–1.0` image coordinates so resolution changes don't break calibration) in `SCR-013`.
  - Each table requires a unique `table_code` per venue (e.g., `T01`), `seat_capacity` (`1–20`), `section_name`, and 2D floor map `(x, y, shape)`.
  - Supports optional **Exclusion Zones** (e.g., walkway, door, TV screen) ignored by person/table detectors.
  - Saving calibration atomically pushes updated ROI config to the CV worker via Redis Pub/Sub within 2 seconds without restarting the camera stream.
  - **Validation States**: Self-intersecting polygons, `<3` vertices, or duplicate `table_code` are blocked client-side and return `400 VALIDATION_ERROR` server-side.

---

## 3. Real-Time Computer Vision & Table State Tracking

### `FR-006` — Real-Time Table Occupancy & Guest Counting (`P0`, `DECIDED`)
- **User Story**: As a host, I want every table's occupancy status (`FREE`/`OCCUPIED`) and seated guest count to update automatically from the CCTV feed.
- **Acceptance Criteria**:
  - CV worker samples each active camera at configurable `1–5 FPS` (default `2 FPS`), runs object detection + ByteTrack multi-object tracking, and maps seated persons to table polygons.
  - Transitions from `FREE` -> `OCCUPIED` require continuous detection for `debounce_seconds` (default `10s`) to ignore passersby.
  - Computes real-time venue aggregates: `occupied_tables / total_tables`, `seated_guests / total_seats`, and `capacity_pct`.
  - **Edge Cases**: Guests temporarily standing up (<30s) do not prematurely flip `OCCUPIED` -> `NEEDS_CLEANING`.

### `FR-007` — Dwell & Service Timers (`P0`, `DECIDED`)
- **User Story**: As a host or manager, I want a timer to start automatically when guests sit down so I know how long they have been seated and how long since a waiter last visited.
- **Acceptance Criteria**:
  - `occupied_since` timestamp is recorded on transition to `OCCUPIED` and rendered as a live ticking timer (`MM:SS` / `HH:MM:SS`) on `SCR-005`, `SCR-006`, and `SCR-007`.
  - `last_staff_visit_at` updates whenever the CV pipeline detects a staff-visit event (standing person at table perimeter for `>= 4s` while table is occupied) OR when staff manually taps **Mark Service Attended**.
  - Timer resets to `null` when table returns to `FREE`.

### `FR-008` — Unattended Table Service Alert (`P0`, `DECIDED`)
- **User Story**: As a server/manager, I want an immediate alert if guests have been seated for more than 5 minutes without a waiter arriving.
- **Acceptance Criteria**:
  - If `state == OCCUPIED` AND `last_staff_visit_at IS NULL` AND `(now - occupied_since) >= service_sla_seconds` (default `300s`), table transitions to `NEEDS_SERVICE` and creates an active `UNATTENDED_TABLE` alert.
  - Alert is broadcast via WebSocket within 2s and dispatched to configured external channels (Webhook/Slack/Telegram).
  - Duplicate alerts for the same occupancy session are suppressed via idempotent deduplication key (`venue_id:table_id:session_id:UNATTENDED_TABLE`).
  - Alert auto-resolves when a staff visit is detected or when staff clicks **Acknowledge / Mark Served**.

### `FR-009` — Dirty / Needs-Cleaning Table Alert (`P0`, `DECIDED`)
- **User Story**: As a busser/host, I want an alert when a table becomes free but hasn't been cleaned yet so we can turn it faster for waiting guests.
- **Acceptance Criteria**:
  - When seated guest count drops to `0` for `departure_debounce_seconds` (default `20s`), the table transitions from `OCCUPIED`/`NEEDS_SERVICE` to `NEEDS_CLEANING` (if cleanliness classifier predicts `DIRTY` with confidence >= threshold OR if `require_bussing_confirmation` is enabled).
  - Broadcasts toast (`CCTV: Party left Table XX — Needs Cleaning`) and creates a `NEEDS_CLEANING` alert if uncleaned after `cleaning_alert_delay_seconds` (default `120s`, configurable to `0s` for instant alert).
  - Transitions to `FREE` automatically when cleanliness classifier predicts `CLEAN` for 10 consecutive seconds (with no person obstructing) OR immediately upon staff tapping **Mark Clean**.

### `FR-010` — Low-Confidence / Occluded Fallback (`UNKNOWN` State) (`P0`, `PROPOSED`)
- **User Story**: As a manager, I want the system to clearly flag tables it cannot reliably read instead of showing wrong green/red statuses.
- **Acceptance Criteria**:
  - If camera is offline OR detection/cleanliness confidence remains below `min_confidence_threshold` (default `0.65`) for `> 30s`, table transitions to `UNKNOWN` (distinct from `FREE`/`OCCUPIED`) and enqueues an item in `SCR-011` (ML Review Queue).
  - Host/Manager can manually override an `UNKNOWN` table at any time; manual override holds until cleared or until ML confidence recovers above `0.80` for 30s.

---

## 4. Live Floor Operations, Overrides & Waitlist

### `FR-011` — Live Host Floor Map & Real-Time Sync (`P0`, `DECIDED`)
- **User Story**: As a host, I want a real-time 2D floor map that stays synced across all tablets without manual refreshing.
- **Acceptance Criteria**:
  - `SCR-005` connects to `WS /api/v1/ws/venues/{venue_id}` using authenticated session and receives incremental `table.state_changed`, `alert.created`, `alert.resolved`, and `occupancy.updated` events within 2s p95.
  - If WebSocket disconnects, client displays amber status pill and falls back to polling `GET /api/v1/venues/{venue_id}/floor-state` every 5 seconds until WebSocket reconnects.
  - Search by Table ID and filter by Section/State operate instantaneously client-side.

### `FR-012` — Live Camera Wall with Synced AI Overlays (`P0`, `DECIDED`)
- **User Story**: As a manager, I want to view live CCTV streams with green/red table polygons and guest counts overlaid so I can visually verify the AI.
- **Acceptance Criteria**:
  - Streams delivered via MediaMTX WebRTC (`WHEP`) over HTTPS/WSS with <2s glass-to-glass latency on LAN.
  - Overlay toggles (`Polygons`, `Timers`, `Bounding Boxes`) work per browser session.
  - Face-blur privacy filter is applied server-side before frames leave the edge/media pipeline when `face_blur_enabled=true`.

### `FR-013` — Manual Table Overrides with Audit Trail (`P0`, `PROPOSED`)
- **User Story**: As a host, I want to manually mark a table as `RESERVED`, `FREE`, or `OCCUPIED` when real-world context differs from what the camera sees.
- **Acceptance Criteria**:
  - `PATCH /api/v1/venues/{venue_id}/tables/{table_id}/override` requires `HOST`, `MANAGER`, or `OWNER` (`STAFF` may only mark `FREE`/clean or `SERVED`).
  - Every manual override writes an immutable `audit_logs` record (actor, previous state, new state, reason, timestamp) and a `table_state_events` record with `source='MANUAL'`.
  - Marking a table `RESERVED` prevents CV from reverting it to `FREE` until a party is seated or reservation is cancelled.

### `FR-014` — Waitlist Management & Predicted Next-Available Table (`P0`, `DECIDED`)
- **User Story**: As a host with a line at the entrance, I want to manage the waitlist and see which occupied table will likely become available first.
- **Acceptance Criteria**:
  - Host can add, edit, seat, cancel, or mark no-show on waitlist entries (`SCR-009`).
  - System ranks currently `OCCUPIED` and `NEEDS_CLEANING` tables matching `seat_capacity >= party_size` by `predicted_remaining_minutes` ascending, displaying a range (e.g., `5–12 min`) and confidence tier (`High`/`Medium`/`Low`).
  - Seating a waiting party on a `FREE` table updates waitlist entry to `SEATED` and records `actual_wait_minutes` for analytics.

---

## 5. Analytics, Notifications & ML Review

### `FR-015` — Peak Hours & Staffing Analytics (`P0`, `DECIDED`)
- **User Story**: As a manager, I want weekly peak-hour occupancy and wait-time charts so I can schedule the right number of waiters.
- **Acceptance Criteria**:
  - PostgreSQL 16 (native monthly partitions) scheduled hourly rollups compute hourly `avg_occupancy_pct`, `peak_seated_guests`, `avg_turn_minutes`, `avg_wait_minutes`, and `sla_breach_count` per venue and section.
  - `SCR-010` supports `Today`, `Last 7 Days`, `Last 30 Days`, and custom date ranges up to 365 days.
  - Recommended waiter count formula: `ceil(peak_seated_guests / guests_per_server_ratio)` (default ratio `16`, editable in UI).
  - CSV export downloads a UTF-8 file matching the active filter within 5s.

### `FR-016` — Configurable Alert Rules & External Webhooks (`P1`, `PROPOSED`)
- **User Story**: As a manager, I want to tune service/cleaning alert thresholds and forward alerts to Slack, Telegram, or a custom webhook.
- **Acceptance Criteria**:
  - Rules configurable per venue and optionally overridden per section (`SCR-014`).
  - Outbound webhooks include `X-TablePulse-Signature` (HMAC-SHA256) and retry up to 3 times with exponential backoff on `5xx`/timeout; failures log cleanly without blocking core CV state updates.
  - **Send Test Webhook** button verifies connectivity and displays HTTP status code.

### `FR-017` — ML Human-Review Queue & Active Learning Export (`P1`, `PROPOSED`)
- **User Story**: As a manager/maintainer, I want to review uncertain or flagged table snapshots so we can measure real-world errors and export clean labeled datasets for retraining.
- **Acceptance Criteria**:
  - `SCR-011` lists `ml_review_items` created from low-confidence triggers or manual user flags.
  - Submitting a review records `human_label`, `human_guest_count`, `issue_tags`, and `reviewed_by`.
  - `OWNER` can export reviewed items (face-blurred crops + JSON/COCO annotations, stripped of PII) as a `.zip` bundle for model retraining.

---

## 6. Administration, Privacy & System Controls

### `FR-018` — Multi-Venue & RBAC Administration (`P0`, `PROPOSED`)
- **User Story**: As an owner with two restaurant branches, I want to manage staff permissions per venue and review who changed what.
- **Acceptance Criteria**:
  - Every venue-scoped API enforces both authentication (`401`) and venue+role authorization (`403`) server-side.
  - At least one active `OWNER` must always exist per organization (cannot self-demote or disable the last `OWNER`).
  - All role changes, camera edits, rule changes, and manual overrides are recorded in `audit_logs`.

### `FR-019` — Privacy Controls & Data Retention Enforcement (`P0`, `PROPOSED`)
- **User Story**: As a restaurant owner, I want face blurring enabled by default and automatic purging of review snapshots so we protect patron and staff privacy.
- **Acceptance Criteria**:
  - `face_blur_enabled` defaults to `true`; raw CCTV video is never written to disk in v1.0.
  - Scheduled daily purge job deletes `ml_review_items` snapshot files older than `snapshot_retention_days` (default `7`, configurable `0–30`).
  - **Purge All Snapshots Now** button immediately deletes all stored snapshot files and writes an audit log entry.

### `FR-020` — Global AI Kill Switch & Manual Fallback Mode (`P0`, `PROPOSED`)
- **User Story**: As an owner, if a model update misbehaves during dinner service, I want to pause AI updates immediately while keeping the floor map and waitlist working manually.
- **Acceptance Criteria**:
  - `OWNER` can toggle `ai_inference_enabled=false` in `SCR-016` (stored in `system_settings` and mirrored in Redis).
  - CV worker checks the kill switch before every inference batch; if missing or `false`, inference halts safely (fail-safe default).
  - Floor map (`SCR-005`), manual overrides (`SCR-007`), and waitlist (`SCR-009`) continue functioning normally in Manual Mode with a visible banner.

### `FR-021` — Model Registry & Version Rollback (`P1`, `PROPOSED`)
- **User Story**: As an owner/ML engineer, I want to see which model version is running, view its verified benchmark scores, and roll back to a previous version if accuracy drops.
- **Acceptance Criteria**:
  - `ml_models` table stores `model_name`, `version`, `artifact_sha256`, `dataset_version`, `eval_metrics_json`, and `is_active`.
  - Switching active model triggers a graceful CV worker reload and logs an audit entry.

### `FR-022` — Search, Filtering & Pagination (`P0`, `PROPOSED`)
- **Acceptance Criteria**: All list endpoints (`alerts`, `audit_logs`, `ml_review_items`, `waitlist_entries`, `users`) enforce pagination (`page`, `page_size` default `25`, max `100`) and return `{ items, total, page, page_size }`.

### `FR-023` — Accessibility Compliance (`P0`, `PROPOSED`)
- **Acceptance Criteria**: All 16 screens meet WCAG 2.1 Level AA contrast, full keyboard navigation, screen-reader labels, `prefers-reduced-motion` support, and a non-canvas accessible list alternative for `SCR-005`.

### `FR-024` — Responsive Multi-Device Support (`P0`, `PROPOSED`)
- **Acceptance Criteria**: Verified zero horizontal overflow and usable touch targets (`>=44x44px`) at 360px (mobile), 768px (tablet portrait), 1024px (tablet landscape), and 1440px (desktop).
