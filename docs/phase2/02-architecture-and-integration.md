# TablePulse Phase 2 — Architecture & System Integration

## Quick Reference
- **Deployment Impact**: **Zero new Docker containers required** (`PROPOSED`). All Phase 2 capabilities live inside the existing `api` (FastAPI), `web` (Next.js 15), `db` (PostgreSQL 16), and `valkey` (Valkey 8) containers.
- **Public Route Isolation**: Customer QR scans hit a dedicated, lightweight Next.js route group `(public)/m/[qrToken]` backed by a dedicated unauthenticated, rate-limited API namespace `/api/v1/public/menu/{qr_token}` — completely decoupled from authenticated admin JS bundles and cookies.
- **Media Storage**: Menu item images and venue logos are stored on a local persistent Docker volume (`MENU_MEDIA_DIR`, e.g., `/app/data/menu-media`) served via Caddy/Nginx with immutable cache headers (`Cache-Control: public, max-age=31536000, immutable`) — with an optional S3-compatible adapter interface (`PROPOSED`) for multi-node cloud deployments.

---

## 1. Component Integration Diagram

```text
[Customer Smartphone]                         [Owner / Manager / Host Tablet]
         │                                                   │
         │ HTTPS GET /m/{qr_token} (No Auth)                 │ HTTPS + Bearer JWT / HttpOnly Cookie
         ▼                                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        Caddy / Nginx Reverse Proxy                         │
│  /m/* ──► web (Public Bundle)    /media/menu/* ──► Static Immutable Files  │
│  /api/v1/public/* ──► api (Strict IP Rate Limit)  /api/v1/* ──► api (RBAC) │
└───────────────────────────────┬────────────────────────────┬───────────────┘
                                │                            │
                                ▼                            ▼
                      ┌───────────────────┐        ┌───────────────────┐
                      │  FastAPI Backend  │◄──────►│   Valkey 8  │
                      │ - Table Service   │        │ - Menu Cache (60s)│
                      │ - Menu Service    │        │ - QR Rate Limits  │
                      │ - QR/PDF Gen      │        │ - CV Reload Bus   │
                      │ - Media Validator │        └─────────┬─────────┘
                      └─────────┬─────────┘                  │
                                │                            ▼
                                ▼                  ┌───────────────────┐
                      ┌───────────────────┐        │  CV Worker (v1.0) │
                      │  PostgreSQL 16    │        │ (Reloads active   │
                      │  (15 v1 + 6 v2    │        │  camera polygons) │
                      │   tables + RLS)   │        └───────────────────┘
                      └───────────────────┘
```

---

## 2. Key Architectural Decisions (ADRs `DEC-009`–`DEC-015`)

| ID | Decision | Label | Rationale |
|---|---|---|---|
| `DEC-009` | **No new microservices or containers** — add modular routers/services (`tables`, `menus`, `qr`, `public_menu`, `media`) inside existing `backend/` and `frontend/`. | `PROPOSED` | Preserves 1-command self-hosted `docker compose up -d` simplicity; zero extra operational overhead. |
| `DEC-010` | **Opaque 128-bit CSPRNG QR tokens (`/m/{token}`)** instead of `/venues/{slug}/tables/{table_code}`. | `PROPOSED` | Prevents URL enumeration of other restaurants/tables, enables instant per-table QR revocation without renaming the table, and keeps QR codes short and easy to scan in dim lighting. |
| `DEC-011` | **Integer minor-unit pricing (`price_minor_units BIGINT`) + venue ISO-4217 `currency_code`**. | `PROPOSED` | Eliminates floating-point rounding bugs (`19.9900000001`) across INR, USD, EUR, JPY, etc. |
| `DEC-012` | **Server-side validated image pipeline (Pillow WebP transcoding + magic-byte check + EXIF strip)** instead of direct browser-to-cloud unsigned upload presets. | `PROPOSED` | Eliminates unsigned-upload abuse, blocks polyglot/SVG XSS payloads, strips GPS/camera EXIF metadata, and produces fast mobile WebP thumbnails (`<= 150 KB`). |
| `DEC-013` | **Valkey read-through cache (60s TTL + immediate invalidation on menu/table/QR write)** for `/api/v1/public/menu/{qr_token}`. | `PROPOSED` | Absorbs dinner-rush bursts (e.g., 80 diners scanning QRs within 5 minutes) with `< 5ms` cache hits while reflecting item "86 / Sold Out" updates within 1 second. |
| `DEC-014` | **Server-side QR SVG/PNG/PDF generation (`segno` BSD-3-Clause + `reportlab` BSD)** — never rely on external QR APIs (`chart.googleapis.com` etc.). | `PROPOSED` | Works 100% offline/air-gapped on restaurant LAN, zero external dependency breakage, and strictly permissive open-source licenses. |
| `DEC-015` | **Decouple `tables` creation from `cameras`** (making `polygon_json` nullable and adding `is_active`). | `PROPOSED` | Lets restaurants add/customize tables (including patio/non-CCTV tables) immediately, then optionally map camera polygons in `SCR-013` later. |

