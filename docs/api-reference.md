# TablePulse REST & WebSocket API Reference (v1.0)

All endpoints use the canonical JSON response envelope:
- Success: `{ "success": true, "data": ... }`
- Error: `{ "success": false, "error": { "code": "...", "message": "...", "fields": {...} } }`

## Endpoint Groups (`API-001`–`API-023`)

| ID | Method & Path | Auth / Role | Description |
|---|---|---|---|
| `API-001` | `GET /api/v1/auth/bootstrap-status`, `POST /api/v1/auth/bootstrap` | Public (one-time when `users == 0`) | Check first-run status; create initial org + `OWNER` |
| `API-002` | `POST /api/v1/auth/login` | Public (rate limited 10/min IP, 5 fail/15m acct) | Argon2id login -> 15m JWT + 7d `HttpOnly` refresh cookie |
| `API-003` | `POST /api/v1/auth/refresh` | Refresh cookie | Rotate refresh token; revokes family on reuse |
| `API-004` | `POST /api/v1/auth/logout` | Authenticated | Revoke session & clear cookie |
| `API-005` | `POST /api/v1/auth/forgot-password`, `POST /api/v1/auth/reset-password`, `GET /api/v1/auth/invite-info`, `POST /api/v1/auth/accept-invite` | Public | Password recovery (30m single-use) & invite acceptance (48h) |
| `API-006` | `POST /api/v1/auth/ws-ticket`, `GET /api/v1/auth/me` | Authenticated | Issue 60s single-use WS ticket; get user profile & venues |
| `API-007` | `GET/POST /api/v1/venues`, `PATCH /api/v1/venues/{v}` | `OWNER`, `MANAGER` (GET all roles) | List, create, update venues |
| `API-008` | `GET/POST /api/v1/venues/{v}/cameras`, `PATCH/DELETE /api/v1/venues/{v}/cameras/{c}` | `OWNER`, `MANAGER` | Manage RTSP/RTSPS/Demo MP4 cameras (AES-256-GCM encrypted, SSRF checked) |
| `API-009` | `POST /api/v1/venues/{v}/cameras/{c}/test` | `OWNER`, `MANAGER` | Capture test snapshot (`>=640x480`), face-blurred JPEG |
| `API-010` | `GET/PUT /api/v1/venues/{v}/cameras/{c}/polygons`, `POST .../stream-token` | `OWNER`, `MANAGER` (`HOST` conditional for stream-token) | Bulk validate/save normalized polygons (`0..1`) & exclusion zones |
| `API-011` | `GET /api/v1/venues/{v}/floor-state` | All venue roles | Live floor map state + KPIs (also 5s WS fallback) |
| `API-012` | `GET /api/v1/venues/{v}/tables/{t}` | All venue roles | Single table detail + last 10 `table_state_events` |
| `API-013` | `PATCH /api/v1/venues/{v}/tables/{t}/override` | `OWNER`, `MANAGER`, `HOST`, `STAFF` (clean/served only) | Optimistic-locked (`version`) manual override + audit log |
| `API-014` | `POST /api/v1/venues/{v}/tables/{t}/flag` | `OWNER`, `MANAGER`, `HOST`, `STAFF` | Flag inaccurate AI detection -> `ml_review_items` |
| `API-015` | `GET /api/v1/venues/{v}/alerts`, `PATCH /api/v1/venues/{v}/alerts/{a}` | `OWNER`, `MANAGER`, `HOST`, `STAFF` | Paginated alerts queue + acknowledge/resolve |
| `API-016` | `GET/POST /api/v1/venues/{v}/waitlist`, `PATCH /api/v1/venues/{v}/waitlist/{w}` | `OWNER`, `MANAGER`, `HOST` | Waitlist CRUD + seat party on `FREE` table |
| `API-017` | `GET /api/v1/venues/{v}/turnover-predictions` | `OWNER`, `MANAGER`, `HOST` | Ranked next-available tables matching `party_size` |
| `API-018` | `GET /api/v1/venues/{v}/analytics/peak-hours` | `OWNER`, `MANAGER`, `VIEWER` | Peak-hours occupancy, heatmap, staffing curve & `?format=csv` |
| `API-019` | `GET/PATCH /api/v1/venues/{v}/alert-rules`, `POST .../test-webhook` | `OWNER`, `MANAGER` | Alert thresholds + SSRF-safe HMAC-SHA256 webhooks |
| `API-020` | `GET/PATCH /api/v1/venues/{v}/ml-review`, `GET .../export` | `OWNER`, `MANAGER` (`export` `OWNER` only) | Review uncertain crops & export anonymized zip |
| `API-021` | `GET /api/v1/org/users`, `POST .../invite`, `PATCH .../{u}`, `POST .../revoke-sessions`, `POST .../reset-link`, `GET /api/v1/org/audit-logs` | `OWNER`, `MANAGER` (venue-scoped) | Team management, Last-Owner protection (`409`), audit logs + CSV |
| `API-022` | `GET/PATCH /api/v1/org/system`, `POST .../models/{m}/activate`, `POST .../purge-snapshots` | `OWNER` only | System health, AI kill switch, model registry gate, snapshot purge |
| `API-023` | `GET /api/v1/health`, `POST /api/v1/internal/media-auth` | Public / MediaMTX hook | Liveness/readiness + MediaMTX stream token verification |
| `WS` | `WS /api/v1/ws/venues/{v}?ticket=...` | Authenticated WS ticket | Emits `floor.snapshot`, `table.state_changed`, `alert.created`, `alert.updated`, `system.kill_switch_changed` |

