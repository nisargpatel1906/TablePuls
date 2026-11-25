# TablePulse — UI Screens & Interaction Specification

## Quick Reference
- **Purpose**: Complete, implementation-grade UI specification for all 16 screens (`SCR-001` through `SCR-016`) so visual UI assets can be generated separately into a `UI/` folder and referenced directly by an autonomous coding agent (Antigravity).
- **Target Devices**: Desktop (1280px–1920px+ for managers/admins), Tablet Landscape/Portrait (768px–1279px for host stands — primary operational surface), Mobile (360px–767px for servers/bussers checking alerts).
- **Design Reference Folder**: `UI/` (`DECIDED` — user will place generated screen mockups/assets in `UI/<screen-id>-<slug>.png` or `UI/<screen-id>-<slug>/` for the implementation agent to match visually).
- **Visual Guidance Rule**: This document defines layout regions, information hierarchy, controls, states, and accessibility without dictating rigid hex codes or brand fonts; the implementation agent must take visual styling (colors, typography, spacing, corner radii) from assets placed in `UI/`, falling back to a clean neutral slate + semantic status palette (`PROPOSED`: green=Free, red=Occupied, amber=Needs Cleaning, orange/pulsing=Needs Service, blue=Reserved, gray=Unknown) if an asset is absent.

---

## 1. Screen Inventory & Navigation Map

| Screen ID | Screen Name | Route | Primary Roles | Asset Target Path (`UI/`) |
|---|---|---|---|---|
| `SCR-001` | Login | `/login` | Public (Unauthenticated) | `UI/SCR-001-login.png` |
| `SCR-002` | Accept Invite / Register | `/register` | Public (Invite Token) | `UI/SCR-002-register.png` |
| `SCR-003` | Forgot & Reset Password | `/reset-password` | Public | `UI/SCR-003-reset-password.png` |
| `SCR-004` | First-Run Venue Onboarding Wizard | `/onboarding` | `OWNER` | `UI/SCR-004-onboarding.png` |
| `SCR-005` | Live Floor Map (Live Host Floor) | `/venues/:venueId/floor` | `HOST`, `MANAGER`, `OWNER`, `STAFF`, `VIEWER` | `UI/SCR-005-live-floor-map.png` |
| `SCR-006` | Live Camera Wall & AI Overlay | `/venues/:venueId/cameras/live` | `MANAGER`, `OWNER`, `HOST` (if granted) | `UI/SCR-006-live-camera-wall.png` |
| `SCR-007` | Table Detail & Manual Override Drawer | Overlay on `SCR-005` or `/venues/:venueId/tables/:tableId` | `HOST`, `MANAGER`, `OWNER`, `STAFF` | `UI/SCR-007-table-detail.png` |
| `SCR-008` | Active Alerts & Service Queue | `/venues/:venueId/alerts` | `STAFF`, `HOST`, `MANAGER`, `OWNER` | `UI/SCR-008-alerts-queue.png` |
| `SCR-009` | Waitlist & Predicted Turnover Queue | `/venues/:venueId/waitlist` | `HOST`, `MANAGER`, `OWNER` | `UI/SCR-009-waitlist.png` |
| `SCR-010` | Peak Hours & Staffing Analytics | `/venues/:venueId/analytics` | `MANAGER`, `OWNER`, `VIEWER` | `UI/SCR-010-analytics.png` |
| `SCR-011` | ML Confidence & Human-Review Queue | `/venues/:venueId/ml-review` | `MANAGER`, `OWNER` | `UI/SCR-011-ml-review.png` |
| `SCR-012` | Camera & RTSP Stream Management | `/venues/:venueId/settings/cameras` | `MANAGER`, `OWNER` | `UI/SCR-012-camera-settings.png` |
| `SCR-013` | Interactive Table Polygon & ROI Editor | `/venues/:venueId/settings/cameras/:cameraId/calibrate` | `MANAGER`, `OWNER` | `UI/SCR-013-polygon-editor.png` |
| `SCR-014` | Alert Rules & Threshold Settings | `/venues/:venueId/settings/alerts` | `MANAGER`, `OWNER` | `UI/SCR-014-alert-rules.png` |
| `SCR-015` | Users, Roles & Audit Log Admin | `/org/users` | `OWNER`, `MANAGER` (scoped) | `UI/SCR-015-users-audit.png` |
| `SCR-016` | System Health, Model Registry & Privacy | `/org/system` | `OWNER` | `UI/SCR-016-system-health.png` |

