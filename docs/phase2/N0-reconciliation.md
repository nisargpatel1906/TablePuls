# Phase 2 Stage N0 (9a) — Baseline Reconciliation Report

> **Date:** 2026-11-26  
> **Baseline Commit Before Phase 2:** `9f903e9` (+ uncommitted pre-existing Phase 1.5 camera stream-type & route alias improvements committed in N0)  
> **Rule:** Where the real repository differs from earlier doc templates, **the repository wins** and every mapping is recorded below.

---

## 1. Repository Verification Checklist (per `docs/phase2/00-baseline-reconciliation.md` §2)

| Check Item | Verified Finding in Real Repo | Action Required |
|---|---|---|
| **Alembic Head & DB Schema** | Current revision head is `0002_expand_camera_stream_types` (`down_revision = 0001_initial_schema`). 15 Phase 1 tables verified (`organizations`, `venues`, `users`, `refresh_tokens`, `cameras`, `tables`, `table_state_events`, `occupancy_snapshots` partitioned by month, `alerts`, `waitlist_entries`, `ml_models`, `ml_review_items`, `alert_rules`, `audit_logs`, `system_settings`). RLS enabled on 7 tenant tables (`venues`, `cameras`, `tables`, `alerts`, `waitlist_entries`, `ml_review_items`, `audit_logs`) using `current_setting('app.current_org_id', true)::uuid`. | Phase 2 migration must be **`0003_phase2_tables_menu_qr.py`** (`down_revision = "0002_expand_camera_stream_types"`), not `002_*`. |
| **RBAC Source of Truth & Roles** | Single source of truth: `packages/rbac/matrix.yaml` (`version: 1`). Exact 5 roles: `OWNER`, `MANAGER`, `HOST`, `STAFF`, `VIEWER`. Currently **21** capabilities in `matrix.yaml`, enforced by `require_org_role(capability=...)` and `require_venue_role(capability=...)` in `backend/app/core/rbac.py` and mirrored in `frontend/src/lib/rbac.ts`. | Extend `matrix.yaml`, `rbac.py`, and `rbac.ts` additively with **8** Phase 2 capabilities while keeping all 21 v1.0 capabilities and role counts untouched. (`ADMIN` mentioned in an earlier prompt template maps to `OWNER` / `MANAGER`.) |
| **Route-Policy Completeness Gate** | Enforced in `backend/tests/test_auth_and_rbac.py::test_ws_ticket_and_policy_completeness_and_log_scrubber` via `_tp_rbac_protected` attribute check + explicit `public_or_authn_only` allowlist (`app.routes`). | Keep all new `/api/v1/venues/*` routes annotated with `require_venue_role(capability=...)` and add ONLY `/api/v1/public/menu/{qr_token}` (marked explicitly as `policy="public"`) to the public allowlist. |
| **Polygon / Camera / Floor Coord Consumers** | Audited across backend, CV worker, and frontend (see Section 3 below). | Harden `/api/v1/internal/cv-cameras`, `/api/v1/venues/{v}/floor-state`, `/api/v1/venues/{v}/waitlist` / `turnover-predictions`, `cv-worker/app/main.py`, `FloorCanvas.tsx`, `PolygonEditorCanvas.tsx`, and `SCR-013` calibrate page for nullable `polygon_json`, nullable `camera_id`, `is_active = false`, and `unmonitored_tables`. |
| **Infra, Cache, Proxy, Env Vars** | Compose services: `db` (`postgres:16-alpine`), `valkey` (`valkey/valkey:8-alpine`), `mediamtx`, `api`, `cv-worker`, `web`, `caddy` (`infra/caddy/Caddyfile`). Port dev overlay: `docker-compose.dev.yml`. `.env.example` defines `PUBLIC_APP_URL`, `ALLOWED_ORIGINS`, `VALKEY_URL`. | Mount `menu_media_data:/app/data/menu-media` on `api` and `caddy`, route `/media/menu/*` in `infra/caddy/Caddyfile` with `Cache-Control: public, max-age=31536000, immutable`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'; sandbox`, and add `PUBLIC_DATABASE_URL`, `MENU_MEDIA_DIR`, and fail-closed flags to `.env.example` & `config.py`. |
| **Phase 1 Baseline Test Counts** | Run prior to Phase 2 edits (with `db` + `valkey` up): see Section 4 below — 100% passing. | Preserve 100% pass rate and compare again at N9. |
| **Phase 2 Dependency Licenses** | Checked via PyPI/npm metadata and `config/license-allowlist.yaml`: `segno==1.6.6` (BSD-3), `reportlab==5.1.2` (BSD), `pillow==13.0.0` (MIT-CMU, already installed), `zxing-cpp==3.2.0.post1` (Apache-2.0, dev test dep), `@dnd-kit/core@6.3.1` (MIT), `@dnd-kit/sortable@10.0.0` (MIT), `@dnd-kit/utilities@3.2.2` (MIT). | Zero GPL/AGPL/SSPL/BUSL/non-commercial dependencies. Run `python scripts/license_check.py` after adding deps. |

