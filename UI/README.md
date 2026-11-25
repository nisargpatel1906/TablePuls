# TablePulse UI — Liquid Glass, 3 devices x light/dark

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## What is here
- **17 views** (SCR-001 to SCR-016 plus the Design System Style Sheet) x **3 devices** x **2 themes** = **102 PNGs**.
- One `design.md` per view with per-device layout, components, states, light/dark tokens, accessibility, a **Real Data Binding** table and a **Gaps** list.
- `DESIGN-SYSTEM.md` with global tokens and responsive behaviour.

## Settings used
| Device | Viewport | Pixel ratio | Emulation |
|---|---|---|---|
| Phone | 390 x 844 | 2 | mobile + touch |
| Tablet (portrait) | 834 x 1194 | 2 | mobile + touch |
| Desktop | 1440 x 810 | 1 | none |

Base height is a minimum. Pages taller than the base were captured at full height. SCR-007 is an overlay: its PNGs keep the device viewport and grow only until the sheet content fits.

## How it was captured
Real headless Chrome (not html-to-image). Tailwind compiled locally because the CDN was blocked; Inter used because SF Pro is unavailable. The prototype's state was set directly (screen, theme), preview bar and toasts removed, the pulse animation frozen at one phase, then the viewport was resized to the content height and captured.

## Index (heights are light-mode CSS px: P phone, T tablet, D desktop)
| Screen | Name | Images | Spec | Heights |
|---|---|---|---|---|
| `SCR-001` | Login | `UI/SCR-001-login/` (6 PNGs) | `UI/SCR-001-login/design.md` | P 844 · T 1194 · D 810 |
| `SCR-002` | Accept Invite / Register | `UI/SCR-002-register/` (6 PNGs) | `UI/SCR-002-register/design.md` | P 844 · T 1194 · D 810 |
| `SCR-003` | Forgot & Reset Password | `UI/SCR-003-reset-password/` (6 PNGs) | `UI/SCR-003-reset-password/design.md` | P 844 · T 1194 · D 810 |
| `SCR-004` | First-Run Venue Onboarding Wizard | `UI/SCR-004-onboarding/` (6 PNGs) | `UI/SCR-004-onboarding/design.md` | P 844 · T 1194 · D 810 |
| `SCR-005` | Live Floor Map (Live Host Floor) | `UI/SCR-005-live-floor-map/` (6 PNGs) | `UI/SCR-005-live-floor-map/design.md` | P 2259 · T 1872 · D 1030 |
| `SCR-006` | Live Camera Wall & AI Overlay | `UI/SCR-006-live-camera-wall/` (6 PNGs) | `UI/SCR-006-live-camera-wall/design.md` | P 1658 · T 2369 · D 973 |
| `SCR-007` | Table Detail & Manual Override Drawer | `UI/SCR-007-table-detail/` (6 PNGs) | `UI/SCR-007-table-detail/design.md` | P 959 · T 1194 · D 938 |
| `SCR-008` | Active Alerts & Service Queue | `UI/SCR-008-alerts-queue/` (6 PNGs) | `UI/SCR-008-alerts-queue/design.md` | P 1067 · T 1194 · D 810 |
| `SCR-009` | Waitlist & Predicted Turnover Queue | `UI/SCR-009-waitlist/` (6 PNGs) | `UI/SCR-009-waitlist/design.md` | P 1716 · T 1342 · D 943 |
| `SCR-010` | Peak Hours & Staffing Analytics | `UI/SCR-010-analytics/` (6 PNGs) | `UI/SCR-010-analytics/design.md` | P 1005 · T 1194 · D 810 |
| `SCR-011` | ML Confidence & Human-Review Queue | `UI/SCR-011-ml-review/` (6 PNGs) | `UI/SCR-011-ml-review/design.md` | P 1180 · T 1223 · D 828 |
| `SCR-012` | Camera & RTSP Stream Management | `UI/SCR-012-camera-settings/` (6 PNGs) | `UI/SCR-012-camera-settings/design.md` | P 1278 · T 1194 · D 810 |
| `SCR-013` | Interactive Table Polygon & ROI Editor | `UI/SCR-013-polygon-editor/` (6 PNGs) | `UI/SCR-013-polygon-editor/design.md` | P 1116 · T 1253 · D 810 |
| `SCR-014` | Alert Rules & Threshold Settings | `UI/SCR-014-alert-rules/` (6 PNGs) | `UI/SCR-014-alert-rules/design.md` | P 856 · T 1194 · D 810 |
| `SCR-015` | Users, Roles & Audit Log Admin | `UI/SCR-015-users-audit/` (6 PNGs) | `UI/SCR-015-users-audit/design.md` | P 844 · T 1194 · D 810 |
| `SCR-016` | System Health, Model Registry & Privacy | `UI/SCR-016-system-health/` (6 PNGs) | `UI/SCR-016-system-health/design.md` | P 1491 · T 1362 · D 810 |
| `STYLE-SHEET` | Design System Style Sheet | `UI/TOKENS-style-sheet/` (6 PNGs) | `UI/TOKENS-style-sheet/design.md` | P 1403 · T 1194 · D 810 |

