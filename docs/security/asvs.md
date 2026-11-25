# Security Verification Summary (OWASP ASVS Level 2 Controls)

| Control Area | Verification Evidence | Implementation |
|---|---|---|
| **V2 Authentication** | Argon2id password hashing, HttpOnly SameSite=Strict refresh tokens with rotation & reuse family revocation, optional TOTP MFA, per-IP/account fail-closed login throttling | `backend/app/core/security.py`, `backend/app/api/auth.py` |
| **V3 Session Management** | In-memory-only JWT access tokens (`15 min`), short-lived single-use WS/stream tickets (`60s`–`120s`), session revocation (`revoke-sessions` + Valkey revocation epoch) | `frontend/src/lib/api.ts`, `backend/app/core/valkey_client.py` |
| **V4 Access Control** | Dual AuthN (`get_current_user`) + AuthZ (`require_venue_role`/`require_org_role`) over `packages/rbac/matrix.yaml`; PG16 RLS isolation (`tp_rls_tester` tested); LAST_OWNER trigger; OpenAPI policy-completeness check | `backend/app/core/rbac.py`, `backend/alembic/versions/0001_initial_schema.py`, `backend/tests/test_auth_and_rbac.py` |
| **V5 Validation & SSRF** | Strict Pydantic v2 field validation, server-side geometry self-intersection guard, SSRF private/loopback IP blocking on camera & webhook URLs, CSV formula injection escaping | `backend/app/core/{ssrf.py,geometry.py}`, `backend/app/api/waitlist_analytics.py` |
| **V6 Cryptography** | AES-256-GCM encryption at rest (`TABLEPULSE_DATA_ENCRYPTION_KEY`) for RTSP URLs, camera credentials, webhook URLs/secrets, waitlist phones, and TOTP secrets | `backend/app/core/security.py` |
| **V14 Privacy & Hygiene** | Secret log scrubbing verified with canary test; mandatory face blur-or-drop pipeline; automated snapshot purge & manual OWNER immediate purge; CI license allowlist & secret scanner | `backend/app/core/{logging.py,privacy.py}`, `scripts/{license_check.py,secret_scan.py}` |
