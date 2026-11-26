# TablePulse Phase 2 — Unique Table QR Codes & Customer Digital Menu

## Quick Reference
- **QR Architecture**: Every table has exactly one `ACTIVE` cryptographically random 128-bit URL-safe token (`table_qr_codes.token`) pointing to `{PUBLIC_APP_URL}/m/{qr_token}` (`DEC-010`).
- **Offline-Capable Generation**: QR SVG, high-DPI PNG, and multi-table printable PDF tent-card sheets are generated server-side using permissive BSD libraries (`segno` + `reportlab`) — zero external QR APIs (`DEC-014`).
- **Customer Digital Menu (`SCR-022`)**: Public, zero-login, mobile-first read-only menu view with category pills, instant search, dietary filters, item detail bottom sheet, and strict isolation from all admin/owner routes and internal data (`FR-037`–`FR-040`).

---

## 1. QR Code Lifecycle & Management (`FR-034`, `FR-035`, `FR-036`)

### 1.1 Automatic Generation & Backfill
- **New Tables**: Creating any table (individually via `API-024` or bulk via `API-025`) atomically inserts an `ACTIVE` `table_qr_codes` row with `token = secrets.token_urlsafe(16)` (128 bits of entropy, 22 URL-safe chars).
- **Existing v1.0 Tables**: Alembic migration `002_phase2_tables_menu_qr.py` automatically backfills one `ACTIVE` `table_qr_codes` row for every existing non-deleted row in `tables`.
- **Uniqueness**: Enforced at the database level via `UNIQUE (token)` and partial unique index `UNIQUE (table_id) WHERE status = 'ACTIVE'`.

### 1.2 Regeneration & Revocation Workflow (`FR-035`)
When an `OWNER` or `MANAGER` clicks **Regenerate QR** for a table in `SCR-020` (e.g., if a sticker was copied/shared externally or damaged):
1. Confirmation modal warns: *"The previously printed QR code for Table [table_code] will immediately stop working."*
2. Backend executes inside a single transaction:
   - Updates existing `ACTIVE` row: `status = 'REVOKED'`, `revoked_at = now()`, `revoked_by = current_user.id`, `revoked_reason = 'REGENERATED'`.
   - Inserts new `ACTIVE` row with fresh 128-bit `token`.
   - Writes `QR_REGENERATED` event to `audit_logs`.
3. Immediately evicts `tp:pub:qr:{old_token}` from Valkey so the old QR stops working within `< 1 second`.

### 1.3 Download & Batch Print Formats (`FR-036`)
| Format | Endpoint | Specification | Best Use |
|---|---|---|---|
| **Single SVG** | `GET /api/v1/venues/{v}/tables/{t}/qr/download?format=svg` | Pure vector SVG, Error Correction Level `M` (15% damage recovery), 4-module quiet zone. | Custom print shops & graphic designers. |
| **Single PNG** | `GET /api/v1/venues/{v}/tables/{t}/qr/download?format=png&framed=true` | 1024×1024 px (300 DPI print-ready); when `framed=true`, renders clean card with Venue Name, Table Label (`Table 04`), QR, and `"Scan for Menu"`. | Quick table stickers / standees. |
| **Batch Printable PDF** | `POST /api/v1/venues/{v}/qr/export-pdf` | Accepts `{ table_ids: [...] }` (max 100 tables) and `layout: 'A4_4UP' | 'A4_6UP' | 'LETTER_4UP'`. Generates cut-guided printable PDF sheet with Venue Name, Table Label, QR, and scan prompt. | Printing all venue table tents at once. |

---

## 2. Customer-Facing Digital Menu (`/m/:qrToken`, `SCR-022`) (`FR-037`–`FR-040`)

### 2.1 Zero-Login Access & Strict Data Isolation
- Customers scan the QR code with their native iOS/Android camera -> opens `{PUBLIC_APP_URL}/m/{qr_token}` directly in the mobile browser.
- **No login, no account creation, no app install, no tracking cookies**.
- **Public Payload Whitelist** (ONLY these fields may ever be returned by `GET /api/v1/public/menu/{qr_token}`):
  - `venue`: `{ name, tagline, logo_url, currency_code, timezone }`
  - `table`: `{ label }` (equals `display_name || "Table " + table_code` — NO `table_id`, NO `camera_id`, NO `table_notes`, NO `current_state`, NO `seat_capacity`)
  - `menus`: active & currently scheduled menus -> ordered active `categories` -> ordered non-deleted `items` (`id`, `name`, `description`, `price_minor_units`, `compare_at_price_minor_units`, `image_url`, `thumb_url`, `image_alt`, `is_available`, `is_featured`, `dietary_tags`, `allergens`, `prep_time_minutes`, `calories_kcal`).
