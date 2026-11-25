# TablePulse — Roles, Permissions & Access Control Specification

## Quick Reference
- **Auth Model**: Email + Argon2id password authentication; short-lived JWT access token (15 min, returned in JSON body, kept in memory only on frontend) + rotating refresh token in `HttpOnly; Secure; SameSite=Strict` cookie (7 days). (`PROPOSED`)
- **Authorization Model**: Role-Based Access Control (RBAC) + Multi-Tenant Organization & Venue Scoping enforced strictly in FastAPI dependencies (never UI-only). (`DECIDED`)
- **Roles (5)**: `OWNER`, `MANAGER`, `HOST`, `STAFF`, `VIEWER`.

---

## 1. Authentication vs. Authorization Separation
Per production security best practices, **authentication** ("who are you?") and **authorization** ("are you allowed to perform this action on this specific venue/resource?") are implemented as separate FastAPI dependency layers:
1. `get_current_user`: Validates JWT signature (`HS256`/`EdDSA`), expiry, `token_type == "access"`, and checks user is `is_active == True`. Failure returns `401 AUTH_UNAUTHORIZED`.
2. `require_venue_role(allowed_roles: set[Role])`: Verifies the authenticated user belongs to the target `organization_id`, has access to the requested `venue_id` (owners have access to all org venues; other roles are bound to assigned `venue_ids`), and holds a role in `allowed_roles`. Failure returns `403 AUTH_FORBIDDEN`.
3. **Zero Trust on Client-Provided IDs**: `organization_id` is always derived from the authenticated user record, never trusted from a request body.

---

## 2. Role Definitions (`PROPOSED`)

| Role | Scope | Typical Persona | Default Landing Screen |
|---|---|---|---|
| `OWNER` | Entire Organization (all venues) | Restaurant Owner / IT Admin | `SCR-005` (or `SCR-004` on first run) |
| `MANAGER` | Assigned Venue(s) | Shift / Floor Manager | `SCR-005` |
| `HOST` | Assigned Venue(s) | Front-of-House Host / Receptionist | `SCR-005` |
| `STAFF` | Assigned Venue(s) | Server / Waiter / Busser | `SCR-008` |
| `VIEWER` | Assigned Venue(s) or Org | Ops Analyst / Auditor | `SCR-010` |

---

## 3. Granular Permission Matrix

Legend: `Y` = Allowed, `N` = Denied (`403`), `C` = Conditional (see notes).

| Capability / Resource | `OWNER` | `MANAGER` | `HOST` | `STAFF` | `VIEWER` | Enforcement Layer |
|---|:---:|:---:|:---:|:---:|:---:|---|
| View Live Floor Map (`SCR-005`) | Y | Y | Y | Y | Y | API + WS Auth |
| View Live Camera Wall (`SCR-006`) | Y | Y | C¹ | N | N | API + MediaMTX JWT |
| Mark Table Clean / Service Attended (`SCR-007`/`008`) | Y | Y | Y | Y | N | API RBAC |
| Manual Table Override (Reserved/Occupied/Guest Count) | Y | Y | Y | N | N | API RBAC + Audit |
| Flag Incorrect AI Detection | Y | Y | Y | Y | N | API RBAC |
| View & Manage Waitlist (`SCR-009`) | Y | Y | Y | N | N | API RBAC |
| View Peak Hours Analytics & Export CSV (`SCR-010`) | Y | Y | N | N | Y | API RBAC |
| Review ML Queue & Export Labeled Crops (`SCR-011`) | Y | Y² | N | N | N | API RBAC |
| Add/Edit/Delete Cameras & RTSP Credentials (`SCR-012`) | Y | Y | N | N | N | API RBAC + Audit |
| Edit Table Polygons & Floor Map Layout (`SCR-013`) | Y | Y | N | N | N | API RBAC + Audit |
| Edit Alert Thresholds & Webhooks (`SCR-014`) | Y | Y | N | N | N | API RBAC + Audit |
| Invite/Manage `HOST`, `STAFF`, `VIEWER` (`SCR-015`) | Y | Y | N | N | N | API RBAC + Audit |
| Invite/Manage `OWNER` or `MANAGER` (`SCR-015`) | Y | N | N | N | N | API RBAC + Audit |
| View Audit Logs (`SCR-015`) | Y | Y³ | N | N | N | API RBAC |
| System Health, Model Registry, Kill Switch (`SCR-016`) | Y | N | N | N | N | API RBAC + Audit |
| Privacy Retention & Purge Snapshots (`SCR-016`) | Y | N | N | N | N | API RBAC + Audit |

