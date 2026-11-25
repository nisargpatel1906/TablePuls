# TablePulse — Project Overview & Product Requirements Document (PRD)

## Quick Reference
- **Product**: `TablePulse` (`PROPOSED`) — an open-source, self-hostable AI restaurant table and floor operations platform that turns existing CCTV/RTSP security cameras into real-time occupancy, service-SLA, bussing, waitlist-turnover, and peak-hour staffing intelligence.
- **Target Users**: Restaurant Owners (`OWNER`), Floor/Shift Managers (`MANAGER`), Front-of-House Hosts (`HOST`), Servers/Bussers (`STAFF`), and Operations Analysts (`VIEWER`).
- **License & Distribution**: Open-source under `Apache-2.0` (`PROPOSED`), self-hosted via Docker Compose (edge GPU or CPU).
- **Status**: Production-ready v1.0 MVP specification (`DECIDED`); zero proprietary camera hardware required (`DECIDED`).

---

## 1. Statement Labeling Convention
Every product decision, assumption, and requirement in this document carries one of five labels:
- `DECIDED`: Explicitly confirmed from the reference video (`Video-25376.mp4`) or user prompt.
- `PROPOSED`: Recommended default selected to unblock autonomous implementation; overrideable before build.
- `OPEN`: Unresolved detail with an owner and resolve-by milestone.
- `PROFESSIONAL REVIEW`: Requires legal, privacy, or compliance counsel; no legal conclusion is asserted here.
- `DEFERRED`: Explicitly out of scope for v1.0 MVP; planned for a future release.

---

## 2. Problem Statement & Value Proposition
- **Problem** (`DECIDED`): Full-service restaurants and high-traffic cafes lose revenue and guest satisfaction from four operational blind spots: (1) hosts cannot see real-time table availability across large or multi-room floors, (2) seated guests wait too long for initial waiter greeting/service, (3) vacated tables sit uncleaned ("dirty") while a waitlist grows at the entrance, and (4) managers schedule waiter shifts by guesswork rather than measured hourly occupancy curves.
- **Existing Alternatives** (`PROPOSED`, verified 2026-11-24): Manual host-stand tablet apps (OpenTable, SevenRooms, Yelp Guest Manager) require hosts to tap every seating and bussing event manually, which breaks down during rush hours. Proprietary AI camera startups charge recurring per-camera SaaS fees and lock restaurants into closed cloud ecosystems.
- **Value Proposition** (`DECIDED`): `TablePulse` connects directly to existing IP/CCTV RTSP cameras, runs computer-vision inference locally (on-premise or private server), automates table state detection and service/bussing alerts, predicts upcoming table turnover for waiting guests, and gives managers weekly peak-hour analytics — completely open-source and free of vendor lock-in.

---

## 3. Target Users & Personas

| Persona | System Role | Trigger Situation | Primary Goals |
|---|---|---|---|
| **Front-of-House Host** (`DECIDED`) | `HOST` | Rush-hour queue forms at entrance; guests ask "How long is the wait?" | See live color-coded floor map, spot newly freed/cleaned tables, see which occupied table will turn over soonest, manage waitlist quotes accurately. |
| **Server / Busser** (`DECIDED`) | `STAFF` | Floor is busy and newly seated or vacated tables go unnoticed. | Receive immediate, actionable alerts when a table has waited >5 min for service or needs cleaning after guests leave; mark tables resolved in one tap. |
| **Floor / Shift Manager** (`DECIDED`) | `MANAGER` | Weekly shift scheduling, mid-shift bottlenecks, or camera/floor-plan adjustments. | Monitor live capacity and SLA breaches, review weekly peak-hours heatmaps to schedule optimal waiter headcount, calibrate table polygons, review uncertain AI detections. |
| **Restaurant Owner / Ops Admin** (`PROPOSED`) | `OWNER` | Initial deployment across 1+ venues, staff onboarding, privacy compliance. | Connect existing RTSP cameras, configure privacy controls (face blur, zero video storage), manage user roles, review audit logs and system health. |
| **Operations Analyst** (`PROPOSED`) | `VIEWER` | Monthly multi-venue capacity review. | View read-only occupancy trends and export CSV/JSON analytics reports without modifying live floor state. |

---

## 4. Scope Decision: v1.0 MVP vs. Deferred Enhancements

