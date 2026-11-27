# TablePulse Autonomous Browser QA Final Report

> **Date:** 2026-11-27  
> **Repository:** `https://github.com/nisargpatel1906/TablePulse.git` (`main`, HEAD `5f9f4f7`)  
> **Test Environment:** Clean Docker Compose stack (`DEMO_MODE=false`, `NEXT_PUBLIC_DEMO_MODE=false`, `AI_INFERENCE_ENABLED=true`, `REVIEW_CROPS_ENABLED=true`, `TABLE_ADVANCED_ENABLED=true`, `QR_ENABLED=true`, `PUBLIC_MENU_ENABLED=true`, `MENU_IMAGES_ENABLED=true`) backed by PostgreSQL 16 + RLS, Valkey 8, MediaMTX (`1.21.4`), FastAPI, Next.js 15, Caddy `2.11`, CV Worker, and 3 local CC-licensed RTSP camera streams via `tp-rtsp-sim`.

---

## 1. Executive Summary

- **Clean-Install Uninterrupted Run (Run 27):** Executed continuously from a clean `docker compose down -v` state (`bootstrap_required=true`, `demo_mode=false`) through all **48 QA cases** (`TC-ENV-01`–`TC-RES-02`), **225 viewport/geometry checks** (15 routes × 15 viewports + 200% zoom reflow + large system font), Light/Dark & Glass/Solid & EN/HI sweeps, `axe-core` WCAG 2.1 AA audits, degraded DB cache fallback, and `pg_dump`/`pg_restore` parity verification — **zero uncaught errors, zero console errors, zero unexpected 4xx/5xx responses, zero serious/critical a11y violations**.
- **Independent Visual Browser Subagent Corroboration:** Confirmed live rendering on `http://localhost:3000` and `http://localhost:8080` (`final_step_18.png`) with 12-character `PATIODECK012` table label fitted cleanly on canvas, all 66 dishes organized across real categories with CC food photography, human-readable dietary badges, and 0 failed requests (`50/50` HTTP 200) on the public QR menu.
- **Automated Regression Suites (Post-Final-Fix):**
  - `python scripts/license_check.py`: **PASSED** (0 prohibited licenses)
  - `python scripts/secret_scan.py`: **PASSED** (0 tracked `.env` or secrets)
  - Backend (`ruff check .`, `mypy --strict app` across 44 files, `pytest -v` against isolated PostgreSQL 16 + Valkey 8): **28 passed, 0 failed**
  - CV Worker (`ruff check .`, `mypy --strict app` across 11 files, `pytest -v`): **4 passed, 0 failed**
  - ML (`ruff check .`, `mypy --strict .` across 9 files, `pytest -v`): **4 passed, 0 failed**
  - Frontend (`pnpm lint` 0 errors / 7 pre-existing warnings, `pnpm typecheck` 0 errors, `pnpm test`): **17 passed, 0 failed**

---

## 2. Product Defects Found, Fixed & Verified on `origin/main`

Every product defect discovered during live browser testing triggered a full stop, root-cause diagnosis, regression test addition, full check run, git commit + push to `origin/main`, container rebuild, and restart from `TC-ENV-01`:

| Commit | Trigger Case | Root Cause | Fix & Regression Test |
|---|---|---|---|
| `8e39d99` | `TC-ENV-02` | `AuthProvider` blindly called `POST /api/v1/auth/refresh` on mount even without a `tp_refresh_token` cookie, causing `401` console errors on unauthenticated `/`, `/login`, `/register`. | Added `has_session` boolean to `GET /api/v1/auth/bootstrap-status` (`backend/app/api/auth.py`); gated `AuthProvider` refresh call on `has_session`. Tests in `backend/tests/test_auth_and_rbac.py` and `frontend/src/test/stage6.test.tsx`. |
| `b6b0f7c` | `TC-SEC-02` | Direct-URL visit to a cross-tenant or inaccessible `/venues/:venueId/floor` triggered infinite WebSocket reconnect retries and masked Permission Denied behind fallback UI. | Guarded `floor/page.tsx` and `AppShell.tsx` venue resolution against `AuthProvider.venues`; aborted WS retries on HTTP `403`/`404` in `useVenueRealtime.ts`. Regression test in `stage6.test.tsx`. |
| `2c3bb03` | `TC-P1-03` | OpenCV RTSP `VideoCapture` lacked `rtsp_transport;tcp` and short socket timeouts, causing 12.5s stalls; `flag_table_detection` lacked an async timeout guard; Drawer buttons wrapped awkwardly. | Added `OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp` and 3000ms timeouts (`docker-compose.yml`, `venues_cameras.py`); bounded `flag_table_detection` (`floor_ops.py`); isolated `flagSubmitting` & `min-h-[44px]` buttons (`TableDetailDrawer.tsx`). Test in `test_floor_and_ops.py`. |
| `249ee02` | `TC-P1-03` | Direct URL navigation to `/venues/:v/tables/:t` fetched table detail before `AuthProvider` hydrated the access token, causing race `401`. | Deferred `TableDetailDrawer` fetch until `!authLoading && user`. Regression test in `stage6.test.tsx`. |
| `63fe73f`, `c6df248` | `TC-P1-05` | Polygon calibration could suggest colliding `table_code` across cameras and sent extra `display_name` field rejected by strict Pydantic `TablePolygonInput`. | Added `venue_table_codes` to `GET /polygons` (`venues_cameras.py`), `nextAvailableTableCode()` (`frontend/src/lib/table-codes.ts`), and strict schema serialization in `calibrate/page.tsx`. Tests in `test_cameras_and_polygons.py` and `phase2.test.tsx`. |
| `5333f7c` | `TC-P2-08` | `GET /api/v1/venues/{id}/menu-items?format=csv` omitted the formula-sanitized item `description` column. | Added `_csv_safe(r.description)` to `menus_admin.py` CSV export. Verified in `test_phase2_menu_qr.py`. |
| `2c26955` | `TC-P2-12` | Interactive buttons, dietary chips, and category jump pills on `/m/:qrToken` fell below WCAG/Apple HIG `44×44px` minimum mobile touch target. | Enforced `min-h-[44px] min-w-[44px]` mobile touch targets on `PublicDigitalMenu.tsx`. Verified in `public_menu.test.tsx`. |
| `9f268e2`, `2a1be99` | `TC-UI-01` | Mobile buttons, category action icons, range sliders, and standalone checkboxes measured `<44×44px` on `320px–430px` screens. | Added responsive `@media (max-width: 768px)` 44px touch target rules in `globals.css`, wrapped category action buttons cleanly, and gave checkbox labels `min-h-[44px] min-w-[44px]` hit targets across `menu`, `qr-codes`, `cameras/live`, `ml-review`, and `settings/alerts`. Regression test in `stage6.test.tsx`. |
| `ae132fa` | `TC-P2-06` | `MenuItemDrawer` included `categories` and `defaultCategoryId` in its initialization `useEffect`, wiping unsaved dish inputs mid-edit whenever background refetch completed after saving a prior item. | Guarded initialization with `prevInitKeyRef` so parent category refreshes never erase in-progress form state. React Testing Library test in `phase2.test.tsx`. |
| `42ee9ef` | `TC-UI-01` | `AppShell` mobile bottom dock rendered `/venues//floor`, `/alerts`, `/waitlist` `<Link>`s before `activeVenueId` hydrated on `/org/*` routes, triggering Next.js `_rsc` `404` prefetches and ignoring role capabilities. | Guarded bottom dock links on `activeVenueId` + RBAC capabilities (`AppShell.tsx`). Regression test in `stage6.test.tsx`. |
| `5f9f4f7` | `TC-P2-12` | Dish cards rendered raw uppercase dietary enum keys (`GLUTEN_FREE`, `SPICY_MEDIUM`, `CHEF_SPECIAL`) and 12-char `PATIODECK012` table code overflowed its canvas border. | Added bilingual `formatDietaryTag()` helper (`frontend/src/lib/dietary.ts`) across Menu Studio and Public Menu; scaled Konva `<Text>` font size + `ellipsis` in `FloorCanvas.tsx`. Regression test in `phase2.test.tsx`. |

---

## 3. Clean-Install Verification Matrix (Run 27 — Full Pass)

All evidence paths below sit locally under `qa-evidence/run-27/` (git-ignored).