## Phase 2 Endpoint Groups (`API-024`–`API-035`)

| ID | Method & Path | Auth / Role | Description |
|---|---|---|---|
| `API-024` | `GET/POST /api/v1/venues/{v}/tables`, `PATCH/DELETE /api/v1/venues/{v}/tables/{t}` | `tables.read` / `tables.manage` | List/filter tables + KPIs, create/edit/archive standalone or camera-linked tables (auto 128-bit QR, `409 TABLE_IN_USE` + `?force=true`) |
| `API-025` | `POST/PATCH /api/v1/venues/{v}/tables/bulk` | `tables.manage` | Bulk range generation (`1..50` padded codes + auto QRs) & bulk section/active updates |
| `API-026` | `GET/POST /api/v1/venues/{v}/menus`, `PATCH/DELETE /api/v1/venues/{v}/menus/{m}` | `menu.read` / `menu.manage` | Digital menu CRUD with `DRAFT`/`PUBLISHED`/`ARCHIVED` publish gate (`422 MENU_NOT_PUBLISHABLE`) & time-of-day schedules |
| `API-027` | `PATCH /api/v1/venues/{v}/menu-settings` | `menu.manage` (`OWNER` for `currency_code`) | Venue branding, `menu_public_enabled`, `show_unavailable_items_public`, `allow_host_menu_availability`, `qr_grace_days`, `409 CURRENCY_LOCKED` |
| `API-028` | `GET/POST .../menus/{m}/categories`, `PATCH .../categories/reorder`, `PATCH/DELETE .../categories/{c}` | `menu.read` / `menu.manage` | Menu category CRUD, atomic display reordering, non-empty guard (`409 CATEGORY_NOT_EMPTY`) |
| `API-029` | `GET/POST /api/v1/venues/{v}/menu-items`, `PATCH .../menu-items/reorder`, `PATCH/DELETE .../menu-items/{i}`, `POST .../duplicate` | `menu.read` / `menu.manage` | Menu items CRUD (minor-unit prices, dietary tags, allergens, variants `<=8`, optimistic lock `409`, formula-safe `?format=csv`) |
| `API-030` | `PATCH .../menu-items/{i}/availability`, `PATCH .../menu-items/bulk-availability` | `menu.availability` (+ conditional `HOST`) | 1-tap & bulk Quick-86 availability toggles with immediate public Valkey cache eviction |
| `API-031` | `POST/DELETE /api/v1/venues/{v}/menu/media`, `GET /media/menu/{v}/{filename}` | `menu.manage` / Public immutable WebP | 5 MB validated WebP transcoding (magic bytes, EXIF strip, `800px`+`320px`, SHA-256 dedup), delete (`409 MEDIA_IN_USE`), immutable static WebP delivery |
| `API-032` | `GET /api/v1/venues/{v}/qr-codes` | `qr.read` | Per-table QR directory with short `/m/:token` URLs, 7d/total scan stats, grace-window state |
| `API-033` | `POST .../qr/regenerate`, `POST .../qr/end-grace`, `POST .../qr/preview-link` | `qr.manage` / `qr.read` | Atomic QR rotation with grace period (`COMPROMISED` forces `0` days), immediate grace revocation, 15m HMAC preview links |
| `API-034` | `GET .../qr/download`, `POST /api/v1/venues/{v}/qr/export-pdf` | `qr.read` | Offline `segno` SVG/PNG (plain or framed) & `reportlab` cut-guided multi-up PDF print sheets (`A4_4UP`, `A4_6UP`, `LETTER_4UP`) |
| `API-035` | `GET /api/v1/public/menu/{qr_token}` | Public (zero auth, `tablepulse_public`) | Unauthenticated read-only digital menu resolver (`ETag`/`304`, `404`/`410`, Valkey 60s + 24h `X-Stale: 1` fallback, `60/min` fail-open RL, privacy-safe daily scan telemetry) |
