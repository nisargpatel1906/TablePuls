# 08 — Security & Privacy Requirements

> **Quick reference**
> - Security baseline: **OWASP ASVS L2** as checklist; argon2id; access token in memory + HttpOnly refresh cookie; deny-by-default RBAC + Postgres RLS; secrets only in env/secret files; strict CORS; rate limits; append-only audit.
> - Privacy baseline: **no face recognition or biometrics, no audio, no demographic inference, no raw video at rest, face blur on every frame that leaves the vision process, minimal PII (waitlist phone optional, encrypted, auto-purged).**
> - This document does **not** give legal conclusions. Legal/regulatory items are `PROFESSIONAL REVIEW`.
> - Labels: `PROPOSED` unless marked.

## 1. Assets, actors, entry points

| Assets | Actors | Entry points |
|---|---|---|
| Camera credentials/streams (S1), user accounts & hashes (S2), waitlist PII (S2), tables/analytics (S3), model artifacts (integrity), audit log (integrity), secrets (`SECRET_KEY`, DB URL, SMTP) | Unauthenticated internet user, malicious/curious staff, compromised account, malicious camera/RTSP server, malicious uploaded file/model, supply-chain attacker, insider admin | Login/reset/invite endpoints; REST/WS API; file uploads (logo, layout JSON, video demo, model manifest); RTSP URLs (SSRF); webhook URLs (SSRF); dependencies/images; Docker host |

## 2. Authentication & sessions
- Passwords: min 12 chars, zxcvbn ≥ 3, argon2id (memory ≥ 64 MiB, t=3, p=1 or OWASP-current), pepper optional via env. Constant-time compare; uniform error messages.
- Lockout/rate limit per account and IP (`docs/03-functional-requirements.md` (`FR-001`–`FR-003`)). Credential-stuffing: add exponential delay after 3 fails.
- Access JWT 15 min, in memory only; refresh opaque 256-bit token stored **hashed** (SHA-256) server-side; rotation + reuse detection; cookie `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`.
- TOTP (RFC 6238, 30 s, ±1 step), secrets AES-GCM encrypted; recovery codes hashed (argon2id); 2FA enforceable by org policy; re-auth for sensitive actions.
- Session revocation propagates ≤ 60 s (perm_version + Valkey cache).
- Password reset/invite tokens: 256-bit random, hashed at rest, single-use, expiring.

## 3. Authorization
See `docs/04-rbac-and-access-control.md`. Deny-by-default; permission registry; RLS; 404 for cross-tenant; WebSocket per-topic checks; API-key scope subset rule; re-auth for sensitive actions.

## 4. Secrets management

| Secret | Location | Rotation | Access | Logging rule |
|---|---|---|---|---|
| `TABLEPULSE_SECRET_KEY` (JWT signing/HMAC) | env / Docker secret | 90 d or on compromise; supports 2 active keys (`kid`) | api only | never logged |
| `TABLEPULSE_DATA_KEY` (envelope KEK for camera creds, TOTP, phone) | env / Docker secret | Rotate with `tablepulse admin rotate-keys` (re-wraps DEKs) | api, vision (decrypt camera creds only) | never logged |
| `DATABASE_URL` (separate roles: `tp_api`, `tp_cv`, `tp_jobs`, `tp_migrate`) | env | 180 d | each service its own role | masked |
| SMTP credentials, VAPID keys, webhook secrets | env / DB-encrypted (webhook secret) | On compromise / 365 d | api/jobs | masked |
| Camera credentials | DB, encrypted (AES-256-GCM envelope) | On demand (rotate endpoint) | decrypt only in vision at connect time | never logged; URL logged with creds stripped |
Repo rules: `.env` ignored by git; `deploy/env.example` has placeholders only; `gitleaks` in pre-commit and CI; startup refuses to run in production with default/placeholder secrets (`TABLEPULSE_ENV=production` self-check).

## 5. Encryption

