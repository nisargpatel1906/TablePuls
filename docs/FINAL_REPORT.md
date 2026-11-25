# TablePulse — Final Hand-Off Report (`v1.0.0-rc.1`)

- **Date:** 2026-11-25
- **Repository:** `https://github.com/nisargpatel1906/TablePuls.git` (branch `main`, tag `v1.0.0-rc.1`)
- **License:** Apache-2.0 (`LICENSE`, `NOTICE`, `ACCEPTABLE_USE.md`, verified via `scripts/license_check.py`)

---

## 1. Summary of What Was Built (Traceable to Specification)

| Domain | Scope Implemented | Primary Artifacts |
|---|---|---|
| **Database & Multi-Tenant RLS** | All 15 PostgreSQL 16 tables, native monthly range partitioning (`occupancy_snapshots`), RLS policies (`app.current_org_id`), `LAST_OWNER_PROTECTED` trigger, reversible Alembic migration `0001_initial_schema` | `backend/app/db/{models,partitions,base}.py`, `backend/alembic/versions/0001_initial_schema.py` |
| **Auth, 5-Role RBAC & Audit** (`FR-001`–`FR-003`, `FR-018`) | Argon2id password hashing, HttpOnly `SameSite=Strict` refresh tokens with rotation & reuse family revocation, optional TOTP MFA, fail-closed rate limiting, single source of truth `packages/rbac/matrix.yaml` enforcement across API (`API-001`–`API-006`, `API-021`), OpenAPI policy-completeness verification, CLI `tablepulse admin`, and secret-scrubbing structured logs | `backend/app/core/{rbac,security,logging,valkey_client}.py`, `backend/app/api/{auth,org_users}.py`, `backend/app/cli.py` |
| **Venues, Cameras, Polygons & MediaMTX** (`FR-004`–`FR-005`) | CRUD for venues/cameras (`API-007`–`API-010`), AES-256-GCM encryption at rest (`TABLEPULSE_DATA_KEY`) for RTSP URLs/credentials/webhook secrets/waitlist phones, SSRF blocking for private/loopback endpoints, MediaMTX external HTTP stream auth hook (`POST /api/v1/internal/media-auth`), server/client self-intersecting polygon rejection, normalized `0..1` vertex coordinates, Valkey Pub/Sub reload | `backend/app/core/{ssrf,geometry,privacy}.py`, `backend/app/api/venues_cameras.py`, `infra/{mediamtx,caddy,cascades}/` |
| **CV Worker Pipeline** (`FR-006`–`FR-010`, `ML-01`–`ML-04`) | 1–5 FPS frame sampler, mandatory OpenCV Haar + upper-head Gaussian blur-or-drop (`FaceBlurError`), Apache-2.0 RF-DETR Nano/Small/Medium/Large ONNX wrapper (`cv-worker/app/detector.py`), ByteTrack (`supervision`), cleanliness & statistical/LightGBM ETA estimation, deterministic temporal debounce/SLA state machine (`FREE`, `OCCUPIED`, `NEEDS_SERVICE`, `NEEDS_CLEANING`, `RESERVED`, `UNKNOWN`), Valkey Streams publisher, fail-closed kill switches | `cv-worker/app/{worker,detector,tracker,cleanliness,eta,state_machine,privacy,demo_seed}.py` |
| **Floor Ops, Waitlist, Analytics, Webhooks & Governance** (`FR-011`–`FR-024`) | All 23 API groups (`API-001`–`API-023`) + ticket-authenticated WebSocket hub (`WS /api/v1/ws/venues/{v}`), optimistic-lock `409 VERSION_CONFLICT` manual overrides, STAFF scope restrictions, ranked turnover ETA predictions excluding `UNKNOWN`, PG16 analytics + Day×Hour heatmap + CSV-injection-escaped exports, SSRF-safe HMAC-SHA256 webhooks with circuit breaker, ML review queue & OWNER zip export, OWNER system health, model registry gating, AI kill switch, and snapshot retention/immediate purge | `backend/app/api/{floor_ops,waitlist_analytics,admin_ops}.py`, `backend/app/services/{realtime,webhooks,audit}.py`, `docs/api-reference.md` |
| **Frontend Application (`SCR-001`–`SCR-016`)** | Next.js 15 App Router UI with `UI/` design tokens (`tokens.css`, Light/Dark/Solid modes, EN/HI toggle), memory-only JWT auth + cookie refresh, WebSocket -> 5s HTTP polling fallback, Konva 2D Floor Map & Polygon Editor (`react-konva@19.2.7`), Recharts analytics + accessible HTML table toggle, keyboard-accessible vertex editor & ML review shortcuts (`1–4` + `Enter`) | `frontend/src/{app,components,hooks,lib,providers,styles}/` |
| **ML Harness, Release Gate & Governance** | Strict manifest validator, 5-invariant zero-leakage splitter (`clip_id`, `session_id`, `frame_hash`, temporal gap, venue disjointness), TSM-F1 + session cluster bootstrap + ECE + MAE + G1–G11 release gate (`ml/evaluate_gate.py`) blocking `channel=stable` without `PRODUCTION_LABELED` data passing `TSM-F1 >= 0.90`, model card (`tablepulse-detector-b1@0.1.0`), EN/HI CCTV/Privacy notices, OWASP ASVS L2 checklist, and runbooks | `ml/{evaluate_gate.py,configs/,fixtures/,tablepulse_ml/}`, `docs/{ml,templates,security,runbooks}/` |

