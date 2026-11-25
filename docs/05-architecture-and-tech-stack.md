# TablePulse — Architecture, Tech Stack & Open-Source Licensing

## Quick Reference
- **Architecture Style**: Modular self-hosted containers via Docker Compose (`web`, `api`, `cv-worker`, `mediamtx`, `postgres`, `valkey`, `caddy`) designed for on-premise venue edge PCs (CPU or optional NVIDIA GPU) or private VPS (`PROPOSED`).
- **Media & Live Video**: **MediaMTX (MIT)** pulls RTSP/RTSPS from IP cameras, strips audio at ingest, relays internal RTSP to `cv-worker`, and serves low-latency **WebRTC (`WHEP`)** to authorized browsers.
- **Backend & Data**: Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) + Alembic · Pydantic v2 · **PostgreSQL 16+** (native monthly range partitioning + RLS — **no TimescaleDB TSL**) · **Valkey 8** (BSD-3 Redis-protocol drop-in).
- **Frontend**: Next.js 15 (App Router, React 19, TypeScript `strict: true`) · Tailwind CSS · shadcn/ui · TanStack Query · `react-konva` · Recharts · WebRTC WHEP client.
- **ML Runtime**: **RF-DETR Nano/Small/Medium/Large (Apache-2.0 ONLY)** via ONNX Runtime (MIT) · ByteTrack via `supervision` (MIT) · OpenCV headless (Apache-2.0) · ConvNeXt-Tiny / MobileNetV3 (MIT/Apache-2.0) · LightGBM (MIT) · MLflow + DVC (Apache-2.0).
- **License Traps Explicitly Avoided**: Ultralytics YOLO (`AGPL-3.0`), RF-DETR `Atto/Femto/Pico/XL/2XL` (`Roboflow Platform Model License 1.0`), TimescaleDB compression & continuous aggregates (`TSL` source-available), Redis >= 7.4 (non-OSI), `boxmot` (`AGPL-3.0`), MinIO (`AGPL-3.0`).
- **Version Pinning Rule**: At Stage 0, verify and pin latest stable versions in `uv.lock` and `pnpm-lock.yaml`, recording pinned versions and verification date in `docs/adr/0001-stack.md`.

---

## 1. System Context & Component Architecture

```text
[Existing IP/CCTV Cameras (RTSP/ONVIF)]
                 │ (RTSP / RTSPS — audio stripped)
                 ▼
        ┌─────────────────┐      WebRTC (WHEP over WSS/HTTPS)      ┌──────────────────────────┐
        │    MediaMTX     │ ─────────────────────────────────────► │   Next.js 15 Web App     │
        │  (Media Proxy)  │                                        │ (Host Tablet / Manager)  │
        └────────┬────────┘                                        └────────────┬─────────────┘
                 │ Internal RTSP Relay                                          │ REST + WebSocket
                 ▼                                                              ▼
        ┌─────────────────┐      Valkey Streams / PubSub           ┌──────────────────────────┐
        │   CV Worker     │ ◄────────────────────────────────────► │     FastAPI Backend      │
        │ (RF-DETR ONNX + │      (ROI updates, kill switch,        │ (Auth, RBAC, State API,  │
        │  ByteTrack +    │       state events, alerts)            │  Alerts, Analytics, WS)  │
        │  Cleanliness)   │                                        └──────┬────────────┬──────┘
        └────────┬────────┘                                               │            │
                 │ Face-blurred review crops (local volume)               ▼            ▼
                 └───────────────────────────────────────────────► [PostgreSQL 16     [Valkey 8
                                                                    (Native Partitions  (BSD-3)]
                                                                     + RLS)]
```

### Component Boundaries & State Ownership

