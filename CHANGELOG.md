# Changelog

All notable changes to TablePulse will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0-rc.2] - 2026-11-27

### Added
- **TOTP Two-Factor Authentication (`FR-002`):** Enrollment QR SVG + Base32 secret (`/api/v1/auth/2fa/enroll`), verification + 8 Argon2id single-use recovery codes (`/verify-enroll`), step-up login challenge (`2FA_CHALLENGE` token + `/2fa/verify`), recovery-code regeneration, re-auth disable blocked by policy, and `/account/security` UI + forced enrollment wizard on login.
- **Organization Role & Security Policy Flags:** `require_2fa_roles`, `managers_can_manage_tables`, `managers_can_manage_menu`, `admins_can_manage_tables`, `admins_can_manage_menu` in `system_settings` (`0004_gaps_2fa_sku_policies_i18n.py`), `/api/v1/org/system` UI toggles, and `require_venue_role` enforcement (`403 POLICY_DISABLED`).
- **Menu CSV Import & Round-Trip Export (`FR-031`):** Template download, validated preview (`<=2 MB`, `<=2000` rows, `create_only` & `upsert_by_sku` modes, formula-safe handling), transactional commit (`all_or_nothing` / `skip_invalid`, `410 IMPORT_EXPIRED`), unique per-venue `sku`, and Menu Studio import modal.
- **Phase 2 Should-Items & Hardening:** Duplicate table/menu, Archived tables filter + Restore (`E-05` `new_table_code` prompt) + Purge (`E-07` `409 TABLE_HAS_HISTORY`), bulk menu-item move/delete, `unavailable_until` timed Quick-86 presets + read-time auto-restore, EN/HI `translations_json` across menus/categories/items/public catalog, large-menu progressive loading (`X-Total-Items`/`X-Has-More`/`X-Next-Offset`), `A6_1UP` & `A4_STICKER_12UP` QR PDFs, batch ZIP export, aggregate 30d QR scan stats, `tablepulse admin create-org` CLI, Mailpit dev/QA profile + invite email delivery, and `wcag22aa` `>=44px` touch targets.

## [1.1.0-rc.1] - 2026-11-27

### Added
- **Phase 2 Data Model & Security (`0003_phase2_tables_menu_qr.py`, `packages/rbac/matrix.yaml`):**
  - Extended `venues` and `tables` (nullable `polygon_json` for unmonitored standalone tables, `display_name`, `min_capacity`, `is_active`, `is_combinable`, `table_notes`, `sort_order`).
  - Added 6 RLS-protected tables (`table_qr_codes`, `menus`, `menu_categories`, `menu_items`, `menu_media_assets`, `qr_scan_daily_stats`), least-privilege read-only PostgreSQL role `tablepulse_public`, views `v_public_qr_resolution` & `v_public_menu_catalog`, and 128-bit CSPRNG QR token backfill.
  - Extended canonical 5-role RBAC matrix by 8 Phase 2 capabilities (`21 -> 29`) plus fail-closed feature flags (`TABLE_ADVANCED_ENABLED`, `QR_ENABLED`, `PUBLIC_MENU_ENABLED`, `MENU_IMAGES_ENABLED`) and conditional `HOST` Quick-86 delegation.
- **Phase 2 Backend APIs (`API-024`–`API-035`):**
  - Advanced table directory CRUD + bulk generator (`1..50`) + `TABLE_IN_USE` soft-delete guard.
  - Digital Menu Studio APIs (`menus`, `menu-settings` with `OWNER`-locked currency switch, ordered `categories`, `menu-items` with minor-unit integer pricing, variants, dietary/allergen tags, 1-tap Quick-86 & bulk availability, formula-safe CSV export).
  - Server-validated WebP media pipeline (5 MB limit, magic-byte sniffing, EXIF strip, `800px`+`320px` WebP, SHA-256 dedup, atomic `0600` temp writes, orphan GC `purge_orphan_menu_media_once`, sandbox static route).
  - Offline `segno` QR SVG/PNG cards, `reportlab` batch printable PDF tent sheets (`A4_4UP`, `A4_6UP`, `LETTER_4UP`), atomic grace rotation (`COMPROMISED` -> `0` grace days), 15m HMAC preview links, and isolated unauthenticated `GET /api/v1/public/menu/{qr_token}` with `ETag`/`304`, `60/min` IP rate limit, 24h stale-while-error `X-Stale: 1`, and privacy-safe daily scan telemetry.
- **Phase 2 Frontend (`SCR-017`–`SCR-022`):**
  - Built `SCR-017` Tables Directory, `SCR-018` Menu Studio (`@dnd-kit/sortable` + keyboard reorder + CSV + settings), `SCR-019` Item Drawer, `SCR-020` QR Manager, `SCR-021` Mobile Preview Modal, and isolated zero-login zero-cookie `(public)/m/[qrToken]` Customer Digital Menu (`SCR-022`), plus `SCR-013` unmapped table binding and `SCR-005` `"Manual Mode"` indicator.
  - Verified Light/Dark multi-viewport screenshots (`1440`, `768`, `390`) in `UI/phase2/` and `0` critical/serious `@axe-core/playwright` WCAG 2.1/2.2 AA violations.

## [1.0.0-rc.1] - 2026-11-25

### Added
- **Stages 1–5 (Backend & CV Pipeline):** 15-table PostgreSQL 16 schema with native monthly range partitioning & RLS, Alembic migrations, Argon2id/TOTP/JWT/refresh-rotation auth, 5-role RBAC (`packages/rbac/matrix.yaml`), SSRF-safe camera/webhook guards, AES-256-GCM field encryption, MediaMTX stream auth hook, OpenCV face-blur-or-drop pipeline (`4.14.0.94`), ByteTrack + deterministic state machine, FastAPI 23 API groups + WebSocket hub, waitlist + turnover ETAs, analytics + CSV export, ML review queue & zip export, and OWNER system governance.
- **Stages 6–7 (Next.js 15 Frontend):** All 16 screens (`SCR-001`–`SCR-016`) implemented using extracted design tokens (`tokens.css`) + Dark/Solid accessibility themes + EN/HI toggle, memory-only JWT auth + refresh interceptor, WebSocket + 5s polling fallback, Konva floor & calibration canvases (`react-konva@19.2.7`), Recharts analytics, Playwright E2E + `axe-core` WCAG 2.1 AA verification across Desktop (`1280px`), Tablet (`768px`), and Mobile (`360px`).
- **Stage 8 (ML Gate & Release Readiness):** Leakage-free dataset splitter & 5-invariant verifier, `TSM-F1` + cluster bootstrap CI + ECE + G1–G11 release gate (`ml/evaluate_gate.py`, strictly blocking `stable` without a passing real-data `eval_report.json`), experimental B1 baseline marked `NOT YET MEASURED`, chaos degraded-mode suite, backup/restore verifier, EN/HI privacy templates, ASVS summary, runbooks, and measured benchmarks (`docs/benchmarks.md`).
