# TablePulse Phase 2 — Final Engineering & Release Report (`v1.1.0-rc.1`)

## 1. Delivered Scope (Stages N0–N9)
- **Database & Security (`0003_phase2_tables_menu_qr.py`, `packages/rbac/matrix.yaml`):**
  - Extended `venues` (currency lock, branding, `menu_public_enabled`, `show_unavailable_items_public`, `allow_host_menu_availability`, `qr_grace_days`, `menu_revision`) and `tables` (nullable `polygon_json` for standalone non-camera tables, `display_name`, `min_capacity`, `is_active`, `is_combinable`, `table_notes`, `sort_order`).
  - Added 6 RLS-isolated tables (`table_qr_codes`, `menus`, `menu_categories`, `menu_items`, `menu_media_assets`, `qr_scan_daily_stats`), read-only PostgreSQL role `tablepulse_public`, views `v_public_qr_resolution` & `v_public_menu_catalog`, and CSPRNG 128-bit QR backfill.
  - Extended canonical 5-role RBAC (`OWNER`, `MANAGER`, `HOST`, `STAFF`, `VIEWER`) by 8 capabilities (`21 -> 29`) plus fail-closed Phase 2 flags (`TABLE_ADVANCED_ENABLED`, `QR_ENABLED`, `PUBLIC_MENU_ENABLED`, `MENU_IMAGES_ENABLED`).
- **Backend APIs (`API-024`–`API-035`):**
  - Advanced Tables & Bulk Add/Update (`tables_admin.py`) + unmapped table binding on camera polygon calibration (`venues_cameras.py`).
  - Digital Menu Studio APIs (`menus_admin.py`, `menu_schedule.py`), minor-unit currency handling, formula-safe UTF-8 BOM CSV export, 5 MB WebP image pipeline with magic-byte sniffing, EXIF strip, `800px`/`320px` encoding, SHA-256 deduplication, and orphan GC (`media.py`).
  - Offline `segno` SVG/PNG QR generator, framed cards, `reportlab` cut-guided multi-up PDFs (`A4_4UP`, `A4_6UP`, `LETTER_4UP`), atomic grace rotation, 15m HMAC preview links (`qr_admin.py`, `qr_export.py`).
  - Unauthenticated isolated customer menu `GET /api/v1/public/menu/{qr_token}` (`public_menu.py`) using `tablepulse_public`, strict `PublicMenuResponse(extra="forbid")`, `ETag`/`304`, `Cache-Control: no-cache`, `60/min` IP rate limit, Valkey 60s cache + 24h stale-while-error `X-Stale: 1`, and privacy-safe debounced daily scan telemetry.
- **Frontend UI (`SCR-017`–`SCR-022` + `SCR-005`/`SCR-013`):**
  - `SCR-017` Table Directory (`/venues/[venueId]/settings/tables`), `SCR-018` Menu Studio (`/venues/[venueId]/menu`), `SCR-019` Dish Editor Drawer (`MenuItemDrawer.tsx`), `SCR-020` Table QR Manager (`/venues/[venueId]/settings/qr-codes`), `SCR-021` Live Mobile Preview (`MenuPreviewModal.tsx`), and isolated zero-login zero-cookie Customer Menu (`(public)/m/[qrToken]/page.tsx`, `PublicDigitalMenu.tsx`, `ClientProviders.tsx`).

## 2. Verification & Test Count Comparison (N0 Baseline -> N9 Final)

| Suite / Gate | Stage N0 Baseline | Stage N9 Final | Result |
|---|---:|---:|---|
| License Check (`scripts/license_check.py`) | PASS | PASS | Zero prohibited licenses |
| Secret Scan (`scripts/secret_scan.py`) | PASS | PASS | Zero tracked `.env` or secrets |
| Backend Tests (`backend` pytest) | `15 / 15` | `26 / 26` | Full pass (`ruff` 0, `mypy --strict` 0 across 44 files) |
| CV Worker Tests (`cv-worker` pytest) | `4 / 4` | `4 / 4` | Full pass (`ruff` 0) |
| ML Harness Tests (`ml` pytest) | `4 / 4` | `4 / 4` | Full pass (`ruff` 0) |
| Frontend Unit Tests (`vitest`) | `4 / 4` | `9 / 9` | Full pass (`tsc` 0 errors, `eslint` 0 errors) |
| Phase 2 Live Docker Playwright E2E + `axe-core` | N/A | `1 / 1` | Full pass (`0` horizontal overflow, `0` critical/serious WCAG violations) |

## 3. Measured Benchmarks (`docs/benchmarks.md`)
- `API-035` Valkey warm hit (`n=30`): **p50 = `29.22 ms`**, **p95 = `49.31 ms`** (cold PostgreSQL view read: `213.93 ms`).
- `API-035` `ETag 304 Not Modified` (`n=20`): **p50 = `18.92 ms`**, **p95 = `24.33 ms`**.

## 4. Open Questions, UI Deviations & Professional Reviews
- UI design & WCAG contrast adjustments recorded in [ui-deviations.md](file:///c:/Users/Nisarg%20Patel/Documents/TablePulse/docs/ui-deviations.md) (`UI/phase2/SCR-017..022-*.png` archived).
- Phase 2 safe defaults (`OQ-P2-01`..`OQ-P2-04`) logged in [open-questions.md](file:///c:/Users/Nisarg%20Patel/Documents/TablePulse/docs/open-questions.md).
- Pending legal/compliance sign-offs (`PR-01`–`PR-09`) remain open for human legal/security review in [decision-log-and-reviews.md](file:///c:/Users/Nisarg%20Patel/Documents/TablePulse/docs/decision-log-and-reviews.md) prior to commercial launch.
