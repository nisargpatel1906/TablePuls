# Changelog

All notable changes to TablePulse will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-rc.1] - 2026-11-25

### Added
- **Stages 1–5 (Backend & CV Pipeline):** 15-table PostgreSQL 16 schema with native monthly range partitioning & RLS, Alembic migrations, Argon2id/TOTP/JWT/refresh-rotation auth, 5-role RBAC (`packages/rbac/matrix.yaml`), SSRF-safe camera/webhook guards, AES-256-GCM field encryption, MediaMTX stream auth hook, OpenCV face-blur-or-drop pipeline (`4.14.0.94`), ByteTrack + deterministic state machine, FastAPI 23 API groups + WebSocket hub, waitlist + turnover ETAs, analytics + CSV export, ML review queue & zip export, and OWNER system governance.
- **Stages 6–7 (Next.js 15 Frontend):** All 16 screens (`SCR-001`–`SCR-016`) implemented using extracted design tokens (`tokens.css`) + Dark/Solid accessibility themes + EN/HI toggle, memory-only JWT auth + refresh interceptor, WebSocket + 5s polling fallback, Konva floor & calibration canvases (`react-konva@19.2.7`), Recharts analytics, Playwright E2E + `axe-core` WCAG 2.1 AA verification across Desktop (`1280px`), Tablet (`768px`), and Mobile (`360px`).
- **Stage 8 (ML Gate & Release Readiness):** Leakage-free dataset splitter & 5-invariant verifier, `TSM-F1` + cluster bootstrap CI + ECE + G1–G11 release gate (`ml/evaluate_gate.py`, strictly blocking `stable` without a passing real-data `eval_report.json`), experimental B1 baseline marked `NOT YET MEASURED`, chaos degraded-mode suite, backup/restore verifier, EN/HI privacy templates, ASVS summary, runbooks, and measured benchmarks (`docs/benchmarks.md`).
