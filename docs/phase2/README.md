# TablePulse Phase 2 — Unified Specification Index (`README.md`)

> **Phase 2 Scope (Strictly Phase 2 — Zero Phase 1 Files Modified):** Extends an implemented **TablePulse v1.0** platform (15 tables, 5 roles, FastAPI + Next.js 15 + PostgreSQL 16 + Valkey + MediaMTX) with **Advanced Table Management**, **Menu Management**, **Unique Table QR Codes**, and a **Zero-Login Customer Digital Menu (`/m/:qrToken`)**.
>
> **How to drop into your repo:** Copy `docs/phase2/` into your repository's `docs/phase2/` folder and `UI/PHASE-2-ASSETS.md` into `UI/`. Do **not** overwrite Phase 1 docs.
>
> **Reading order for Antigravity / AI Coding Agents:** `AGENTS.md` (Phase 1 root) -> `docs/phase2/README.md` -> `docs/phase2/00-baseline-reconciliation.md` -> `docs/phase2/12-phase2-build-roadmap.md` -> the module docs for the current stage.

---

## 1. Phase 2 Document Index (15 Docs + 1 UI Asset Guide)

| # | File | Coverage |
|---|---|---|
| 0 | `docs/phase2/README.md` | Master index, decision log (`DEC-P2-01`–`DEC-P2-12`), open questions & professional review items |
| 1 | `docs/phase2/00-baseline-reconciliation.md` | **Mandatory Stage 9a (N0)** repo verification checklist, Phase-1-to-Phase-2 conflict resolutions (`C1`–`C5`), consumer grep checklist |
| 2 | `docs/phase2/01-phase2-overview-and-scope.md` | Phase 2 overview, v1.0 integration map, `FR-025`–`FR-040`, deferred scope & success metrics |
| 3 | `docs/phase2/02-architecture-and-integration.md` | Zero-new-container architecture, `tablepulse_public` read-only DB role/views, Valkey + 24h stale-while-error cache, atomic `menu_revision`, feature flags & permissive libraries |
| 4 | `docs/phase2/03-database-schema-extensions.md` | Additive v1.0 migrations (`venues`, `tables`), 6 new tables (`#16`–`#21`), QR grace states, item variants, 2 public SQL views, indexes & RLS |
| 5 | `docs/phase2/04-table-management.md` | Individual & bulk table lifecycle, active-session delete guards (`409`), archived label reuse & `unmonitored_tables` floor-API separation |
| 6 | `docs/phase2/05-menu-management.md` | Multi-menu schedules (incl. overnight `22:00–02:00`), draft/published status, ordered categories, items & variants, minor-unit pricing, currency lock, Quick-86 & deduplicated WebP image pipeline |
| 7 | `docs/phase2/06-qr-and-digital-menu.md` | 128-bit CSPRNG QR tokens, frozen `/m/{token}` URL contract, optional regeneration grace period, anti-quishing printouts, signed 15-min admin preview, offline SVG/PNG/PDF export & isolated `/m/:qrToken` menu |
| 8 | `docs/phase2/07-rbac-extensions.md` | Extended 5-role + Public permission matrix (`packages/rbac/matrix.yaml`), `policy="public"` route-registry check, isolation guarantees & audit actions |
| 9 | `docs/phase2/08-api-and-backend-spec.md` | Complete REST contract (`API-024`–`API-035`), payloads, error codes, idempotency, pagination & strict public DTO whitelist |
| 10 | `docs/phase2/09-ui-screens-phase2.md` | 6 new UI screens (`SCR-017`–`SCR-022`) aligned with v1.0 design tokens & `UI/PHASE-2-ASSETS.md` |
| 11 | `docs/phase2/10-security-validation-and-edge-cases.md` | 20-threat model (`T1`–`T20`), server validation catalogue, public-surface checklist, upload pipeline security & 28 concrete edge cases |
| 12 | `docs/phase2/11-testing-and-acceptance-criteria.md` | Phase 2 test pyramid, direct PostgreSQL checks, CI QR-decode verification (`zxing-cpp`/`pyzbar`), `tablepulse_public` isolation test, Playwright/axe-core & DoD checklist |
| 13 | `docs/phase2/12-phase2-build-roadmap.md` | 7-step build plan (`Stage 9a` reconciliation + `Stage 9`–`Stage 14` with human checkpoints), feature-flag rollout/rollback plan & copy-paste Antigravity prompts |
| 14 | `docs/phase2/consistency-report.md` | Automated cross-document audit confirming zero contradictions and zero Phase 1 base mismatches |
| 15 | `UI/PHASE-2-ASSETS.md` | Priority mockup checklist for `SCR-017`–`SCR-022` + ready-to-paste UI-generation prompt |

