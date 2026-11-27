# TablePulse — Complete Specification vs. Implementation Gap Audit (`Part A`)

> **Date:** 2026-11-27  
> **Baseline Commit:** `98f3e21` (`main`)  
> **Run 27 Context:** [FINAL_QA_REPORT.md](../qa-evidence/FINAL_QA_REPORT.md) & [TEST_PLAN.md](../qa/TEST_PLAN.md)  
> **Statuses Used:**
> - `implemented` — Requirement built end-to-end (DB + API + UI + tests) and matches spec.
> - `partial` — Core path exists, but specific acceptance criteria, UI controls, edge cases, or policy toggles are incomplete.
> - `missing` — Specified or required feature absent from codebase; scheduled for Part B build.
> - `differs-from-docs` — Intentional repository architectural/naming choice documented and reconciled cleanly (see Section 1).

---

## 1. Intentional Differences & Spec Reconciliation (`differs-from-docs`)

| Topic | Prompt / Early Template Term | Real Repository Implementation (`Wins`) | Decision / Disposition |
|---|---|---|---|
| **Phase 2 Doc & Requirement Numbering** | `P2-00`…`P2-16`, `FR-T`/`FR-M`/`FR-Q`/`FR-CM`, `S-70`…`S-92` | `docs/phase2/00`…`12`, `FR-025`–`FR-040`, `SCR-017`–`SCR-022`, `API-024`–`API-035` ([N0-reconciliation.md](phase2/N0-reconciliation.md)) | **differs-from-docs (reconciled)** — Preserve unified `docs/phase2/` IDs; cross-referenced in tables below. |
| **Role Names & Count** | `owner, admin, manager, host, analyst, viewer` | 5 canonical DB-enforced roles (`ck_users_role`) in [packages/rbac/matrix.yaml](../packages/rbac/matrix.yaml) & [models.py](../backend/app/db/models.py#L106-L114): `OWNER`, `MANAGER`, `HOST`, `STAFF`, `VIEWER` | **differs-from-docs (reconciled + enhanced)** — `OWNER` covers org owner + org admin; `MANAGER` covers venue admin/manager; `STAFF` covers servers/bussers; `VIEWER` covers read-only analyst (`01-prd.md` §3). Add explicit org policy flags (`managers_can_manage_tables`, `managers_can_manage_menu`, `admins_can_manage_tables`, `admins_can_manage_menu`, `require_2fa_roles`) in `system_settings` so delegation policies work on the canonical roles. |
| **Admin UI Routes** | `/admin/*`, `/setup` | Next.js 15 App Router routes: `/register?bootstrap=true`, `/onboarding`, `/venues/[venueId]/settings/tables`, `/venues/[venueId]/menu`, `/venues/[venueId]/settings/qr-codes`, `/org/users`, `/org/system`, `/m/[qrToken]` | **differs-from-docs (reconciled)** — Intentional v1.0/Phase-2 route hierarchy (`docs/02-ui-screens.md` & `docs/phase2/09-ui-screens-phase2.md`). |
| **Public Customer GET API** | 4 separate public GET routes | Consolidated read-only endpoint `GET /api/v1/public/menu/{qr_token}` (`API-035`) + immutable `GET /media/menu/{venue_id}/{filename}` (`API-031`) + `GET /api/v1/health`, `/api/v1/auth/bootstrap-status`, `/api/v1/auth/invite-info` | **differs-from-docs (reconciled)** — Preserves single `API-035` contract and strict `policy="public"` route-completeness allowlist (`test_auth_and_rbac.py`). Lazy category chunking will use query parameters on `GET /api/v1/public/menu/{qr_token}` rather than proliferating unauthenticated endpoints. |
| **Phase 2 Migration Sequence** | `002_phase2_tables_menu_qr.py` | Repo already had `0001_initial_schema.py` & `0002_expand_camera_stream_types.py`; Phase 2 landed in `0003_phase2_tables_menu_qr.py` | **differs-from-docs (reconciled)** — Part B schema additions will land in reversible `0004_gaps_2fa_sku_policies_i18n.py`. |
| **Telemetry DB Extension** | Earlier notes mentioned TimescaleDB | PostgreSQL 16+ native monthly range partitioning on `occupancy_snapshots` (no TSL dependency) | **differs-from-docs (reconciled)** — Strict Apache-2.0 / OSI license policy (`AGENTS.md`). |

---

## 2. Phase 1 Functional Requirements (`FR-001`–`FR-024`)

| ID | Requirement Summary | Status | Evidence (Repo Files) | Gaps / Part B Action |
|---|---|---|---|---|
| `FR-001` | First-run `OWNER` bootstrap & onboarding (`SCR-002`, `SCR-004`) | `implemented` | `backend/app/api/auth.py` (`/bootstrap`, advisory lock), `frontend/src/app/register/page.tsx`, `frontend/src/app/onboarding/page.tsx` | Verify cleanly in clean-install Run 28+ browser test. |
| `FR-002` | Email/password Auth, JWT in memory, HttpOnly refresh rotation, rate limits, **TOTP 2FA** | **partial** | `auth.py` (`/login`, `/refresh`, `/logout`), `security.py` (`Argon2id`, `verify_totp`), `models.py` (`totp_secret_encrypted`, `totp_enabled`) | **MISSING full TOTP 2FA lifecycle:** `/auth/2fa/enroll` (QR SVG + manual Base32 secret), `/auth/2fa/verify-enroll`, login challenge-token step `/auth/2fa/verify`, Argon2id-hashed single-use recovery codes + regeneration, `/auth/2fa/disable` (re-auth + blocked if org policy requires 2FA), UI challenge & self-service security settings (`SCR-001` + `/account/security`). |
| `FR-003` | Invites, password reset, min-12 password policy | **partial** | `auth.py` (`/forgot-password`, `/reset-password`, `/invite-info`, `/accept-invite`), `org_users.py` (`/users/invite`), `email.py` | **Bug & Infra Gap:** `org_users.py::invite_user` does **not** call `send_email_if_configured(...)`; `docker-compose.yml` lacks Mailpit (`dev`/`qa` profile). Fix `invite_user` to email invites when SMTP is configured & add opt-in Mailpit service. |
| `FR-004` | RTSP/RTSPS/Demo MP4 cameras, AES-256-GCM creds, test connection | `implemented` | `venues_cameras.py`, `ssrf.py`, `0002_expand_camera_stream_types.py`, `settings/cameras/page.tsx` | None; verify via browser & API tests. |
| `FR-005` | Interactive table polygon & ROI calibration, exclusion zones | `implemented` | `venues_cameras.py` (`/polygons`), `geometry.py`, `PolygonEditorCanvas.tsx`, `calibrate/page.tsx` | None. |
| `FR-006` | Real-time CV occupancy & guest counting (RF-DETR + ByteTrack) | **partial (runtime test pending footage)** | `cv-worker/`, `realtime.py`, `floor_ops.py` | Unit tests pass; E2E state transition test requires a `>= 2 min` fixed elevated restaurant footage clip (`qa-evidence/footage/` clips are `6.92s–19.37s`). Search CC archives in Part C or mark state-transition video TC `BLOCKED` if none exists. |
| `FR-007` | Dwell & service timers (`occupied_since`, `last_staff_visit_at`) | `implemented` | `floor_ops.py`, `FloorCanvas.tsx`, `TableDetailDrawer.tsx` | None. |
| `FR-008` | Unattended table service alerts (`UNATTENDED_TABLE`) | `implemented` | `realtime.py`, `floor_ops.py`, `alerts/page.tsx`, `webhooks.py` | None. |
| `FR-009` | Dirty / needs-cleaning alerts (`NEEDS_CLEANING`) | `implemented` | `realtime.py`, `floor_ops.py`, `alerts/page.tsx` | None. |
| `FR-010` | Low-confidence / offline `UNKNOWN` fallback | `implemented` | `floor_ops.py`, `TableStateBadge.tsx`, `ml-review/page.tsx` | None. |
| `FR-011` | Live floor map, WS + 5s polling fallback | `implemented` | `floor/page.tsx`, `useVenueRealtime.ts`, `realtime.py` | None. |
| `FR-012` | Live camera wall with overlays & face blur | `implemented` | `cameras/live/page.tsx`, `venues_cameras.py` (`live-mjpeg`, `/media-auth`), `privacy.py` | None. |
| `FR-013` | Manual table overrides + immutable audit log | `implemented` | `floor_ops.py` (`/override`), `TableDetailDrawer.tsx`, `audit.py` | None. |
| `FR-014` | Waitlist management & turnover ETA predictions | `implemented` | `waitlist_analytics.py`, `waitlist/page.tsx` | None. |
| `FR-015` | Peak hours, heatmap, staffing analytics & CSV export | `implemented` | `waitlist_analytics.py` (`/analytics/peak-hours`), `analytics/page.tsx` | None. |
| `FR-016` | Alert rules & SSRF-protected HMAC webhooks | `implemented` | `admin_ops.py`, `webhooks.py`, `ssrf.py`, `settings/alerts/page.tsx` | None. |
| `FR-017` | ML human-review queue & anonymized zip export | `implemented` | `admin_ops.py` (`/ml-review`), `ml-review/page.tsx` | None. |
| `FR-018` | Multi-venue, 5-role RBAC, Last-Owner protection, audit log | `implemented` | `packages/rbac/matrix.yaml`, `core/rbac.py`, `org_users.py`, `org/users/page.tsx` | Extend with org-level policy flags & `create-org` CLI. |
| `FR-019` | Privacy defaults, face blur, snapshot retention & purge | `implemented` | `admin_ops.py`, `core/privacy.py`, `org/system/page.tsx` | None. |
| `FR-020` | Global AI kill switch (fail-closed) | `implemented` | `admin_ops.py`, `valkey_client.py`, `cv-worker/`, `org/system/page.tsx` | None. |
| `FR-021` | Model registry, honesty rule (`NOT_MEASURED`), gate status | `implemented` | `admin_ops.py`, `ml/evaluate_gate.py`, `org/system/page.tsx` | None. |
| `FR-022` | Search, filtering & pagination (`page`, `page_size`) | `implemented` | `org_users.py`, `floor_ops.py`, `admin_ops.py`, `tables_admin.py` | None. |
| `FR-023` | Accessibility Compliance | **partial** | `frontend/e2e/phase2.spec.ts` runs `withTags(["wcag2a", "wcag2aa"])` | Upgrade Playwright & automated checks to **`wcag22aa`** (WCAG 2.2 AA), enforce `>=44x44px` touch targets on all buttons/switches (`AppShell` nav links, Quick-86 badges, table action buttons, QR action buttons), verify 0 serious/critical axe issues at 200% zoom & large font. |
| `FR-024` | Responsive multi-device support | `implemented` | Tailwind responsive layouts + `assertNoHorizontalOverflow` | Expand browser verification across all 15 viewports (`320`–`1920`), `200%` zoom, and visual `browser` subagent audit. |

---

## 3. Phase 2 Functional Requirements & Should Items (`FR-025`–`FR-040` / `FR-T`/`FR-M`/`FR-Q`/`FR-CM`)

| ID / Domain | Requirement & Should Item | Status | Evidence (Repo Files) | Gaps / Part B Action |
|---|---|---|---|---|
| `FR-025` / `FR-T` | Individual table CRUD, optimistic locking, unmonitored tables | `implemented` | `tables_admin.py` (`API-024`), `settings/tables/page.tsx` | Add optional **Duplicate Table**, **Archived Tables list + Restore** (new code if taken per `E-05`), and **Permanent Purge** (`409 TABLE_HAS_HISTORY` per `E-07`). |
| `FR-026` / `FR-T` | Bulk table add (`1–50`), bulk section/active updates | **partial** | `tables_admin.py` (`/tables/bulk`), `settings/tables/page.tsx` | Bulk bar lacks `Download QRs PDF` shortcut specified in `09-ui-screens-phase2.md` §2 (`SCR-017`) and bulk delete/archive action. |
| `FR-027` / `FR-T` | Safe deactivation & soft-delete (`409 TABLE_IN_USE` + `?force=true`) | `implemented` | `tables_admin.py` (lines 688–796), `settings/tables/page.tsx` | Add `restore` (with code collision handling) & `purge` (blocked on history) UI + API. |
| `FR-028` / `FR-T` | Sync tables with `SCR-005`, `SCR-013`, and `cv-worker` | `implemented` | `floor_ops.py` (`unmonitored_tables`), `calibrate/page.tsx`, `cv-worker` | None. |
| `FR-029` / `FR-M` | Multi-menu CRUD, Draft/Published/Archived, time-of-day schedules, org/venue settings | **partial** | `menus_admin.py` (`API-026`, `API-027`), `menu_schedule.py`, `menu/page.tsx` | Add **Duplicate Menu** (`POST /menus/{m}/duplicate`), **EN/HI translations** (`translations_json` on menus/categories/items + UI inputs), and **Org policy flags** (`managers_can_manage_menu`, etc.). |
| `FR-030` / `FR-M` | Menu category CRUD, atomic drag+keyboard reorder, non-empty guard | `implemented` | `menus_admin.py` (`API-028`), `menu/page.tsx` (`@dnd-kit`) | Add `hi` translation inputs in Category Modal. |
| `FR-031` / `FR-M` | Menu items CRUD, minor units, dietary/allergen tags, duplicate, **variants**, **CSV import/export** | **partial** | `menus_admin.py` (`API-029`), `MenuItemDrawer.tsx`, `schemas/menus_qr.py` | **MISSING:** (1) **`sku`** column on `menu_items` (`0004_*`), (2) **Menu CSV Import** (`import-template`, `import/preview` <=2MB/<=2000 rows + 15m expiry `410 IMPORT_EXPIRED`, `import/commit` `all_or_nothing`/`skip_invalid` + `create_only`/`upsert_by_sku`), (3) round-trip CSV export including `sku`/all item fields, (4) bulk item delete/move category, (5) `hi` item translations. |
| `FR-032` / `FR-M` | Validated WebP image pipeline (5 MB, magic bytes, EXIF strip, 800/320, SHA-256 dedup, orphan GC) | `implemented` | `services/media.py`, `menus_admin.py` (`API-031`), `MenuItemDrawer.tsx` | None. |
| `FR-033` / `FR-M` | Quick-86 availability toggle, bulk availability, **`unavailable_until` auto-restore**, **Mobile Preview (`SCR-021`)** | **partial** | `menus_admin.py`, `public_menu.py` (`eff_available`), `MenuPreviewModal.tsx`, `menu/page.tsx` | **MISSING UI + Admin Read Sync for `unavailable_until`:** Backend DB/public route supports `unavailable_until`, but neither `menu/page.tsx` nor `MenuItemDrawer.tsx` exposes UI presets/datetime picker for `unavailable_until`, and `list_menu_items` returns raw `r.is_available` instead of applying read-time auto-restore (`_effective_available`). |
| `FR-034` / `FR-Q` | 128-bit CSPRNG QR generation + backfill + `PUBLIC_APP_URL` only | `implemented` | `qr_export.py::build_qr_url`, `tables_admin.py`, `0003_phase2_tables_menu_qr.py` | None (`Host` header is never used). |
| `FR-035` / `FR-Q` | QR regenerate + grace period (`0–30d`) + end-grace + preview link | `implemented` | `qr_admin.py` (`API-033`), `settings/qr-codes/page.tsx` | None. |
| `FR-036` / `FR-Q` | QR downloads (`SVG`, `PNG`, batch `PDF`) + **A6 / sticker / ZIP downloads** + **QR scan stats** | **partial** | `qr_export.py`, `qr_admin.py` (`API-034`), `settings/qr-codes/page.tsx` | **MISSING:** `A6` single-card PDF layout (`A6_1UP`), sticker sheet PDF layout (`A4_STICKER_12UP`), batch **ZIP** download (`POST .../qr/export-zip`), and aggregate scan trends endpoint (`GET .../qr-codes/stats`) + chart/summary UI in `SCR-020`. |
| `FR-037` / `FR-CM` | Public digital menu `/m/:qrToken`, zero cookies/storage, strict headers & isolation | **partial** | `public_menu.py`, `ClientProviders.tsx`, `PublicDigitalMenu.tsx`, `infra/caddy/Caddyfile` | **Gaps in `public_menu.py`:** (1) Rate limit uses `request.client.host` instead of trusted `X-Forwarded-For` behind Caddy; (2) Invalid tokens don't short-circuit `^[A-Za-z0-9_-]{22}$` before hitting DB (`10-security` §2); (3) Verify direct `next` headers too (not only Caddy) for `/m/*` security headers. |
| `FR-038` / `FR-CM` | Customer menu search, dietary filters, category pills, bottom sheet, **EN/HI dish copy**, **large-menu lazy loading** | **partial** | `PublicDigitalMenu.tsx` | **MISSING:** (1) Localized dish/category/menu names & descriptions when customer selects `HI` (`translations_json.hi`), (2) Lazy / paginated item loading (`> 200` items or `> 400 KB` payload per `E-24`) in `public_menu.py` + progressive loading in `PublicDigitalMenu.tsx` & `SCR-018`. |
| `FR-039` / `FR-CM` | Revoked (`410`), unavailable table (`410`), invalid token (`404`), disabled/no-menu (`200`), DB down stale (`X-Stale: 1` / `503`) | `implemented` | `public_menu.py`, `PublicDigitalMenu.tsx` | Explicitly cover every state in automated QA cases. |
| `FR-040` / `FR-CM` | Privacy-safe daily scan telemetry & Valkey invalidation | `implemented` | `public_menu.py`, `QrScanDailyStat` | Enhance `SCR-020` visualization with aggregate stats chart/breakdown (`API-032` extension). |

---

## 4. Infrastructure, Admin CLI, Security & Test Data Gaps

| Category | Item | Status | Evidence | Part B Action |
|---|---|---|---|---|
| **Admin CLI** | `create-org` command (plus `revoke-all`, `rotate-keys`, `backup`, `restore`) | **missing** | `backend/app/cli.py` (has only the latter 4) | Add `tablepulse admin create-org` (non-interactive options + idempotent/validation checks + `audit_logs` write) and unit/integration tests. |
| **Mail Path** | Local SMTP dev/QA inbox (Mailpit) + real invite/reset email dispatch | **missing / partial** | `docker-compose.yml` lacks Mailpit; `org_users.py::invite_user` skips `send_email_if_configured` | Add `mailpit` (`axllent/mailpit`, MIT, `profiles: ["dev", "demo", "qa"]` — disabled in default prod), wire `invite_user` to `send_email_if_configured`, document in `.env.example` & `docs/runbooks/README.md`. |
| **Org Policy Flags** | `require_2fa_roles`, `managers_can_manage_tables`, `managers_can_manage_menu` (+ `admins_can_manage_*`) | **missing** | `SystemSetting` in `models.py` + `admin_ops.py` + `org/system/page.tsx` | Add columns via `0004_*` migration, enforce in `require_venue_role` (`403 POLICY_DISABLED` per `E-38`) & login (`2FA enrollment required`), expose in `/api/v1/auth/me` + `/api/v1/org/system` UI. |
| **Accessibility** | WCAG 2.2 AA (`wcag22aa`, >=44px target sizes, focus visibility) | **partial** | `phase2.spec.ts` checks `wcag2a`, `wcag2aa` only; several `<button>`/<Link> below 44px | Update E2E axe checks to `wcag22aa`, fix all small touch targets (`AppShell.tsx`, `menu/page.tsx`, `qr-codes/page.tsx`, `tables/page.tsx`), confirm 0 serious/critical issues across Light/Dark & EN/HI. |
| **Test Menu Media (`qa-evidence/media/`)** | 65 Wikimedia menu images provenance & visual match audit | **defective (needs full cleanup)** | `qa-evidence/data-sources.md` | Confirmed bad mappings (`hara_bhara_kabab.jpg` -> Chicken Seekh Kebab; `filter_coffee.jpg` -> disassembled empty filter; `mango_lassi.jpg` -> branded "Costco treats"; `kokum_sharbat.jpg` -> raw fruit/seeds; `thandai.jpg` -> Bhang label; `cold_coffee.jpg` -> Author `Unknown`). Inspect **all 65 photos visually via `read_file`**, replace all mismatched/branded/unattributed items with verified clean Wikimedia photos, and update `data-sources.md` & `media-manifest.json`. |
| **QA Evidence Hygiene** | Synthetic emails & footage duration check | **partial / blocker check** | `qa-evidence/FINAL_QA_REPORT.md` uses `@malabarspice.in`, `@decanchai.in`; `qa-evidence/footage/` clips are `6.92s–19.37s` | Scrub all non-`example.com` emails from `FINAL_QA_REPORT.md` & `TEST_PLAN.md`; search Wikimedia/CC sources for a `>= 2 min` fixed elevated restaurant clip or mark camera state-transition video cases `BLOCKED` cleanly. |
