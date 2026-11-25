# Consistency Report (Unified TablePulse v1.0 Spec Pack)

> **Audit Result:** **PASS (0 defects found)**
> **Pack Scope:** 18 Markdown files · 2,050 lines · ~28,339 words (excluding this report).

## 1. Automated Cross-Document Checks

| Check | Result |
|---|---|
| Naming consistency (zero `FloorSight` leftovers) | PASS |
| Pure OSI licensing (zero unreconciled TimescaleDB TSL / AGPL references) | PASS |
| Internal spec cross-references (`AGENTS.md`, `README.md`, `UI/README.md`, `docs/*.md`) | PASS |
| Scope alignment | 15 DB tables · 16 UI screens (`SCR-001`–`SCR-016`) · 24 FRs (`FR-001`–`FR-024`) · 23 API groups (`API-001`–`API-023`) · 5 roles · 6 table states · 9 build stages (`Stage 0`–`Stage 8`) |
| ML honesty & license guardrails | `TSM-F1` primary metric (`NOT YET MEASURED`), RF-DETR Apache-2.0 sizes enforced, fail-closed kill switches (`missing = false`), blur-or-drop privacy enforced |

## 2. File Inventory

| File | Lines | Words |
|---|---:|---:|
| `AGENTS.md` | 55 | 898 |
| `README.md` | 45 | 709 |
| `UI/README.md` | 56 | 673 |
| `docs/01-prd.md` | 112 | 1,864 |
| `docs/02-ui-screens.md` | 259 | 3,860 |
| `docs/03-functional-requirements.md` | 193 | 2,403 |
| `docs/04-rbac-and-access-control.md` | 94 | 1,291 |
| `docs/05-architecture-and-tech-stack.md` | 104 | 1,502 |
| `docs/06-data-model-and-api.md` | 118 | 2,214 |
| `docs/07-ml-spec-and-evaluation.md` | 247 | 3,994 |
| `docs/07b-ml-templates.md` | 85 | 697 |
| `docs/08-security-and-privacy.md` | 119 | 1,600 |
| `docs/09-reliability-and-ops.md` | 231 | 2,503 |
| `docs/10-testing-and-release-criteria.md` | 58 | 942 |
| `docs/11-open-source-and-contributing.md` | 71 | 710 |
| `docs/12-agent-build-plan.md` | 155 | 1,539 |
| `docs/decision-log-and-reviews.md` | 48 | 940 |
