# 09 — Reliability, Setup, Deployment & Operations

> **Quick reference**
> - Design rule: **fail visible, fail safe.** When a camera/model/worker fails, tables become `UNKNOWN` (never silently `FREE`), staff keep operating manually, the UI says why.
> - Capacity target (v1.0): 1 venue · ≤ 8 cameras · ≤ 120 tables · ≤ 50 concurrent UI sessions.
> - Numbers below are **targets to be measured** by `make bench`; reference-hardware results go in `docs/benchmarks.md` with date and hardware. No result is claimed here.
> - RPO ≤ 24 h, RTO ≤ 2 h.

## 1. Failure-mode table

| Component / dependency | Failure | Detection | User-visible effect | Automatic handling | Manual action (runbook) |
|---|---|---|---|---|---|
| Camera/RTSP | Stream drops, bad creds, network | No frame ≥ `camera_stale_s`; reconnect counter | Tables of that camera → `UNKNOWN`; banner; alert `CAMERA_OFFLINE` after 120 s | Exponential reconnect 1→60 s | `runbooks/camera-offline.md` |
| Vision camera process | Crash (codec/segfault) | Supervisor heartbeat miss 15 s | Same as above | Restart w/ backoff; crash-loop breaker after 5 in 10 min → `degraded` + alert | `runbooks/cv-worker-crashloop.md` |
| Detector/model | Load failure, NaN, slow | Exceptions, latency p95 > budget | `UNKNOWN`; `MODEL_QUALITY_DEGRADED` | Auto-rollback to previous active model if new model fails health check in first 10 min | `runbooks/model-rollback.md` |
| GPU unavailable | Driver/OOM | Init error | Falls back to CPU at reduced FPS (flag `degraded`) | Adapter fallback | `runbooks/gpu.md` |
| PostgreSQL | Down/slow | `/readyz`, query timeouts | API 503; floor shows last-known data labelled stale; workers buffer ≤ 60 s | Retry w/ backoff; pool recycle | `runbooks/db-down.md` |
| Valkey | Down | Ping fail | Realtime degrades to 5 s polling; rate limiting fails **closed** for auth endpoints, open for reads | Reconnect; local in-process fallback caches | `runbooks/valkey-down.md` |
| api | Crash/overload | Healthcheck | UI "Reconnecting…" | Container restart; replicas | — |
| api background worker | Stuck/lag | Queue depth metric, task age | Delayed analytics/alerts | Restart; time limits; alert `JOB_FAILING` | `runbooks/jobs.md` |
| Disk full | Writes fail | Disk metric ≥ 90 % | Alert `DISK_LOW` | Purge job priority; stop evidence snapshots first | `runbooks/disk.md` |
| SMTP/Web Push/webhook | Delivery fails | Delivery log | In-app only | Retries; disable noisy endpoint | `runbooks/notifications.md` |
| Clock skew | Drift > 2 s | NTP check metric | Timers off | Warn in System Health | `runbooks/time.md` |
| Bad deploy/migration | Failed upgrade | CI/smoke tests | — | Migration in transaction; keep previous image tag; documented rollback | `runbooks/rollback.md` |

## 2. Timeouts

| Call | Timeout |
|---|---|
| Camera connect / first frame | 10 s / 15 s |
| Frame stall | 10 s (reconnect) |
| DB statement (API) | 5 s (analytics 15 s) |
| DB pool acquire | 3 s |
| Valkey ops | 500 ms |
| Webhook delivery | connect 5 s, total 10 s |
| SMTP | 10 s |
| WebSocket idle | ping 20 s, close after 2 misses |
| API request overall | 30 s |
| Detector per frame | 1 s hard limit (skip frame) |

## 3. Retries

| Operation | Policy |
|---|---|
| Camera reconnect | Exponential 1→60 s, jitter, unlimited |
| DB write from worker | 3 immediate-then-backoff attempts (100 ms, 500 ms, 2 s), then buffer |
| Email | 3× (30 s, 2 m, 10 m) |
| Webhook | 5× (1 m, 5 m, 30 m, 2 h, 12 h) |
| Background jobs | `autoretry_for` transient errors, max 3, jitter; no retry on validation errors |
All retried operations are idempotent (`docs/05-architecture-and-tech-stack.md`).

## 4. Circuit breakers
- Per webhook endpoint: open after 10 consecutive failures for 10 min; auto-disable after 50 total failures.
- Per camera: crash-loop breaker (5 crashes/10 min).
- DB buffer breaker: stop buffering at 10k events/60 s.
- Model health breaker: if inference error rate > 20 % over 1 min ⇒ mark `degraded` ⇒ tables `UNKNOWN`.