---

## 2. Verification & Test Counts (Directly Observed)

| Suite / Check | Command Executed | Observed Result |
|---|---|---|
| **Backend Lint, Format & Strict Types** | `cd backend; uv run ruff check . ; uv run ruff format --check . ; uv run mypy --strict app` | **0 errors** across 40 files (32 source files mypy `--strict`) |
| **Backend Unit & Integration Tests (PG16 + Valkey)** | `cd backend; uv run pytest -v` | **15 passed, 0 failed** (15.58s) — schema/partitioning/RLS, AuthN/RBAC/demo-login, SSRF/encryption/MediaMTX, floor ops/waitlist/analytics/WS/kill-switch |
| **CV Worker Lint, Strict Types & Unit Tests** | `cd cv-worker; uv run ruff check . ; uv run ruff format --check . ; uv run mypy --strict app ; uv run pytest -v` | **0 errors** (11 source files mypy `--strict`); **4 passed, 0 failed** (1.65s) |
| **ML Harness Lint, Strict Types & Unit Tests** | `cd ml; uv run ruff check . ; uv run ruff format --check . ; uv run mypy --strict tablepulse_ml evaluate_gate.py ; uv run pytest -v` | **0 errors** (7 source files mypy `--strict`); **4 passed, 0 failed** (0.23s) |
| **ML Release Gate Fixture Check** | `cd ml; uv run python evaluate_gate.py --fixture-check` | **PASS** (verified `FIXTURE-NOT-FOR-REPORTING` is strictly blocked (`FAIL`) from `stable` promotion) |
| **Frontend Types, Lint & Vitest** | `cd frontend; pnpm typecheck ; pnpm lint ; pnpm test ; pnpm build` | **0 TS errors**, **0 ESLint errors/warnings**, **4 passed, 0 failed** (Vitest), all 16 App Router pages built cleanly |
| **Playwright E2E + `@axe-core/playwright` WCAG 2.1 AA** | `cd frontend; pnpm test:e2e` (against live PG16 + Valkey + FastAPI + Next.js) | **3 passed, 0 failed** (46.6s) across Desktop (`1280px`, 12.2s), Tablet (`768px`, 10.8s), and Mobile (`360px`, 9.1s); zero 404s, zero horizontal overflow, zero critical/serious WCAG violations |
| **Chaos & Degraded-Mode Suite** | `backend\.venv\Scripts\python.exe scripts\chaos_test.py` | **4/4 scenarios PASSED** (camera outage -> `UNKNOWN`, Valkey outage fail-closed, missing kill switches -> `False`, webhook `500` retries + circuit breaker open) |
| **Backup & Restore Verification** | `python scripts/restore_test.py` | **PASSED** (`pg_dump -Fc` -> clean `tablepulse_restore_verify` DB -> `pg_restore` -> 100% row parity) |
| **Docker Compose Full Demo Stack** | `docker-compose --profile demo up -d --build` + `smoke_test.py` + `demo-login`/`floor-state` | All 8 services started cleanly (`db`, `valkey`, `mediamtx`, `api` healthy, `cv-worker`, `web`, `caddy`, `demo-seed`); smoke test passed; `demo-login` + `floor-state` returned 3 seeded tables & live KPIs |
| **License, Secret & Vulnerability Audits** | `scripts/license_check.py` (repo + `pip-licenses` across all 3 Python envs + `pnpm licenses list`), `scripts/secret_scan.py`, `uv run pip-audit` | **0 prohibited licenses/packages**, **0 exposed secrets**, **0 known CVEs** (`pip-audit` on `backend`) |

---

## 3. Benchmarks (`docs/benchmarks.md`)