---

## 2. Phase 2 Master Decision Log (`DEC-P2-01`–`DEC-P2-12`)

| ID | Decision | Label | Rationale |
|---|---|---|---|
| `DEC-P2-01` | Zero new Docker containers — extend existing `api`, `web`, `db`, `valkey`, `caddy` | `PROPOSED` | Preserves 1-command self-hosted `docker compose up -d` simplicity |
| `DEC-P2-02` | Mandatory **Stage 9a (N0) Baseline Reconciliation** before coding | `DECIDED` | Real repo wins over docs; prevents broken migrations or mismatched names |
| `DEC-P2-03` | Dedicated read-only DB role `tablepulse_public` + 2 SQL views for `/api/v1/public/*` | `DECIDED` | Defense-in-depth: even a public API bug cannot read staff, auth, or camera tables |
| `DEC-P2-04` | 128-bit CSPRNG opaque QR tokens (`/m/{token}`) bound to `table_id`, URL from `PUBLIC_APP_URL` config only | `DECIDED` | Anti-enumeration, Host-header poisoning prevention, table renames never break printed QRs |
| `DEC-P2-05` | Optional **QR regeneration grace period** (`qr_grace_days` default `7`, `0` = immediate revoke) | `PROPOSED` | Prevents stranding seated diners while staff physically swap table stickers |
| `DEC-P2-06` | Integer `price_minor_units` + ISO-4217 `currency_code` + currency lock when priced items exist | `PROPOSED` | Eliminates floating-point bugs and accidental currency mismatch |
| `DEC-P2-07` | Draft/Published menus + optional item variants (`variants_json`, max 8) + atomic `venues.menu_revision` | `PROPOSED` | Safe menu prep before going live, supports Half/Full or Small/Large pricing, clean ETag invalidation |
| `DEC-P2-08` | Server-validated Pillow WebP pipeline (magic bytes, EXIF strip, SHA-256 hash dedup, no SVG/URL-fetch) | `DECIDED` | Blocks SVG-XSS/polyglots/SSRF, prevents duplicate disk bloat, fast 4G mobile loads |
| `DEC-P2-09` | Valkey 60s menu cache + immediate write invalidation + **24h stale-while-error fallback** if DB drops | `PROPOSED` | Absorbs dinner-rush scan bursts and keeps digital menus readable during brief DB outages |
| `DEC-P2-10` | Offline permissive QR/PDF stack (`segno` BSD-3 + `reportlab` BSD + Noto Sans SIL OFL) | `DECIDED` | Works air-gapped on restaurant LAN; 100% Apache-2.0/MIT/BSD/OFL license compatible |
| `DEC-P2-11` | Decouple `tables` from `cameras` (`polygon_json` nullable) + return `unmonitored_tables` separately on floor API | `DECIDED` | Supports non-CCTV tables without distorting Phase 1 occupancy % or crashing `cv-worker` |
| `DEC-P2-12` | Fail-closed Phase 2 feature flags (`TABLE_ADVANCED_ENABLED`, `QR_ENABLED`, `PUBLIC_MENU_ENABLED`, `MENU_IMAGES_ENABLED`; missing = `false`) | `DECIDED` | Enables safe staged rollout and clean rollback |

---

## 3. Open Questions & Professional Review Items

| ID | Type | Item | Blocking Build? | Default Used |
|---|---|---|---|---|
| `OPEN-P2-01` | `OPEN` | Should `HOST` be allowed to toggle item availability ("Quick 86") by default, or opt-in per venue? | No | `allow_host_menu_availability=false` (opt-in) |
| `OPEN-P2-02` | `OPEN` | Default venue currency (`INR` vs `USD`) and tax-inclusive/exclusive note on `SCR-022` | No | `INR` default, editable by `OWNER` |
| `OPEN-P2-03` | `OPEN` | Media storage for multi-node cloud installs: local Docker volume vs. optional S3/R2 adapter | No | Local volume behind clean storage interface |
| `PR-P2-01` | `PROFESSIONAL REVIEW` | Restaurant legal liability for allergen, dietary (`VEG`/`VEGAN`/`GLUTEN_FREE`), and calorie accuracy displayed to diners | **Before live restaurant rollout** | Venue Owner / Legal Counsel |
