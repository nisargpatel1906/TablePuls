# TablePulse — Autonomous Agent Build Plan, Conventions & Prompts

## Quick Reference

* **Target Agent**: Antigravity (or Claude Code / Cursor / Windsurf) executing autonomously in ordered, verifiable stages.

* **Working Method**: Execute **one stage at a time**, run the exact verification command + DB/UI check, fix any failures in a loop before advancing, and stop immediately if a Stop Condition is hit.

* **UI Reference Rule**: Before building any screen (`SCR-001`–`SCR-016`), inspect the `UI/` folder for matching visual assets (`UI/SCR-XXX-*.png`). Match visual styling from `UI/` while strictly implementing every control, state, and accessibility rule from `02-ui-screens.md`.

## 1. Standing Agent Conventions (`16b-agent-conventions`)

1. **Strict Types & Validation**: TypeScript `strict: true` everywhere in `frontend/`; Python 3.12 type hints + Pydantic v2 + `mypy --strict` in `backend/` and `cv-worker/`.

2. **Unified API Envelopes**: Every REST endpoint returns `{ "success": true, "data": ... }` or `{ "success": false, "error": { "code": "...", "message": "...", "fields": {...} } }`. Never return raw FastAPI/SQLAlchemy tracebacks.

3. **Separate AuthN & AuthZ**: Every protected route uses both `get_current_user` (`401`) and `require_venue_role(...)` (`403`). Never trust `organization_id` from request bodies.

4. **Secrets & `.gitignore` First**: Commit `.gitignore` and `.env.example` in Stage 0 before writing any application code. Never hardcode `localhost` URLs, JWT secrets, or RTSP credentials.

5. **Apache-2.0 License Cleanliness**: Never install `ultralytics` or any AGPL/GPL package. Use `rfdetr` Nano/Small/Medium/Large ONLY (Apache-2.0; ban Atto/Femto/Pico/XL/2XL), `onnxruntime` (MIT), `supervision`/`bytetrack` (MIT), `opencv-python-headless` (Apache-2.0), `lightgbm` (MIT).

6. **Mandatory Test-and-Verify Loop**: Never mark a stage done until tests pass AND database writes are verified directly via SQL/assertions AND bad inputs (`400`/`401`/`403`/`404`/`409`) are tested.

7. **Auto-Update API Docs**: Whenever an endpoint is added or modified, regenerate/update `docs/api-reference.md` (or OpenAPI schema) in the same commit.

## 2. Decisions the Agent May NOT Make Alone (Stop Conditions)

The coding agent MUST stop, report clearly, and wait for human confirmation if a step requires:

* Adding/removing a database table, column, constraint, or delete behavior not in `06-data-model-and-api.md`.

* Adding a paid external service or any non-permissive (GPL/AGPL/proprietary) dependency.

* Weakening authentication, RBAC, RLS, encryption, face-blur defaults, or the fail-safe AI kill switch.

* Weakening a failing test or lowering an ML release gate threshold (`< 90%` TSM-F1 (or lower 95% CI `< 85%`)) to make CI pass.

* Proceeding after 3 failed verification attempts on the same blocker without an identified root cause.

* Resolving a `PROFESSIONAL REVIEW` item (`PR-01`–`PR-12` in `docs/decision-log-and-reviews.md`).

## 3. Staged Autonomous Build Plan (9 Stages)

### Stage 0 — Repository Scaffold, Docker Compose & Hygiene

* **Deliverables**: Repo directory structure (`frontend/`, `backend/`, `cv-worker/`, `ml/`, `infra/`, `UI/`), `.gitignore`, `.env.example`, `LICENSE` (Apache-2.0), `NOTICE`, `docker-compose.yml` (PostgreSQL 16 (native monthly partitions), Valkey 8, MediaMTX, API, Web, CV Worker, Caddy), GitHub Actions CI skeletons, `Makefile`, `scripts/license_check.py`, `config/license-allowlist.yaml`, and `docs/adr/0001-stack.md` with verified pinned versions.

* **Verification**: `docker compose config` succeeds with 0 warnings; `git status` confirms `.env` is ignored; `gitleaks detect` passes; `scripts/license_check.py` fails on an injected AGPL test dependency.

### Stage 1 — Database Schema, Alembic Migrations & RLS Policies

