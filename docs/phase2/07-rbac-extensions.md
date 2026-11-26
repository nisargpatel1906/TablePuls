# TablePulse Phase 2 — Role-Based Access Control (RBAC) Extensions

## Quick Reference
- **Zero New Roles Required**: Strictly extends the existing 5 v1.0 roles (`OWNER`, `MANAGER`, `HOST`, `STAFF`, `VIEWER`) plus unauthenticated **Public Customer** access restricted exclusively to `/m/:qrToken` (`API-035`) (`DECIDED`).
- **Role Mapping**: "Owners and authorized Admins" map directly to `OWNER` (full org/all venues) and `MANAGER` (assigned venue(s)), matching v1.0's exact authorization model.
- **Enforcement**: Every authenticated Phase 2 endpoint enforces both `get_current_user` (`401`) and `require_venue_role(...)` (`403`) + PostgreSQL RLS (`app.current_org_id`).

---

## 1. Phase 2 Permission Matrix (Additive to v1.0 Matrix)

Legend: `Y` = Allowed, `N` = Denied (`403 AUTH_FORBIDDEN`), `C` = Conditional (see notes).

| Phase 2 Capability / Resource | `OWNER` | `MANAGER` | `HOST` | `STAFF` | `VIEWER` | Public (QR Diner) | Enforcement Layer |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| View Table Configuration List (`SCR-017`) | Y | Y | Y (read) | N | Y (read) | N | API RBAC + RLS |
| Create / Edit / Rename / Deactivate / Delete Tables | Y | Y | N | N | N | N | API RBAC + Audit |
| Bulk Create / Bulk Update Tables | Y | Y | N | N | N | N | API RBAC + Audit |
| View Menus, Categories & Items (Admin View `SCR-018`) | Y | Y | Y (read) | Y (read) | Y (read) | N | API RBAC + RLS |
| Create / Edit / Reorder / Delete Menus & Categories | Y | Y | N | N | N | N | API RBAC + Audit |
| Create / Edit / Duplicate / Delete Menu Items | Y | Y | N | N | N | N | API RBAC + Audit |
| Upload / Delete Menu Images & Venue Logo | Y | Y | N | N | N | N | API RBAC + Audit |
| Toggle Item Availability ("Quick 86 / Sold Out") | Y | Y | C¹ | N | N | N | API RBAC + Audit |
| Publish / Unpublish Venue Digital Menu & Currency | Y | Y² | N | N | N | N | API RBAC + Audit |
| View Table QR Codes & Download SVG/PNG/PDF (`SCR-020`) | Y | Y | Y³ | N | N | N | API RBAC + RLS |
| Regenerate / Revoke Table QR Codes | Y | Y | N | N | N | N | API RBAC + Audit |
| View QR Daily Scan Counts | Y | Y | N | N | Y | N | API RBAC + RLS |
| Browse Public Digital Menu (`/m/:qrToken`, `SCR-022`) | Y | Y | Y | Y | Y | **Y** | Public Token + Rate Limit |

### Conditional Notes
- `C¹`: `HOST` can toggle `is_available` (Quick 86) ONLY if the venue setting `allow_host_menu_availability == true` (`PROPOSED`, default `false` — keeps strict Owner/Manager control unless explicitly delegated).
- `Y²`: `MANAGER` can toggle `menu_public_enabled` and `show_unavailable_items_public` for their assigned venue; changing venue `currency_code` is restricted to `OWNER` (`PROPOSED` — prevents accidental currency symbol mismatches).
- `Y³`: `HOST` can view/download an existing table's QR PNG (e.g., to reprint a damaged table sticker at the host stand) but CANNOT regenerate or revoke QR codes.

---

## 2. Explicit Isolation Guarantees for Public QR Customers
1. **No Session Elevation**: Scanning `/m/:qrToken` NEVER sets an auth cookie, NEVER issues a JWT, and NEVER grants access to any `/api/v1/venues/*`, `/api/v1/org/*`, or `/api/v1/ws/*` route.
2. **Logged-In Staff Scanning a QR**: If an authenticated `OWNER`/`MANAGER` opens `/m/:qrToken` on their phone to test it, the public route still calls `/api/v1/public/menu/{qr_token}` without sending Bearer credentials — ensuring the exact same payload diners see.
3. **RBAC Config Sync**: If the repository uses a centralized RBAC manifest (e.g., `packages/rbac/matrix.yaml`), add all Phase 2 permission keys (`tables:manage`, `menu:read`, `menu:manage`, `menu:availability`, `qr:read`, `qr:regenerate`) there so backend FastAPI guards and frontend UI visibility checks stay 100% synchronized.

---

## 3. New Audit Log Action Constants (`audit_logs.action`)
Every mutating Phase 2 action appends an immutable row to existing `audit_logs` with `before_json`, `after_json`, `actor_user_id`, and `ip_address`:
- `TABLE_CREATED`, `TABLE_BULK_CREATED`, `TABLE_UPDATED`, `TABLE_DEACTIVATED`, `TABLE_DELETED`
- `MENU_CREATED`, `MENU_UPDATED`, `MENU_DELETED`, `MENU_PUBLISH_TOGGLED`
- `CATEGORY_CREATED`, `CATEGORY_UPDATED`, `CATEGORY_REORDERED`, `CATEGORY_DELETED`
- `MENU_ITEM_CREATED`, `MENU_ITEM_UPDATED`, `MENU_ITEM_AVAILABILITY_CHANGED`, `MENU_ITEM_DELETED`
- `MENU_MEDIA_UPLOADED`
- `QR_REGENERATED`, `QR_REVOKED`, `QR_BATCH_PDF_EXPORTED`


---

## 4. Single Source of Truth & Public Route Registry Enforcement
- All Phase 2 role permissions are appended to `packages/rbac/matrix.yaml` (single source of truth inherited from v1.0).
- The FastAPI route-policy completeness test MUST allow `policy="public"` **exclusively** on `/api/v1/public/menu/{qr_token}` (plus existing v1.0 public auth/health routes); any other unauthenticated Phase 2 route fails CI.
- Destructive or high-impact Phase 2 actions (`QR_REGENERATED` with `reason=COMPROMISED`, bulk QR regeneration, `CURRENCY_OVERRIDE`, force-deleting an occupied table) require explicit confirmation and write immutable `audit_logs` records with `before_json` and `after_json`.
