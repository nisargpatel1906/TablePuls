# TablePulse Phase 2 — Overview, Scope & Integration Summary

## Quick Reference
- **Phase**: Phase 2 (`v1.1` / `v2.0` extension) — **Advanced Table Management**, **Menu Management**, and **Unique Table QR-Based Digital Menu Access** (`DECIDED`).
- **Foundation**: Strictly extends the completed TablePulse v1.0 platform (15 DB tables, 5 RBAC roles, 16 screens `SCR-001`–`SCR-016`, 24 FRs `FR-001`–`FR-024`, 23 API groups `API-001`–`API-023`, FastAPI + Next.js 15 + PostgreSQL 16 + Valkey/Valkey). **Zero v1.0 features are rebuilt or overwritten.**
- **ID Continuations**: `FR-025`–`FR-040`, `SCR-017`–`SCR-022`, `API-024`–`API-035`, `DEC-009`–`DEC-015`, DB tables `#16`–`#21`, Build `Stage 9`–`Stage 14`.
- **License**: Continues under **Apache-2.0**; all new libraries (`segno`, `reportlab`, `Pillow`) are permissively licensed (BSD/MIT-CMU).

---

## 1. Statement Labeling Convention
Every decision and requirement across the Phase 2 documentation suite uses:
- `DECIDED`: Explicitly confirmed in the Phase 2 prompt or inherited from completed v1.0.
- `PROPOSED`: Recommended architectural/product default chosen to unblock implementation; overrideable before coding begins.
- `OPEN`: Non-blocking decision tracked in `README.md` with an owner and resolve-by point.
- `PROFESSIONAL REVIEW`: Legal/compliance item requiring domain counsel (e.g., allergen/nutrition labeling accuracy regulations).
- `DEFERRED`: Explicitly out of scope for Phase 2 (e.g., online ordering, carts, payments).

---

## 2. How Phase 2 Fits Into Existing TablePulse v1.0

| Existing v1.0 Capability | Phase 2 Extension | Integration Boundary |
|---|---|---|
| **Tables (`tables` table, `SCR-005`, `SCR-013`)** | Full standalone table lifecycle (create, bulk add, rename, configure, deactivate, soft-delete) independent of CCTV calibration. | `camera_id` and `polygon_json` become optional for non-camera tables; `SCR-005` Live Floor Map and `SCR-013` Polygon Editor automatically reflect table additions/renames/deactivations. |
| **RBAC (`OWNER`, `MANAGER`, `HOST`, `STAFF`, `VIEWER`)** | Extends existing 5-role permission matrix with Table Admin, Menu Admin, Quick Item Availability ("86"), and QR Management permissions. | Reuses existing `get_current_user`, `require_venue_role`, and PostgreSQL RLS (`app.current_org_id`). Adds a strictly isolated public read-only namespace (`/api/v1/public/menu/{qr_token}`) for unauthenticated diners. |
| **UI Design System (`SCR-001`–`SCR-016`)** | Adds 5 authenticated management screens (`SCR-017`–`SCR-021`) + 1 public mobile-first Digital Menu screen (`SCR-022`). | Inherits existing iOS 26+ Liquid Glass floating controls over solid content cards, Light/Dark + Glass/Solid toggle, typography, and spacing tokens from `UI/`. |
| **Audit Logging (`audit_logs`)** | Logs all table CRUD, bulk table changes, menu/category/item mutations, QR regenerations, and image uploads. | Appends new action constants to existing immutable `audit_logs` table. |

---

## 3. Phase 2 Scope: In-Scope vs. Deferred

### 3.1 In-Scope for Phase 2 (`DECIDED` / `PROPOSED`)
1. **Advanced Table Management (`FR-025`–`FR-028`)**: Create, edit, rename, bulk-add, deactivate/reactivate, and soft-delete tables; configure display name, section, min/max seat capacity, shape, combinability, and accessibility/operational notes; seamlessly link/unlink with CV camera polygons.
2. **Menu Management (`FR-029`–`FR-033`)**: Create/manage multiple menus per venue (e.g., Main, Lunch, Drinks) with optional active schedules; manage ordered categories; create/edit/duplicate/delete food & beverage items with integer minor-unit pricing, descriptions, dietary/allergen tags, prep time, and server-validated food images; 1-tap availability ("Available / Sold Out") toggle; admin mobile menu preview.
3. **Unique Table QR Codes (`FR-034`–`FR-036`)**: Automatic cryptographically unguessable QR token generation on table creation (plus backfill migration for existing v1.0 tables); instant QR regeneration with immediate invalidation of prior tokens; single SVG/PNG download and multi-table printable PDF tent-card sheet export; privacy-preserving daily scan counts.
4. **Customer-Facing Digital Menu (`FR-037`–`FR-040`)**: Public, zero-login mobile-first digital menu at `/m/:qrToken`; displays venue branding, table label, active menus, categories, item photos, descriptions, prices, dietary badges, and availability; instant search and dietary filters; graceful states for revoked QR, deleted/inactive table, or unpublished menu; zero access to admin/owner routes or internal data.