### Persistent App Shell (Authenticated Screens `SCR-005`–`SCR-016`)
- **Left Navigation Rail** (Desktop: 240px collapsible to 64px icons; Tablet: collapsible drawer; Mobile: bottom tab bar with 4 core items: Floor, Alerts, Waitlist, More):
  - Venue switcher dropdown (top)
  - Primary nav: Live Floor (`SCR-005`), Live Cameras (`SCR-006`), Alerts (`SCR-008` with live unread badge), Waitlist (`SCR-009`), Analytics (`SCR-010`), ML Review (`SCR-011` with pending count badge)
  - Admin nav (role-gated): Cameras (`SCR-012`), Alert Rules (`SCR-014`), Users & Audit (`SCR-015`), System & Privacy (`SCR-016`)
- **Top Status Bar** (56px height):
  - Live WebSocket connection pill (`Live` green / `Reconnecting...` amber / `Polling Fallback` gray)
  - Current venue occupancy summary pill (`Tables 12/24 • Guests 42/96 • 44%`)
  - Real-time toast container (top-center, e.g., `CCTV: Party left Table 23 — Needs Cleaning`)
  - User menu (profile, role badge, dark/light mode toggle, Sign Out)

---


### Canonical Table-State Visual Legend (Color + Icon + Pattern — Never Color-Only)
| State | Label | Icon Concept | Non-Color Pattern | Token (from `UI/`) |
|---|---|---|---|---|
| `FREE` | Free | Check circle | Solid outline | `--state-free` |
| `OCCUPIED` | Occupied | People | Solid fill | `--state-occupied` |
| `NEEDS_SERVICE` | Needs Service | Bell / hand | Pulsing double-ring (static if reduced motion) | `--state-needs-service` |
| `NEEDS_CLEANING` | Needs Cleaning | Sparkle / broom | Dashed outline | `--state-needs-cleaning` |
| `RESERVED` | Reserved | Bookmark | Dotted outline | `--state-reserved` |
| `UNKNOWN` | Unsure / Offline | Question / camera-off | Diagonal hatch | `--state-unknown` |

*See `UI/README.md` for asset naming conventions, P1/P2 priority tiers, and token extraction rules.*

---

## 2. Detailed Screen Specifications

### `SCR-001` — Login
- **Purpose & Users**: Authenticate existing users into TablePulse. All roles.
- **Layout & Regions**: Centered single-column card (max-width 420px) on clean neutral canvas; top product logo + title; form body; footer links. Responsive: full-width padded card on mobile.
- **Visible Content & Controls**:
  - Email input (`type="email"`, autocomplete `username`)
  - Password input with show/hide visibility toggle
  - Primary CTA: **Sign In**
  - Secondary link: **Forgot password?** -> `SCR-003`
  - Optional Demo Mode banner (visible only when `DEMO_MODE=true` env var is enabled) with a one-click **Sign in as Demo Manager** button.
- **Navigation**: Entry from any unauthenticated route; Exit on success to default role home (`SCR-005` for Host/Manager/Owner/Viewer, `SCR-008` for Staff) or `SCR-004` if no venue exists yet.
- **States**:
  - *Loading*: Button disabled with spinner and text "Signing in...".
  - *Validation Error*: Inline field errors ("Enter a valid email", "Password is required").
  - *Auth Error*: Banner above form ("Invalid email or password") without leaking whether the email exists. Rate-limit error (`429`) shows countdown timer.
  - *Session Expired*: Info banner when redirected with `?reason=expired`.
