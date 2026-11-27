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
| `FR-002` | Email/password Auth, JWT in memory, HttpOnly refresh rotation, rate limits, **TOTP 2FA** | `implemented` (Part B) | `auth.py` (`/2fa/enroll`, `/2fa/verify-enroll`, `/2fa/verify`, `/2fa/disable`, `/2fa/recovery-codes`), `security.py`, `login/page.tsx`, `account/security/page.tsx` | Resolved in Part B: QR SVG + Base32 enrollment, 8 Argon2id recovery codes, forced setup/login step-up, re-auth disable blocked by `require_2fa_roles`. |
| `FR-003` | Invites, password reset, min-12 password policy | `implemented` (Part B) | `auth.py`, `org_users.py` (`send_email_if_configured`), `email.py`, `docker-compose.yml` (`mailpit` dev/qa profile) | Resolved in Part B: invites & reset links dispatch over SMTP / Mailpit inbox with safe URL fallback when SMTP is unset. |
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
| `FR-023` | Accessibility Compliance | `implemented` (Part B) | `frontend/e2e/tablepulse.spec.ts` & `phase2.spec.ts` (`wcag22aa`), `>=44px` touch targets across `AppShell` & operational UI | Upgraded automated axe-core audits to `wcag22aa` and enforced `>=44px` interactive targets. Verified across viewports in Part C. |
| `FR-024` | Responsive multi-device support | `implemented` | Tailwind responsive layouts + `assertNoHorizontalOverflow` | Expand browser verification across all 15 viewports (`320`–`1920`), `200%` zoom, and visual `browser` subagent audit. |

---

## 3. Phase 2 Functional Requirements & Should Items (`FR-025`–`FR-040` / `FR-T`/`FR-M`/`FR-Q`/`FR-CM`)

| ID / Domain | Requirement & Should Item | Status | Evidence (Repo Files) | Gaps / Part B Action |
|---|---|---|---|---|
| `FR-025` / `FR-T` | Individual table CRUD, optimistic locking, unmonitored tables | `implemented` (Part B) | `tables_admin.py`, `settings/tables/page.tsx` | Added Duplicate Table, Archived Tables filter, Restore (`new_table_code` on `409`), and Purge (`409 TABLE_HAS_HISTORY`). |
| `FR-026` / `FR-T` | Bulk table add (`1–50`), bulk section/active updates | `implemented` (Part B) | `tables_admin.py`, `settings/tables/page.tsx` | Added `Export QRs PDF` shortcut right in the bulk selection action bar. |
| `FR-027` / `FR-T` | Safe deactivation & soft-delete (`409 TABLE_IN_USE` + `?force=true`) | `implemented` (Part B) | `tables_admin.py`, `settings/tables/page.tsx` | Added Restore (conflict prompt `E-05`) and Purge (`E-07`). |
| `FR-028` / `FR-T` | Sync tables with `SCR-005`, `SCR-013`, and `cv-worker` | `implemented` | `floor_ops.py` (`unmonitored_tables`), `calibrate/page.tsx`, `cv-worker` | None. |
| `FR-029` / `FR-M` | Multi-menu CRUD, Draft/Published/Archived, time-of-day schedules, org/venue settings | `implemented` (Part B) | `menus_admin.py`, `menu_schedule.py`, `menu/page.tsx` | Added Duplicate Menu (`DRAFT`), EN/HI `translations_json` inputs, and `managers_can_manage_menu`/`admins_can_manage_menu` enforcement. |
| `FR-030` / `FR-M` | Menu category CRUD, atomic drag+keyboard reorder, non-empty guard | `implemented` (Part B) | `menus_admin.py`, `menu/page.tsx` (`@dnd-kit`) | Added EN/HI category translation fields. |
| `FR-031` / `FR-M` | Menu items CRUD, minor units, dietary/allergen tags, duplicate, **variants**, **CSV import/export** | `implemented` (Part B) | `menus_admin.py`, `MenuItemDrawer.tsx`, `menu/page.tsx`, `0004_*` | Added unique per-venue `sku`, 2-step CSV import (`template`, `preview`, `commit`, `create_only`/`upsert_by_sku`, `410 IMPORT_EXPIRED`), round-trip formula-safe CSV export, bulk delete/move, and Hindi dish fields. |
| `FR-032` / `FR-M` | Validated WebP image pipeline (5 MB, magic bytes, EXIF strip, 800/320, SHA-256 dedup, orphan GC) | `implemented` | `services/media.py`, `menus_admin.py` (`API-031`), `MenuItemDrawer.tsx` | None. |
| `FR-033` / `FR-M` | Quick-86 availability toggle, bulk availability, **`unavailable_until` auto-restore**, **Mobile Preview (`SCR-021`)** | `implemented` (Part B) | `menus_admin.py`, `public_menu.py`, `MenuPreviewModal.tsx`, `menu/page.tsx` | Added Quick-86 `unavailable_until` duration presets (`2h`, tomorrow `09:00`), card badge, and admin read-time auto-restore sync (`list_menu_items`). |
| `FR-034` / `FR-Q` | 128-bit CSPRNG QR generation + backfill + `PUBLIC_APP_URL` only | `implemented` | `qr_export.py::build_qr_url`, `tables_admin.py`, `0003_phase2_tables_menu_qr.py` | None (`Host` header is never used). |
| `FR-035` / `FR-Q` | QR regenerate + grace period (`0–30d`) + end-grace + preview link | `implemented` | `qr_admin.py` (`API-033`), `settings/qr-codes/page.tsx` | None. |
| `FR-036` / `FR-Q` | QR downloads (`SVG`, `PNG`, batch `PDF`) + **A6 / sticker / ZIP downloads** + **QR scan stats** | `implemented` (Part B) | `qr_export.py`, `qr_admin.py`, `settings/qr-codes/page.tsx` | Added `A6_1UP`, `A4_STICKER_12UP` print sheets, batch ZIP export (`POST .../qr/export-zip`), and aggregate 30d scan stats UI (`GET .../qr-codes/stats`). |
| `FR-037` / `FR-CM` | Public digital menu `/m/:qrToken`, zero cookies/storage, strict headers & isolation | `implemented` (Part B) | `public_menu.py`, `ClientProviders.tsx`, `PublicDigitalMenu.tsx`, `infra/caddy/Caddyfile` | Added trusted `X-Forwarded-For` IP extraction and `^[A-Za-z0-9_-]{16,64}$` fast-path `404` before DB queries. |
| `FR-038` / `FR-CM` | Customer menu search, dietary filters, category pills, bottom sheet, **EN/HI dish copy**, **large-menu lazy loading** | `implemented` (Part B) | `public_menu.py`, `PublicDigitalMenu.tsx` | Added client & `?lang=en|hi` localization plus progressive pagination (`>200` items -> 100/slice with `X-Total-Items`/`X-Has-More`/`X-Next-Offset` headers & `"Load more dishes"` UI). |
| `FR-039` / `FR-CM` | Revoked (`410`), unavailable table (`410`), invalid token (`404`), disabled/no-menu (`200`), DB down stale (`X-Stale: 1` / `503`) | `implemented` | `public_menu.py`, `PublicDigitalMenu.tsx` | Explicitly verify every state in automated QA cases. |
| `FR-040` / `FR-CM` | Privacy-safe daily scan telemetry & Valkey invalidation | `implemented` (Part B) | `public_menu.py`, `QrScanDailyStat`, `settings/qr-codes/page.tsx` | Aggregate 30d breakdown surfaced in QR Console without any PII. |