| Where | Requirement |
|---|---|
| In transit | HTTPS only (Caddy; HSTS 1 y; TLS ≥ 1.2). Internal service traffic on private Docker network; DB/Valkey **not published** to host. RTSPS recommended; plain RTSP allowed on LAN with warning in UI |
| At rest | Disk encryption recommended (documented); field-level encryption for S1/S2 fields (camera creds, TOTP, phone) |
| Backups | Encrypted (age/GPG) before leaving host; key stored separately |

## 6. Input validation & uploads
- All inputs validated by Pydantic with length/range/regex limits; reject unknown fields (`extra='forbid'`).
- Uploads: allow-listed MIME **and** magic bytes; logo PNG/SVG (SVG sanitized, no scripts) ≤ 512 KB; layout JSON ≤ 1 MB schema-validated; demo video ≤ 200 MB via CLI only; model files only via CLI/registry with SHA-256; **never unpickle** untrusted files (`torch.load` only with `weights_only=True`; prefer ONNX/safetensors).
- **SSRF controls:** camera and webhook hosts resolved server-side; block loopback, link-local (`169.254.0.0/16`, `fe80::/10`), cloud metadata IPs, and (for webhooks) private ranges unless `ALLOW_PRIVATE_WEBHOOK_HOSTS=true`; re-resolve at connect time (DNS-rebinding guard); limit redirects; timeouts (connect 5 s, read 10 s).
- Output encoding: React escaping; no `dangerouslySetInnerHTML` (lint rule); CSV export neutralises formula injection (`=,+,-,@` prefixed with `'`).
- SQL: parameterised queries only (ORM); no string-built SQL (semgrep rule).

## 7. Network exposure
- Only the reverse proxy publishes ports (80/443). DB, Valkey, api, workers live on a private Docker network; `/metrics` is reachable only from that network or with an API key.
- Cameras should sit on a separate VLAN/subnet; the vision worker is the only service that needs a route to them. Document firewall rules in `docs/runbooks/network.md`.
- Remote access for the venue: VPN or an authenticated tunnel; never expose camera RTSP ports to the internet.
- Default admin/service accounts do not exist; first-run setup is one-time (`FR-001`).

## 8. Web security headers & CORS
`Content-Security-Policy` (default-src 'self'; img-src 'self' data: blob:; connect-src 'self' wss:; frame-ancestors 'none'), `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy` (camera/mic/geolocation denied), cookie flags as above. CORS allow-list only; WebSocket `Origin` check.

## 9. Abuse controls
Rate limits (`docs/06-data-model-and-api.md`); body size caps; WebSocket subscription caps; account enumeration protection; export rate limit; invite spam limit (20/day/admin); webhook auto-disable; Celery task time limits.

## 10. Logging hygiene
Structured JSON; fields: `ts, level, service, request_id, user_id (uuid), org_id, venue_id, route, status, latency_ms`. **Never log:** passwords, tokens, cookies, `Authorization` headers, camera URLs with credentials, TOTP codes, full phone numbers, frame data. Scrubbing middleware + unit test with canary secrets. Error tracking (optional) uses `before_send` scrubbing.


### MediaMTX & Live Stream Security (`DECIDED`)
- MediaMTX strips all audio tracks at ingest and holds stream buffers in RAM only (zero disk recording).
- Browser WebRTC (`WHEP`) playback requires a short-lived signed stream token validated by MediaMTX's external auth hook (`POST /api/v1/internal/media-auth`), enforcing `OWNER`/`MANAGER` (or `HOST` only when `venue.allow_host_camera_view == true`).
- Face blurring runs inside `cv-worker` before any review crop is written to disk; **if face blur fails, the frame is dropped immediately** (never saved unblurred).

## 11. Privacy by design

