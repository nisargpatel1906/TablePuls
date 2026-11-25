# ADR 0001: Technology Stack & Pinned Dependency Versions

- **Status**: Accepted
- **Verification Date**: 2026-11-25
- **License Policy**: Strict Apache-2.0 / MIT / BSD / PostgreSQL OSI stack. Zero AGPL/GPL/SSPL/BUSL/TSL/Roboflow-PML-1.0 components.

## Verified Pinned Versions (Checked 2026-11-25 against PyPI, npm, and GitHub Releases)

### Infrastructure & Containers
| Component | Image / Release | License | Purpose |
|---|---|---|---|
| PostgreSQL | `postgres:16-alpine` | PostgreSQL License (OSI) | Primary relational store, native monthly range partitioning, RLS |
| Valkey | `valkey/valkey:8-alpine` | BSD-3-Clause | Streams (`tp:cv:events`), Pub/Sub (`tp:cv:control`), rate limiting |
| MediaMTX | `bluenviron/mediamtx:1.21.4` | MIT | RTSP/RTSPS ingest (audio stripped) -> WebRTC WHEP |
| Caddy | `caddy:2.11-alpine` (latest `v2.11.9`) | Apache-2.0 | TLS reverse proxy with security headers |
| Python | `3.12` (`python:3.12-slim`) | PSF | Backend API, CV Worker, ML Harness |
| Node.js | `22` (`node:22-alpine`) | MIT | Next.js 15 frontend build & runtime |

### Backend Python (`backend/pyproject.toml`)
- `fastapi==0.165.0` (MIT)
- `uvicorn==0.54.0` (BSD-3-Clause)
- `sqlalchemy==2.1.9` (MIT)
- `alembic==1.20.1` (MIT)
- `asyncpg==0.32.0` (Apache-2.0)
- `pydantic==2.14.4` (MIT)
- `pydantic-settings==2.16.3` (MIT)
- `argon2-cffi==25.1.0` (MIT)
- `pyjwt==2.15.1` (MIT)
- `cryptography==50.0.2` (Apache-2.0 OR BSD-3-Clause)
- `valkey==6.2.0` (MIT)
- `httpx==0.28.1` (BSD-3-Clause)
- `prometheus-client==0.26.0` (Apache-2.0)
- `structlog==26.1.0` (MIT OR Apache-2.0)
- `typer==0.29.2` (MIT)
- `pyotp==2.12.1` (MIT)
- `zxcvbn==4.5.0` (MIT)
- `python-multipart==0.0.34` (Apache-2.0)
- `pyyaml==6.0.4` (MIT)
- Dev/CI: `pytest==9.2.0`, `pytest-asyncio==1.5.0`, `pytest-cov==7.1.0`, `hypothesis==6.170.17` (MPL-2.0), `ruff==0.17.6`, `mypy==2.4.1`, `pip-licenses==5.5.5`, `pip-audit==2.10.1`

### CV Worker & ML (`cv-worker/pyproject.toml`, `ml/pyproject.toml`)
- `onnxruntime==1.32.0` (MIT)
- `opencv-python-headless==4.14.0.94` (Apache-2.0, latest OpenCV 4.x with full `CascadeClassifier` / `objdetect` support)
- `supervision==0.32.1` (MIT)
- `numpy==2.5.5` (BSD-3-Clause)
- `pillow==13.0.0` (MIT-CMU)
- `lightgbm==4.7.0` (MIT)
- `scikit-learn==1.9.1` (BSD-3-Clause)
- `scipy==1.18.1` (BSD-3-Clause)
- `rfdetr==1.12.1` (Apache-2.0 — **Nano / Small / Medium / Large sizes ONLY**; `Atto/Femto/Pico/XL/2XL` banned by `config/license-allowlist.yaml`)

### Frontend (`frontend/package.json`)
- `next==15.5.29` (MIT, latest stable Next.js 15 backport release)
- `react==19.3.1`, `react-dom==19.3.1` (MIT)
- `@tanstack/react-query==5.108.4` (MIT)
- `konva==10.11.0`, `react-konva==19.3.2` (MIT)
- `recharts==3.11.1` (MIT)
- `lucide-react==1.80.0` (ISC)
- `tailwindcss==4.3.5` (MIT)
- `typescript==5.8.3` (Apache-2.0, compatible with Next 15 & `eslint-config-next`)
- `vitest==5.1.1`, `@testing-library/react==16.3.3`, `@playwright/test==1.65.1`, `@axe-core/playwright==4.14.1`

## Explicit License Exclusions
- `ultralytics` YOLO (`AGPL-3.0`) -> Replaced by RF-DETR Nano/Small/Medium/Large (`Apache-2.0`).
- `boxmot` (`AGPL-3.0`) -> Replaced by ByteTrack via `supervision` (`MIT`) + in-repo tracker fallback.
- TimescaleDB TSL (`TSL`) -> Replaced by PostgreSQL 16 native monthly range partitioning.
- Redis >= 7.4 (non-OSI) -> Replaced by Valkey 8 (`BSD-3-Clause`).
- MinIO (`AGPL-3.0`) -> Replaced by local volume storage with retention purge.