---

## 2. Spec & Repo Reconciliation Map

| Prompt / Earlier Doc Term | Unified Spec / Real Repo Counterpart | Decision |
|---|---|---|
| `P2-00`..`P2-15` doc IDs | `docs/phase2/README.md`, `00`..`12`, `consistency-report.md`, `UI/PHASE-2-ASSETS.md` (installed cleanly from `tablepulse-phase2-unified-spec/`) | Use unified `docs/phase2/` numbering (`FR-025`–`FR-040`, `API-024`–`API-035`, `SCR-017`–`SCR-022`). |
| `S-70`..`S-82` & `S-90`..`S-92` screen IDs | `SCR-017` (Tables), `SCR-018` (Menus & Categories), `SCR-019` (Item Editor Drawer), `SCR-020` (QR Manager & Print Center), `SCR-021` (Live Mobile Preview Modal), `SCR-022` (Customer Digital Menu `/m/[qrToken]`) | Build `SCR-017`–`SCR-022` using existing `tokens.css` & `globals.css` primitives. |
| Stages `N0`..`N9` | `N0` (`Stage 9a` Reconcile) -> `N1` (`Stage 9` DB/Migration) -> `N2` (RBAC/Flags) -> `N3` (`Stage 10` Tables) -> `N4` (`Stage 11` Media/Menu/QR API) -> `N5`–`N6` (`Stage 12` Tables/Menu/QR UI) -> `N7` (`Stage 13` Public API & `/m/[qrToken]`) -> `N8`–`N9` (`Stage 14` Hardening/E2E/Release) | Report both `N<k>` progress files (`docs/progress/N0.md`..`N9.md`) and unified stage coverage cleanly. |
| `ADMIN` role / total 6 roles | Real repo has **5** DB-constrained roles (`OWNER`, `MANAGER`, `HOST`, `STAFF`, `VIEWER`) + unauthenticated Public Diner (`API-035`) | Preserve exact 5 roles (`ck_users_role`) + add 8 capabilities in `packages/rbac/matrix.yaml` (21 -> 29 total capabilities; OWNER 29, MANAGER 23 + conditional, HOST 10 + 2 conditional, STAFF 6, VIEWER 5). |
| `002_phase2_tables_menu_qr.py` | Repo already has `0002_expand_camera_stream_types.py` | Name Phase 2 migration **`0003_phase2_tables_menu_qr.py`**. |
| Prompt routes `/admin/*` vs v1.0 `/venues/[venueId]/*` | v1.0 routes live under `/venues/[venueId]/...` (`settings/cameras`, `settings/alerts`, `floor`, `waitlist`, `analytics`) and `/org/*`; redirect alias pattern already used in `settings/page.tsx` and `tables/page.tsx` | Primary admin UI routes live at `/venues/[venueId]/settings/tables` (`SCR-017`), `/venues/[venueId]/menu` (`SCR-018`), `/venues/[venueId]/settings/qr-codes` (`SCR-020`); public customer menu lives at `/m/[qrToken]` (`SCR-022`). |
| Pre-existing working tree edits | `0002_expand_camera_stream_types.py`, `venues_cameras.py` (HLS/HTTP_MJPEG/RTMP + live MJPEG stream), `ssrf.py`, `AppShell.tsx` (`pb-28` + auth guard), route redirects (`tables/`, `cameras/`, `settings/page.tsx`) | Verified passing all 15 backend tests, ruff, mypy, pnpm typecheck/lint/test; committed in N0 as clean base before Phase 2. |

---

## 3. Consumer Grep Audit (`polygon_json`, `camera_id`, `floor_x`/`floor_y`, `DiningTable`)

