# TablePulse — Decision Log, Open Questions & Professional Review Register

## 1. Master Decision Log

| ID | Decision | Label | Rationale | Affected Docs |
|---|---|---|---|---|
| `DEC-001` | Edge/self-hosted Docker Compose first (zero raw video cloud upload) | `PROPOSED` | Cuts bandwidth/cloud cost and maximizes CCTV privacy | `05`, `08`, `09` |
| `DEC-002` | Apache-2.0 project license + RF-DETR Nano/Small/Medium/Large (Apache-2.0) over Ultralytics YOLO (AGPL-3.0) & restricted RF-DETR sizes | `PROPOSED` | Permissive commercial adoption + patent grant; zero copyleft or platform-license traps | `05`, `07`, `11` |
| `DEC-003` | PostgreSQL 16+ with **native monthly range partitioning** (no TimescaleDB TSL) | `PROPOSED` | Keeps 100% OSI open-source stack while handling 1–2 GB/yr operational data cleanly in one backupable DB | `05`, `06`, `09` |
| `DEC-004` | MediaMTX (MIT) for RTSP/RTSPS -> WebRTC (`WHEP`) live camera wall with audio stripped | `PROPOSED` | Low-latency browser video without custom streaming servers or disk recording | `02`, `05`, `08` |
| `DEC-005` | Normalized (`0.0–1.0`) table polygon coordinates | `PROPOSED` | Calibration survives camera substream resolution changes | `03`, `06` |
| `DEC-006` | Valkey 8 (`valkey/valkey:8-alpine`, BSD-3) for Streams, Pub/Sub & rate limiting | `PROPOSED` | Wire-compatible Redis drop-in keeping 100% OSI-approved licensing | `05`, `09` |
| `DEC-007` | HttpOnly rotating refresh cookie + in-memory JWT access token + `packages/rbac/matrix.yaml` SSoT | `DECIDED` | Protects against XSS token theft; prevents RBAC drift across backend/frontend | `04`, `08` |
| `DEC-008` | Face blur ON by default (**drop frame on blur failure**); zero raw video retention; fail-closed kill switches (`missing = false`) | `DECIDED` | Privacy-by-design and fail-safe operation for patrons and staff | `01`, `08`, `09` |
| `DEC-009` | Separate `UNKNOWN` (low ML confidence / camera offline) from `FREE` and route to `SCR-011`; penalize `UNKNOWN` in `TSM-F1` | `DECIDED` | Prevents silent wrong table states and prevents gaming ML metrics via abstention | `02`, `07`, `09` |
| `DEC-010` | Lean v1.0 scope (15 tables, 16 screens, 23 API groups, 9 stages) | `DECIDED` | Maximizes autonomous AI-agent buildability and code quality without enterprise bloat | `01`, `06`, `12` |

---

## 2. Open Questions Register (Non-Blocking for v0.x Build)

| ID | Type | Item | Default Used | Owner / Resolve-By |
|---|---|---|---|---|
| `OPEN-001` | `OPEN` | First POS integration target for v1.1 (Toast, Square, Clover, Petpooja) | `DEFERRED` (v1.1) | Maintainer / v1.1 |
| `OPEN-002` | `OPEN` | Optional uniform-color hint vs. pure standing-proximity heuristic for staff visits | Standing-proximity heuristic + zone prior | Maintainer / Pilot |
| `OPEN-003` | `OPEN` | Confirm final project name `TablePulse` and trademark/GitHub org availability | Working name `TablePulse` | Project Owner / Pre-launch |
| `OPEN-004` | `OPEN` | Confirm rights/provenance for generated `UI/` mockups and demo MP4 clip | Store provenance in `UI/PROVENANCE.md` | Project Owner / Pre-launch |

---

## 3. Professional Review Register (Legal, Privacy, Licensing & Security)

> These documents **do not constitute legal advice**. Each item below requires a qualified legal, privacy, or security reviewer to assign an owner and status before declaring `v1.0` (does not block `0.x` prototypes).

| ID | Area | Question for the expert | Why it matters | Needed before | Owner | Status |
|---|---|---|---|---|---|---|
| PR-01 | Privacy law (India DPDP Act & Rules 2025; GDPR/other where deployed) | Lawful basis/consent/notice for processing images of customers and **employees** by CCTV-based analytics; whether analytics on already-installed CCTV needs new notice; retention periods; breach-notification duties; children's data | Rules were notified Nov 2025 with phased commencement (secondary sources, **unverified dates**) | Pilot + 1.0 | — | Open |
| PR-02 | Employment/labour law | Permissibility and notice requirements for any staff-presence detection (used only to detect cleaning); works-council/union consultation; whether "staff as a class" is sufficient to avoid monitoring obligations | Labour/privacy exposure | Pilot | — | Open |
| PR-03 | CCTV regulation/signage | Signage wording (EN/HI templates in `docs/templates/`), local municipal/police rules | Compliance | Pilot | — | Open |
| PR-04 | Project licence | Apache-2.0 vs AGPL-3.0; patent implications; NOTICE obligations; whether a separate AGPL YOLO plugin repo is safe (`docs/05-architecture-and-tech-stack.md` option C) | Open-source terms | First public push | — | Open |
| PR-05 | Third-party model licences | Confirm RF-DETR size licences at time of use (verified 2026-11-24: N/S/M/L Apache-2.0); base-weights/pretraining-data implications for redistributing fine-tuned weights | Redistribution rights | First model release | — | Open |
| PR-06 | Dataset licences & consent | Public datasets (COCO, CrowdHuman, Objects365, Open Images…) licence terms; venue data-contribution agreement; blurred-footage release; cross-border transfer | Dataset publication | E1 / dataset release | — | Open |
| PR-07 | Responsible-use terms | RAIL-style restrictions on weights; enforceability; wording of `ACCEPTABLE_USE.md` | Misuse mitigation | First model release | — | Open |
| PR-08 | Fairness evaluation | Ethics review of proxy-group and optional skin-tone evaluation; annotator guidelines | Bias assessment legitimacy | E6 | — | Open |
| PR-09 | Security review | Independent review/pen-test against ASVS L2; cryptography choices (AES-GCM envelope, argon2 params) | Assurance | 1.0 | — | Open |
| PR-10 | Trademark | Name/logo clearance | Brand | Public repo | — | Open |
| PR-11 | Accuracy claims | Wording of any marketing/README claims about accuracy; consumer-protection rules | Misleading claims risk | Any public claim | — | Open |
| PR-12 | Data-subject rights process | Handling of customer requests when system does not identify people; waitlist data | DPDP/GDPR rights | 1.0 | — | Open |