- **Environment, Bootstrap & Multi-Tenancy (`TC-ENV-01`–`TC-ENV-05`):**
  - Verified `bootstrap_required=true, demo_mode=false` on fresh Postgres/Valkey volumes.
  - Bootstrapped **Malabar Spice Hospitality** (`Arjun Mehta`, `arjun.mehta@malabarspice.in`), onboarded **Malabar Spice Courtyard** (`Asia/Kolkata`, `08:00 - 23:30`) with real RTSP camera **Dining Hall Overhead 1** (`rtsp://tp-rtsp-sim:8554/dining`) and starter tables `T01`–`T03`.
  - Invited and registered **5 staff accounts** (`MANAGER` Priya Nair, `HOST` Rohan Kapoor, `STAFF` Anita Deshmukh, `VIEWER` Vikram Joshi, second `OWNER` Kavita Rao) via real single-use invite links, confirming expired/reused token rejection.
  - Provisioned second organization **Deccan Chai Co.** (`Indiranagar`) for real cross-tenant isolation.
- **Auth, Security & RBAC (`TC-AUTH-01`–`05`, `TC-SEC-01`–`03`, `TC-RBAC-02`–`06`):**
  - Login validation, show/hide toggle, generic wrong-password error, 429 rate-limit banner + window rollover, reload refresh token persistence, `?reason=expired`, single-use forgot/reset password flow, Sign Out, zero tokens in `localStorage`/`sessionStorage`, cross-org direct-URL denial, `MANAGER`/`HOST`/`STAFF`/`VIEWER` route & UI gating, and `409 LAST_OWNER_PROTECTED`.
  - Verified `/m/:qrToken` via Caddy (`http://localhost:8080`) sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, zero `Set-Cookie`, zero cookies in incognito context, and zero authenticated API calls.
- **Phase 1 Operations & Real RTSP Pipeline (`TC-P1-01`–`TC-P1-14`):**
  - Verified Light/Dark, Glass/Solid, EN/HI, Live Floor KPIs, `Map`/`List` views, Table Detail Drawer + standalone route, **2-tab `409 VERSION_CONFLICT`**, AI flagging, SSRF loopback rejection (`rtsp://localhost:8554/bad` -> 400), 3 active CC RTSP streams (`dining`, `foodcourt`, `lima`), polygon calibration (`SCR-013`), Live Camera Wall (`SCR-006`), CV worker active heartbeat (`3/3 ONLINE`), **RTSP stream stop -> `422` -> restart -> recovery**, Alerts (`SCR-008`), Waitlist (`SCR-009`), Analytics + CSV (`SCR-010`), ML Review Queue + ZIP export (`SCR-011`), Alert Rules (`SCR-014`), System Health + AI Kill Switch (`SCR-016`), and offline/reconnect handling.
- **Phase 2 Tables, Menus, QR & Public Portal (`TC-P2-01`–`TC-P2-13`):**
  - Created 23+ realistic tables (`T01`–`T08`, `P01`–`P10`, `B01`–`B04`, 12-char `PATIODECK012`), tested bulk add, deactivate/reactivate, archive + code reuse, duplicate `table_code` `409`.
  - Created 2 published menus (**All-Day Dining**, 45 dishes across 6 categories; **Breakfast & Chai**, 21 dishes across 2 categories = **66 dishes total**), Hindi Devanagari text, emoji, `₹0` complimentary items, `Half`/`Full` variants, formula text `=SUM(A1:B2)`, magic-byte rejection of `.svg`/`.gif`/`.pdf` renamed to `.jpg`, WebP photo upload + SHA-256 provenance (`qa-evidence/data-sources.md`), Quick-86 + `HOST` policy toggle (`allow_host_menu_availability`), `CURRENCY_LOCKED` 409 guard, formula-safe CSV export (`'=SUM(A1:B2)`), Mobile Preview modal (`SCR-021`), physical `cv2.QRCodeDetector()` decode of downloaded `PNG` QR -> `http://localhost:3000/m/5HT7-qozTBT9Ag3wzFTACg`, `SVG`, `%PDF` batch print sheet, 7-day grace + `End Grace Now` + `410` revocation, and paused public menu notice.
