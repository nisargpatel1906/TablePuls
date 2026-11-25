# TablePulse — Testing Strategy & Release Criteria

## Quick Reference
- **Core Testing Philosophy** (`DECIDED` — from `production-ready-vibe-coding`): AI coding agents default to happy-path code. Every feature is **not done** until the agent tests valid inputs, bad inputs, unauthorized access, and verifies actual PostgreSQL database state directly — looping fix -> re-test until all pass.
- **Test Pyramid**: Unit tests (`pytest`, `vitest`), API Integration + DB State Verification (`pytest` + real Postgres/Valkey test containers), Frontend E2E (`Playwright`), CV/ML Evaluation Gate (`ml/evaluate_gate.py`), and Failure-Injection tests.
- **Release Gate**: No v1.0 release ships unless automated software tests pass 100%, zero critical/high security findings remain, and the ML release gate publishes verified metrics from the held-out benchmark test set.

---

## 1. Test Layers & Pass Criteria

| Layer | Tools | Scope & Specific Checks | Pass Criteria |
|---|---|---|---|
| **Backend Unit** | `pytest`, `hypothesis` | Table state machine transitions, debounce timers, polygon self-intersection geometry, Argon2id/JWT helpers, SSRF validator, log scrubber. | 100% pass; `>= 85%` branch coverage on state machine & auth modules. |
| **Backend Integration + DB Verification** | `pytest`, `httpx.AsyncClient`, Testcontainers (PostgreSQL 16, Valkey) | Every single endpoint (`API-001`–`API-023`) tested with: (1) valid payload + **direct SQL check confirming DB state mutated correctly**, (2) missing/wrong-type/out-of-bounds fields (`400`), (3) unauthenticated (`401`), (4) wrong role & cross-org tenant (`403`), (5) optimistic-lock conflict (`409`). | 100% of endpoints covered; 0 unhandled `500`s on bad inputs. |
| **Frontend Unit & Component** | `Vitest`, React Testing Library | Floor map filtering/search, polygon editor vertex validation, loading/error/success states on all forms, WebSocket-to-polling fallback hook. | 100% pass; 0 TypeScript strict errors. |
| **Frontend E2E & Responsive** | `Playwright` | Full journeys: Bootstrap -> Onboarding (`SCR-004`) -> Demo Video Live Floor (`SCR-005`) -> Manual Override (`SCR-007`) -> Alert Ack (`SCR-008`) -> Waitlist Seat (`SCR-009`) -> Analytics CSV (`SCR-010`) -> Kill Switch (`SCR-016`). Direct-URL navigation tested on all 16 routes (zero 404s). | 100% pass across 360px, 768px, 1280px viewports; 0 uncaught browser console errors. |
| **Accessibility Audit** | `axe-core` (Playwright) | Automated WCAG 2.1 AA scan across all 16 screens + keyboard-only navigation on `SCR-005` list view and modals. | 0 critical or serious `axe-core` violations. |
| **Failure-Injection** | `pytest` + Docker Compose chaos script | (1) Kill RTSP source -> verify `UNKNOWN` + `CAMERA_OFFLINE` alert + auto-reconnect within 30s; (2) Kill Valkey -> verify UI falls back to 5s polling; (3) Toggle Kill Switch -> verify CV worker halts within 5s while manual floor mode works; (4) Webhook endpoint returns `500` -> verify 3 retries + circuit breaker without blocking floor updates. | All 4 chaos scenarios recover cleanly. |
| **ML Evaluation Gate** | `ml/evaluate_gate.py` | Frozen held-out multi-venue test set evaluation comparing Baselines B1–B3 vs. candidate models across all subgroups with 95% CIs. | Meets Section 2 gates in `07-ml-spec-and-evaluation.md` (TSM-F1 >= 90% with lower 95% cluster-bootstrap CI >= 85%, Guest MAE <= 0.35, Dirty F1 >= 90%, subgroup floor >= 82%). |

---

## 2. Production Readiness Requirements (`DECIDED` — Mandatory for Coding Agent)

### Error Handling
- Every endpoint returns `{ success: true, data }` or `{ success: false, error: { code, message, fields? } }`.
- Validation errors return `400` with field-level details, never a generic `500`.
- Every DB call and external stream/webhook call is wrapped cleanly; malformed input may never crash the server.

### Security
- Authentication (`401`) and authorization (`403`) are implemented and tested as separate checks on every endpoint.
- Secrets live strictly in `.env` / platform env vars — verified by `gitleaks` in CI.
- CORS locked to `ALLOWED_ORIGINS`; PostgreSQL/Valkey isolated to internal Docker network; RLS enabled on multi-tenant tables.
- Refresh tokens in `HttpOnly; Secure; SameSite=Strict` cookies; access tokens in memory only.

### Frontend Resilience
- Every async user action implements visible **Loading**, **Error** (inline/toast), and **Success** states — zero silent failures.
- Action buttons reset cleanly after completion (no "works only on first click" bugs).
- Direct-URL navigation works on all 16 routes without 404s.

---

## 3. Release Criteria (Go / No-Go Checklist for v1.0)
A release candidate is marked **GO** only when ALL of the following are verified and recorded:
1. [ ] All CI pipelines green (`lint`, `typecheck`, `backend-unit`, `backend-integration`, `frontend-e2e`, `axe-a11y`, `gitleaks`).
2. [ ] Fresh-clone smoke test: `git clone` -> `cp .env.example .env` -> `docker compose up -d` with `DEMO_MODE=true` reaches a live annotated floor map on `SCR-005` in `<= 15 minutes`.
3. [ ] All 4 failure-injection scenarios pass on the release candidate image.
4. [ ] ML benchmark report (`docs/benchmarks/v1.0-eval-report.md`) generated by `ml/evaluate_gate.py` on the frozen multi-venue test split meets all numeric gates (or any unmet gate is explicitly documented as a beta/experimental disclaimer — never hidden or faked).
5. [ ] `LICENSE` (Apache-2.0), `NOTICE`, `SECURITY.md`, `CONTRIBUTING.md`, and `.env.example` are present and audited against third-party dependency licenses (`pip-licenses` + `license-checker` showing zero AGPL/GPL contamination).
6. [ ] Backup and restore test executed successfully on a fresh PostgreSQL 16 container.


### Additional Security, Privacy & License Gates (Ported from ASVS L2 Checklist)
- **License Gate (`scripts/license_check.py`)**: CI fails on any AGPL/GPL/TSL/SSPL/Roboflow-PML dependency (including Ultralytics or restricted RF-DETR sizes).
- **Privacy Self-Test**: Automated check confirms zero raw frames on disk, face-blur failure drops the frame instead of saving unblurred, and log-scrubbing canary test strips secrets & RTSP passwords.
- **Security Baseline**: OWASP ASVS L2 self-review checklist (`docs/security/asvs.md`), OWASP ZAP baseline scan (0 high alerts), and `make restore-test` verifying backup/restore into a clean PostgreSQL 16 container.
- **Professional Review Gate**: All 12 items in `docs/decision-log-and-reviews.md` (`PR-01`–`PR-12`) have an assigned owner and recorded status before declaring `v1.0` (0.x prototypes may proceed with `Open` items documented).
