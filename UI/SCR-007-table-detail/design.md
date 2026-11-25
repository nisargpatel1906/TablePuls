# SCR-007 — Table Detail & Manual Override Drawer

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-007`
- **Route (prototype):** `/venues/:venueId/tables/:tableId`
- **Priority tier:** P1
- **Roles with access:** HOST, MANAGER, OWNER, STAFF
- **Purpose:** Inspect one table and apply manual actions. An overlay on SCR-005, not a separate page.
- **App chrome:** Floating liquid-glass shell: sidebar (>=1024px) or header pill + bottom dock (<1024px)

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-007-table-detail-phone-light.png` | Phone | Light | 390 x 959 CSS px | @2x -> 780 x 1918 px |
| `SCR-007-table-detail-phone-dark.png` | Phone | Dark | 390 x 959 CSS px | @2x -> 780 x 1918 px |
| `SCR-007-table-detail-tablet-light.png` | Tablet | Light | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-007-table-detail-tablet-dark.png` | Tablet | Dark | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-007-table-detail-desktop-light.png` | Desktop | Light | 1440 x 938 CSS px | @1x -> 1440 x 938 px |
| `SCR-007-table-detail-desktop-dark.png` | Desktop | Dark | 1440 x 938 CSS px | @1x -> 1440 x 938 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (overlay screen: the device viewport is kept and grown only until the sheet content no longer scrolls).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** Bottom sheet: grab handle, 28px top radius, max 92% of viewport height, dimmed + blurred page behind. Content scrolls inside; the PNG viewport was grown until nothing scrolls (959px tall).
- **Tablet (834px):** Right-side floating sheet, 440px wide, full height with 16px inset, rounded 28px.
- **Desktop (1440px):** Same right-side sheet, 440px wide.

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 959 / 959 | 1194 / 1194 | 938 / 938 |
| Sidebar visible | no | no | yes |
| Bottom dock visible | yes | yes | no |
| Hamburger visible | yes | yes | no |
| Spatial floor map visible | no | yes | yes |
| Horizontal-scroll containers | 0 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 23 | 23 | 24 |
| Examples under 44px | Open navigation menu, 4, Toggle theme, All | Open navigation menu, 4, Toggle theme, All | [Venue Name — Primary] [Venue Name — Sec, Sign Out, 4, Toggle theme |

## 4. Components and controls
- Header: `Table T04`, optional `Manual` chip, section · seats · dwell, close button 36px.
- State badge + `ML Confidence: 95%`.
- `Latest Anonymized Table Crop` (16:9, face-blurred, with timestamp and blur badge).
- Quick actions 2x2: `Mark Clean (Free)`, `Mark Attended`, `Toggle Reserved`, `Manual Override`; full-width `Flag Wrong AI Detection`.
- Manual Override form (expands): state select, guest count, required reason, `Save Override`.
- `Recent Activity Timeline`: three entries with time, source, description.

**Auto-extracted from the desktop render:**
- Headings: `Live Host Floor · [Venue Name — Primary]`, `Table T04`
- Table headers: —
- Form fields:
  - `select-one` Venue selector: `[Venue Name — Primary]`
  - `select-one` Filter by table status: `All Statuses`
  - `search` Search T01...: `—`

## 5. States
Open/closed, override form open, saving, conflict (state changed by someone else), read-only role (shows 'Read-only role' notice), offline table (no crop), success toast.

## 6. Interactions and navigation
Close or Esc -> back to SCR-005 · Flag -> SCR-011 queue.

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Sheet glass rgba(28,28,30,0.74) with 13% white edge and inner highlight; quick-action tints #30D158 / #409CFF; timeline rows white 5%.

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
`role=dialog` with `aria-modal` and label; Esc closes; focus should be trapped and returned to the tile.

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- Table `T04`, section `Main Hall`, 4 seats, dwell 05:42, confidence 95%
- Timeline rows with `[HH:MM:SS]` and `[Staff Name]`
- Crop image (illustration)

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Header (id, section, seats, dwell) | Table + TableState.since | Table endpoint + realtime | Dwell mm:ss computed from `since` | Realtime | Deleted table -> close sheet |
| State badge + confidence | TableState.status, confidence | Realtime | Enum + percent | Realtime | Offline -> 'Offline' |
| Table crop image | Detection.snapshotRef | Signed, short-lived URL; face-blurred server-side | Image | On open + on new detection | Retention policy applies. Placeholder when none |
| Quick actions | POST table state override (new status, guestCount?, reason) | Override endpoint, role-checked (OWNER/MANAGER/HOST/STAFF) | Writes AuditLog | On click | 409 conflict -> refresh and ask again |
| Manual override form | status, guestCount (0..seats), reason (required) | Same endpoint | Reason saved in audit | On submit | Block empty reason |
| Timeline | TableStateEvent + AuditLog for this table | Event list endpoint, newest first | Time in venue timezone; source = detector or user name | On open + realtime | Empty -> 'No activity yet' |
| Flag Wrong AI Detection | ReviewItem create (table, detection) | Review endpoint | - | On click | Success toast + link to queue |
| Role gating | Current user's role | Session | canAct, canOverride flags | On load | Hide, do not just disable, forbidden actions |

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
- `Mark Attended` in the prototype sets the table to OCCUPIED with `guests || 2`. That invents a guest count. Real build must use the detected or entered count.
- The reason input in the override form has no name and is never read by the prototype, so the reason is lost. Must be captured and audited.
- `Mark Clean (Free)` is offered for every state. Define allowed transitions.
- Timeline and crop are static illustrations in the prototype.
- PNGs for this screen are overlay captures (see device layout), not full-page captures of the page behind.