- **Responsive Matrix, Accessibility & Resilience (`TC-UI-01`, `TC-UI-02`, `TC-RES-01`, `TC-RES-02`):**
  - Swept all 14 authenticated core routes + `/m/:token` across all **15 viewports** (`320×568` through `2560×1440`, 225 geometry audits) + **200% zoom reflow (`640×360`)** + **20px large system font** with **0 overflow, 0 off-screen controls, 0 same-layer overlaps, 0 broken images, and 0 `<44×44px` mobile touch targets**.
  - Verified Dark mode + `prefers-reduced-motion: reduce` + EN/HI + `@axe-core/playwright` WCAG 2.1 AA (**0 critical/serious violations**).
  - Stopped PostgreSQL briefly (`TC-RES-01`) and confirmed public menu served cached `200` from Valkey, recovered DB cleanly, exported Audit Log CSV, and passed `scripts/restore_test.py` (`pg_dump`/`pg_restore` 100% row parity).

---

## 4. Honest Gaps, `BLOCKED (Not Implemented)`, `NOT MEASURED` & Review Items

- **Unimplemented Features (`BLOCKED — Not Implemented` in Repo):**
  1. **2FA / TOTP Setup UI (`TC-AUTH-06`):** `auth.py` checks `user.totp_enabled` on login, but no TOTP enrollment QR/verification UI or setup endpoints exist.
  2. **Menu CSV Import (`TC-P2-08`):** `menus_admin.py` supports UTF-8 formula-safe CSV export; bulk CSV import UI/API is not implemented.
  3. **Admin CLI `create-org` (`TC-ENV-05`):** `backend/app/cli.py` provides `revoke-all`, `rotate-keys`, `backup`, and `restore`, without an `admin create-org` subcommand (second organization provisioned cleanly via documented SQLAlchemy models).
  4. **SMTP Dev Mail Catcher (`TC-ENV-04`, `TC-AUTH-04`):** Project documents blank `SMTP_HOST` fallback displaying copyable single-use invite/reset URLs directly in the Admin UI rather than bundling a MailHog/Mailpit container.
- **ML Release Gate (`NOT MEASURED`):**
  - Real labeled restaurant floor test datasets do not ship in the repository, and unlabeled Wikimedia restaurant clips cannot measure classification accuracy. Therefore **TSM-F1** and release-gate metrics remain strictly **`NOT MEASURED`** (`NOT YET MEASURED` in `SCR-016` and `evaluate_gate.py`).
  - **Informal Visual Sanity Check (NOT the Release Gate):** Visual inspection of `qa-evidence/run-27/sanity-cam1.png` confirmed live RTSP/MJPEG frame decoding, `T01`/`T02`/`T03` polygon overlays, and Haar face-blur masking in active frames, while qualitatively noting that angled/capped heads near frame edges can occasionally escape Haar frontal cascade detection.
- **`PROFESSIONAL REVIEW` Items:** All items flagged `PROFESSIONAL REVIEW` in `docs/decision-log-and-reviews.md` remain untouched for human/legal sign-off.

---

## 5. Run Recordings Verification (`ffprobe` + SHA-256)

Key clean final Run (`run-27`) WebM artifacts verified locally (`qa-evidence/run-27/`, git-ignored):

| File | Duration | Size (bytes) | SHA-256 |
|---|---|---|---|
| `run-27-main.webm` | `281.20s` | `62237111` | `A08C6FC1547E367F82FF919E437D75C734200FA057B272A348CF1134164E4DCB` |
| `run-27-1-invite-MANAGER.webm` | `1.80s` | `129128` | `B0BE2148E7CF78C3E675BD6DAC5790DB1EF566540F53040FEC1009A8C8E56544` |
| `run-27-2-invite-HOST.webm` | `1.80s` | `127456` | `6EFE0D933AA7C86839BD80419A3F09825093304F15D5C73797BE92F6E9057E7E` |
| `run-27-3-invite-STAFF.webm` | `1.88s` | `131015` | `D7033726F9104DB9EB6B92CA42D8E79E5BDC9131AB8A5782EE37E0F1C3E8379B` |
| `run-27-4-invite-VIEWER.webm` | `1.76s` | `128876` | `C62BBF29E3F3A7AB5743A795DE7A2B033A984E7D7658DF80DF698690E8D49D9C` |
| `run-27-5-invite-OWNER.webm` | `1.80s` | `127399` | `0E70F868361EA5808124122BCF3E9B036A5A660FC0CB96059451F8C0EF7312E8` |

Prior iterative QA Runs `run-1` through `run-26` (`.webm` files all verified non-empty via `ffprobe` and SHA-256) remain preserved locally in `qa-evidence/run-*/` alongside `timestamps.csv` and `data-sources.md`.