---

## 3. Caching & Real-Time Propagation Strategy
- **Cache Keys in Valkey**:
  - `tp:pub:qr:{qr_token}` -> `{ status, venue_id, table_id, table_display_label }` (TTL: `300s`).
  - `tp:pub:menu:{venue_id}` -> Pre-serialized public menu JSON + ETag hash (TTL: `60s`).
- **Immediate Invalidation Triggers**:
  - Any mutation to `menus`, `menu_categories`, `menu_items`, or venue branding (`logo`, `currency_code`, `menu_public_enabled`) immediately deletes `tp:pub:menu:{venue_id}`.
  - Any table rename, deactivation, soft-delete, or QR regeneration immediately deletes `tp:pub:qr:{old_token}` and `tp:pub:qr:{new_token}`.
  - Any table create/edit/delete affecting a camera-mapped table publishes `roi.updated` on existing Valkey Pub/Sub channel `tp:cv:control` so `cv-worker` stays in sync without restart.
- **HTTP Caching for Mobile Diners**:
  - Public menu endpoint sends `ETag` + `Cache-Control: public, max-age=15, stale-while-revalidate=30`, making repeat tab opens instantaneous while staying fresh.

---

## 4. Capacity & Load Delta (Phase 2 Additions)
- **Peak QR Scan Traffic (H1 Single Venue, 25 tables, 100 seats)**: ~150–300 QR scans/day; burst peak ~30 scans/minute during dinner seating. Easily served from Valkey (`< 2%` CPU).
- **Menu Image Storage (H1 Single Venue)**: ~80 menu items × 2 sizes (WebP full `800px` ~90 KB + thumbnail `320px` ~25 KB) = `~9.2 MB` per venue (~230 MB for 25 venues in H3).
- **PDF Batch Export Load**: Generating a 25-table PDF tent-card sheet via `reportlab` + `segno` takes `~350ms` in memory; capped at 100 tables per PDF request to protect API worker memory.


---

## 5. Public Surface Isolation, Resilience & Feature Flags (Ported Hardening)

### 5.1 Dedicated Read-Only Database Role (`tablepulse_public`)
- The public endpoint `GET /api/v1/public/menu/{qr_token}` MUST execute database reads using a dedicated, least-privilege PostgreSQL role **`tablepulse_public`** whose only privilege is `SELECT` on two explicit public views (`v_public_qr_resolution` and `v_public_menu_catalog`).
- `tablepulse_public` has **zero** access to `users`, `refresh_tokens`, `cameras`, `audit_logs`, `table_notes`, `waitlist_entries`, or any write statements.

### 5.2 Atomic Venue Revision & Stale-While-Error Fallback
- `venues.menu_revision` (`BIGINT`) increments atomically inside the same DB transaction as any change affecting the public payload (menu, category, item, variant, media, venue branding, or QR assignment).
- **Valkey Cache + Stale Fallback:** Public menu payloads are cached under `tp:pub:menu:{venue_id}:v{menu_revision}` (60s normal TTL) with a secondary stale copy kept up to **24 hours**. If PostgreSQL is temporarily unreachable, `API-035` serves the stale cached payload with header `X-Stale: 1` instead of returning `500` to diners.
- **Valkey Down Fallback:** If Valkey is temporarily down, `API-035` falls back to a short 30s in-process LRU cache + direct read via `tablepulse_public`; rate limiting fails **open** for public `GET`s (and stays **closed** for admin/auth routes).

### 5.3 Public Security Headers (Caddy / Next.js on `/m/*` and `/media/menu/*`)
- `/m/*`: `Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'`, `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`, `X-Robots-Tag: noindex, nofollow`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`, and **zero `Set-Cookie` headers**.
- `/media/menu/*`: `Cache-Control: public, max-age=31536000, immutable`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'; sandbox`.

### 5.4 Phase 2 Fail-Closed Feature Flags (Missing = `false`)
| Flag | Default When Missing | Purpose |
|---|---|---|
| `TABLE_ADVANCED_ENABLED` | `false` | Enables creating non-camera/uncalibrated tables (`polygon_json IS NULL`). Keep `false` during initial migration deploy until smoke tests pass. |
| `QR_ENABLED` | `false` | Enables QR management, download, and regeneration endpoints. |
| `PUBLIC_MENU_ENABLED` | `false` | Master deployment kill switch for `/m/*` and `API-035`. |
| `MENU_IMAGES_ENABLED` | `false` | Enables menu image upload pipeline (`API-031`). |

### 5.5 Phase 2 Dependency License Verification
All new libraries MUST pass `scripts/license_check.py` (no AGPL/GPL/SSPL/non-commercial):
- `segno` (BSD-3-Clause) · `reportlab` open-source (BSD) · `Pillow` (HPND/MIT-CMU) · Noto Sans + Noto Sans Devanagari fonts for PDF cards (SIL OFL) · `@dnd-kit/*` for accessible keyboard drag-and-drop (MIT) · `zxing-cpp` or `pyzbar` (dev/CI test dependency only — verify license at Stage 9a).