- **Accessibility**: Proper `<label>` bindings, `aria-invalid` and `aria-describedby` on errors, `Enter` submits form, focus moves to error summary on failure.

### `SCR-002` — Accept Invite / Register
- **Purpose & Users**: Complete account creation from an `OWNER`/`MANAGER` invitation link (or bootstrap the very first `OWNER` account on a fresh install).
- **Layout & Regions**: Centered card (max-width 460px); invite context header ("You've been invited to join [Venue Name] as [Role]"); form fields.
- **Visible Content & Controls**: Read-only pre-filled Email, Full Name input, Password input with live strength indicator (min 12 chars, mixed classes), Confirm Password input, **Create Account** CTA.
- **Navigation**: Entry via `/register?token=...` or `/setup` (first-run bootstrap); Exit to `SCR-004` (if bootstrap owner) or `SCR-005` (if invited staff).
- **States**: Loading (validating invite token), Expired/Invalid Token state (clear message + link to `SCR-001`), Validation Error, Success (auto-login & redirect).
- **Accessibility**: Password requirements linked via `aria-describedby`; strength meter uses `aria-live="polite"`.

### `SCR-003` — Forgot & Reset Password
- **Purpose & Users**: Self-service password recovery for all roles.
- **Layout & Regions**: Centered card (max-width 420px). Two sub-states: Request Reset (email input) and Confirm Reset (when `?token=` is present).
- **Visible Content & Controls**: Email input + **Send Reset Link**; OR New Password + Confirm Password + **Reset Password**.
- **Navigation**: Entry from `SCR-001` or email link; Exit to `SCR-001` with success banner.
- **States**: Loading, Generic Success ("If an account exists for that email, a reset link has been sent" — prevents email enumeration), Expired Token error, Validation error.
- **Accessibility**: Same form accessibility contract as `SCR-001`.

### `SCR-004` — First-Run Venue Onboarding Wizard
- **Purpose & Users**: Guided 4-step setup so a new `OWNER` goes from fresh Docker deploy to a live floor map in <=15 minutes.
- **Layout & Regions**: Full-page stepper header (Steps 1–4), centered content panel (max-width 760px), sticky bottom bar (`Back`, `Skip for now`, `Continue`).
- **Steps & Controls**:
  1. **Venue Details**: Venue Name, Timezone selector, Opening/Closing hours, Privacy Default toggle (`Face Blur ON by default`).
  2. **Connect First Camera**: RTSP URL input, username/password (optional), **Test Connection** button showing live snapshot preview, OR **Load Sample Restaurant Video** button for instant testing.
  3. **Map Tables**: Embedded simplified polygon drawer (`SCR-013` component) to draw at least 1 table polygon + seat count.
  4. **Alert Thresholds**: Unattended service alert minutes (default `5`), Dirty table alert minutes (default `2`), **Launch Live Floor** CTA.
- **Navigation**: Entry after bootstrap registration; Exit to `SCR-005`.
- **States**: Camera connection testing spinner, RTSP connection failure with actionable troubleshooting hint (credentials, port 554, firewall), Step validation errors.
- **Accessibility**: Stepper uses `aria-current="step"`, keyboard navigation between form fields, non-mouse fallback instructions for polygon step.

