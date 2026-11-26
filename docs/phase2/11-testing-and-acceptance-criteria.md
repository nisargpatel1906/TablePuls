# TablePulse Phase 2 — Testing Strategy & Acceptance Criteria

## Quick Reference
- **Core Rule (`DECIDED` — `production-ready-vibe-coding`)**: Every Phase 2 endpoint and UI screen must pass valid-input, bad-input, RBAC/cross-tenant, and **direct PostgreSQL state verification** tests before a stage is marked done.
- **Regression Gate**: 100% of v1.0 test suites (`Stage 0`–`Stage 8`) must remain green alongside all Phase 2 tests.

---

## 1. Phase 2 Test Pyramid & Pass Criteria

| Layer | Tools | Specific Phase 2 Checks | Pass Criteria |
|---|---|---|---|
| **Backend Unit** | `pytest` | CSPRNG token entropy/format, minor-unit price validation, schedule window timezone evaluator, magic-byte image validator (rejects `.svg`/polyglot/oversize), QR SVG/PNG/PDF generator output validity. | 100% pass; `>= 85%` coverage on new services. |
| **Backend Integration + DB Verification** | `pytest`, `httpx.AsyncClient`, Testcontainers (Postgres 16, Valkey) | Every endpoint `API-024`–`API-035`: (1) valid writes verified directly via SQL (`tables`, `table_qr_codes`, `menus`, `menu_categories`, `menu_items`, `menu_media_assets`, `audit_logs`), (2) bad inputs (`400`/`409`/`413`), (3) unauthenticated (`401`), (4) wrong role & cross-org tenant (`403`), (5) public `API-035` returns `200`/`404`/`410`/`429` with zero leaked private fields, (6) QR regeneration immediately evicts Valkey cache and returns `410` on old token. | 100% of `API-024`–`API-035` covered; 0 unhandled `500`s. |
| **Frontend Unit & Component** | `Vitest`, RTL | Currency formatting (INR/USD/JPY), bulk table code previewer, category reorder controls, optimistic Quick-86 toggle + error rollback, `SCR-022` client-side search & dietary filters. | 100% pass; `tsc --noEmit` 0 errors. |
| **Frontend E2E & Multi-Device** | `Playwright` | Full journeys: (1) Owner bulk-adds 4 tables -> verifies live appearance on `SCR-005` -> downloads batch QR PDF; (2) Manager creates menu, category, item with photo -> toggles Sold Out -> verifies live update on unauthenticated `/m/:qrToken` (`SCR-022`); (3) Manager regenerates QR -> verifies old `/m/:oldToken` shows friendly `410` state and new token works; (4) Direct-URL navigation on `SCR-017`–`SCR-022` (zero 404s). | 100% pass at 375px (mobile), 768px (tablet), 1280px (desktop); 0 browser console errors. |
| **Security & Isolation Tests** | `pytest` + `Playwright` | Unauthenticated context visiting `/m/:qrToken` verifies: (1) no admin links in DOM, (2) zero auth cookies set, (3) calling `/api/v1/venues/*` returns `401`, (4) public JSON contains no `table_notes`, `camera_id`, `organization_id`, or `current_state`. | 100% pass; `gitleaks` & license check (`pip-licenses` zero GPL/AGPL) green. |
| **Accessibility Audit** | `axe-core` (Playwright) | WCAG 2.1 AA scan across `SCR-017`–`SCR-022` in both Light and Dark mode + keyboard-only category reorder and item bottom sheet close. | 0 critical or serious violations. |

---

## 2. Acceptance Criteria Checklist (Definition of Done for Phase 2)
1. [ ] **Tables (`FR-025`–`FR-028`)**: `OWNER`/`MANAGER` can add, bulk-add, rename, edit, deactivate, and soft-delete tables; changes reflect immediately on `SCR-005` and `SCR-013` without breaking existing v1.0 CCTV polygons.
2. [ ] **Menus (`FR-029`–`FR-033`)**: `OWNER`/`MANAGER` can manage multiple menus, ordered categories, and items (name, description, minor-unit price, validated WebP photo, dietary/allergen tags, 1-tap availability) and preview mobile layout (`SCR-021`).
3. [ ] **Unique QR Codes (`FR-034`–`FR-036`)**: Every existing and newly created table has a unique 128-bit QR token; SVG, PNG, and batch PDF downloads open cleanly and scan on real iOS/Android cameras; regeneration revokes the prior token within `< 1s`.
4. [ ] **Public Digital Menu (`FR-037`–`FR-040`)**: Scanning any active table QR opens `SCR-022` without login, displays venue branding, table label, categories, items, prices, and images, supports search/dietary filters, handles revoked/deleted/unpublished states gracefully, and exposes zero admin functionality or internal data.
5. [ ] **Zero v1.0 Regression**: All v1.0 tests (`Stage 0`–`Stage 8`) pass unchanged and all 13 original v1.0 spec files remain untouched.
6. [ ] **Visual Continuity**: `SCR-017`–`SCR-022` follow v1.0's iOS 26+ Liquid Glass design system across Desktop, Tablet, and Phone viewports.


---

## 3. Additional Automated Hardening Checks (Ported from P2-13)
1. **Read-Only DB Role Isolation Test**: Execute `API-035` queries as `tablepulse_public` and assert `SELECT * FROM users`, `SELECT * FROM cameras`, and `UPDATE tables ...` all fail with PostgreSQL `InsufficientPrivilege`.
2. **Automated QR Decode Reliability Test**: Decode generated SVG/PNG QR codes in CI (`zxing-cpp` or `pyzbar`) and verify the decoded URL exactly matches `{PUBLIC_APP_URL}/m/{token}` (and never reflects a spoofed `Host` header).
3. **Resilience & Edge-Case Tests**: Verify (a) 24h stale-while-error cache serves `200` + `X-Stale: 1` when DB is unreachable, (b) Valkey-down falls back cleanly to DB without `500`, (c) overnight menu schedules (`22:00–02:00`) evaluate accurately in venue timezone, (d) QR regeneration with `grace_days=7` keeps both old and new tokens working until `end-grace` or expiry, and (e) duplicate image upload deduplicates by SHA-256.
4. **Phase 1 Non-Regression Baseline**: Compare Stage 14 test counts against `docs/phase2/N0-reconciliation.md` baseline—zero skipped, weakened, or failing Phase 1 tests.