* **Deliverables**: SQLAlchemy 2.0 async models for all 15 tables (`06-data-model-and-api.md`), initial Alembic migration creating tables, check constraints, indexes, native PostgreSQL 16 monthly range partitioning on `occupancy_snapshots` + scheduled hourly rollup view, and PostgreSQL RLS policies.

* **Verification**: `alembic upgrade head` succeeds on clean PostgreSQL 16 (native monthly partitions) container; `pytest backend/tests/test_schema_and_rls.py` confirms all 15 tables, constraints, and cross-org RLS isolation.

### Stage 2 — Auth, RBAC, Account Lifecycle & Audit Logging (`FR-001`–`FR-003`, `FR-018`)

* **Deliverables**: `API-001`–`API-006`, `API-021` (bootstrap owner, Argon2id login, HttpOnly refresh cookie rotation + reuse detection, logout, password reset, invite links, WS ticket issuer, user management, last-owner protection, immutable `audit_logs`).

* **Verification**: `pytest backend/tests/test_auth_and_rbac.py` tests every role (`OWNER`, `MANAGER`, `HOST`, `STAFF`, `VIEWER`), cross-tenant isolation (`403`), refresh token replay revocation, rate limiting (`429`), and directly queries PostgreSQL to verify `refresh_tokens` and `audit_logs` rows.

### Stage 3 — Venue, Camera Management, Polygon Calibration & MediaMTX Integration (`FR-004`, `FR-005`)

* **Deliverables**: `API-007`–`API-010`, AES-256-GCM encryption for RTSP credentials, MediaMTX config + external auth hook (`POST /api/v1/internal/media-auth`), RTSP/Demo MP4 connection tester returning face-blurred JPEG preview, normalized polygon validator (min 3 vertices, no self-intersection), Valkey Pub/Sub config reload publisher.

* **Verification**: `pytest backend/tests/test_cameras_and_polygons.py` verifies encrypted DB storage (ciphertext != plaintext), polygon validation errors (`400`), and MediaMTX auth rejection for unauthorized tokens.

### Stage 4 — CV Worker & ML Inference Pipeline (`FR-006`–`FR-010`, `ML-01`–`ML-04`)

* **Deliverables**: `cv-worker/` service pulling frames from MediaMTX (or Demo MP4 loop), OpenCV face-blurring filter, RF-DETR ONNX detector wrapper, ByteTrack tracker, table ROI geometry mapper, debounce & service-SLA state machine (`FREE`, `OCCUPIED`, `NEEDS_SERVICE`, `NEEDS_CLEANING`, `UNKNOWN`), cleanliness classifier interface + ONNX runner, LightGBM + Baseline B3 turnover ETA predictor, Valkey Streams event publisher (`tp:cv:events`), kill-switch fail-safe guard (`tp:kill_switch`), and back-pressure frame dropper.

* **Verification**: `pytest cv-worker/tests/` passes deterministic synthetic-video state-machine tests (passerby ignored <10s, seated >10s -> `OCCUPIED`, unattended >5m -> `NEEDS_SERVICE`, departed with dishes -> `NEEDS_CLEANING`, low confidence >30s -> `UNKNOWN`, kill switch off -> 0 events emitted).

### Stage 5 — Floor Operations, Alerts, Waitlist, Analytics & ML Review APIs (`FR-011`–`FR-022`)

* **Deliverables**: `API-011`–`API-020`, `API-022`, `API-023`; Valkey Streams consumer updating `tables`, `table_state_events`, `occupancy_snapshots`, and `alerts`; WebSocket hub (`/api/v1/ws/venues/{v}`); optimistic-lock manual overrides; waitlist & turnover ranking; PostgreSQL 16 partitioned peak-hours analytics + CSV export; SSRF-safe outbound webhooks with HMAC signatures & circuit breaker; ML review queue + anonymized zip export; daily retention purge job.

* **Verification**: Full backend integration suite (`pytest backend/tests/`) passes 100% including DB state checks, concurrency `409` test, SSRF loopback rejection test, and WebSocket event delivery test.

### Stage 6 — Frontend Core Auth, Shell & Operational Screens (`SCR-001`–`SCR-009`)

* **Deliverables**: Next.js 15 app shell, in-memory token refresh interceptor, `UI/README.md` token extraction (`frontend/src/styles/tokens.css`) and `UI/` asset visual alignment, `SCR-001`–`SCR-004` (Auth & Onboarding Wizard), `SCR-005` (Live Floor Map with Konva canvas + accessible HTML table toggle + WS/polling fallback), `SCR-006` (Live Camera Wall via MediaMTX WHEP + SVG polygon overlay), `SCR-007` (Table Detail & Override Drawer), `SCR-008` (Alerts Queue), `SCR-009` (Waitlist & Turnover Queue).