### 4.1 v1.0 MVP (Launch Scope — `DECIDED` / `PROPOSED`)
1. **Existing CCTV/RTSP Camera Ingestion** (`DECIDED`): Connect standard RTSP/RTSPS IP cameras (ONVIF Profile S/T compatible) and sample/uploaded test video files (MP4) for demo/testing without hardware.
2. **Interactive Table Polygon & ROI Calibration** (`PROPOSED`): Browser-based canvas editor over a live camera snapshot to draw polygonal table boundaries, assign Table IDs (`T01`, `T02`...), set seat capacity, assign floor sections, and map tables onto a 2D floor map.
3. **Real-Time Table Occupancy & Guest Counting** (`DECIDED`): Per-table detection of `FREE`, `OCCUPIED`, `NEEDS_SERVICE`, `NEEDS_CLEANING`, `RESERVED`, and `UNKNOWN` states, plus live seated guest count and venue-wide metrics (`Tables Occupied X/Y`, `Seated Guests A/B`, `Capacity Z%`).
4. **Automatic Dwell & Service Timers** (`DECIDED`): Start a live timer (`MM:SS` / `HH:MM:SS`) the moment guests are seated; track time-since-seated and time-since-last-staff-visit.
5. **Unattended Table Service Alerts** (`DECIDED`): Trigger an alert when guests remain seated for longer than a configurable threshold (default: `5 minutes`) without a detected staff visit.
6. **Table Cleaning / Bussing Alerts** (`DECIDED`): Trigger an alert when guests vacate a table and tableware/mess is detected (or bussing confirmation is pending) so bussers can reset it immediately.
7. **Live Host Floor Map & Camera Wall** (`DECIDED`): Interactive 2D floor map ("Live Host Floor") with real-time WebSocket updates, toast notifications (e.g., `CCTV: Party left Table 23`), manual override controls, and an optional live CCTV overlay view showing table polygons and guest counts.
8. **Waitlist & Predicted Turnover Availability** (`DECIDED`): Front-desk waitlist queue paired with ranked "Next Available Table" predictions based on elapsed dwell time vs. historical party-size turn duration.
9. **Peak Hours & Staffing Analytics** (`DECIDED`): Daily and weekly occupancy, wait-time, average turn duration, and SLA-breach charts by hour of day and day of week, with CSV export and recommended waiter-count guidance.
10. **ML Confidence & Human-Review Fallback** (`PROPOSED`): Surface low-confidence (`UNKNOWN`) table states and contested transitions in a review queue so managers can correct labels and feed clean data into future model retraining.
11. **Production Auth, RBAC & Privacy Safeguards** (`PROPOSED`): Email/password auth with HTTP-only refresh cookies, 5-role RBAC, multi-venue scoping, audit logging, real-time face-blur privacy mode on live views/snapshots, and zero raw video retention by default.

### 4.2 Explicitly Deferred (Post-MVP — `DEFERRED`)
- **POS System Integration** (Square, Toast, Clover, Petpooja) to correlate check-drop events with turnover prediction (`DEFERRED` to v1.1).
- **Automated Staff Uniform / Wearable Badge Detection** beyond general staff-visit heuristics (`DEFERRED` to v1.1; MVP supports optional color/apron zone heuristic + dwell-time proximity).
- **Native iOS / Android Mobile Apps** (`DEFERRED` to v1.2; v1.0 ships as a responsive web app / PWA optimized for iPad/Android tablets and desktops).
- **Multi-Camera Cross-View Person Re-Identification** across non-overlapping rooms (`DEFERRED` to v1.2).
- **SMS / WhatsApp Guest Waitlist Notifications** via Twilio/WhatsApp Business API (`DEFERRED` to v1.1; MVP provides webhook/Slack/Telegram staff alerts).

### 4.3 Permanently Out of Scope (`PROPOSED`)
- **Facial Recognition or Biometric Identification**: TablePulse will never identify, store, or track individual customer identities across visits.
- **Audio Recording or Conversation Analysis**: Audio tracks from RTSP streams are stripped at ingest.
- **Automated Employee Disciplinary Scoring**: Analytics focus on floor coverage and service bottlenecks, not automated punitive scoring of named individuals.

---

## 5. Core User Journeys (`PROPOSED` — inferred and expanded from video workflows)

### Journey 1: First-Time Venue Setup (Owner / Manager)
1. Owner deploys TablePulse via Docker Compose, visits `/onboarding`, creates the initial `OWNER` account, and creates their first venue (name, timezone, operating hours, total seat capacity).
2. Owner adds an RTSP camera stream URL (or uploads a sample MP4 clip in Demo Mode) and clicks **Test Connection** to verify live frame capture.
3. Owner opens the **Table Polygon Editor**, draws polygons around each table on the camera snapshot, enters Table ID (`T01`–`T24`), seat capacity, and section (`Main Hall`, `Patio`), and places each table on the 2D Floor Map.
4. Owner reviews default alert thresholds (Unattended Service = `5 min`, Dirty Table = `2 min`) and activates monitoring. The Live Floor Map immediately begins reflecting table states.