**Conditional Notes**:
- `C¹`: `HOST` can view live camera streams only if `venue.allow_host_camera_view == true` (default: `false` to minimize unnecessary CCTV exposure).
- `Y²`: `MANAGER` can label/review items in `SCR-011`; only `OWNER` can export the bulk training dataset archive.
- `Y³`: `MANAGER` can view audit logs scoped only to their assigned venue(s); `OWNER` sees organization-wide audit logs.

---

## 4. Token, Session & WebSocket Security Rules (`PROPOSED`)

| Mechanism | Specification | Rationale |
|---|---|---|
| **Password Hashing** | Argon2id (`time_cost=3`, `memory_cost=65536`, `parallelism=4`) | Resistant to GPU/ASIC cracking; OWASP recommended. |
| **Access Token** | JWT, 15-minute TTL, signed with `JWT_SECRET` (>=256-bit random env var). Stored in React memory state only. | Short blast radius; immune to `localStorage` XSS theft. |
| **Refresh Token** | 32-byte cryptographically random opaque token, stored SHA-256 hashed in `refresh_tokens` table, sent only via `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth` cookie (7-day TTL). | JavaScript cannot read cookie; supports instant server-side revocation and reuse detection. |
| **Refresh Token Rotation** | Every `/auth/refresh` issues a new refresh token and marks the old one `revoked_at`. Presenting an already-revoked token revokes the entire `token_family_id` and forces re-login. | Detects stolen refresh token replay immediately. |
| **WebSocket Auth** | Client requests a short-lived (60s) single-use WS ticket via `POST /api/v1/auth/ws-ticket` (authenticated with Bearer token), then connects to `/api/v1/ws/venues/{venue_id}?ticket=...`. | Avoids putting long-lived JWTs in URL query strings/server logs. |
| **MediaMTX Stream Auth** | MediaMTX external auth hook calls `POST /api/v1/internal/media-auth` verifying a short-lived signed stream token issued only to authorized users. | Prevents unauthorized LAN users from pulling camera streams directly from MediaMTX. |

---

## 5. Account Lifecycle & Recovery Flows
1. **Bootstrap (`OWNER`)**: Available only when `SELECT count(*) FROM users` equals `0`. Creates org + first owner atomically inside a DB transaction.
2. **Invitation**: Admin submits `{ email, role, venue_ids }`. Backend generates invite token (48h TTL), emails invite link (or displays copyable invite URL in UI when SMTP is unconfigured in self-hosted mode!).
3. **Password Reset**: `POST /api/v1/auth/forgot-password` always returns `200` with generic message. When SMTP is configured, sends 30-min single-use reset link. In air-gapped self-hosted deployments without SMTP, an `OWNER` can generate a one-time reset link for a staff member from `SCR-015` (logged in `audit_logs`).
4. **Deactivation & Immediate Revocation**: Disabling a user (`is_active=false`) immediately revokes all rows in `refresh_tokens` for that user, disconnects active WebSockets via Redis Pub/Sub `user.revoked` event, and blocks all subsequent requests within <=15 min (or immediately if token JTI denylist is checked in Redis).
5. **Last-Owner Protection**: Database trigger and service check prevent deleting, disabling, or demoting the last active `OWNER` in an organization (`409 LAST_OWNER_PROTECTED`).

---

## 6. Cross-Tenant & Row-Level Isolation
- All multi-tenant tables include `organization_id` (and `venue_id` where venue-scoped).
- Every repository query filters explicitly by `organization_id = current_user.organization_id` and `venue_id IN current_user.allowed_venue_ids`.
- PostgreSQL Row-Level Security (RLS) policies are enabled on `venues`, `cameras`, `tables`, `alerts`, `waitlist_entries`, `ml_review_items`, and `audit_logs` as defense-in-depth (`SET LOCAL app.current_org_id = ...` per DB transaction).
- Automated security integration tests verify that a user from Org A cannot read, mutate, or subscribe via WebSocket to any resource in Org B (expecting `403` or `404`).


---

## 7. Single Source of Truth & Policy Completeness (`DECIDED`)
- The permission matrix above is encoded once in `packages/rbac/matrix.yaml` and loaded by the FastAPI RBAC dependency layer (with generated TypeScript types for frontend nav gating).
- A mandatory startup & CI **policy-completeness test** verifies that every non-public route in the FastAPI OpenAPI schema explicitly declares a `require_venue_role(...)` or `require_org_role(...)` dependency—unprotected routes fail CI.
- Sensitive actions (`TOGGLE_KILL_SWITCH`, `PURGE_SNAPSHOTS`, `ACTIVATE_MODEL`, role elevation to `OWNER`) write immutable `audit_logs` records with `before_json` and `after_json`.
