# SCR-004 — First-Run Venue Onboarding Wizard

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-004`
- **Route (prototype):** `/onboarding`
- **Priority tier:** P1
- **Roles with access:** OWNER
- **Purpose:** First-run setup wizard for an OWNER: venue details, first camera, table mapping, alert thresholds.
- **App chrome:** None. Standalone full-page layout

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-004-onboarding-phone-light.png` | Phone | Light | 390 x 844 CSS px | @2x -> 780 x 1688 px |
| `SCR-004-onboarding-phone-dark.png` | Phone | Dark | 390 x 844 CSS px | @2x -> 780 x 1688 px |
| `SCR-004-onboarding-tablet-light.png` | Tablet | Light | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-004-onboarding-tablet-dark.png` | Tablet | Dark | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-004-onboarding-desktop-light.png` | Desktop | Light | 1440 x 810 CSS px | @1x -> 1440 x 810 px |
| `SCR-004-onboarding-desktop-dark.png` | Desktop | Dark | 1440 x 810 CSS px | @1x -> 1440 x 810 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** No shell. Stepper is a 2x2 grid of pills; content card full width minus 16px (padding 20px). Footer row wraps Back / Skip / Continue. Page can exceed 844px on later steps.
- **Tablet (834px):** Stepper is one row of 4 pills (4 columns start at 640px). Content card up to 780px centred.
- **Desktop (1440px):** Stepper in one row of 4 pills; content card 780px max, centred.

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 844 / 844 | 1194 / 1194 | 810 / 810 |
| Horizontal-scroll containers | 0 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 4 | 4 | 4 |
| Examples under 44px | 1 Venue Details, 2 Connect Camera, 3 Map Tables, 4 Alert Rules | 1 Venue Details, 2 Connect Camera, 3 Map Tables, 4 Alert Rules | 1 Venue Details, 2 Connect Camera, 3 Map Tables, 4 Alert Rules |

## 4. Components and controls
- Header `Venue Onboarding` + sub copy.
- Stepper (liquid-glass pill group): `1 Venue Details`, `2 Connect Camera`, `3 Map Tables`, `4 Alert Rules`. Active = blue fill, done = green tint, `aria-current=step`.
- Step 1: Venue Name, Timezone select, Operating Hours text, green `Privacy Face Blur (ON by default)` panel with ON badge.
- Step 2: RTSP URL (mono), `Test Connection`, `Load Sample Restaurant Video`, 16:9 camera preview.
- Step 3: helper copy, 16:9 preview with polygons, `Mapped Polygons: 4 tables`, `Open Full Polygon Editor` (-> SCR-013).
- Step 4: numeric `Unattended Service Alert (min)` and `Dirty Table Alert Delay (min)`.
- Footer: `Back`, `Skip for now`, `Continue` / green `Launch Live Floor`.

**Auto-extracted from the desktop render:**
- Headings: `Venue Onboarding`
- Table headers: —
- Form fields:
  - `text` (unlabelled): `[Venue Name — Primary]`
  - `select-one` (unlabelled): `[IANA Timezone — e.g. UTC / Local]`
  - `text` (unlabelled): `[HH:MM] – [HH:MM]`

## 5. States
Per-step validation, RTSP test progress/success/failure (firewall hint), saving draft, skip confirmation, launch success.

## 6. Interactions and navigation
Continue / steps pills move within the wizard; Skip and Launch -> SCR-005; Open Full Polygon Editor -> SCR-013.

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Stepper group uses liquid-pill dark (rgba 36,36,38 @78%) with 14% white edge; done pills text #30D158; camera previews are identical to light (feeds stay dark).

| Token (measured on desktop render) | Light | Dark |
|---|---|---|
| Body text | `rgb(28, 28, 30)` | `rgb(245, 245, 247)` |
| Solid content card fill | `rgb(255, 255, 255)` | `rgb(28, 28, 30)` |
| Card border | `rgba(60, 60, 67, 0.086)` | `rgba(255, 255, 255, 0.09)` |
| Liquid-glass fill | — | — |
| Liquid-pill fill | `rgba(255, 255, 255, 0.78)` | `rgba(36, 36, 38, 0.78)` |
| Heading colour | `rgb(28, 28, 30)` | `rgb(245, 245, 247)` |
| Heading size | `24px` | `24px` |
| Secondary text | `rgb(99, 99, 102)` | `rgb(174, 174, 178)` |
| Primary button fill | `rgb(0, 122, 255)` | `rgb(0, 122, 255)` |

| Canvas | `#F2F2F7` + soft blue/green washes | `#000000` + brighter blue/green washes |
| Solid card | `#FFFFFF`, 1px rgba(60,60,67,.085) | `#1C1C1E`, 1px rgba(255,255,255,.09) |
| Inset field | `#F2F2F7` | `#2C2C2E` |
| Secondary label | `#636366` | `#AEAEB2` |
| Accent | `#007AFF` | `#0A84FF` (text accents `#409CFF`) |

The theme is switched with the `dark` class on `<html>` plus `dark-canvas` on `<body>`. A Reduce Transparency solid mode also exists in the prototype (`solid-mode` class); it is not part of these PNGs.

## 8. Accessibility
`aria-current=step` on the active pill; all controls 42-46px high; preview is decorative (needs alt text describing mapped tables).

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- `[Venue Name — Primary]`, `[IANA Timezone — e.g. UTC / Local]`, `[HH:MM] – [HH:MM]`
- RTSP `rtsp://[camera-ip]:554/[stream-path]`
- `Mapped Polygons: 4 tables`
- Defaults 5 min and 2 min

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Venue name | Venue.name | Venue create/update endpoint | Free text | On step save | Required |
| Timezone | Venue.timezone | IANA list from server/browser | IANA id | On step save | Required; drives every timestamp in the product |
| Operating hours | Venue.operatingHours (per weekday?) | Venue endpoint | Local time HH:MM, 24h or locale | On step save | CONFIRM: prototype has one range, real venues need per-day |
| Face blur default | PrivacyPolicy.faceBlurEnforced | Policy endpoint | Boolean (read-only here) | On load | Cannot be turned off from onboarding |
| RTSP URL | Camera.rtspUrl + credentials | Camera create endpoint | Write-only secret; never echoed back | On Test / Continue | Failure shows reason and port/firewall hint |
| Preview image | Latest camera snapshot (anonymised) | Snapshot endpoint after successful test | Image, face-blurred server-side | On Test | Placeholder when unavailable |
| Mapped polygons count | count(TablePolygon where camera) | Calibration data | Integer | After SCR-013 saves | 0 -> Continue disabled |
| Alert thresholds | AlertRule.serviceDelayMin, dirtyDelayMin | AlertRule endpoint | Whole minutes, ranges 1-30 and 0-15 | On step save | Validation messages |

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
- Step state is not validated or saved in the prototype; every button just advances.
- `Load Sample Restaurant Video` is a demo feature. Remove or hide in production.
- Face blur is shown as a static ON badge (not a switch). The earlier prototype had a switch. CONFIRM WITH PRODUCT.
- Steps 2-4 are not shown in the PNGs (only step 1 is captured). See README.
