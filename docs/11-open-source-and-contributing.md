# TablePulse — Open-Source License, Governance & Contribution Guide

## Quick Reference
- **Recommended License**: **Apache License 2.0 (`Apache-2.0`)** (`PROPOSED`).
- **Why Apache-2.0**: Permissive (anyone — indie restaurants, cafes, startups, enterprises — can self-host, modify, and build commercial products around TablePulse for free), includes an **explicit patent grant** (stronger protection than MIT), and aligns cleanly with our Apache-2.0 / MIT dependency stack (`RF-DETR`, `ByteTrack`, `MediaMTX`, `FastAPI`, `Next.js`, `PostgreSQL`).
- **License Hygiene Rule**: Strictly prohibit AGPL-3.0 / GPL-3.0 dependencies (such as Ultralytics YOLO) in core packages so downstream adopters never inherit viral copyleft obligations.

---

## 1. Open-Source License Comparison & Selection Rationale

| License | Commercial Use | Patent Grant | Copyleft Obligation | Verdict for TablePulse |
|---|---|---|---|---|
| **Apache-2.0** (`PROPOSED`) | Allowed | **Explicit patent grant + retaliation clause** | None (permissive) | **Recommended** — Gold standard for open-source AI/ML & enterprise-adoptable tools. Matches RF-DETR and OpenCV. |
| **MIT** | Allowed | Implicit only | None (permissive) | Viable simpler alternative if you prefer minimal boilerplate, though lacks explicit patent protection. |
| **AGPL-3.0** | Allowed only if entire hosted app is open-sourced | Explicit | Strong network copyleft | **Not recommended** unless you specifically want to block closed-source SaaS wrappers (also reduces corporate/integrator adoption). |

- **`PROFESSIONAL REVIEW` (`PRO-002`)**: Before publishing fine-tuned model weights publicly, verify the exact license of every dataset used during training (e.g., CC-BY-4.0 attribution requirements in `NOTICE`, and signed contributor release forms for any partner restaurant footage) with open-source legal counsel.

---

## 2. Repository Structure (`PROPOSED`)

```text
tablepulse/
├── LICENSE                      # Apache-2.0 full text
├── NOTICE                       # Required attributions (RF-DETR, ByteTrack, MediaMTX, datasets)
├── README.md                    # Quickstart, demo screenshot/GIF, architecture, license badge
├── CONTRIBUTING.md              # Dev setup, PR checklist, coding standards
├── CODE_OF_CONDUCT.md           # Contributor Covenant v2.1
├── SECURITY.md                  # Private vulnerability disclosure process
├── CHANGELOG.md                 # Keep a Changelog (SemVer)
├── .env.example                 # Complete documented env template
├── docker-compose.yml           # CPU default stack (web, api, cv-worker, mediamtx, db, redis, caddy)
├── docker-compose.gpu.yml       # NVIDIA GPU override for cv-worker
├── UI/                          # User-supplied visual UI reference assets (SCR-001..SCR-016)
├── docs/                        # This specification suite + API docs + ML benchmark reports
├── frontend/                    # Next.js 15 TypeScript strict app
├── backend/                     # FastAPI async API + Alembic migrations + pytest suite
├── cv-worker/                   # RF-DETR + ByteTrack + Cleanliness + Turnover ETA inference worker
├── ml/                          # Training scripts, dataset manifest validator, evaluate_gate.py
├── infra/                       # mediamtx.yml, Caddyfile, Prometheus config, backup scripts
└── .github/
    ├── workflows/               # ci-backend.yml, ci-frontend.yml, ci-security-licenses.yml, ml-eval.yml
    ├── ISSUE_TEMPLATE/          # bug_report.md, feature_request.md, model_error_report.md
    └── PULL_REQUEST_TEMPLATE.md
```

---

## 3. Contribution Standards & Workflow
1. **Branching & Commits**: Fork -> feature branch (`feat/short-name`, `fix/short-name`) -> Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
2. **Code Quality Gates (Enforced in CI)**:
   - Python (`backend/`, `cv-worker/`, `ml/`): `ruff` (lint + format), `mypy --strict`, `pytest`.
   - TypeScript (`frontend/`): `eslint`, `prettier`, `tsc --noEmit`, `vitest`, `playwright`.
   - Dependency License Check: `pip-licenses` and `license-checker` fail CI if any GPL/AGPL package is added.
   - Secret Scanning: `gitleaks` blocks commits containing credentials or `.env` files.
3. **Pull Request Requirements**:
   - Reference an issue or spec ID (`FR-XXX`, `SCR-XXX`, `API-XXX`).
   - Include tests (including bad-input and RBAC tests for any new API endpoint).
   - Update API docs if any request/response schema changed.
   - For ML model PRs: attach `eval_report.json` output from `ml/evaluate_gate.py` showing comparison against baselines on the frozen test split.
4. **Security Disclosure (`SECURITY.md`)**: Never open public GitHub issues for security vulnerabilities (especially auth bypasses or RTSP credential leaks). Report privately via GitHub Security Advisories or maintainer security email; target 72-hour acknowledgment.
5. **Governance**: Benevolent Maintainer model for v1.x; RFC issue process (`docs/rfcs/`) for breaking API, schema, or privacy policy changes.


### Additional Open-Source Governance Rules (`PROPOSED`)
- **DCO (`Signed-off-by:`)**: Use Developer Certificate of Origin on commits rather than a heavyweight CLA to keep contributor friction low.
- **`ACCEPTABLE_USE.md`**: Non-binding responsible-use statement clarifying prohibited deployments (no face recognition, no covert surveillance, no per-employee scoring); consider RAIL-style terms for released model weights (`PR-07`).
- **`LICENSE-EXCEPTIONS.md`**: Any exception to `config/license-allowlist.yaml` requires documented legal sign-off; core images remain 100% permissive OSI open source.
- **Documentation & Data Licensing**: Docs under `CC BY 4.0`; project-released anonymized datasets under `CDLA-Permissive-2.0` or `CC BY 4.0` only where all contributing sources permit redistribution (`PR-06`).