| Component | Responsibility | Owned State | Prohibited Actions | Deployment Unit |
|---|---|---|---|---|
| **Web Frontend (`web`)** | Renders `SCR-001`–`SCR-016`, live floor map, polygon editor, WebRTC player, analytics charts. | In-memory access token, UI filter/zoom state. | Never stores tokens in `localStorage`; never connects directly to DB or RTSP cameras. | Docker (`node:22-alpine`) |
| **API Server (`api`)** | Auth/RBAC, CRUD APIs, WebSocket hub, alert routing, analytics rollups, MediaMTX auth hook, scheduled retention/partition jobs. | PostgreSQL 16 (sole SQL writer for config/auth/overrides/waitlist), Valkey cache. | Never runs synchronous ML inference inside HTTP request handlers. | Docker (`python:3.12-slim`) |
| **CV Worker (`cv-worker`)** | Samples frames from MediaMTX, applies face blur (**drop frame if blur fails**), runs RF-DETR + ByteTrack + cleanliness classifier + state machine, emits state events. | In-memory per-camera tracklets & debounce timers; writes face-blurred review crops to local volume. | Never accepts external HTTP traffic; never writes raw unblurred video to disk; halts when kill switch is `false`/missing. | Docker (`python:3.12` + optional CUDA/ONNX) |
| **Media Server (`mediamtx`)** | Pulls RTSP/RTSPS from IP cameras, strips audio, relays RTSP to `cv-worker`, serves WebRTC (`WHEP`) to authorized browsers. | Ephemeral stream buffers in RAM only. | Never exposes unauthenticated streams externally; never records video clips to disk. | Docker (`bluenviron/mediamtx`) |
| **Database (`db`)** | Relational config, audit logs, alerts, waitlist, ML registry, and natively partitioned `occupancy_snapshots` + `table_state_events`. | Durable persistent volume. | Never exposed on public internet interfaces (Docker internal network only). | Docker (`postgres:16-alpine`) |
| **Broker (`valkey`)** | WebSocket Pub/Sub fan-out, Redis-protocol Streams (`tp:cv:events`), rate limiting, alert deduplication, CV config reload bus, kill-switch cache. | Ephemeral in-memory state (not durable source of truth). | Never treated as durable source of truth for business records. | Docker (`valkey/valkey:8-alpine`) |

---

## 2. Communication Patterns & Consistency Model

| Path | Pattern | Reason |
|---|---|---|
| Browser <-> API (CRUD, Auth, Analytics) | Synchronous REST (HTTPS JSON) | Strict Pydantic v2 validation and cacheable GETs. |
| API -> Browser (Live floor & alerts) | WebSocket (`/api/v1/ws/venues/{venue_id}`) + 5s HTTP polling fallback | Sub-2s floor updates; polling fallback survives restrictive restaurant Wi-Fi proxies. |
| CV Worker -> API | Valkey Streams (`tp:cv:events`) | Decouples frame processing speed from DB write latency; provides back-pressure and at-least-once delivery. |
| API -> CV Worker (Polygon edit / Kill switch) | Valkey Pub/Sub (`tp:cv:control`) + startup DB pull | Instant (<2s) live ROI reload without restarting camera streams; startup pull prevents missed messages. |
| API -> External Webhooks (Slack/Telegram/Custom) | Async background queue with 3–5x retry & circuit breaker | External webhook outages never block floor state updates. |

- **Strong consistency (ACID):** Auth/tokens, RBAC roles, camera/polygon calibration, manual table overrides (optimistic lock `version`), waitlist seating, audit logs.
- **Eventual consistency (<2s):** Live floor map fan-out, aggregate occupancy KPIs, hourly materialized analytics rollups (refreshed every 5 minutes via advisory-locked job).

---

## 3. Capacity Model & Reference Hardware Profiles (`PROPOSED`)

| Profile / Horizon | Hardware | Expected Capacity (targets to measure via `make bench`, not guarantees) |
|---|---|---|
| **P0 Demo / Dev** | 4–8 core laptop CPU, 8–16 GB RAM | 1–2 cameras @ 2 FPS, RF-DETR-Nano ONNX INT8 |
| **P1 Single Venue (CPU)** | Mini-PC 6–8 core CPU, 16 GB RAM, 256 GB NVMe | 2–4 cameras @ 2 FPS, ~25 tables, ~6 concurrent UI users |
| **P2 Standard Venue (GPU)** | Mini-PC/server + entry NVIDIA GPU (6–8 GB VRAM, e.g., RTX 3060/L4) | 6–12 cameras @ 2–4 FPS, up to 120 tables, up to 50 concurrent UI users |
| **P3 Edge Device** | NVIDIA Jetson Orin Nano/NX (TensorRT, arm64) | 2–6 cameras @ 2–3 FPS |