### Journey 2: Rush-Hour Hosting & Turnover Prediction (Host)
1. Host keeps **Live Host Floor** (`SCR-005`) open on a stand tablet. Top bar displays `Tables: 14/24`, `Seated Guests: 48/96`, `Capacity: 50%`.
2. A party of 4 arrives at the entrance while all 4-tops are full. Host adds them to the **Waitlist** (`SCR-009`).
3. The panel highlights `Table 04 (4-top, Occupied 52m — Est. Free in ~8m)` as the top predicted turnover candidate.
4. When guests at `Table 23` stand up and leave, a toast fires: `CCTV: Party left Table 23 — Needs Cleaning`. Table 23 turns amber (`NEEDS_CLEANING`).
5. Once a busser clears the table and the camera confirms a clean tabletop (or staff taps **Mark Clean**), Table 23 turns green (`FREE`). Host seats the waiting party and taps **Seat Party**.

### Journey 3: Unattended Table & Bussing Alerts (Server / Busser)
1. Two guests sit at `Table 02`. The CV pipeline detects 2 seated persons inside `T02`'s polygon for >10 seconds, transitioning `T02` to `OCCUPIED` (red) and starting the `00:00` timer.
2. Five minutes pass without a staff member stopping at `T02`. TablePulse transitions `T02` to `NEEDS_SERVICE`, fires a high-priority alert in `SCR-008` and via optional Slack/Webhook notification: `Table 02 waiting 05:00 without service (2 guests)`.
3. Server visits `Table 02` (auto-detected by staff proximity/interaction OR tapped **Acknowledge** on tablet), clearing the service alert.
4. After the meal, guests leave dishes behind. `T02` transitions to `NEEDS_CLEANING`. Busser wipes the table; CV detects clean surface (or busser taps **Cleaned**) and `T02` returns to `FREE`.

### Journey 4: Weekly Peak Hours Review & Staffing (Manager)
1. On Sunday evening, Manager opens **Peak Hours & Staffing Analytics** (`SCR-010`) and selects the past 7 days.
2. Charts display hourly occupancy %, average wait time, average turn duration, and service-SLA breach count across lunch (12:00–14:30) and dinner (19:00–21:30) peaks.
3. Manager spots recurring SLA breaches on Friday/Saturday 19:30–20:30 when capacity exceeds 85%, exports the CSV report, and schedules 2 additional servers for next weekend.

---

## 6. Success Criteria & Measurable Targets (`PROPOSED`)
| Metric | Target | Measurement Method | Review Cadence |
|---|---|---|---|
| **Table Occupancy Classification (Macro-F1)** | `>= 90%` (stretch `95%`) on documented benchmark test set | Offline evaluation suite on held-out restaurant CCTV scenes (see ML Evaluation Spec) | Every model release (CI gate) |
| **Guest Count Error (MAE)** | `<= 0.35 guests/table` | Held-out labeled evaluation frames across 1–8 top tables | Every model release |
| **End-to-End Alert Latency** | `<= 15s` p95 from state trigger (after debounce) to UI alert | Synthetic RTSP replay integration benchmark | Pre-release & weekly ops check |
| **Live Floor Map UI Sync** | `<= 2s` p95 from backend state event to WebSocket render | Automated E2E test with WebSocket timestamp instrumentation | Every release |
| **Camera Stream Uptime Recovery** | Auto-reconnect within `30s` after transient RTSP drop | Failure-injection test killing MediaMTX/RTSP source | Every release |
| **Self-Host Time-to-First-Floor-Map** | `<= 15 minutes` from `git clone` to working demo with sample video | Clean-machine Docker Compose smoke test | Every release |

---

## 7. Open Questions & Professional Review Items
- `OPEN-001`: Which POS system (Toast, Square, Clover, Petpooja) should be prioritized for v1.1 webhook integration? (Owner: Project Maintainer; Resolve-by: Post-v1.0 roadmap)
- `OPEN-002`: Should staff-visit detection in v1.0 rely primarily on standing-person-at-table-edge dwell heuristics, or also allow optional uniform-color calibration per venue? (`PROPOSED` default: standing-person proximity heuristic + optional apron/shirt color hint, with manual tap override always available).
- `PROFESSIONAL REVIEW` (`PRO-001`): Restaurants deploying TablePulse must comply with local workplace monitoring and CCTV privacy laws (e.g., signage notifying patrons and staff, GDPR Art. 6/13, CCPA, India DPDP Act 2023). Deployers must obtain legal counsel for their jurisdiction before enabling camera monitoring in production.
