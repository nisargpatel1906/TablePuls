# TablePulse Phase 2 — Baseline Reconciliation & Conflict Resolutions (`Stage 9a`)

> **Quick reference**
> - Phase 2 **extends** your implemented **TablePulse v1.0** repository without rebuilding or modifying Phase 1 features.
> - **Mandatory Rule (Stage 9a / N0):** Before writing any migration or application code, the coding agent MUST inspect the actual repository and verify every checkbox in §2 against real code. **The real repository always wins over doc assumptions.** Record actual table names, permission strings, env var prefixes, and baseline Phase 1 test counts in `docs/phase2/N0-reconciliation.md`.

---

## 1. Phase-1-to-Phase-2 Conflicts & Exact Resolutions (`C1`–`C5`)

| ID | Phase 1 Design Fact | Why It Conflicts With Phase 2 | Resolution in Phase 2 |
|---|---|---|---|
| **C1** | `tables.polygon_json` is `NOT NULL` and tied to camera calibration (`SCR-013`). | Restaurants must be able to create tables (and print QRs) **without CCTV** or before calibrating cameras. | Alter `tables.polygon_json` to nullable, default `floor_x`/`floor_y` to `0.0`, add `is_active`; `cv-worker` filters strictly to `camera_id IS NOT NULL AND polygon_json IS NOT NULL AND is_active = true AND deleted_at IS NULL`. |
| **C2** | `UNIQUE (venue_id, table_code) WHERE deleted_at IS NULL` + active tables with history should not be hard-deleted. | Deactivating/archiving a table (e.g., `T05`) should allow reusing `T05` if retired, while preserving historical sessions. | Keep soft-delete (`deleted_at`) for permanent removal (blocked with `409 TABLE_IN_USE` if currently `OCCUPIED`/`NEEDS_SERVICE`/`NEEDS_CLEANING` unless `?force=true`) and `is_active=false` for temporary seasonal hide. |
| **C3** | `GET /api/v1/venues/{v}/floor-state` and KPI HUD assume every active table has a vision occupancy state. | Unmonitored/uncalibrated tables (no camera/polygon) have no vision state and would distort `Floor Capacity %`. | Return uncalibrated active tables in an additive `unmonitored_tables` array on `/floor-state` (or flag `is_monitored: false`) so v1.0 occupancy KPIs exclude them unless manually overridden. |
| **C4** | Phase 1 has **no money fields, no user media uploads, and no unauthenticated public surface**; all routes require JWT auth. | Menus require currency-safe pricing, food photo uploads, and anonymous diner QR access. | Introduce `price_minor_units` (`BIGINT`) + ISO-4217 `currency_code`, a server-validated Pillow WebP upload pipeline, and an explicit `policy="public"` route class backed by read-only DB role `tablepulse_public`. |
| **C5** | Phase 1 non-goals explicitly exclude POS, customer ordering, carts, and payments. | Digital menus can tempt scope creep into ordering/checkout. | Customer digital menu (`SCR-022`) stays strictly **read-only**. Ordering/cart/payments remain `DEFERRED` to Phase 3 (and Phase 3 must NOT rely on a static table QR alone to authorize orders). |

---

## 2. Mandatory Repo Verification Checklist (Complete in Stage 9a)

Before executing Stage 9, the agent must verify each item in the actual repository and write `docs/phase2/N0-reconciliation.md`:
- [ ] Confirm actual PostgreSQL schema & Alembic revision head (`alembic current`), verifying exact column names on `venues`, `tables`, `audit_logs`, and `system_settings`.
- [ ] Confirm RBAC implementation (`packages/rbac/matrix.yaml` vs. FastAPI `require_venue_role` dependencies) and verify exact role names (`OWNER`, `MANAGER`, `HOST`, `STAFF`, `VIEWER`).
- [ ] Confirm route-policy registry / completeness test (if present) and how a `public` unauthenticated route marker is registered.
- [ ] Grep **every** consumer of `tables.polygon_json`, `tables.camera_id`, and `tables.floor_x/floor_y` across `backend/`, `cv-worker/`, and `frontend/` (`SCR-005`, `SCR-013`) and list every place requiring null-safety hardening.
- [ ] Confirm cache/broker service name (`valkey` vs. `redis`), `docker-compose.yml` volumes, Caddyfile routes, and `.env.example` variable names (`PUBLIC_APP_URL`, `ALLOWED_ORIGINS`).
- [ ] Run the full Phase 1 test suite (`pytest`, `pnpm typecheck`, `pnpm test`, Playwright smoke) and record exact baseline pass counts so Stage 14 can prove zero regression.
- [ ] Verify licenses and latest stable versions of Phase 2 dependencies (`segno`, `reportlab`, `Pillow`, `dnd-kit`, `zxing-cpp`/`pyzbar` dev test dep) via `scripts/license_check.py`.
