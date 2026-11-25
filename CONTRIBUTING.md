# Contributing to TablePulse

Thank you for helping build TablePulse!

## 1. Prerequisites
- Python 3.12+ and `uv`
- Node.js 22+ and `pnpm`
- Docker Engine 24+ and Docker Compose v2

## 2. Developer Certificate of Origin (DCO)
All commits must include a `Signed-off-by:` line (`git commit -s -m "..."`), certifying that you have the right to submit the contribution under the Apache-2.0 license.

## 3. Coding & License Standards
- **Apache-2.0 Purity**: Never add dependencies licensed under AGPL, GPL, SSPL, BUSL, TSL, or non-commercial/source-available terms (including `ultralytics` YOLO, `boxmot`, TimescaleDB TSL, MinIO, Redis >= 7.4, or RF-DETR `Atto/Femto/Pico/XL/2XL`).
- **Python (`backend/`, `cv-worker/`, `ml/`)**: `ruff check`, `ruff format --check`, `mypy --strict`, and `pytest` must pass.
- **Frontend (`frontend/`)**: TypeScript `strict: true`, ESLint, `vitest`, and Playwright E2E/a11y checks must pass.
- **API & DB Rules**:
  - Use the unified API envelope `{ "success": true, "data": ... }` / `{ "success": false, "error": { "code", "message", "fields?" } }`.
  - Enforce both `get_current_user` (`401`) and `require_venue_role` (`403`) on protected routes.
  - Update `docs/api-reference.md` and `CHANGELOG.md` when endpoints or behaviors change.

## 4. Pull Request Checklist
- [ ] References an issue or spec ID (`FR-XXX`, `SCR-XXX`, `API-XXX`, `ML-XX`)
- [ ] Includes unit/integration tests covering bad inputs (`400`, `401`, `403`, `404`, `409`)
- [ ] `make check` and `scripts/license_check.py` pass with zero errors
- [ ] `gitleaks` / secret scan is clean
- [ ] Commits are signed off (`git commit -s`)
