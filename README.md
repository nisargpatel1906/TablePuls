# TablePulse — Unified Project Specification Pack (v1.0)

> **Quick reference**
> - **What:** Open-source (**Apache-2.0**), self-hostable **AI restaurant floor-operations platform**. Connects existing CCTV/RTSP cameras via **MediaMTX** (WebRTC live view, audio stripped) and a **CV Worker** (RF-DETR Apache-2.0 + ByteTrack + Cleanliness Classifier) to provide live table states, guest counts, dwell/service timers, unattended-table & bussing alerts, waitlist turnover ETAs, and peak-hour staffing analytics.
> - **Designed for autonomous coding agents:** Combines lean, buildable v1.0 scope (**15 tables · 16 screens · 23 API groups · 9 build stages**) with strict open-source license hygiene, OWASP ASVS L2 security/privacy, reliability matrices, and publication-grade ML evaluation (`TSM-F1`).
> - **Honest ML status:** Target is `>= 90%` (stretch `95%`) on **TSM-F1** on a frozen held-out-venue test set — a *target to be measured*, **not achieved or guaranteed**. Status today: **NOT YET MEASURED** (`docs/07-ml-spec-and-evaluation.md`). The repository ships the zero-shot baseline strictly as **`experimental`** (`tablepulse-detector-b1@0.1.0`); achieving the 90%–95% production gate requires real labelled multi-venue CCTV footage & GPU fine-tuning supplied by the deploying operator.
> - **Quickstart (Docker Demo Stack):**
>   ```bash
>   cp .env.example .env
>   docker compose --profile demo up -d --build
>   # Open http://localhost:3000 (use "Sign in as Demo Manager" when DEMO_MODE=true)
>   ```
> - **Checks:** `make check` (`scripts/dev.ps1 check`), `make eval` (`scripts/dev.ps1 eval`), `make smoke` (`scripts/dev.ps1 smoke`), `make restore-test` (`scripts/dev.ps1 restore-test`).
> - **Labels used everywhere:** `DECIDED` · `PROPOSED` · `OPEN` · `PROFESSIONAL REVIEW` · `DEFERRED`.

## 1. Document Index (Single Source of Truth)

| File | Purpose |
|---|---|
| `AGENTS.md` | Standing rules, canonical vocabulary, license bans, safety defaults & stop conditions for the AI coding agent |
| `UI/README.md` | Visual asset hand-off naming (`UI/SCR-XXX-...`), P1/P2 tiers, `tokens.css` extraction & UI-generation prompt |
| `docs/01-prd.md` | Project overview, problem statement, personas, v1.0 MVP vs. deferred scope, user journeys |
| `docs/02-ui-screens.md` | Complete 16-screen UI & interaction specification (`SCR-001`–`SCR-016`) + non-color state cues |
| `docs/03-functional-requirements.md` | 24 numbered functional requirements (`FR-001`–`FR-024`), user stories & acceptance criteria |
| `docs/04-rbac-and-access-control.md` | 5-role RBAC matrix (`packages/rbac/matrix.yaml`), auth/session lifecycle, MediaMTX stream auth & RLS |
| `docs/05-architecture-and-tech-stack.md` | System architecture (MediaMTX WebRTC + CV Worker + FastAPI + Next.js 15), capacity model, verified Apache-2.0/MIT stack, RF-DETR size license rules & CI allowlist |
| `docs/06-data-model-and-api.md` | 15-table PostgreSQL 16 schema (native monthly range partitioning), indexes, REST (`API-001`–`API-023`) & WebSocket contract |
| `docs/07-ml-spec-and-evaluation.md` | ML tasks (`ML-01`–`ML-04`), frozen `TSM-F1` definition, leakage-proof `T-seen`/`T-unseen` splits, cluster bootstrap CIs, baselines & hard CI release gate |
| `docs/07b-ml-templates.md` | Model Card, Datasheet, Evaluation Report, Labelling Guide & Experiment Log templates |
| `docs/08-security-and-privacy.md` | OWASP ASVS L2 security controls, secrets/encryption, SSRF guard, privacy-by-design, blur-or-drop rule, hard biometric prohibitions & DPDP/GDPR notes |
| `docs/09-reliability-and-ops.md` | Failure-mode & degraded-mode matrices, timeouts/retries/circuit breakers, kill switches, `.env.example`, Docker Compose (CPU/GPU), deployment runbooks & backups |
| `docs/10-testing-and-release-criteria.md` | Test pyramid, DB-verified test-everything loop, Production Readiness Requirements, chaos tests, license/security gates & v1.0 Go/No-Go checklist |
| `docs/11-open-source-and-contributing.md` | Apache-2.0 license rationale, DCO, `NOTICE`, `ACCEPTABLE_USE.md`, repo layout & contribution workflow |
| `docs/12-agent-build-plan.md` | 9-stage autonomous build plan (`Stage 0`–`Stage 8`), standing rules, stop conditions, progress report template & copy-paste prompts (Prompts A, B, C) |
| `docs/decision-log-and-reviews.md` | Master Decision Log (`DEC-001`–`DEC-010`), Open Questions (`OPEN-001`–`OPEN-004`) & 12-item Professional Review Register (`PR-01`–`PR-12`) |
| `docs/consistency-report.md` | Automated cross-document verification report confirming zero contradictions and zero license leaks |

## 2. Reading Order
- **Humans:** `README.md` -> `docs/01-prd.md` -> `docs/02-ui-screens.md` -> `UI/README.md` -> `docs/07-ml-spec-and-evaluation.md` -> `docs/decision-log-and-reviews.md`.
- **AI Coding Agent (Antigravity / Claude Code / Cursor):** `AGENTS.md` -> `README.md` -> `docs/12-agent-build-plan.md` -> the specific docs listed for the current stage.

## 3. Recommended Tools & MCP Connectors for Antigravity
1. **GitHub MCP / `gh` CLI** — Repo creation, `.gitignore` from commit 1, PRs, GitHub Actions CI, releases.
2. **Docker / Local Terminal** — Spin up PostgreSQL 16, Valkey 8, MediaMTX, API, Web, CV Worker; run `alembic`, `pytest`, `make check`.
3. **PostgreSQL MCP (or `psql` CLI)** *(dev DB only)* — Direct SQL row verification during the mandatory Test-Everything Loop.
4. **Playwright MCP** *(localhost only)* — E2E journeys, direct-URL navigation on all 16 routes, responsive checks (360/768/1280px), visual comparison against `UI/`, and `axe-core` WCAG 2.1 AA audits.
5. **Context7 / Docs Lookup MCP** *(optional, read-only)* — Fetch current Next.js 15, FastAPI, SQLAlchemy 2.0, RF-DETR, and MediaMTX docs.

## 4. How to Hand This Pack to Antigravity
1. Copy this entire folder into your repository root (`AGENTS.md`, `README.md`, `UI/`, `docs/`).
2. Generate UI mockups from `docs/02-ui-screens.md` using the prompt in `UI/README.md` and save them in `UI/` (you may start backend Stages 0–5 immediately and add `UI/` before Stage 6).
3. Start Antigravity with **Prompt A** from `docs/12-agent-build-plan.md` beginning at **Stage 0**, advancing strictly one stage at a time after reviewing `docs/progress/S<n>.md`.