### 3.2 Explicitly Deferred (`DEFERRED` to Phase 3+)
- **Customer Self-Ordering, Carts, Kitchen Tickets (KOT), or Online Payments** (`DECIDED` — explicitly excluded from Phase 2).
- **Item Modifiers / Add-On Pricing Trees** (e.g., "+Extra Cheese $1.50", "Choose 2 Sides") (`DEFERRED` to Phase 3 — Phase 2 supports flat item prices + optional description notes).
- **Multi-Language Menu Translations** (`DEFERRED` to Phase 3 — Phase 2 stores single venue-language text; schema leaves room for `translations_json` later).
- **Customer Feedback / Ratings / Waiter Call Button from QR Page** (`DEFERRED` to Phase 3).
- **POS Menu Sync** (importing menu items from Toast/Square/Petpooja) (`DEFERRED` to Phase 3).

---

## 4. Phase 2 Functional Requirement Summary (`FR-025`–`FR-040`)

| ID | Module | Requirement Summary | Priority |
|---|---|---|---|
| `FR-025` | Tables | Create, edit, rename, and configure individual tables (with or without camera polygon) | `P0` |
| `FR-026` | Tables | Bulk create tables by prefix/range and bulk section/status updates | `P0` |
| `FR-027` | Tables | Safe table deactivation and soft-deletion with active-session guard & analytics preservation | `P0` |
| `FR-028` | Tables | Sync table changes to `SCR-005` Live Floor Map, `SCR-013` Polygon Editor, and `cv-worker` | `P0` |
| `FR-029` | Menu | Create, edit, schedule, activate/deactivate, and soft-delete venue menus | `P0` |
| `FR-030` | Menu | Create, edit, reorder, activate/deactivate, and soft-delete menu categories | `P0` |
| `FR-031` | Menu | Full CRUD + duplicate for menu items (name, description, minor-unit price, dietary/allergen tags) | `P0` |
| `FR-032` | Menu | Server-validated menu item image upload (magic-byte check, WebP transcoding, EXIF strip) | `P0` |
| `FR-033` | Menu | 1-tap item availability ("86 / Sold Out") toggle + admin live mobile preview | `P0` |
| `FR-034` | QR | Auto-generate unique 128-bit CSPRNG QR token per table (and backfill v1.0 tables) | `P0` |
| `FR-035` | QR | Regenerate table QR code (atomically revoking old token) with audit log | `P0` |
| `FR-036` | QR | Download single QR (SVG/PNG) and export batch printable PDF table-tent sheets | `P0` |
| `FR-037` | Public Menu | Zero-login public digital menu access via `/m/:qrToken` with strict admin isolation | `P0` |
| `FR-038` | Public Menu | Category navigation, instant search, dietary filtering, and item detail bottom sheet | `P0` |
| `FR-039` | Public Menu | Graceful handling of revoked QR, deleted/inactive table, or unpublished menu | `P0` |
| `FR-040` | Public Menu | Privacy-preserving daily QR scan counter (zero customer PII/cookies) & cache invalidation | `P1` |

---

## 5. Success Criteria (`PROPOSED`)
- **Zero Regression**: 100% of existing v1.0 backend, frontend, CV, and E2E tests continue passing unchanged.
- **Public Menu Performance**: `GET /api/v1/public/menu/{qr_token}` responds in `<= 100ms` p95 (Valkey cached) and `SCR-022` achieves First Contentful Paint `<= 1.5s` on simulated 4G mobile.
- **Security Isolation**: Automated security tests confirm unauthenticated `/m/:qrToken` requests cannot access any `/api/v1/venues/*` or `/api/v1/org/*` route and receive zero internal UUIDs, RTSP URLs, or staff notes.
- **QR Uniqueness & Revocation**: 100% of active tables have distinct cryptographically random tokens; regenerating a QR invalidates the prior token within `< 1s` (DB + Valkey cache purge).
