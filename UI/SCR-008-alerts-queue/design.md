# SCR-008 — Active Alerts & Service Queue

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-008`
- **Route (prototype):** `/venues/:venueId/alerts`
- **Priority tier:** P1
- **Roles with access:** STAFF, HOST, MANAGER, OWNER
- **Purpose:** Operational alert inbox with 1-tap acknowledge.
- **App chrome:** Floating liquid-glass shell: sidebar (>=1024px) or header pill + bottom dock (<1024px)

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-008-alerts-queue-phone-light.png` | Phone | Light | 390 x 1067 CSS px | @2x -> 780 x 2134 px |
| `SCR-008-alerts-queue-phone-dark.png` | Phone | Dark | 390 x 1067 CSS px | @2x -> 780 x 2134 px |
| `SCR-008-alerts-queue-tablet-light.png` | Tablet | Light | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-008-alerts-queue-tablet-dark.png` | Tablet | Dark | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-008-alerts-queue-desktop-light.png` | Desktop | Light | 1440 x 810 CSS px | @1x -> 1440 x 810 px |
| `SCR-008-alerts-queue-desktop-dark.png` | Desktop | Dark | 1440 x 810 CSS px | @1x -> 1440 x 810 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** App shell. Title + two buttons wrap; status segmented control and type select wrap; alert cards stack, each with severity chip, title, elapsed time, message and two buttons.
- **Tablet (834px):** Same layout with more horizontal room; card rows keep the stacked-then-row pattern (row from 640px).
- **Desktop (1440px):** Sidebar + single column list; each card shows text left and buttons right.

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 1067 / 1067 | 1194 / 1194 | 810 / 810 |
| Sidebar visible | no | no | yes |
| Bottom dock visible | yes | yes | no |
| Hamburger visible | yes | yes | no |
| Horizontal-scroll containers | 0 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 9 | 9 | 10 |
| Examples under 44px | Open navigation menu, 4, Toggle theme, Chime: ON | Open navigation menu, 4, Toggle theme, Chime: ON | [Venue Name — Primary] [Venue Name — Sec, Sign Out, 4, Toggle theme |

## 4. Components and controls
- Title `Active Alerts & Service Queue` + sub copy; `Chime: ON/Muted` and `Alert Rules` (-> SCR-014).
- Filter bar: `Active / Resolved / All` segmented control, `All Alert Types` select (Needs Service, Needs Cleaning, Camera Offline, Low Confidence).
- Alert card (radius 22): severity chip (Critical red / Warning orange / Info grey), `Table T04 · Main Hall`, mono elapsed time, message, `Acknowledge` (blue, 44px) and `View Table`.
- Empty state: green check + `All tables attended — no active alerts`.

**Auto-extracted from the desktop render:**
- Headings: `Active Alerts & Service Queue`
- Table headers: —
- Form fields:
  - `select-one` Venue selector: `[Venue Name — Primary]`
  - `select-one` Filter alert type: `All Alert Types`

## 5. States
Active, resolved, all, empty, acknowledging (pending), failed acknowledge, muted chime.

## 6. Interactions and navigation
View Table -> SCR-007 drawer · Alert Rules -> SCR-014.

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Cards #1C1C1E; severity chips #FF6961 / #FF9F0A / #D1D1D6 text; secondary buttons #2C2C2E.

| Token (measured on desktop render) | Light | Dark |
|---|---|---|
| Body text | `rgb(28, 28, 30)` | `rgb(245, 245, 247)` |
| Solid content card fill | `rgb(255, 255, 255)` | `rgb(28, 28, 30)` |
| Card border | `rgba(60, 60, 67, 0.086)` | `rgba(255, 255, 255, 0.09)` |
| Liquid-glass fill | `rgba(255, 255, 255, 0.72)` | `rgba(28, 28, 30, 0.74)` |
| Liquid-pill fill | `rgba(255, 255, 255, 0.78)` | `rgba(36, 36, 38, 0.78)` |
| Heading colour | `rgb(28, 28, 30)` | `rgb(245, 245, 247)` |
| Heading size | `22px` | `22px` |
| Secondary text | `rgb(99, 99, 102)` | `rgb(174, 174, 178)` |
| Primary button fill | `rgba(0, 0, 0, 0)` | `rgba(0, 0, 0, 0)` |

| Canvas | `#F2F2F7` + soft blue/green washes | `#000000` + brighter blue/green washes |
| Solid card | `#FFFFFF`, 1px rgba(60,60,67,.085) | `#1C1C1E`, 1px rgba(255,255,255,.09) |
| Inset field | `#F2F2F7` | `#2C2C2E` |
| Secondary label | `#636366` | `#AEAEB2` |
| Accent | `#007AFF` | `#0A84FF` (text accents `#409CFF`) |

The theme is switched with the `dark` class on `<html>` plus `dark-canvas` on `<body>`. A Reduce Transparency solid mode also exists in the prototype (`solid-mode` class); it is not part of these PNGs.

## 8. Accessibility
List is `aria-live=polite`; severity is text; buttons are 44px high.

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- Four sample alerts with texts and elapsed times
- Message `Guests waiting [MM:SS] without waiter visit`
- `[Camera Name — Patio] RTSP stream disconnected`

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Alert card | Alert.id, type, severity, tableId, section, createdAt, status, params | Alert list + realtime | Elapsed = now - createdAt (ticks live) | Realtime | - |
| Message text | Generated from Alert.type + params (e.g. waiting minutes, camera name) | Client or server template | Localised sentence | On change | Never store seeded prose |
| Acknowledge | POST alert acknowledge (user, time) | Alert endpoint | Writes audit | On click | Optimistic UI, rollback on error |
| Status / type filters | Query params | List endpoint | Enum | On change | Empty state |
| Chime mute | UserPreference.alertSound | Preferences endpoint | Boolean | On click | - |
| `Resolved` tab window | Time window (prototype says all resolved; spec says today) | List endpoint | Venue-day boundaries in venue timezone | On change | CONFIRM WITH PRODUCT |

**Rules**
- Lists, counts, badges, charts and tables come from queries, never from fixed arrays.
- Derived numbers (percentages, totals, elapsed times, recommended staff) are computed from real data, not stored or typed in.
- Dates, times and numbers use the venue's timezone and the user's locale.
- What is shown respects the logged-in user's role and venue scope.
- No demo credentials, demo banners or prefilled demo values in production.
- If the backend field does not exist yet, mark it CONFIRM WITH BACKEND instead of inventing it.

## 10. Implementation notes
- Two-layer system: floating liquid-glass controls (28px radius, blur 28px, saturate 195%) over crisp solid content cards (24px radius). Inner tiles 16px, pills fully rounded.
- Minimum touch target 44px: see the measured table above for elements that are smaller in the prototype.
- Use tabular numerals for timers, counts and KPIs.
- Every table state is shown by icon + text + border pattern, not colour alone.
- Virtualise long lists and debounce realtime updates.

## 11. Gaps / decisions needed
- Prototype does not sort. Requirement is severity first, then longest elapsed.
- Elapsed times are static strings in the prototype.
- Camera-offline and low-confidence alerts have no `Mark ...` action beyond Acknowledge (fine).
