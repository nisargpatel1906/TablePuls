# SCR-009 — Waitlist & Predicted Turnover Queue

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-009`
- **Route (prototype):** `/venues/:venueId/waitlist`
- **Priority tier:** P1
- **Roles with access:** HOST, MANAGER, OWNER
- **Purpose:** Match waiting parties to tables that free up soonest.
- **App chrome:** Floating liquid-glass shell: sidebar (>=1024px) or header pill + bottom dock (<1024px)

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-009-waitlist-phone-light.png` | Phone | Light | 390 x 1716 CSS px | @2x -> 780 x 3432 px |
| `SCR-009-waitlist-phone-dark.png` | Phone | Dark | 390 x 1716 CSS px | @2x -> 780 x 3432 px |
| `SCR-009-waitlist-tablet-light.png` | Tablet | Light | 834 x 1342 CSS px | @2x -> 1668 x 2684 px |
| `SCR-009-waitlist-tablet-dark.png` | Tablet | Dark | 834 x 1342 CSS px | @2x -> 1668 x 2684 px |
| `SCR-009-waitlist-desktop-light.png` | Desktop | Light | 1440 x 943 CSS px | @1x -> 1440 x 943 px |
| `SCR-009-waitlist-desktop-dark.png` | Desktop | Dark | 1440 x 943 CSS px | @1x -> 1440 x 943 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** App shell. Header with `+ Add Party`. Two cards stack: Waiting Parties (each row stacks name/meta over buttons), then Predicted Next Available with `>=2 / >=4 / >=6` filter. Page 1716px.
- **Tablet (834px):** Same stacking (two columns only from 1024px). Rows put meta and buttons side by side. Page 1342px.
- **Desktop (1440px):** Sidebar + two equal columns.

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 1716 / 1716 | 1342 / 1342 | 943 / 943 |
| Sidebar visible | no | no | yes |
| Bottom dock visible | yes | yes | no |
| Hamburger visible | yes | yes | no |
| Horizontal-scroll containers | 0 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 12 | 12 | 13 |
| Examples under 44px | Open navigation menu, 4, Toggle theme, Assign & Seat | Open navigation menu, 4, Toggle theme, Assign & Seat | [Venue Name — Primary] [Venue Name — Sec, Sign Out, 4, Toggle theme |

## 4. Components and controls
- `+ Add Party` (blue, 44px) opens a modal: party name, size, note.
- Waiting row: `[Party Name #1] · 4 guests`, `Waited 12 min · Quoted 15–20 min · note`, green `Assign & Seat`, `Cancel`.
- Predicted card: size filter, then rows `T02 · 4 seats (Main Hall)`, current dwell, state badge, `Est. ~[X–Y] min (Med)` or `Available now`.

**Auto-extracted from the desktop render:**
- Headings: `Waitlist & Predicted Turnover`, `Waiting Parties (3)`, `Predicted Next Available`
- Table headers: —
- Form fields:
  - `select-one` Venue selector: `[Venue Name — Primary]`

## 5. States
Empty waitlist, add-party validation, no suitable table, seating success, cancel confirmation, prediction unavailable.

## 6. Interactions and navigation
Assign & Seat -> toast and table update (prototype stays on page).

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Rows #2C2C2E at 80% on #1C1C1E cards; ETA text #F5F5F7; badges use dark variants.

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
ETA confidence is written as text; modal needs focus trap and Esc.

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- Parties `[Party Name #1..3]` with sizes 4/2/6
- Waited / quoted minutes, notes in brackets
- Prediction text `~[X–Y] min (Med)`
- `FIFO + Party Size` caption

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Waiting row | WaitlistEntry.partyName, size, createdAt, quotedMinutes, notes | Waitlist list + realtime | Waited = now - createdAt; names are personal data | Realtime | Empty -> 'No parties waiting' |
| Add Party | WaitlistEntry create (name, size, notes, optional phone) | Waitlist endpoint | Size 1-20 | On submit | Validation messages |
| Assign & Seat | Seat action (entryId, tableId) -> TableState occupied with guestCount = party size | Seating endpoint | - | On click | Let the host pick the table; show conflicts |
| Cancel | Entry status CANCELLED + optional reason | Waitlist endpoint | - | On click | Confirm first |
| Predicted rows | Tables filtered by seats >= filter, state in FREE/NEEDS_CLEANING/OCCUPIED, TurnoverPrediction | Prediction service | `Available now` or range + High/Med/Low | Poll 30-60s | No prediction -> 'Not enough data' |
| Quoted time | Quote rule or manual | Venue settings | Minutes or range | On create | - |

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
- `Assign & Seat` auto-picks the first free table in the prototype. A host needs to choose.
- `Cancel` removes without confirmation. Waitlist names are personal data: define retention.
- Prediction text and confidence are placeholders; sort order is not by ETA in the prototype.