| File / Symbol | Current Assumption / Behavior | Required Phase 2 Hardening (`N1` / `N3`) |
|---|---|---|
| `backend/app/db/models.py` (`DiningTable`) | `polygon_json` is `nullable=False` (`server_default='[]'::jsonb`). Missing `display_name`, `min_capacity`, `is_active`, `is_combinable`, `table_notes`, `sort_order`. | Alter `polygon_json` to `nullable=True`, add all 6 columns (`min_capacity >= 1`, `is_active`, etc.). |
| `backend/app/api/venues_cameras.py::list_internal_cv_cameras` (`/api/v1/internal/cv-cameras`) | Queries `DiningTable.deleted_at.is_(None)` and sends any table with `camera_id IS NOT NULL`, even if `polygon_json` is empty/NULL or `is_active=False`. | Filter strictly: `is_active == True`, `deleted_at.is_(None)`, `camera_id.is_not(None)`, `polygon_json.is_not(None)`, and `len(polygon_json) >= 3`. |
| `backend/app/api/venues_cameras.py::save_polygons` (`/polygons`) | Soft-deletes any table on that camera not present in submitted list (`existing_cam_ids - submitted_ids`), and checks `by_id`. | Preserve non-deleted tables that were merely unlinked from the camera OR let `save_polygons` support linking uncalibrated tables created in `SCR-017` without breaking unmonitored tables (`camera_id=None`, `polygon_json=None`). |
| `backend/app/api/floor_ops.py::build_floor_snapshot` (`/floor-state`) | Queries all `deleted_at.is_(None)` tables and includes every table in `total_tables`, `total_seats`, and `tables[]`. | Filter `is_active == True`; keep calibrated (`camera_id IS NOT NULL AND polygon_json IS NOT NULL`) tables in `tables` + KPIs, and return uncalibrated tables in `unmonitored_tables` (with `is_monitored: false`) so capacity KPI denominators stay accurate (`C3`). |
| `backend/app/api/waitlist_analytics.py::get_turnover_predictions` & `update_waitlist` | Queries `DiningTable.deleted_at.is_(None)`. | Add `DiningTable.is_active.is_(True)` so deactivated seasonal tables are never recommended for seating. |
| `cv-worker/app/main.py::_parse_camera_config` | Reads `t.get("polygon_json", [])`; assumes non-null list. | Filter/skip tables with `not t.get("polygon_json") or len(t["polygon_json"]) < 3` cleanly so null/partial polygons never crash CV worker. |
| `frontend/src/components/FloorCanvas.tsx` | Reads `tbl.floor_x` / `tbl.floor_y` directly (`0` defaults to `idx` grid layout). | Handle unmonitored badge / null `polygon_json` gracefully and merge `tables` + `unmonitored_tables` visually with `"Manual Mode"` indicator when `is_monitored === false`. |
| `frontend/src/components/PolygonEditorCanvas.tsx` & `SCR-013` | Assumes `tbl.polygon_json` is an array (`tbl.polygon_json.map`). | Guard `(tbl.polygon_json ?? []).map(...)` and show unmapped active tables (`camera_id === null` or `polygon_json === null`) in `SCR-013` sidebar for 1-click camera binding. |

---

## 4. Phase 1 Baseline Test Counts (Measured 2026-11-26 Prior to Phase 2 Code)

| Suite | Command | Result |
|---|---|---|
| **License & Privacy Gate** | `python scripts/license_check.py` | **PASS** (0 prohibited packages or licenses) |
| **Backend Lint & Format & Strict Types** | `cd backend && uv run ruff check . && uv run mypy --strict app` | **PASS** (All checks passed; 33 source files clean) |
| **Backend Integration + DB + RLS Tests** | `cd backend && uv run pytest -v` (with PG16 + Valkey dev containers) | **15 passed, 0 failed** (`test_auth_and_rbac`: 6, `test_cameras_and_polygons`: 2, `test_floor_and_ops`: 3, `test_schema_and_rls`: 4) |
| **CV Worker Unit Tests** | `cd cv-worker && uv run pytest -v` | **4 passed, 0 failed** |
| **ML Gate Unit Tests** | `cd ml && uv run pytest -q` | **4 passed, 0 failed** |
| **Frontend Typecheck, Lint & Unit Tests** | `cd frontend && pnpm typecheck && pnpm lint && pnpm test` | **PASS** (`tsc --noEmit`: 0 errors; `eslint`: 0 errors, 1 pre-existing warning in `TableDetailDrawer.tsx:101`; `vitest`: **4 passed**) |
| **Frontend E2E Playwright Suite** | `frontend/e2e/tablepulse.spec.ts` | Baseline 1 full end-to-end journey test present (re-verified alongside new Phase 2 E2E tests once full stack is built at N8/N9) |
