# SCR-011 — ML Confidence & Human-Review Queue

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-011`
- **Route (prototype):** `/venues/:venueId/ml-review`
- **Priority tier:** P2
- **Roles with access:** MANAGER, OWNER
- **Purpose:** Human review of low-confidence or host-flagged detections.
- **App chrome:** Floating liquid-glass shell: sidebar (>=1024px) or header pill + bottom dock (<1024px)

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-011-ml-review-phone-light.png` | Phone | Light | 390 x 1180 CSS px | @2x -> 780 x 2360 px |
| `SCR-011-ml-review-phone-dark.png` | Phone | Dark | 390 x 1180 CSS px | @2x -> 780 x 2360 px |
| `SCR-011-ml-review-tablet-light.png` | Tablet | Light | 834 x 1223 CSS px | @2x -> 1668 x 2446 px |
| `SCR-011-ml-review-tablet-dark.png` | Tablet | Dark | 834 x 1223 CSS px | @2x -> 1668 x 2446 px |
| `SCR-011-ml-review-desktop-light.png` | Desktop | Light | 1440 x 828 CSS px | @1x -> 1440 x 828 px |
| `SCR-011-ml-review-desktop-dark.png` | Desktop | Dark | 1440 x 828 CSS px | @1x -> 1440 x 828 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** App shell. Header with `Pending / Agreement` pill; queue card, then inspection card with preview, four label buttons (2x2), checkbox and `Save & Next`. Page 1180px.
- **Tablet (834px):** Same stacking (two columns from 1024px); label buttons in one row of 4 from 640px.
- **Desktop (1440px):** Sidebar + 4/8 split: queue list left, inspection right.

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 1180 / 1180 | 1223 / 1223 | 828 / 828 |
| Sidebar visible | no | no | yes |
| Bottom dock visible | yes | yes | no |
| Hamburger visible | yes | yes | no |
| Horizontal-scroll containers | 0 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 3 | 3 | 4 |
| Examples under 44px | Open navigation menu, 4, Toggle theme | Open navigation menu, 4, Toggle theme | [Venue Name — Primary] [Venue Name — Sec, Sign Out, 4, Toggle theme |

## 4. Components and controls
- Pill: `Pending: 3 · Agreement Rate: [XX.X%]`.
- Queue rows: `T08 · Low Confidence`, confidence %, camera name; selected row has blue border.
- Inspection: title with table, predicted state, guests, confidence, timestamp; 16:9 face-blurred crop; label buttons `[1] FREE`, `[2] OCCUPIED`, `[3] NEEDS CLEANING`, `[4] OCCUPIED WITH STAFF`; `Exclude from training dataset` checkbox; `Save & Next (Enter)`.

**Auto-extracted from the desktop render:**
- Headings: `ML Confidence & Human-Review Queue`, `Inspecting ML-001 · Table T08`
- Table headers: —
- Form fields:
  - `select-one` Venue selector: `[Venue Name — Primary]`
  - `checkbox` (unlabelled): `on`

## 5. States
Empty queue message, loading next item, label saved, network error, item already reviewed by someone else.

## 6. Interactions and navigation
-

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Selected row blue 12% fill; unselected #2C2C2E; preview identical in both themes.

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
Shortcut hints are in the button text; they must be implemented and announced.

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- Three queue items with tables T08/T03/T05, reasons, confidences
- `[YYYY-MM-DD HH:MM:SS]` timestamps
- Agreement `[XX.X%]`
- Label list incl. `OCCUPIED_WITH_STAFF`

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Queue rows | ReviewItem.id, tableId, cameraId, predictedState, predictedGuests, confidence, reason, capturedAt | Review queue endpoint | Reason enum (Low Confidence, Host Flagged, Occlusion...) | On load + after save | Empty -> 'No uncertain detections pending review' |
| Preview image | ReviewItem.imageRef | Signed URL, face-blurred, retention applies | Image | On select | Expired -> 'Image purged' state |
| Label buttons | Label enum (must match table state enum) | Config | Enum | - | CONFIRM: `OCCUPIED_WITH_STAFF` is not a table state in this product |
| Save & Next | ReviewLabel create (itemId, label, guests, excludeFromTraining, reviewer) | Review endpoint | - | On click / Enter | Retry on failure |
| Agreement rate | Share of human labels equal to model prediction over a window | Computed metric | Percent 1 decimal | Daily | '—' until enough reviews |

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
- Prototype label buttons only show a toast; the choice is not stored and `Save & Next` just removes the item.
- Guest-count editing from the earlier design is absent here. CONFIRM WITH PRODUCT.
- Keyboard shortcuts (1-4, Enter) are shown but not implemented.