### `SCR-005` — Live Floor Map (Live Host Floor)
- **Purpose & Users**: Primary real-time operational workspace (inspired directly by the video's "LIVE HOST FLOOR" screen). Used by `HOST`, `MANAGER`, `OWNER`, `STAFF`, `VIEWER`.
- **Layout & Regions**:
  - **Top KPI Strip**: 4 compact cards — `Tables Occupied (X/Y)`, `Seated Guests (A/B)`, `Floor Capacity (%)`, `Active Alerts (N)`.
  - **Filter & Control Bar**: Section filter chips (`All Sections`, `Main Hall`, `Patio`, `Bar`), Status filter (`All`, `Free`, `Occupied`, `Needs Service`, `Needs Cleaning`, `Unknown`), Search by Table ID, Zoom/Fit controls, Toggle `Show Timers` / `Show Guest Counts`.
  - **Main Canvas (70% width on desktop/tablet landscape)**: Interactive 2D floor plan displaying each table shape (square/circle/rectangle) with:
    - Table ID (`T01`), Status color + distinct icon/pattern (color-blind safe), Guest count (`3/4`), Live dwell timer (`14:22`), and subtle pulsing ring for `NEEDS_SERVICE` or `NEEDS_CLEANING`.
  - **Right Operational Sidebar (30% width, collapsible drawer on tablet portrait/mobile)**: Two tabs — `Active Alerts` (top 5 urgent alerts with 1-tap Ack/Clean) and `Next Available` (ranked occupied tables closest to predicted turnover + mini waitlist count).
- **Interactions**:
  - Clicking/tapping any table opens `SCR-007` (Table Detail & Manual Override Drawer).
  - Clicking an alert item highlights and pans to that table on the floor map.
  - Real-time updates arrive over WebSocket without full-page reloads; top-center toast appears on major state transitions (e.g., `CCTV: Party left Table 23`).
- **Navigation**: Default home screen; links to `SCR-006`, `SCR-007`, `SCR-008`, `SCR-009`.
- **States**:
  - *Loading*: Skeleton KPI cards + canvas shimmer.
  - *Empty (No Tables Configured)*: Centered illustration + **Configure Cameras & Tables** CTA (`OWNER`/`MANAGER`) or "Ask your manager to configure tables" (`HOST`/`STAFF`).
  - *Degraded / WebSocket Disconnected*: Amber banner ("Live stream paused — refreshing every 5s") with auto-polling fallback.
  - *Camera Offline*: Affected tables show gray `UNKNOWN` badge with camera-offline icon.
  - *Permission-Denied (Viewer)*: Manual override buttons hidden; read-only badge shown.
- **Accessibility**: Every table also accessible via a toggleable **Accessible Table List View** (standard keyboard-navigable HTML table) so screen-reader and keyboard-only users never rely solely on canvas interaction. Statuses use icon + text label in addition to color.

### `SCR-006` — Live Camera Wall & AI Overlay View
- **Purpose & Users**: Live WebRTC CCTV grid with real-time AI polygon overlays (mirrors the video's green/red overhead table overlays). Used by `OWNER`, `MANAGER`, and `HOST` (if camera view permission is enabled).
- **Layout & Regions**: Top toolbar (grid selector `1x1`, `2x2`, `3x3`; overlay toggles: `Table Polygons`, `Guest Counts & Timers`, `Bounding Boxes`, `Face Blur Indicator`), Main video grid.
- **Visible Content & Controls**:
  - Each camera tile renders a low-latency WebRTC (`WHEP`) video player with an SVG/Canvas overlay synced to the latest inference frame: green polygon (`T01 FREE`), red polygon (`T02 • 2 Guests • 00:05`), amber polygon (`T05 NEEDS CLEANING`), orange pulsing polygon (`T04 NEEDS SERVICE • 05:12`).
  - Top-left HUD inside single-camera focus mode: `RESTAURANT OCCUPANCY | TABLES 2/6 | SEATED GUESTS 6/24 | CAPACITY 25%`.
  - Per-tile header: Camera name, FPS & inference latency badge (`12 FPS • 48ms`), `Privacy Blur: ON` shield badge, Fullscreen button, **Calibrate Polygons** shortcut (`SCR-013`).
- **Navigation**: Entry from left nav or `SCR-005` / `SCR-007`; Exit to `SCR-013` (calibration) or `SCR-005`.
- **States**: Loading stream spinner, Stream Offline / Reconnecting overlay with last-seen timestamp and **Retry Stream** button, Empty (no cameras connected), Permission Denied (for `STAFF`/`VIEWER` or ungranted `HOST`).
- **Accessibility**: Video tiles have `aria-label` describing camera name and live occupancy summary; keyboard `Esc` exits fullscreen; flashing/pulsing overlays respect `prefers-reduced-motion`.

### `SCR-007` — Table Detail & Manual Override Drawer
- **Purpose & Users**: Inspect a single table's live state, camera crop snapshot, recent event timeline, and perform manual overrides. Used by `HOST`, `STAFF`, `MANAGER`, `OWNER`.
- **Layout & Regions**: Slide-over right drawer (440px wide on desktop/tablet; full-screen sheet on mobile).
- **Visible Content & Controls**:
  - Header: Table ID (`T04`), Section (`Main Hall`), Capacity (`4 seats`), Current State badge, Live dwell timer.
  - Latest Anonymized Snapshot (face-blurred crop of just this table) + ML confidence score (`94% confidence` or `Low confidence: 58%`).
  - **Quick Action Buttons** (role-filtered):
    - `Mark Clean (Free)` (`STAFF`, `HOST`, `MANAGER`, `OWNER`)
    - `Mark Service Attended` (`STAFF`, `HOST`, `MANAGER`, `OWNER`)
    - `Toggle Reserved` (`HOST`, `MANAGER`, `OWNER`)
    - `Override State / Guest Count` (`HOST`, `MANAGER`, `OWNER`) — opens inline selector with required reason note.
    - `Flag Wrong AI Detection` (`HOST`, `MANAGER`, `OWNER`) — creates an item in `SCR-011` ML Review Queue.
  - **Recent Activity Timeline**: Last 10 state transitions with timestamp, source (`AI` vs `Manual by [Name]`), and confidence.
- **Navigation**: Opens from `SCR-005`, `SCR-006`, or `SCR-008`; closes back to parent screen.
- **States**: Loading timeline, Action submitting spinner, Conflict error (`409` if state changed concurrently — refreshes automatically), Success toast.
- **Accessibility**: Focus trapped inside drawer while open, `Esc` closes drawer and restores focus to triggering table.

### `SCR-008` — Active Alerts & Service Queue
- **Purpose & Users**: Dedicated operational inbox for `NEEDS_SERVICE`, `NEEDS_CLEANING`, `CAMERA_OFFLINE`, and `LOW_CONFIDENCE` alerts. Primary mobile/tablet screen for `STAFF`.
- **Layout & Regions**: Top filter bar (Alert Type, Section, Status: `Active` / `Acknowledged` / `Resolved Today`), Audio chime mute toggle, Main vertical alert card list sorted by severity and elapsed duration.
- **Visible Content & Controls**:
  - Each alert card shows: Severity badge, Table ID + Section, Alert description (`Table 02: Guests waiting 05:24 without waiter`), Elapsed time ticker, Primary 1-tap button (`Acknowledge` / `Mark Cleaned` / `Mark Served`), Secondary button (`View Table` -> `SCR-007`).
- **Navigation**: Entry from left nav, bottom tab bar, or toast click; links to `SCR-007` and `SCR-014` (Alert Rules for managers).
- **States**: Loading skeleton cards, Empty ("All tables attended — no active alerts" with green checkmark), Action error with retry, Success confirmation toast.
- **Accessibility**: New critical alerts announced via `aria-live="assertive"`; large >=44x44px touch targets for busy servers on mobile.

### `SCR-009` — Waitlist & Predicted Turnover Queue
- **Purpose & Users**: Manage waiting entrance parties and match them to the tables predicted to become free soonest (directly fulfilling the video's entrance-line scenario). Used by `HOST`, `MANAGER`, `OWNER`.
- **Layout & Regions**: Two-column split on desktop/tablet landscape (stacked tabs on mobile):
  - **Left Column — Waiting Parties**: `+ Add Party` button, ordered list of waiting guests (Party Name, Party Size, Wait Elapsed, Quoted Wait, Notes, Actions: `Seat`, `Cancel`, `No-Show`).
  - **Right Column — Predicted Next Available Tables**: Filter by party size (`>=2`, `>=4`, `>=6`), ranked table cards showing Table ID, Seats, Current Dwell Time, **Estimated Time to Free** (e.g., `~6–10 min`, confidence badge `High`/`Med`/`Low`), and current state (`FREE` / `NEEDS_CLEANING` / `OCCUPIED`).
- **Visible Content & Controls**: Add Party modal (Name, Party Size 1–20, Optional Phone/Note, Quoted Wait auto-suggested from predicted turnover), 1-click **Assign & Seat** flow linking a waiting party to a `FREE` table.
- **Navigation**: Entry from left nav or `SCR-005` sidebar; Exit to `SCR-005` on seat assignment.
- **States**: Loading, Empty waitlist ("No parties waiting"), Insufficient historical data state for ETA ("Using baseline 45m turn estimate — improves after 7 days of venue data"), Validation error on Add Party.
- **Accessibility**: Modal focus trap, clear table/list semantics, ETA confidence conveyed in text (not color alone).

### `SCR-010` — Peak Hours & Staffing Analytics Dashboard
- **Purpose & Users**: Historical occupancy, wait-time, turn-time, and SLA breach analytics to schedule the right number of waiters (directly fulfilling the video's weekly Peak Hours Analysis tablet view). Used by `MANAGER`, `OWNER`, `VIEWER`.
- **Layout & Regions**:
  - Top Control Bar: Date Range picker (`Today`, `Last 7 Days`, `Last 30 Days`, `Custom`), Section filter, **Export CSV** button.
  - KPI Summary Row (4 cards): `Peak Occupancy Hour`, `Avg Table Turn Time`, `Avg Service Response Time`, `SLA Breach Rate (%)`.
  - Primary Chart (Full width): **Peak Hours Occupancy & Guest Volume** multi-series line chart (X-axis: Hour of day `08:00`–`23:00`; Y-axis: Occupancy % & Seated Guests; series comparing selected days or Weekday vs. Weekend).
  - Secondary Row (2 columns):
    - Left: **Day × Hour Heatmap** (Mon–Sun vs. operating hours) highlighting peak windows.
    - Right: **Recommended Waiter Staffing Curve** bar chart (derived from configurable guests-per-server ratio, e.g., 1 server per 16 guests, editable inline).
  - Bottom Table: Per-table utilization & average turn duration breakdown.
- **Navigation**: Entry from left nav; standalone analytics view.
- **States**: Loading skeletons, Empty ("Not enough data yet — analytics populate after 1 hour of live monitoring"), Export generating spinner, Error banner with retry.
- **Accessibility**: Every chart includes a **View as Data Table** toggle and descriptive `aria-label`; color palettes are CVD-safe.

### `SCR-011` — ML Confidence & Human-Review Queue
- **Purpose & Users**: Human-in-the-loop review queue for low-confidence (`UNKNOWN`) table states and host-flagged misclassifications, supporting model auditability and dataset improvement. Used by `MANAGER`, `OWNER`.
- **Layout & Regions**: Filter bar (`Pending`, `Reviewed`, Filter by Camera/Table/Reason), Split view: Left list of queued snapshots, Right inspection pane.
- **Visible Content & Controls**:
  - Face-blurred table crop image with model's predicted state, guest count, and confidence score.
  - Reviewer controls: Correct State selector (`FREE`, `OCCUPIED`, `NEEDS_CLEANING`, `OCCUPIED_WITH_STAFF`), Correct Guest Count stepper, Occlusion/Lighting tag checkboxes (`Low Light`, `Heavy Occlusion`, `Glare`, `Edge of Frame`), **Save & Next** CTA, **Exclude from Training** checkbox.
  - Top summary: Review completion count and current measured agreement rate vs. model predictions.
- **Navigation**: Entry from left nav or `SCR-007` flag action.
- **States**: Loading, Empty ("No uncertain detections pending review"), Error saving correction.
- **Accessibility**: Keyboard shortcuts (`1`–`4` for state selection, `Enter` to save & advance) documented in a visible shortcut legend.

### `SCR-012` — Camera & RTSP Stream Management
- **Purpose & Users**: Add, test, edit, disable, or delete RTSP/ONVIF cameras and sample demo video streams. Used by `OWNER`, `MANAGER`.
- **Layout & Regions**: Header with `+ Add Camera` CTA; table/card grid of configured cameras.
- **Visible Content & Controls**:
  - Per camera: Name (`Ceiling Cam North`), Masked RTSP URL (`rtsp://***@192.168.1.40:554/stream1`), Status (`Online`, `Reconnecting`, `Offline`, `Disabled`), Mapped Tables count, Target FPS (`2`–`5 FPS` inference), Privacy Face-Blur toggle, Actions (`Test`, `Calibrate Polygons` -> `SCR-013`, `Edit`, `Delete`).
  - Add/Edit Modal: Camera Name, Stream Type (`RTSP/RTSPS`, `Demo MP4 File`), URL, Credentials (encrypted at rest, never echoed back after save), Inference FPS slider (`1`–`5 FPS`), Privacy Blur toggle, **Test Connection** button.
- **Navigation**: Entry from Admin nav; links to `SCR-013` and `SCR-006`.
- **States**: Testing spinner, Invalid RTSP URL validation, Connection refused diagnostic message, Delete confirmation modal warning that mapped tables will lose automated tracking.
- **Accessibility**: Masked credential inputs with explicit "Leave blank to keep existing password" helper text.

### `SCR-013` — Interactive Table Polygon & ROI Calibration Editor
- **Purpose & Users**: Visually map each table's pixel polygon on a camera snapshot and place/align it on the 2D Floor Map. Used by `OWNER`, `MANAGER`.
- **Layout & Regions**:
  - Top Toolbar: Camera selector, **Refresh Snapshot**, Mode buttons (`Draw Polygon`, `Select/Edit Vertex`, `Draw Exclusion Zone`), Undo/Redo, **Save Calibration** CTA.
  - Main Canvas (75% width): High-resolution camera snapshot with interactive draggable polygon vertices and table labels.
  - Right Inspector Panel (25% width): Selected Table properties — Table ID (`T01`), Display Label, Section dropdown, Seat Capacity (`1`–`20`), Shape (`Rectangle`, `Circle`, `Booth`), Floor Map X/Y coordinates preview, **Delete Polygon** button.
- **Visible Content & Controls**: Vertex snapping, polygon self-intersection validation warning, minimum 3-point polygon enforcement.
- **Navigation**: Entry from `SCR-012`, `SCR-006`, or `SCR-004`; unsaved-changes guard modal on exit.
- **States**: Loading snapshot, Snapshot unavailable (camera offline), Validation error (duplicate Table ID or <3 vertices), Save success toast.
- **Accessibility**: Coordinate list editor fallback in right panel so vertices can be adjusted numerically via keyboard.

### `SCR-014` — Alert Rules & Threshold Settings
- **Purpose & Users**: Configure per-venue or per-section operational thresholds and notification channels. Used by `OWNER`, `MANAGER`.
- **Layout & Regions**: Tabbed form layout: `Thresholds`, `Notification Channels`, `Quiet Hours`.
- **Visible Content & Controls**:
  - **Thresholds**: Unattended service alert delay (default `5 min`, range `1–30 min`), Dirty table alert delay (default `2 min`, range `0–15 min`), Occupancy debounce window (default `10 sec`), Low-confidence escalation delay (default `30 sec`), Alert cooldown/snooze duration.
  - **Notification Channels**: In-App Toast & Sound (on/off), Generic Webhook URL (with HMAC signing secret + **Send Test Webhook** button), Slack Webhook URL, Telegram Bot Token + Chat ID.
  - **Quiet Hours**: Suppress alerts outside venue operating hours.
- **Navigation**: Entry from Admin nav or `SCR-008`.
- **States**: Loading, Test webhook sending/success/failure feedback, Validation errors on out-of-range numbers or invalid URLs, Unsaved changes bar.
- **Accessibility**: Range sliders paired with numeric inputs; test results announced via `aria-live="polite"`.

### `SCR-015` — Users, Roles & Audit Log Administration
- **Purpose & Users**: Invite users, assign venue-scoped roles, revoke sessions, and inspect immutable audit logs. Used by `OWNER` (full) and `MANAGER` (limited to `HOST`/`STAFF`/`VIEWER` in their venue).
- **Layout & Regions**: Two tabs — `Team Members` and `Audit Log`.
- **Visible Content & Controls**:
  - *Team Members*: `+ Invite User` CTA, searchable table (Name, Email, Role badge, Assigned Venues, Status `Active`/`Pending`/`Disabled`, Last Login, Actions: `Change Role`, `Disable`, `Revoke Sessions`).
  - *Audit Log*: Filter by Actor, Action (`OVERRIDE_TABLE`, `UPDATE_CAMERA`, `CHANGE_ROLE`, `TOGGLE_KILL_SWITCH`), Date Range; paginated read-only table + CSV export.
- **Navigation**: Entry from Admin nav.
- **States**: Loading, Empty search results, Self-demotion prevention error ("At least one active Owner is required"), Permission denied for non-admins.
- **Accessibility**: Proper table headers (`scope="col"`), confirmation dialog for destructive revocations.

### `SCR-016` — System Health, Model Registry & Privacy Settings
- **Purpose & Users**: Monitor inference worker health, GPU/CPU load, active ML model version, drift metrics, global AI kill switch, and privacy retention policies. Used by `OWNER` only.
- **Layout & Regions**: 4 modular panels in a 2×2 responsive grid:
  1. **Service & Worker Health**: API, PostgreSQL 16, Valkey, MediaMTX, CV Worker status cards; per-camera FPS, queue depth, inference p95 latency.
  2. **ML Model Registry & Evaluation**: Active detector & cleanliness model versions, date deployed, recorded offline Macro-F1 / MAE benchmark metrics (clearly labeled with dataset version), **Switch / Rollback Model** control.
  3. **AI Pipeline Kill Switch**: Prominent emergency toggle (`Pause All AI Inference — Manual Floor Mode Only`) with confirmation modal and audit log entry.
  4. **Privacy & Data Retention**: Face Blur enforcement toggle, Snapshot Retention days (default `7 days` for review queue; `0` to disable snapshots entirely), Analytics Retention days (default `365 days`), **Purge All Snapshots Now** action.
- **Navigation**: Entry from Admin nav.
- **States**: Loading, Worker degraded/down red alert banner, Confirmation modal for kill switch or purge, Permission denied (403 screen for non-Owners).
- **Accessibility**: Destructive toggles require explicit confirmation dialog; status indicators pair icons and text labels.

---

## 3. Global UI Quality & Interaction Rules
1. **Every async action** (button click, form submit, override, export) must render explicit **Loading**, **Error** (inline or toast with actionable message — never console-only), and **Success** states (`DECIDED` — production-readiness rule).
2. **SPA Direct-URL Routing**: Navigating directly to any route (e.g., `/venues/123/analytics`) must load cleanly with zero 404s (`DECIDED`).
3. **Uncertainty vs. Failure Separation**: Low ML confidence (`UNKNOWN` — amber/gray question icon) must look and behave distinctly from camera hardware failure (`OFFLINE` — red disconnected-camera icon) (`DECIDED`).
4. **Asset Integration Contract for Antigravity**: When building any screen `SCR-XXX`, check `UI/SCR-XXX-*.png` (or `UI/SCR-XXX-*/`). Match layout proportions, palette, and component styling from the asset while preserving 100% of the functional controls, states, and accessibility requirements specified above.