## 5. Degraded-mode matrix

| Condition | Floor | Waitlist | Analytics | Alerts |
|---|---|---|---|---|
| Camera down | Its tables `UNKNOWN`, others live | Works; queue estimate "unavailable" if entrance cam | Data gap marked `unknown_s` | `CAMERA_OFFLINE` |
| Model/worker down | All `UNKNOWN`; manual overrides still work | Works; recommendations ignore UNKNOWN | Gap | Critical |
| Valkey down | 5 s polling | Works | Works | In-app via DB poll |
| DB down | Read-only stale cache in browser | Disabled | Unavailable | Unavailable |
| Jobs down | Live OK | OK | Stale | Delayed |

## 6. Recovery objectives & backups

| Data | RPO | RTO | Mechanism |
|---|---|---|---|
| PostgreSQL (all durable data) | 24 h (nightly) / ≤ 5 min with WAL archiving (optional) | 2 h | `tablepulse admin backup` → `pg_dump` custom format + config, encrypted; optional WAL-G/pgBackRest |
| Model artifacts/config | 24 h | 2 h | Included in backup (checksums) |
| Valkey | n/a (ephemeral) | minutes | Rebuild |
- **Restore test:** monthly automated restore into a scratch Compose stack + smoke test (`make restore-test`); results logged. A backup never restored is not a backup.
- Retention: 7 daily, 4 weekly, 3 monthly (configurable).

## 7. Back-pressure & load shedding
- Vision: drop-oldest frames; reduce `target_fps` automatically (floor 1 FPS) if p95 latency > 2× budget for 60 s (`adaptive_fps` flag, on by default), restore when healthy; surfaces in `SCR-012`.
- API: per-principal rate limits; analytics queries have statement timeouts and result caps; exports async.
- WebSocket: slow-consumer disconnect; frame topics throttled first.
- Jobs: separate queues (`critical` alerts/notifications; `default`; `bulk` exports/reports) with dedicated worker concurrency.

## 8. Kill switches
| Flag | Default when missing | Who may change | Read by | Logged |
|---|---|---|---|---|
| `AI_INFERENCE_ENABLED` | **false** | `OWNER` | cv-worker before each inference batch | audit |
| `PUSH_ENABLED` | false | same | jobs before each send | audit |
| `WEBHOOKS_ENABLED` | false | same | jobs before each send | audit |
| `REVIEW_CROPS_ENABLED` | false | `OWNER` | cv-worker before writing a snapshot | audit |
| `SMS_ENABLED` (future) | false | same | jobs before each send | audit |
Seed script sets `INFERENCE_ENABLED=true` for new installs after the setup wizard's "Go live".

## 9. Performance budgets

| Path | Budget |
|---|---|
| Event → UI (end-to-end) p95 | ≤ 5 s (of which: confirm window is *not* counted; measured from transition decision to render) |
| Vision frame (decode→publish) p95 | ≤ 250 ms/camera at `target_fps` on reference hardware |
| API read p95 | ≤ 300 ms |
| Analytics 90-day p95 | ≤ 2 s |
| Web app initial load (LCP, 4G tablet) | ≤ 2.5 s; JS bundle ≤ 300 KB gz initial route |
| Memory | api ≤ 512 MB, jobs ≤ 512 MB, cv-worker ≤ 2 GB + 300 MB/camera (CPU) |

## 10. Capacity model (assumptions → numbers)

| Quantity | Assumption | Calculation | Result |
|---|---|---|---|
| Cameras | 8 | — | 8 |
| FPS | 3 | 8 × 3 | 24 frames/s total |
| Table-state events | 120 tables × ~12 transitions/day (4 turns × 3 transitions) | 1,440/day | ~0.5 M/yr |
| Event row size | ~200 B + index ≈ 400 B | 0.5 M × 400 B | ~200 MB/yr |
| Queue observations | 1 per camera per 5 s while open, 16 h/day, 2 entrance cams | 2 × 11,520 | ~23 k/day → ~8.4 M/yr raw (kept 90 d ⇒ ~2 M rows ≈ 250 MB) |
| Camera health samples | 8 × 1/min × 1440 | 11.5 k/day | 90 d ≈ 1 M rows |
| Audit log | ~2 k/day | — | ~0.8 M/yr, < 500 MB |
| Rollups | 120 tables × 24 h × 365 | 1.05 M/yr | ~150 MB/yr |
| Review crops | 200/week × 50 KB (+ extras) | — | < 1 GB (14 d TTL) |
| **Total DB growth** | | | **≈ 1–2 GB/year** at the stated assumptions |
| Live-view bandwidth | 1–3 fps JPEG ~60 KB × 5 viewers × 8 cams (only subscribed cams) | ~1.4 MB/s worst case | LAN OK; Wi-Fi tablets ≤ 3 fps/cam |
| Peak factor | Friday dinner = 3× average UI traffic | — | design for 150 rps API burst |

