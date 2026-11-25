# AGENTS.md — Rules for AI Coding Agents Working on TablePulse

> Working name: **TablePulse** (rename allowed; grep `TablePulse|tablepulse`). Read this file first, every session. Master index: `README.md`. Detailed specs live in `docs/`. Stage order: `docs/12-agent-build-plan.md`.

## 1. What you are building (30 seconds)
An **open-source, Apache-2.0, self-hostable restaurant floor-intelligence platform**: existing IP/CCTV cameras (RTSP/ONVIF) -> MediaMTX (RTSP->WebRTC WHEP, audio stripped) + CV Worker -> live **table states**, seated guest counts, dwell & service timers, unattended-table & bussing alerts, waitlist turnover ETAs, and peak-hour staffing analytics; with RBAC, PostgreSQL RLS, audit logs, privacy-by-design, and a measured ML release gate. Production quality, not a prototype.

## 2. Canonical vocabulary (never rename)
- **Table states (6):** `FREE`, `OCCUPIED`, `NEEDS_SERVICE`, `NEEDS_CLEANING`, `RESERVED`, `UNKNOWN`. `RESERVED` is manual-only. Source: `AI|MANUAL|SYSTEM`.
- **Roles (5):** `OWNER` (org-wide); `MANAGER`, `HOST`, `STAFF`, `VIEWER` (venue-scoped). Single source of truth: `packages/rbac/matrix.yaml` (see `docs/04-rbac-and-access-control.md`).
- **Defaults:** `occupancy_debounce_sec=10`, `departure_debounce_sec=20`, `unattended_service_sec=300`, `cleaning_alert_delay_sec=120`, `min_confidence=0.65`, `camera_stale_s=30`, `target_fps=2` (range 1–5).
- **API Envelope:** `{ "success": true, "data": ... }` / `{ "success": false, "error": { "code", "message", "fields?" } }`.
- **Primary ML metric:** **TSM-F1** (latency-compensated Table-State Macro-F1; see `docs/07-ml-spec-and-evaluation.md`). **Channels:** `experimental`, `stable`.

## 3. Stack (verify & pin latest stable at Stage 0; do not rely on unverified versions)
Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) + Alembic · Pydantic v2 · **PostgreSQL 16+** (native monthly range partitioning + RLS; **no TimescaleDB TSL**) · **Valkey 8** (BSD-3 Redis-protocol drop-in) · **MediaMTX** (MIT, RTSP->WebRTC WHEP) · Next.js 15 (App Router, React 19, TypeScript `strict: true`) · Tailwind CSS + shadcn/ui · TanStack Query · `react-konva` · Recharts · **RF-DETR (Nano/Small/Medium/Large Apache-2.0 ONLY)** via ONNX Runtime · ByteTrack (`supervision`, MIT) · OpenCV headless · ConvNeXt-Tiny/MobileNetV3 (MIT/Apache-2.0) · LightGBM (MIT) · Docker Compose · Caddy · Prometheus + structured JSON logs · `uv` · `pnpm`.

**License policy (strict):** Project license is **Apache-2.0**. **Never add** AGPL/GPL/SSPL/BUSL/TSL/non-commercial/Roboflow-PML dependencies — specifically banned: `ultralytics` YOLO (AGPL-3.0), RF-DETR `Atto/Femto/Pico/XL/2XL` (Roboflow Platform Model License 1.0), TimescaleDB TSL features (compression/continuous aggregates), Redis >= 7.4 (non-OSI), `boxmot` (AGPL-3.0), MinIO (AGPL-3.0). CI `scripts/license_check.py` must pass on every PR.

## 4. Commands (create these in Stage 0)
`make dev` · `make check` (lint + typecheck + unit + license-check) · `make test` · `make e2e` · `make eval` · `make smoke` · `make restore-test`.

## 5. Always
1. Work **one stage at a time** (`docs/12-agent-build-plan.md`, Stages 0–8); finish -> test -> write `docs/progress/S<n>.md` -> stop for human review.
2. **Mandatory Test-Everything Loop:** build -> test valid, missing, wrong-type, out-of-range (`400`), unauthenticated (`401`), wrong-role & cross-org (`403`), not-found (`404`), optimistic-lock (`409`), and degraded paths -> **verify writes directly in PostgreSQL** -> fix failures -> re-test until 100% green.
3. Separate **AuthN** (`get_current_user` -> `401`) and **AuthZ** (`require_venue_role` -> `403`) on every protected endpoint. Never trust `organization_id` from request bodies.
4. Every async UI action implements visible **Loading**, **Error**, and **Success** states; every screen implements empty and permission-denied states where applicable; WCAG 2.1 AA; test direct-URL navigation on all 16 routes.
5. Secrets only in `.env` / environment variables (`.gitignore` committed in Stage 0); never log secrets, PII, or `rtsp://user:pass@` URLs.
6. Use UTC (`TIMESTAMPTZ`) in storage; venue timezone only for UI presentation and analytics bucketing.
7. Look in `UI/` before building any frontend screen (`UI/README.md`). Visuals come from `UI/`; behavior, controls, states, and accessibility come from `docs/02-ui-screens.md`. If an asset is missing, build with neutral tokens and mark `// TODO(ui-asset): SCR-XXX`.
8. Keep OpenAPI / `docs/api-reference.md`, `.env.example`, and `CHANGELOG.md` updated with every change.

## 6. Never
- Implement **face recognition**, biometrics, cross-session person re-identification, demographic inference, audio capture/storage, or per-individual employee scoring.
- Persist raw video/frames to disk (only face-blurred review crops with configurable TTL, default 7 days); publish or save an unblurred frame (**drop the frame** if face blur fails).
- Fabricate datasets, labels, benchmark numbers, or "accuracy" claims; mark an ML gate `PASS` without a stored `eval_report.json`; change metric definitions or thresholds after seeing test results.
- Commit secrets, `.env`, model weights, datasets, or sample copyrighted video.
- Disable tests, linters, type checks, or license checks to get green; weaken RBAC/RLS; use wildcard CORS with credentials; store JWTs in `localStorage`.
- Call paid/external APIs by default; every optional external integration (webhooks, SMTP) is behind an env var + kill switch.

## 6b. Always-on safety defaults
Kill switches (`AI_INFERENCE_ENABLED`, `WEBHOOKS_ENABLED`, `REVIEW_CROPS_ENABLED`) -> **missing or unreachable = `false`** (fail-safe paused). Uncertain/failed inference or offline camera -> table `UNKNOWN`, never silently `FREE`.

## 7. Stop and ask the user when
- Adding/removing a DB table, column, constraint, or delete behavior not in `docs/06-data-model-and-api.md`.
- Any dependency/model/dataset license is unknown or incompatible with `config/license-allowlist.yaml`.
- Two spec documents contradict each other and single sources of truth do not settle it.
- A change would delete durable data, rewrite git history, drop tables, or require a real secret/credential.
- A requirement would need a prohibited non-goal (face recognition, audio, individual staff scoring).
- Any request to report unmeasured ML accuracy or lower the `>= 90%` TSM-F1 release gate.
- Resolving a `PROFESSIONAL REVIEW` legal/compliance item (`docs/decision-log-and-reviews.md`).
- A blocker persists after **3 failed fix-and-retest iterations** on the same issue.

## 8. Definition of done (every stage)
Acceptance criteria automated · validation + unified error envelope · AuthN/AuthZ + cross-tenant tests · direct DB state verification · UI loading/error/success + a11y + direct-URL navigation · audit logged · reversible Alembic migration · CI green (lint, strict types, tests, license check, `gitleaks`).