* **Verification**: `pnpm typecheck && pnpm test` passes; every async form/button verified for Loading, Error, and Success states; direct-URL navigation verified on all 9 routes.

### Stage 7 — Frontend Analytics, Calibration & Admin Screens (`SCR-010`–`SCR-016`)

* **Deliverables**: `SCR-010` (Peak Hours charts, heatmap, staffing curve, CSV download, accessible data table toggle), `SCR-011` (ML Review Queue with keyboard shortcuts), `SCR-012` (Camera Management), `SCR-013` (Interactive Polygon & Exclusion Zone Editor), `SCR-014` (Alert Rules & Test Webhook), `SCR-015` (Users, Roles & Audit Log), `SCR-016` (System Health, Model Registry, Kill Switch & Privacy Purge).

* **Verification**: `pnpm playwright test` passes full E2E suite across 360px/768px/1280px viewports + `axe-core` WCAG 2.1 AA audit (0 critical/serious violations) + 0 browser console errors.

### Stage 8 — ML Evaluation Harness, Failure Injection & Release Readiness

* **Deliverables**: `ml/evaluate_gate.py` (leakage-free group-split validator, Baselines B1–B3, subgroup 95% bootstrap CIs, ECE calibration check, hard release gate), chaos/failure-injection test script, dependency license audit (`pip-licenses`, `license-checker`), backup/restore script verification, and `docs/benchmarks/` report template.

* **Verification**: All CI workflows green; failure-injection suite passes 4/4 scenarios; clean-clone `docker compose up -d` Demo Mode smoke test passes end-to-end.

## 4. Copy-Paste Prompts for Antigravity (Testing & Hardening Loops)

### Prompt A — Execute a Build Stage

```
Read README.md and AGENTS.md, docs/12-agent-build-plan.md, and the relevant spec files for Stage {N}.
Inspect the UI/ folder if building frontend screens.
Implement Stage {N} completely, following all standing conventions and stop conditions.
Do not skip error handling, RBAC checks, or loading/error/success UI states.
When finished, run the exact verification commands for Stage {N} and report:
1. Files created/changed
2. Exact verification commands and outputs
3. Spec IDs covered
4. Any deviations or open items
5. Confirmation that no stop-condition decision was made alone.

```

### Prompt B — Mandatory Endpoint Test-Everything Loop (Run After Stages 2, 3, 5)

```
Test every endpoint built in this stage for logic and correctness — not just HTTP 200.
1. Run actual test commands from the terminal.
2. Query PostgreSQL directly to confirm records were created, updated, encrypted, or deleted as specified.
3. Deliberately test bad inputs: missing required fields, wrong data types, out-of-range numbers, unauthenticated requests (401), wrong roles and cross-org IDs (403), and stale version overrides (409).
4. If any case fails or returns a 500, fix it and immediately re-test that exact case before moving on. Loop until 100% pass.

```

### Prompt C — Pre-Release Security & Deployment Sanity Check (Run After Stage 8)

```
Audit the entire repository before release:
1. Verify .gitignore excludes .env, node_modules, .next, dist, snapshots, and IDE folders.
2. Scan for hardcoded secrets or localhost URLs that should come from environment variables.
3. Verify every protected endpoint checks both authentication (401) and authorization (403) plus org/venue scoping.
4. Verify pip-licenses and license-checker report zero AGPL/GPL packages in core dependencies.
5. List every required environment variable and confirm it is documented in .env.example.
Fix any issues found and re-run the test suite.

```

## 5. Reporting Format After Each Completed Stage

1. **Deliverable**: Exact files created or modified.

2. **Verification**: Exact commands executed and pass/fail outputs.

3. **Traceability**: `FR-XXX`, `SCR-XXX`, `API-XXX`, `ML-XX` IDs satisfied.

4. **Deviations**: Any deviation from spec and its reason.

5. **Progress File**: Write this report to `docs/progress/S<n>.md`.

6. **Open Items**: Any newly discovered issues (blocking vs. non-blocking).

7. **Stop-List Check**: Explicit confirmation that no restricted decision was made unilaterally.