### 11.1 Data we process
| Data | Purpose | Stored? | Retention |
|---|---|---|---|
| Video frames | Inference | **In memory only**; discarded after processing | — |
| Blurred annotated frames | Live view | Valkey ≤ 5 s TTL | 5 s |
| Evidence snapshots (optional, off) | Incident review | Disk, blurred | ≤ 72 h |
| Review crops (blurred) | Human labelling | Disk | 14 d |
| Table states, sessions, counts | Operations/analytics | DB | 400 d (rollups 5 y) |
| Track IDs | Tracking | Memory only | seconds |
| Staff/customer class | Cleaning logic | Not stored per person; only aggregates | — |
| Waitlist name/phone/notes | Manage queue | DB (phone encrypted) | 30 d |
| User account data | Operate app | DB | Until deletion |
| Audit log | Accountability | DB | 400 d |

### 11.2 Hard prohibitions (enforced by code review + CI checks)
No face detection used for **recognition**; no face/gait/appearance **embeddings** persisted or used for re-identification across time beyond a single tracking session; no demographic attribute inference (age, gender, ethnicity, emotion, disability); no audio; no per-individual staff metrics; no data sale/sharing. CI: dependency allow-list excludes face-recognition libraries; grep rule for `face_recognition|insightface|deepface|arcface`; model cards must state "no biometric processing".
*(Face **blurring** uses a face/head-region detector only to obscure pixels; its outputs are not stored.)*

### 11.3 Transparency & notices
Provide templates in `docs/templates/`: CCTV signage text (EN/HI), staff notice/consent-or-notice template, customer privacy notice, data-processing summary. Setup wizard final step requires acknowledging that the venue operator is responsible for lawful notices. `PROFESSIONAL REVIEW`: which legal basis, notice wording, employee-monitoring rules and retention periods apply per jurisdiction (e.g., India's DPDP Act/Rules, GDPR, local CCTV/labour laws).

### 11.4 Data subject rights tooling
User accounts: export + delete (`FR-003`). Customers are not identified by the system; waitlist entries purge automatically and can be deleted on request by staff with `HOST`/`MANAGER`/`OWNER`. Document the process in `docs/privacy.md`.

### 11.5 Data contributed for model improvement
Opt-in only (`OWNER`), blurred crops + labels + metadata, no raw video; manifest records consent basis, venue, date; contributors can revoke → export pipeline removes their items from future dataset versions (past released versions remain; documented). `PROFESSIONAL REVIEW` for consent wording and licensing of contributed data.

## 12. Supply chain & build security
Pin dependencies via lockfiles; Dependabot/Renovate; `pip-audit`, `osv-scanner`, `trivy image`; SBOM (CycloneDX) generated per release; images built reproducibly, non-root user, read-only filesystem where possible, `cap_drop: ALL`, healthchecks; signed release tags and container signatures (cosign) — `Should`. GitHub Actions: least-privilege `permissions:`, pinned action SHAs, no secrets in PR builds from forks.

## 13. Pre-release security checkpoints (all must pass)
1. ASVS L2 checklist reviewed with evidence links (`docs/security/asvs.md`).
2. Zero critical/high findings in dependency, image and SAST scans.
3. RBAC matrix and RLS tests pass; policy-completeness test passes.
4. Pen-test style checks run (OWASP ZAP baseline against Compose stack): no high alerts.
5. Secret scan clean on full git history.
6. Privacy checks: disk scan shows no raw frames; blur self-test passes; logs scrubbed test passes.
7. `SECURITY.md` published with disclosure process; first release has a named security contact.
8. `PROFESSIONAL REVIEW` items in `decision-log-and-reviews.md` have an owner and status (does **not** need resolution to ship `0.x`; **must** be addressed before declaring `1.0`).

## 14. Incident response (minimal)
Runbook `docs/runbooks/security-incident.md`: rotate secrets, revoke sessions (`tablepulse admin revoke-all`), preserve audit logs, notify affected users per policy (legal review), publish advisory (GitHub Security Advisories).

## 15. Related documents
`04-rbac-and-access-control.md` · `06-data-model-and-api.md` · `09-reliability-and-ops.md` · `decision-log-and-reviews.md`