- **Zero Admin Leakage**: The `(public)` Next.js layout does NOT import admin navigation, auth contexts, WebSocket hooks, or internal routes. No link to `/login` or `/venues/*` exists anywhere on `SCR-022`.

### 2.2 Edge-Case Lifecycle States (`FR-039`)
| Condition | HTTP Status | Error Code | Customer-Facing Screen (`SCR-022`) |
|---|---|---|---|
| **Valid Active QR & Published Menu** | `200 OK` | — | Full interactive digital menu with venue header & table badge (`Table 04`). |
| **QR Token Was Regenerated (`status='REVOKED'`, `reason='REGENERATED'`)** | `410 Gone` | `QR_CODE_REVOKED` | Friendly neutral card: *"This table QR code has been updated. Please ask your server for the current menu."* |
| **Table Soft-Deleted (`reason='TABLE_DELETED'`) or Deactivated (`is_active=false`)** | `410 Gone` | `TABLE_UNAVAILABLE` | Friendly card: *"This table is currently unavailable. Please ask a host or server for assistance."* |
| **Unknown / Forged Token** | `404 Not Found` | `QR_CODE_NOT_FOUND` | Generic card: *"Menu not found. Please scan the QR code placed on your table."* (No hint about valid tokens). |
| **Venue Unpublished Menu (`menu_public_enabled=false`) or Zero Active Menus** | `200 OK` (with `menus: []`) | — | Venue header + friendly notice: *"Our digital menu is being updated right now. Please ask your server for a menu."* |
| **Menu Updated While Customer Is Browsing** | `200 OK` / `304 Not Modified` | — | Pull-to-refresh or page reload fetches fresh menu within `<= 15s` (immediate server cache invalidation on write). |

### 2.3 Privacy-Preserving Scan Counter (`FR-040`)
- On valid `200 OK` scan, backend asynchronously increments `table_qr_codes.scan_count`, updates `last_scanned_at`, and upserts `qr_scan_daily_stats (venue_id, table_id, current_date)` via a lightweight non-blocking background task (debounced per IP hash in memory/Valkey for 5 minutes so page refreshes don't inflate scan counts, without storing raw IP addresses in PostgreSQL).


---

## 3. Advanced QR Lifecycle, Anti-Quishing & Preview Controls (Ported from P2-07/P2-08)

### 3.1 Frozen URL Contract & Host-Header Poisoning Ban
- Generated QR codes MUST build URLs strictly from the validated environment variable `PUBLIC_APP_URL` (`https://<domain>/m/{token}` in production; never derived from HTTP `Host` or `X-Forwarded-Host` headers).
- The `/m/{token}` path prefix is a **frozen public contract** (must remain supported >= 2 years across future releases so printed table tents never break).

### 3.2 Optional Grace Period on Regeneration
- `POST /api/v1/venues/{v}/tables/{t}/qr/regenerate` accepts `{ "reason": "DAMAGED|COMPROMISED|REBRAND|OTHER", "grace_days": 0..30 }` (default: venue `qr_grace_days`, or forced `0` when `reason == "COMPROMISED"`).
- When `grace_days > 0`: the new token becomes `ACTIVE` immediately while the old token transitions to `GRACE` until `grace_until` so seated diners aren't broken while staff swap stickers. Admins can click **End Grace Now** at any time to revoke immediately.
- A background job (every 5 minutes) transitions expired `GRACE` rows to `REVOKED` and evicts Valkey keys.

### 3.3 Anti-Quishing & Operational Verification
- **Printed Card Short URL**: Every framed PNG and PDF tent card prints the short human-readable domain (`floor.myrestaurant.com`) below the QR so guests can visually verify the domain against tampered sticker overlays ("quishing").
- **Zero-Scan Watchlist**: `SCR-020` provides a `"Never scanned (30d)"` filter to help managers spot missing or tampered table stickers.
- **Signed 15-Minute Admin Preview Link**: `POST /api/v1/venues/{v}/tables/{t}/qr/preview-link` returns a short-lived HMAC-signed URL (`/m/{token}?p=<hmac>`) that bypasses scan counting and optionally renders `DRAFT` menus for staff testing without ever exposing drafts to unauthenticated diners.
- **CI Scan-Reliability Test**: Automated tests decode generated SVG/PNG QR outputs using `zxing-cpp` or `pyzbar` to confirm valid URLs and readable quiet zones (4 modules, ECC Level `M`).