- **Peak Factor**: `3.0x` baseline event rate during Friday/Saturday dinner rush (19:00–21:30).
- **Storage Growth (Single venue, 25 tables)**: `occupancy_snapshots` (~21,000 rows/day -> ~1.5 GB/year raw in native monthly PostgreSQL partitions; old partitions dropped cleanly via `DROP TABLE` after retention window). Face-blurred `ml_review_items` (~30 crops/day × 40 KB, 7-day retention): `< 10 MB` steady-state. Raw video stored on disk: `0 bytes`.
- **Three Named Bottlenecks**:
  1. **CV inference on CPU-only boxes:** Mitigated by ONNX INT8 quantization, adaptive FPS throttling (`2 FPS` -> `1 FPS`), and `camera_id` worker sharding.
  2. **RTSP flakiness on restaurant Wi-Fi:** Mitigated by MediaMTX TCP RTSP transport (`rtspTransport: tcp`), exponential reconnects, and per-camera `UNKNOWN` isolation.
  3. **12-month analytics query latency:** Mitigated by native PostgreSQL 16 monthly range partitions + scheduled hourly rollup table (`rollup_hourly_venue`).

---

## 4. Tech Stack & Verified Open-Source Licensing (Checked 2026-11-24)

| Layer | Choice | License | Rejected Alternatives & Why |
|---|---|---|---|
| **Object Detector** | **RF-DETR Nano / Small / Medium / Large** (ONNX export) | **Apache-2.0** (verified `roboflow.com/model-licenses/rf-detr`) | **Ultralytics YOLO**: `AGPL-3.0`/Enterprise (forces copyleft or paid license). **RF-DETR Atto/Femto/Pico/XL/2XL**: `Roboflow Platform Model License 1.0` (non-OSI; requires Roboflow plan/Enterprise add-on). |
| **Multi-Object Tracker** | **ByteTrack** (`supervision` or in-repo) | **MIT** | **`boxmot`**: `AGPL-3.0`. **DeepSORT**: Appearance Re-ID embeddings create biometric/privacy risk + extra GPU cost. |
| **Cleanliness Classifier** | **ConvNeXt-Tiny / MobileNetV3** (ONNX) | **MIT / Apache-2.0** | VLMs: Too slow/expensive for 2 FPS real-time CCTV. |
| **Turnover ETA** | **Statistical venue-median/IQR (v1.0 default)** + optional **LightGBM** | **MIT** | Deep sequence models: Overkill and opaque to hosts; statistical fallback works from day 1 without training data. |
| **Media Server** | **MediaMTX** | **MIT** | Custom FFmpeg/WebRTC server: High maintenance; MediaMTX handles RTSP/RTSPS -> WebRTC natively. |
| **Backend API** | **Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic** | **MIT** | Node/NestJS: Keeping API & CV/ML in Python shares schemas and tooling cleanly. |
| **Database** | **PostgreSQL 16+** (native monthly range partitioning + RLS) | **PostgreSQL License (OSI)** | **TimescaleDB compression & continuous aggregates**: Source-available (`TSL`), not Apache-2.0. Native PG16 partitioning covers 1–2 GB/yr cleanly with zero license risk. |
| **Cache / Broker** | **Valkey 8** (`valkey/valkey:8-alpine`) | **BSD-3-Clause** | **Redis >= 7.4**: Non-OSI/source-available license changes. Valkey is a 100% wire-compatible BSD-3 fork. |
| **Frontend** | **Next.js 15 (App Router, TS strict) + Tailwind + shadcn/ui + Konva + Recharts** | **MIT** | Full React/TS ecosystem with clean routing and SSR/API proxy support. |
| **Reverse Proxy** | **Caddy** | **Apache-2.0** | Manual Nginx TLS scripts: Caddy automates HTTPS/WSS with minimal config. |
| **ML Tooling** | **PyTorch (BSD-3), ONNX Runtime (MIT), MLflow (Apache-2.0), DVC (Apache-2.0)** | **Permissive OSI** | Proprietary SaaS trackers: Breaks offline/self-hosted promise. |

### Automated CI License Gate (`scripts/license_check.py`)
Every PR runs `pip-licenses` and `license-checker` against `config/license-allowlist.yaml`.
- **Allowed:** `MIT`, `BSD-2-Clause`, `BSD-3-Clause`, `Apache-2.0`, `ISC`, `PSF`, `MPL-2.0` (file-level), `PostgreSQL`, `LGPL-2.1+/3.0` (dynamically linked system libs only), `CC0`, `Unlicense`.
- **Hard Fail:** `AGPL`, `GPL`, `SSPL`, `BUSL`, `TSL`, `Non-Commercial`, `Research-Only`, `Roboflow-PML` — unless explicitly recorded in `LICENSE-EXCEPTIONS.md` with legal sign-off (`PR-04`/`PR-05`).
- **Review Cadence:** Re-verify stack licenses before each minor release (and no later than 2027-02-24).