## Assumed data model (CONFIRM WITH BACKEND)
Venue (name, timezone, operatingHours) · Section · Table (label, section, seats, shape, layout x/y/w/h) · TableState (status, guestCount, confidence, since, manualOverride) · TableStateEvent · Camera (name, rtspUrl [secret], status, targetFps, lastFrameAt) · TablePolygon / ExclusionZone · Detection (snapshotRef) · Alert (type, severity, tableId, createdAt, status, params) · WaitlistEntry (partyName, size, createdAt, quotedMinutes, notes) · TurnoverPrediction (etaRange, confidence) · ReviewItem / ReviewLabel · User / Membership (role, venueScope) · Invitation · AuditLog · AlertRule · NotificationChannel · ModelVersion (+ evaluation) · RetentionPolicy · SystemFlag (aiInferenceEnabled). Endpoint and field names in the specs are placeholders until the real schema is confirmed.

## Global findings from the prototype (apply to many screens)
1. **Invalid Tailwind opacity steps.** These classes cannot be generated (Tailwind only supports steps like 10, 15, 20, 25...), so the tint never appears, in the exports and in a normal browser: `bg-[#34C759]/14`, `bg-[#007AFF]/14`, `bg-[#007AFF]/12`, `bg-[#FF3B30]/14`, `bg-[#8E8E93]/18`, `bg-[#FF9500]/16`, `dark:bg-[#0A84FF]/24`, `bg-[#FF3B30]/12`, `bg-[#FFCC00]/22`, `dark:bg-[#FF9F0A]/22`, `dark:bg-[#0A84FF]/22`, `dark:bg-[#8E8E93]/28`, `bg-white/12`, `bg-[#FF9500]/18`, `bg-black/32`, `bg-[#007AFF]/26`, `dark:bg-[#0A84FF]/32`. Effect: many pill/badge tints are missing, the non-peak bars on SCR-010 are invisible, and the dim backdrop (`bg-black/32`) is not applied. Fix with valid steps or `/[0.14]` syntax.
2. **Sticky offsets assume a preview bar.** Header uses `top-12`, sidebar `top-14`; without the 48px bar they shift content. Export copy overrides to 0 (small screens) and 14px (large). Implement the same.
3. **Placeholders appear literally** in messages such as `Guests waiting [MM:SS] ...` and `~[X–Y] min`. Real text must be generated from data.
4. **Prototype shortcuts that fake behaviour:** `Mark Attended` invents 2 guests; override reason is never read; label buttons on SCR-011 do not store labels; SCR-013 canvas is not interactive; kill switch and purge have no confirmation; `Switch` chip on SCR-003 and the demo block on SCR-001 are review aids.
5. **Not captured:** other wizard steps (SCR-004 steps 2-4), SCR-003 confirm state, SCR-005 Table List and Next Available tabs, SCR-014 other tabs, SCR-015 Audit tab, modals, the mobile menu, solid (Reduce Transparency) mode, tablet landscape. They are described in each design.md and can be added as extra captures.