---

## 4. Infrastructure, Admin CLI, Security & Test Data Gaps

| Category | Item | Status | Evidence | Part B Status / Resolution |
|---|---|---|---|---|
| **Admin CLI** | `create-org` command (plus `revoke-all`, `rotate-keys`, `backup`, `restore`) | `implemented` (Part B) | `backend/app/cli.py`, `backend/tests/test_cli_and_mail.py` | Added `tablepulse admin create-org` with full options, org/venue/policy/audit creation & integration tests. |
| **Mail Path** | Local SMTP dev/QA inbox (Mailpit) + real invite/reset email dispatch | `implemented` (Part B) | `docker-compose.yml` (`mailpit`), `org_users.py::invite_user`, `docs/runbooks/README.md` | Bundled Mailpit (`profiles: ["dev", "demo", "qa"]`) and wired invite/reset email delivery + URL fallback. |
| **Org Policy Flags** | `require_2fa_roles`, `managers_can_manage_tables`, `managers_can_manage_menu`, `admins_can_manage_tables`, `admins_can_manage_menu` | `implemented` (Part B) | `0004_gaps_2fa_sku_policies_i18n.py`, `core/rbac.py`, `admin_ops.py`, `org/system/page.tsx`, `AuthProvider.tsx` | Enforced in backend RBAC (`403 POLICY_DISABLED`) & login, toggled in `SCR-015` System Controls, synced to frontend UI gates. |
| **Accessibility** | WCAG 2.2 AA (`wcag22aa`, `>=44px` target sizes, focus visibility) | `implemented` (Part B) | `frontend/e2e/{tablepulse,phase2}.spec.ts`, `frontend/src/` | Upgraded axe tags to `wcag22aa` and elevated interactive controls to `>=44px`. Verified in Part C. |
| **Test Menu Media (`qa-evidence/media/`)** | 65 Wikimedia menu images provenance & visual match audit | `implemented` (Part B) | `qa-evidence/data-sources.md`, `qa-evidence/media-manifest.json` | Visually inspected all images, replaced 22 mismatched/branded/unknown-author items with verified unbranded CC/PD photos, regenerated SHA-256 manifest, zero unknown authors. |
| **QA Evidence Hygiene** | Synthetic emails & footage duration check | `pending Part C` | `qa-evidence/FINAL_QA_REPORT.md`, `qa/TEST_PLAN.md`, `qa-evidence/footage/` | Footage verified via `ffprobe` (`6.92s–19.47s`; no `>=2 min` permissive fixed elevated clip exists — state-transition video cases marked `BLOCKED`); scrub `@malabarspice.in` / `@decanchai.in` in Part C/D. |
