# TablePulse Phase 2 — Implementation Roadmap & Autonomous Agent Build Plan

## Quick Reference
- **Prerequisite**: TablePulse v1.0 (`Stage 0`–`Stage 8`) is completed and passing CI.
- **Execution Order**: 7 sequential, verifiable stages (`Stage 9a` reconciliation + `Stage 9`–`Stage 14`), pausing for human review after each stage (never run non-stop without review) designed for **Antigravity** (or Claude Code / Cursor). Execute **one stage at a time**, run verification + direct DB checks, and confirm before advancing.
- **UI Assets Rule**: Before executing `Stage 12` and `Stage 13`, generate visual reference mockups from `09-ui-screens-phase2.md` (using `[Placeholder]` tokens and v1.0 Liquid Glass tokens) and place them in ``UI/PHASE-2-ASSETS.md` (`UI/SCR-017-*.png` through `UI/SCR-022-*.png`).

---

## 1. Staged Implementation Roadmap (`Stage 9`–`Stage 14`)

### Stage 9a — Baseline Reconciliation & Repo Verification (`P0`, Mandatory First Step)
- **Depends On**: Implemented TablePulse v1.0 repository.
- **Deliverables**:
  - Execute every checkbox in `docs/phase2/00-baseline-reconciliation.md` §2 against the actual repo.
  - Grep all consumers of `tables.polygon_json`, `tables.camera_id`, and `tables.floor_x/floor_y` across `backend/`, `cv-worker/`, and `frontend/`.
  - Record exact Phase 1 test baseline counts and verify licenses of new dependencies (`segno`, `reportlab`, `Pillow`, `@dnd-kit/*`, `zxing-cpp`/`pyzbar`) via `scripts/license_check.py`.
  - Write `docs/phase2/N0-reconciliation.md` with any real-repo name mappings.
- **Verification**: `docs/phase2/N0-reconciliation.md` committed; Phase 1 test suite 100% green before any Phase 2 code is written. Stop and ask human if the repo contradicts a core assumption (missing Alembic, missing RLS, or incompatible license).

### Stage 9 — Phase 2 Database Migration, Models & QR Backfill (`P0`)
- **Depends On**: v1.0 `Stage 1`–`Stage 8`.
- **Deliverables**:
  - Alembic migration `002_phase2_tables_menu_qr.py`: additive columns on `venues` & `tables`, 6 new tables (`table_qr_codes`, `menus`, `menu_categories`, `menu_items`, `menu_media_assets`, `qr_scan_daily_stats`), indexes, PostgreSQL RLS policies, and automatic 128-bit QR token backfill for all existing non-deleted v1.0 tables.
  - SQLAlchemy 2.0 async models, Pydantic v2 schemas, `tablepulse_public` read-only DB role + 2 public SQL views, and null-geometry hardening on every consumer identified in Stage 9a.
  - Add permissive dependencies (`segno`, `reportlab`, `Pillow`) to `backend/pyproject.toml`; add `MENU_MEDIA_DIR` to `.env.example` and `docker-compose.yml` volume + Caddy static route (`/media/menu/*`).
- **Verification**: `alembic upgrade head` on a DB seeded with v1.0 tables succeeds; `pytest backend/tests/test_phase2_schema.py` confirms all 6 tables, constraints, RLS isolation, and 100% QR backfill; `pip-licenses` confirms zero GPL/AGPL packages.

### Stage 10 — Advanced Table Management & QR Code Backend (`FR-025`–`FR-028`, `FR-034`–`FR-036`) (`P0`)
- **Depends On**: `Stage 9`.
- **Deliverables**:
  - `API-024`, `API-025`: Individual & bulk table CRUD, optimistic locking (`version`), active-session delete guard (`409 TABLE_IN_USE`), auto-QR provisioning, `audit_logs` writes, and Valkey Pub/Sub sync to `SCR-005` & `cv-worker`.
  - `API-032`, `API-033`, `API-034`: QR listing, atomic QR regeneration (revokes old token + evicts Valkey cache), offline SVG/PNG generation (`segno`), and batch printable PDF tent-card export (`reportlab`, capped at 100 tables).
  - RBAC matrix updates (`packages/rbac/matrix.yaml` if present + FastAPI `require_venue_role` guards).
- **Verification**: `pytest backend/tests/test_phase2_tables_qr.py` verifies valid CRUD, direct SQL checks on `tables` & `table_qr_codes` & `audit_logs`, collision `409`s, RBAC `403`s for `HOST`/`STAFF`/`VIEWER`, and valid SVG/PNG/PDF binary signatures.

### Stage 11 — Menu Management, Validated Media Pipeline & Public QR API (`FR-029`–`FR-033`, `FR-037`–`FR-040`) (`P0`)
- **Depends On**: `Stage 10`.
- **Deliverables**:
  - `API-026`–`API-030`: Menus (with `schedule_json` evaluator), ordered categories, menu items (minor-unit pricing, dietary/allergen tags, duplicate, reorder), venue menu settings, and fast 1-tap/bulk availability ("Quick 86").
  - `API-031`: Server-side validated image upload (5 MB max, magic-byte check, decompression bomb guard, EXIF strip, WebP full + 320px thumb).
  - `API-035`: Public unauthenticated `GET /api/v1/public/menu/{qr_token}` with strict whitelisted `PublicMenuResponse`, Valkey 60s cache + immediate invalidation on writes, ETag/304, IP rate limits (`429`), `404`/`410` lifecycle states, and async privacy-safe scan counter (`qr_scan_daily_stats`).
- **Verification**: `pytest backend/tests/test_phase2_menu_public.py` verifies full menu CRUD, SVG/polyglot upload rejection (`400`), cache invalidation `< 1s` on Quick-86 and QR regen, zero leaked private fields on `API-035`, and Valkey-down graceful fallback.

### Stage 12 — Admin Frontend Screens: Tables, Menu & QR Print Center (`SCR-017`–`SCR-021`) (`P0`)
- **Depends On**: `Stage 10`, `Stage 11`, and `UI/SCR-017..021` assets.
- **Deliverables**:
  - Add role-gated navigation entries (`Menu`, `Tables`, `QR Codes`) to v1.0 Left Rail without altering `SCR-001`–`SCR-016`.
  - Build `SCR-017` (Table Management + Bulk Add), `SCR-018` (Menu & Category Management + Quick-86 + keyboard reorder), `SCR-019` (Menu Item Editor Drawer + image uploader), `SCR-020` (QR Manager + SVG/PNG/PDF downloads + Regenerate modal), and `SCR-021` (Live Mobile Preview Modal).
  - Sync `SCR-013` Polygon Editor sidebar to list uncalibrated tables created in `SCR-017`.
- **Verification**: `pnpm typecheck && pnpm test` passes; every async action has Loading, Error, and Success states; direct-URL navigation works on all 5 routes; visual alignment verified against `UI/` assets.

### Stage 13 — Public Customer Digital Menu (`SCR-022`, `/m/:qrToken`) (`P0`)
- **Depends On**: `Stage 11`, and `UI/SCR-022` asset.
- **Deliverables**:
  - Isolated Next.js `(public)/m/[qrToken]` route group (zero admin imports, zero auth cookies, zero `/login` links).
  - Mobile-first Liquid Glass menu UI: Venue header + Table badge, sticky menu switcher/search/dietary chips/category scroll-spy, lazy-loaded WebP item cards, Item Detail bottom sheet with allergens, and clean `404` / `410` (revoked/unavailable) / unpublished states.
- **Verification**: `Playwright` tests at 375px/768px/1280px verify search, dietary filters, item bottom sheet, `410` revoked state, zero admin links in DOM, FCP `< 1.5s`, and 0 `axe-core` critical/serious violations.

### Stage 14 — End-to-End Integration, Regression & Release Hardening (`P0`)
- **Depends On**: `Stage 12`, `Stage 13`.
- **Deliverables**: Full E2E Playwright suite covering cross-module flows (Table -> QR -> Menu Edit -> Public Scan -> QR Regen), weekly orphan-media cleanup job, updated `docs/api-reference.md`, and complete v1.0 + Phase 2 regression run.
- **Verification**: 100% of v1.0 (`Stage 0`–`Stage 8`) + Phase 2 (`Stage 9`–`Stage 14`) tests pass; `gitleaks` & license checks green; clean `docker compose up -d` verified.

---

## 2. Standing Agent Rules & Stop Conditions (Inherited + Phase 2 Additions)
- **Never Overwrite v1.0 Docs**: All Phase 2 docs live in `docs/phase2/` (never overwrite v1.0 specs).
- **Stop & Ask Human** if a step requires: adding customer ordering/cart/payment logic (`DEFERRED`), using a non-permissive (GPL/AGPL) QR/PDF library, exposing any internal table/camera field on `API-035`, disabling image magic-byte validation, or weakening any failing test.

---

## 3. Copy-Paste Antigravity Execution Prompt (Per Stage)
```text
Read docs/phase2/README.md, docs/phase2/12-phase2-build-roadmap.md, and the relevant Phase 2 spec files for Stage {N}.
Do not rebuild or break existing v1.0 features. Inspect UI/ for SCR-017..SCR-022 assets if building frontend screens.
Implement Stage {N} completely following all standing conventions, RBAC checks, and error/loading/success UI states.
Run the exact verification commands, verify database state directly via SQL for all writes, test bad inputs (400/401/403/404/409/410/413), and loop fix -> re-test until 100% pass.
Write your stage report to `docs/progress/S{N}.md` containing: (1) files created/changed, (2) exact commands & outputs, (3) FR/API/SCR IDs covered, (4) deviations/open items, (5) stop-list confirmation — then STOP for human review before starting the next stage.
```


---

## 4. Safe Rollout & Rollback Plan (Ported from P2-14 §7)
1. **Backup First**: Snapshot PostgreSQL before running `002_phase2_tables_menu_qr.py`.
2. **Deploy With Feature Flags Off**: Deploy Phase 2 containers with `TABLE_ADVANCED_ENABLED=false`, `QR_ENABLED=false`, `PUBLIC_MENU_ENABLED=false`, `MENU_IMAGES_ENABLED=false`. This guarantees Phase 1 image rollback stays safe while verifying health.
3. **Enable Sequentially Per Venue**: Turn on `TABLE_ADVANCED_ENABLED` -> `MENU_IMAGES_ENABLED` -> `QR_ENABLED` -> `PUBLIC_MENU_ENABLED` after smoke tests pass.
4. **Before Printing Physical QR Stickers**: Verify `PUBLIC_APP_URL` is set to the final production `https://` domain and test-scan a printed proof on both iOS and Android phones.
5. **Backup Scope Update**: Include `MENU_MEDIA_DIR` alongside PostgreSQL dumps in nightly backups.