**Top three bottlenecks:** (1) inference throughput on CPU-only hosts → mitigated by low FPS, adaptive FPS, ONNX; (2) WebSocket frame fan-out bandwidth → throttle, subscribe-only-when-viewing; (3) analytics queries over raw sessions → rollups + indexes.

## 11. Benchmarks required before 1.0 (`make bench`)
Inference latency/throughput per profile (P0–P3); API load (Locust/k6) at 50 rps for 10 min; WebSocket soak (50 clients × 1 h); 24 h cv-worker soak with simulated RTSP drops; DB growth projection from a 30-day synthetic dataset. Results committed to `docs/benchmarks.md` with hardware and date.

---

## 12. Setup, Environment Contract & Deployment Guide

### 12.1 Prerequisites & Local Development Setup

### 1.1 Hardware & Software Requirements
- **Minimum (Demo / 1–4 Cameras CPU-only)**: 4-core x86_64/ARM64 CPU, 8 GB RAM, 20 GB SSD, Docker Engine `>= 24.0`, Docker Compose v2.
- **Recommended (4–12 Cameras Production)**: 6-core CPU, 16 GB RAM, NVIDIA GPU with `>= 6 GB VRAM` (e.g., RTX 3060 / L4 / Jetson Orin) + NVIDIA Container Toolkit.
- **Local Dev Tools**: Python `3.12+`, `uv` or `pip`, Node.js `22 LTS`, `pnpm` `9+`, Git.

### 1.2 Mandatory `.gitignore` (Required in First Commit — `DECIDED`)
```gitignore
.env
.env.*
!.env.example
node_modules/
.next/
dist/
build/
__pycache__/
*.pyc
.venv/
.pytest_cache/
data/snapshots/
data/models/*.onnx
.cursor/
.vscode/
.idea/
```

### 1.3 Environment Variable Contract (`.env.example`)
Never hardcode `localhost`, API keys, or DB passwords anywhere in source code. Every variable below must be documented in `.env.example` and configured in the deployment environment:

| Variable | Owner | Required | Example / Default | Secret? |
|---|---|---|---|---|
| `APP_ENV` | `api`, `web` | Yes | `development` / `production` | No |
| `PUBLIC_APP_URL` | `web`, `api` | Yes | `https://floor.myrestaurant.com` | No |
| `ALLOWED_ORIGINS` | `api` | Yes | `https://floor.myrestaurant.com` | No |
| `DATABASE_URL` | `api` | Yes | `postgresql+asyncpg://tp:***@db:5432/tablepulse` | **Yes** |
| `REDIS_URL` | `api`, `cv-worker` | Yes | `redis://:***@redis:6379/0` | **Yes** |
| `JWT_SECRET` | `api` | Yes | 64-char hex (`openssl rand -hex 32`) | **Yes** |
| `DB_ENCRYPTION_KEY` | `api`, `cv-worker` | Yes | 32-byte base64 AES-256-GCM key | **Yes** |
| `MEDIAMTX_INTERNAL_URL` | `api`, `cv-worker` | Yes | `rtsp://mediamtx:8554` | No |
| `MEDIAMTX_WEBRTC_PUBLIC_URL` | `web` | Yes | `https://floor.myrestaurant.com/webrtc` | No |
| `ML_DEVICE` | `cv-worker` | No | `cpu` or `cuda:0` | No |
| `ML_MODEL_DIR` | `cv-worker` | No | `/app/data/models` | No |
| `SNAPSHOT_STORAGE_DIR` | `api`, `cv-worker` | No | `/app/data/snapshots` | No |
| `DEMO_MODE` | `api`, `web` | No | `false` (`true` enables demo MP4 & quick login) | No |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | `api` | No | Optional; if unset, UI shows copyable invite/reset links | **Yes** |

---

## 2. Deployment Options & Pipeline

### 2.1 Option A: On-Premise / Edge Docker Compose (Recommended Default)
- Runs on a mini-PC or GPU workstation inside the restaurant LAN alongside the existing NVR/CCTV switch.
- **Advantages**: Zero cloud video egress, `< 500ms` RTSP ingest latency, ~$0/month recurring cloud bills, keeps CCTV traffic strictly on local LAN.
- **Startup Flow**:
  1. `cp .env.example .env` and generate strong secrets (`JWT_SECRET`, `DB_ENCRYPTION_KEY`).
  2. `docker compose up -d` (or `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d`).
  3. API container runs `alembic upgrade head` automatically on boot (or via explicit `migrate` init container) with a DB advisory lock so concurrent replicas never race migrations.
  4. Visit `https://<host>/register?bootstrap=true` to run the onboarding wizard (`SCR-004`).