- **Measured At:** 2026-11-25 10:17 UTC
- **Hardware:** `Windows 11` · `Intel64 Family 6 Model 183 Stepping 1, GenuineIntel` (16 logical cores), CPU reference path:
  - **720p Frame Face-Blur + JPEG Encode + State Step (60 iterations):** Mean `313.17 ms`, p50 `233.12 ms`, p95 `501.12 ms`
  - **ML Release Gate (`G1–G11` + 500-resample cluster bootstrap, 10 iterations):** Mean `0.71 ms`, p50 `0.61 ms`, p95 `1.07 ms`
- **Model Accuracy (TSM-F1 / Guest Count MAE / Calibration ECE):** **NOT YET MEASURED** on real restaurant footage. Zero-shot baseline `tablepulse-detector-b1@0.1.0` ships strictly in `channel: experimental` (`gate_status: NOT_MEASURED`).

---

## 4. Deviations, Assumptions & Known Items

1. **Docker & Windows Command Invocation:** Windows Docker Desktop exposes `docker-compose` rather than `docker compose` plugin syntax, and Windows lacks GNU `make`. Added `scripts/dev.ps1` alongside `Makefile` so both Linux CI and Windows operators execute identical checks.
2. **UI & Contrast Adjustments (`docs/ui-deviations.md`):**
   - Adjusted `--tp-accent` / `--accent-primary` from `#007AFF` (`4.01:1` with white text) to `#0062CC` (`5.88:1`), and status pill shades (`emerald-700/800`, `amber-700/800/900`, `red-700/900`) after `@axe-core/playwright` flagged contrast failures on `/register` and `/org/system`.
   - Downgraded `react-konva` from `19.3.2` to `19.2.7` and `eslint` to `9.39.5` so Next.js `15.5.29`'s bundled React runtime and `eslint-config-next@15.5.29` work without runtime or patch mismatch.
   - Pinned `opencv-python-headless==4.14.0.94` (OpenCV `5.1.0.95` omitted `cv2.CascadeClassifier`).
3. **Permissive License Allowlist Metadata (`LICENSE-EXCEPTIONS.md`):** Added explicit SPDX strings `"BSD"`, `"BlueOak-1.0.0"`, `"Python-2.0"`, and `"CC-BY-4.0"` to `config/license-allowlist.yaml` for verified permissive transitive build/runtime tools.
4. **Known Limitation — `TSM-F1` 90%–95% Production Target:** The shipped zero-shot RF-DETR Nano baseline is unmeasured on real multi-venue restaurant CCTV footage. The release gate in `ml/evaluate_gate.py` and `POST /api/v1/org/system/models/{id}/activate` enforces blocking `channel=stable` until a real `PRODUCTION_LABELED` evaluation report passes `G1–G11`.

---

## 5. Action Items Requiring Human Operator Ownership

1. **Real Multi-Venue Dataset Collection & Labeling:** Capture privacy-compliant CCTV clips across varied lighting/angles, review/annotate via `SCR-011` or offline labeling tools following `docs/ml/labeling-guide.md`.
2. **GPU Fine-Tuning & Production Gate Execution:** Train Apache-2.0 `rfdetr` (`nano`/`small`/`medium`/`large` ONLY) on `docker-compose.gpu.yml` / GPU nodes, export ONNX, and run `ml/evaluate_gate.py --manifest <real_manifest.json> --channel stable --out-json eval_report.json`.
3. **Legal & Compliance Sign-Off (`PR-01`–`PR-12`):** Have counsel adapt `docs/templates/cctv-notice-en-hi.md`, `staff-privacy-notice.md`, and `customer-privacy-notice.md` for jurisdiction-specific signage & data-retention laws (DPDP / GDPR / state privacy laws).
4. **Pilot Venue Provisioning & Production Secrets:** Generate high-entropy production values in `.env` (`TABLEPULSE_SECRET_KEY`, `TABLEPULSE_DATA_KEY`, `MEDIAMTX_HOOK_SECRET`, DB/Valkey passwords, TLS certificates in Caddy), disable `DEMO_MODE=false`, and onboard real RTSP streams on a segmented camera VLAN.

---

## 6. Exact Commands to Run & Verify

```bash
# 1. Start the full containerized demo stack
cp .env.example .env
docker compose --profile demo up -d --build   # (use `docker-compose` on Windows if needed)

# 2. Run API & Web smoke check
python scripts/smoke_test.py

# 3. Run full lint, typecheck, unit/integration tests, and license/secret scans
make check            # Linux / macOS
.\scripts\dev.ps1 check   # Windows PowerShell

# 4. Run ML release-gate fixture check, chaos suite, and backup/restore test
make eval             # or .\scripts\dev.ps1 eval
backend\.venv\Scripts\python.exe scripts\chaos_test.py
make restore-test     # or .\scripts\dev.ps1 restore-test
```
