# SCR-005 — Live Floor Map (Live Host Floor)

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-005`
- **Route (prototype):** `/venues/:venueId/floor`
- **Priority tier:** P1
- **Roles with access:** HOST, MANAGER, OWNER, STAFF, VIEWER
- **Purpose:** Primary host-stand workspace: live KPIs, floor map, alerts and next-available tables.
- **App chrome:** Floating liquid-glass shell: sidebar (>=1024px) or header pill + bottom dock (<1024px)

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-005-live-floor-map-phone-light.png` | Phone | Light | 390 x 2259 CSS px | @2x -> 780 x 4518 px |
| `SCR-005-live-floor-map-phone-dark.png` | Phone | Dark | 390 x 2259 CSS px | @2x -> 780 x 4518 px |
| `SCR-005-live-floor-map-tablet-light.png` | Tablet | Light | 834 x 1872 CSS px | @2x -> 1668 x 3744 px |
| `SCR-005-live-floor-map-tablet-dark.png` | Tablet | Dark | 834 x 1872 CSS px | @2x -> 1668 x 3744 px |
| `SCR-005-live-floor-map-desktop-light.png` | Desktop | Light | 1440 x 1030 CSS px | @1x -> 1440 x 1030 px |
| `SCR-005-live-floor-map-desktop-dark.png` | Desktop | Dark | 1440 x 1030 CSS px | @1x -> 1440 x 1030 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** App shell: floating glass header pill (menu, live pill, `5/12 · 36%`, alerts, theme) + bottom glass dock (Floor, Alerts, Waitlist, More). KPIs 2x2. Tables render as a 2-column CARD GRID (no spatial map). Alerts/Next-Available panel stacks below. Long page (2259px).
- **Tablet (834px):** Same header/dock. KPIs 2x2. Spatial floor map IS shown (md+). Alerts panel stacks below the map (xl split not reached). Page 1872px.
- **Desktop (1440px):** Left glass sidebar 256px (sticky), header pill row, KPIs 4 across, 8/4 split: floor map (min 490px high) and alerts / next-available card. Page ~1030px.

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 2259 / 2259 | 1872 / 1872 | 1030 / 1030 |
| Sidebar visible | no | no | yes |
| Bottom dock visible | yes | yes | no |
| Hamburger visible | yes | yes | no |
| Spatial floor map visible | no | yes | yes |
| Horizontal-scroll containers | 0 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 21 | 21 | 22 |
| Examples under 44px | Open navigation menu, 4, Toggle theme, All | Open navigation menu, 4, Toggle theme, All | [Venue Name — Primary] [Venue Name — Sec, Sign Out, 4, Toggle theme |

## 4. Components and controls
- Header pill: live-state dot + text, `Tables 5/12 · Guests 16/44 · 36%`; right pill: alerts button with count, theme toggle.
- 4 KPI cards (radius 20-22): Tables Occupied, Seated Guests, Floor Capacity, Active Alerts, each with caption.
- Filter bar (liquid pill): section segmented control (All / Main Hall / Patio / Bar), status select, search `Search T01...`, `Table List` toggle.
- Floor map card: title `Live Host Floor · <venue>`, `Open Camera Wall`, dotted floor grid, zone bands (Kitchen Pass & Service Window, Host Stand · Entrance, Patio Terrace, Bar Lounge), 12 table tiles.
- Tile anatomy: icon + id, guests/seats (or `Manual` chip when overridden), status label, section/dwell timer. Seven distinct state styles (solid green, solid red, dashed amber, pulsing orange, dotted blue, hatched grey, double grey + red icon).
- Legend chips for all seven states (icon + text).
- Side card with segmented tabs: `Active Alerts (n)` (table, section, elapsed, message, Acknowledge, Inspect) and `Next Available` (ETA text, `Open Waitlist (n waiting)`).

**Auto-extracted from the desktop render:**
- Headings: `Live Host Floor · [Venue Name — Primary]`
- Table headers: —
- Form fields:
  - `select-one` Venue selector: `[Venue Name — Primary]`
  - `select-one` Filter by table status: `All Statuses`
  - `search` Search T01...: `—`

## 5. States
Live / reconnecting / polling, AI-paused indicator in header, Table List (accessible table: Table, Section, State, Guests, Dwell, Inspect), empty alerts, filters with no match, offline camera tile, low-confidence tile, manual override chip, loading skeletons.

## 6. Interactions and navigation
Tile or Inspect -> SCR-007 drawer · Open Camera Wall -> SCR-006 · alerts button -> SCR-008 · Open Waitlist -> SCR-009 · sidebar/dock to every other screen.

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Canvas #000 with brighter blue/green washes; cards #1C1C1E; floor map #141416; glass rgba(28,28,30,0.74); tile fills use 14-16% tints of #30D158/#FF453A/#FFD60A/#FF9F0A/#0A84FF; text #F5F5F7 / #AEAEB2.

| Token (measured on desktop render) | Light | Dark |
|---|---|---|
| Body text | `rgb(28, 28, 30)` | `rgb(245, 245, 247)` |
| Solid content card fill | `rgb(255, 255, 255)` | `rgb(28, 28, 30)` |
| Card border | `rgba(60, 60, 67, 0.086)` | `rgba(255, 255, 255, 0.09)` |
| Liquid-glass fill | `rgba(255, 255, 255, 0.72)` | `rgba(28, 28, 30, 0.74)` |
| Liquid-pill fill | `rgba(255, 255, 255, 0.78)` | `rgba(36, 36, 38, 0.78)` |
| Heading colour | `rgb(28, 28, 30)` | `rgb(245, 245, 247)` |
| Heading size | `19px` | `19px` |
| Secondary text | `rgb(99, 99, 102)` | `rgb(174, 174, 178)` |
| Primary button fill | `rgba(0, 0, 0, 0)` | `rgba(0, 0, 0, 0)` |

| Canvas | `#F2F2F7` + soft blue/green washes | `#000000` + brighter blue/green washes |
| Solid card | `#FFFFFF`, 1px rgba(60,60,67,.085) | `#1C1C1E`, 1px rgba(255,255,255,.09) |
| Inset field | `#F2F2F7` | `#2C2C2E` |
| Secondary label | `#636366` | `#AEAEB2` |
| Accent | `#007AFF` | `#0A84FF` (text accents `#409CFF`) |

The theme is switched with the `dark` class on `<html>` plus `dark-canvas` on `<body>`. A Reduce Transparency solid mode also exists in the prototype (`solid-mode` class); it is not part of these PNGs.

## 8. Accessibility
State is conveyed by icon + text + border pattern, not colour only; tiles are buttons with focus ring; pulse respects reduced motion; Table List is the non-spatial alternative.

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- Venue `[Venue Name — Primary]`
- Tables T01-T12, sections Main Hall / Patio / Bar
- KPIs 5/12, 16/44, 36%, 4 alerts
- Dwell timers (e.g. 30:42, 05:42), confidence values
- Alert text `Guests waiting [MM:SS] without waiter visit`
- ETA `~[X–Y] min`, `ETA Confidence: Med`
- Zone labels Kitchen Pass / Host Stand / Patio Terrace / Bar Lounge

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Venue name / selector | Venue.name; user's venue memberships | Venue list endpoint | Text | On load | Single venue -> selector hidden |
| Tables Occupied | count(Table where state in OCCUPIED, NEEDS_SERVICE) / count(Table) | Derived from current table states | `n / total` | Realtime | 0 tables -> empty state with link to SCR-013. CONFIRM the occupied definition |
| Seated Guests | sum(TableState.guestCount) / sum(Table.seats) | Derived | `n / total` | Realtime | - |
| Floor Capacity % | guests / seats | Derived, never stored | Whole percent, round half up | Realtime | Hide when seats = 0 |
| Active Alerts | count(Alert where status = ACTIVE) | Alert list | Integer; red dot when > 0 | Realtime | 0 -> green dot |
| Section tabs | Section.name list for the venue | Venue layout endpoint | Names as configured | On load | 'All' always first. All names are seed here |
| Table tile | Table.id/label, section, seats, shape, x/y/w/h; TableState.status, guestCount, confidence, since; manualOverride | Table list + realtime table-state events | Dwell = now - since, computed on the client each second | Realtime | Offline camera -> 'No feed'; low confidence -> hatched |
| Floor zones and bar counter | Venue layout config (zones, labels, positions) | Layout endpoint | Text + geometry | On load | Fallback to plain grid when missing |
| Active alerts list | Alert.type, tableId, section, createdAt, message params | Alert list | Elapsed = now - createdAt; message generated from type + params | Realtime | Empty -> 'All tables attended' |
| Next Available ETA + confidence | TurnoverPrediction.etaRange, confidence per table | Prediction service | `~X-Y min` + High/Med/Low | Poll 30-60s | No model -> show 'Not enough data', never fabricate |
| Realtime pill | Connection state (live / reconnecting / polling) | Client socket status | Text | Live | - |

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
- Phone shows a card grid instead of the floor map. CONFIRM this is intended (no spatial view on phone).
- `Next Available` is sorted by longest dwell in the prototype, which is a placeholder heuristic, not an ETA.
- ETA text and `ETA Confidence: Med` are hardcoded placeholders.
- Zone labels are hardcoded text in the prototype; must come from venue layout.
- Tablet portrait (834px) uses the phone-style header + dock; sidebar only appears from 1024px. Tablet landscape is not captured.
- Sticky offsets in the prototype assume a 48px preview bar. Export copy overrides them; implement with 0 (small) and 14px (large).