### 2.2 Option B: Private Cloud VPS / Managed Hosting
- Deploy `web` + `api` + `db` on a private VPS (Hetzner/DigitalOcean/AWS EC2) while running `mediamtx` + `cv-worker` on an on-premise edge device connected via WireGuard VPN, OR stream RTSPS over VPN to a GPU VPS.
- **Monorepo Rule**: If deploying `web` and `api` separately on PaaS platforms (Vercel/Render/Railway), set explicit root paths (`/frontend`, `/backend`), carry over every env var in the platform dashboard, and redeploy whenever any env var changes.
- **Database IP Allow-List**: If using a managed PostgreSQL provider (Neon/Supabase/RDS), restrict inbound network rules to the API server's egress IP only.

### 2.3 Common Deployment Failure Runbook (`DECIDED` — Production Readiness)
| Symptom | Root Cause | Immediate Fix |
|---|---|---|
| `502 Bad Gateway` right after deploy | API failed DB connection or migration; or managed DB blocked server IP | Check `docker compose logs api`; verify `DATABASE_URL` and DB IP allow-list. |
| Direct URL (e.g., `/venues/1/analytics`) returns `404` | Reverse proxy/static host missing SPA/App-Router rewrite | Ensure Caddy/Nginx proxies all non-`/api` paths to Next.js server (`web:3000`). |
| Live WebRTC camera or snapshot fails in prod HTTPS but works locally | Mixed-content HTTP URL served on HTTPS page | Verify `PUBLIC_APP_URL` and `MEDIAMTX_WEBRTC_PUBLIC_URL` use `https://` / `wss://`. |
| Env var change doesn't take effect | Running container/platform didn't reload environment | Recreate containers (`docker compose up -d --force-recreate`) or trigger platform redeploy. |
| RTSP stream drops every 60s | UDP packet loss on restaurant Wi-Fi | Force `rtspTransport: tcp` in `mediamtx.yml`. |

---

## 3. Observability, Backups & Self-Hosted Cost Model

### 3.1 Logging, Metrics & Alerts
- **Structured JSON Logs**: Every log line contains `timestamp`, `level`, `service`, `request_id`, `org_id`, `venue_id`, and `message` (scrubbed of secrets/credentials).
- **Key Prometheus Metrics**:
  - `tp_http_requests_total` & `tp_http_request_duration_seconds`
  - `tp_cv_frames_processed_total{camera_id}` & `tp_cv_inference_duration_ms`
  - `tp_cv_camera_status{camera_id}` (`1`=online, `0`=offline)
  - `tp_table_unknown_ratio{venue_id}` & `tp_manual_override_rate{venue_id}`
- **Operational Alerts**:
  - `CVWorkerDown`: Heartbeat missing `> 30s` -> Owner runbook: check GPU/RAM, inspect `docker logs cv-worker`, confirm manual floor mode active.
  - `DiskUsageHigh`: Volume `> 85%` -> Run `POST /api/v1/org/system/purge-snapshots` and verify PostgreSQL 16 (native partitions) compression policy.

### 3.2 Backup & Restore Verification
- **Nightly Automated Backup**: Cron/sidecar runs `pg_dump --format=custom` to encrypted local/offsite backup storage (retains 14 daily + 4 weekly backups).
- **Restore Test Schedule**: Monthly automated restore into an ephemeral test container verifying row counts and schema integrity (RPO `<= 24h`, RTO `<= 30 min`).

### 3.3 Self-Hosted Cost Model (`PROPOSED`)
- **Software License Cost**: `$0` (Apache-2.0 open-source; zero per-camera SaaS fees, zero paid AI API calls).
- **On-Premise Edge Hardware (One-Time)**: Existing mini-PC (~$300–$500 CPU-only for 1–4 cameras) or GPU edge workstation (~$800–$1,200 for 4–12 cameras).
- **Optional Cloud VPS (If Not On-Prem)**: Single 4-vCPU VPS (~$20–$40/mo) for API/Web/DB + on-prem edge box for CV, or GPU VPS (~$150–$300/mo).


## 13. Related Documents
`05-architecture-and-tech-stack.md` · `06-data-model-and-api.md` · `08-security-and-privacy.md` · `10-testing-and-release-criteria.md`
