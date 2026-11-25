# SCR-010 — Peak Hours & Staffing Analytics

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-010`
- **Route (prototype):** `/venues/:venueId/analytics`
- **Priority tier:** P1
- **Roles with access:** MANAGER, OWNER, VIEWER
- **Purpose:** Historical occupancy, SLA metrics and staffing recommendations.
- **App chrome:** Floating liquid-glass shell: sidebar (>=1024px) or header pill + bottom dock (<1024px)

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-010-analytics-phone-light.png` | Phone | Light | 390 x 1005 CSS px | @2x -> 780 x 2010 px |
| `SCR-010-analytics-phone-dark.png` | Phone | Dark | 390 x 1005 CSS px | @2x -> 780 x 2010 px |
| `SCR-010-analytics-tablet-light.png` | Tablet | Light | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-010-analytics-tablet-dark.png` | Tablet | Dark | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-010-analytics-desktop-light.png` | Desktop | Light | 1440 x 810 CSS px | @1x -> 1440 x 810 px |
| `SCR-010-analytics-desktop-dark.png` | Desktop | Dark | 1440 x 810 CSS px | @1x -> 1440 x 810 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** App shell. Title, then range select / `View as Data Table` / `Export CSV` wrap to 3 rows. KPIs 2x2. Chart card: header + `Guests per server` field above a bar chart that scrolls horizontally inside its card (min 560px wide).
- **Tablet (834px):** KPIs stay 2x2 (4 across starts at 1280px). Controls fit on one row; chart fits without horizontal scrolling.
- **Desktop (1440px):** Sidebar; KPIs 4 across; chart card full width.

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 1005 / 1005 | 1194 / 1194 | 810 / 810 |
| Sidebar visible | no | no | yes |
| Bottom dock visible | yes | yes | no |
| Hamburger visible | yes | yes | no |
| Horizontal-scroll containers | 1 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 7 | 7 | 8 |
| Examples under 44px | Open navigation menu, 4, Toggle theme, Today Last 7 Days Last 30 Days | Open navigation menu, 4, Toggle theme, Today Last 7 Days Last 30 Days | [Venue Name — Primary] [Venue Name — Sec, Sign Out, 4, Toggle theme |

## 4. Components and controls
- Controls: range select (Today / Last 7 Days / Last 30 Days), data-table toggle, `Export CSV`.
- KPI cards: Peak Occupancy Hour, Avg Table Turn Time, Avg Service Response, SLA Breach Rate (values are bracketed placeholders).
- Chart card `Hourly Occupancy & Recommended Waiter Curve`: `Guests per server` number field (min 6), 10 hourly bars with server count labels (peak >= 75% in solid blue), hour labels in mono.
- Data table view: Hour, Occupancy %, Avg Guests, Recommended Waiters.

**Auto-extracted from the desktop render:**
- Headings: `Peak Hours & Staffing Analytics`, `Hourly Occupancy & Recommended Waiter Curve`
- Table headers: —
- Form fields:
  - `select-one` Venue selector: `[Venue Name — Primary]`
  - `select-one` (unlabelled): `Last 7 Days`
  - `number` (unlabelled): `16`

## 5. States
Loading, no data for the range, chart vs table view, export in progress, partial data for today.

## 6. Interactions and navigation
-

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Cards #1C1C1E; non-peak bars intended as 32% blue; peak bars #007AFF; mono labels #AEAEB2.

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
Chart has a full table alternative; bar values also printed as text (`4 srv`).

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- KPI placeholders `[HH:00]`, `[XX min]`, `[X.X min]`, `[X.X%]`
- Ten fixed hour rows (11:00-22:00 with 15:00-16:00 missing), occupancy and guest numbers
- Peak threshold 75%
- Guests per server 16

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Range select | Date range (venue timezone) | Analytics endpoint | Day boundaries in venue timezone | On change | - |
| KPI cards | Aggregates: peak hour, avg turn minutes, avg service response, SLA breach % | Analytics endpoint | Hour as HH:00; minutes with 1 decimal; percent 1 decimal | On range change | No data -> '—' |
| Bars (occupancy %) | Hourly OccupancySnapshot aggregates (guests/seats) | Analytics endpoint | Whole percent | On range change | Buckets come from operating hours, not a fixed list |
| Server count label | ceil(avgGuests / guestsPerServer) | Derived | Integer >= 1 | On input | - |
| Guests per server | Venue staffing setting | Settings endpoint | 6-32 | On change (persist per venue) | - |
| Export CSV | Server-generated CSV for the range | Export endpoint | UTF-8 CSV, timezone noted | On click | Progress + error toast |

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
- Non-peak bars use `bg-[#007AFF]/26` and `dark:.../32`, which Tailwind cannot generate. They are invisible in these PNGs (same as in the prototype opened in a browser). Fix needed.
- Peak threshold (75%) is hardcoded; make it a setting or compute.
- KPI deltas show bracket placeholders; they are not wired.
