# SCR-013 — Interactive Table Polygon & ROI Editor

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-013`
- **Route (prototype):** `/venues/:venueId/settings/cameras/:cameraId/calibrate`
- **Priority tier:** P1
- **Roles with access:** MANAGER, OWNER
- **Purpose:** Draw and edit table polygons and exclusion zones on a camera frame.
- **App chrome:** Floating liquid-glass shell: sidebar (>=1024px) or header pill + bottom dock (<1024px)

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-013-polygon-editor-phone-light.png` | Phone | Light | 390 x 1116 CSS px | @2x -> 780 x 2232 px |
| `SCR-013-polygon-editor-phone-dark.png` | Phone | Dark | 390 x 1116 CSS px | @2x -> 780 x 2232 px |
| `SCR-013-polygon-editor-tablet-light.png` | Tablet | Light | 834 x 1253 CSS px | @2x -> 1668 x 2506 px |
| `SCR-013-polygon-editor-tablet-dark.png` | Tablet | Dark | 834 x 1253 CSS px | @2x -> 1668 x 2506 px |
| `SCR-013-polygon-editor-desktop-light.png` | Desktop | Light | 1440 x 810 CSS px | @1x -> 1440 x 810 px |
| `SCR-013-polygon-editor-desktop-dark.png` | Desktop | Dark | 1440 x 810 CSS px | @1x -> 1440 x 810 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** App shell. Toolbar rows wrap (camera select, 3 modes, Refresh, Save). Canvas card, then `Select T0x` chips, then the inspector card below. Page 1116px.
- **Tablet (834px):** Same stacking (8/4 split begins at 1280px). Page 1253px.
- **Desktop (1440px):** Sidebar + 8/4 split: canvas left, inspector right.

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 1116 / 1116 | 1253 / 1253 | 810 / 810 |
| Sidebar visible | no | no | yes |
| Bottom dock visible | yes | yes | no |
| Hamburger visible | yes | yes | no |
| Horizontal-scroll containers | 0 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 17 | 17 | 18 |
| Examples under 44px | Open navigation menu, 4, Toggle theme, [Camera Name — Main Hall North] [Camera  | Open navigation menu, 4, Toggle theme, [Camera Name — Main Hall North] [Camera  | [Venue Name — Primary] [Venue Name — Sec, Sign Out, 4, Toggle theme |

## 4. Components and controls
- Toolbar: camera select, modes `Draw Polygon / Edit Vertex / Exclusion Zone`, `Refresh Snapshot`, `Save Calibration`.
- Canvas: 16:9 camera frame with four polygons coloured by state, labels `T01 · 0/4 · FREE`, blur badge.
- Select chips `Select T01..T04`.
- Inspector: Table ID, Section, Seats, `Keyboard Vertex Coordinates (Fallback)` text, `Delete Polygon`.

**Auto-extracted from the desktop render:**
- Headings: `Polygon Inspector · T01`
- Table headers: —
- Form fields:
  - `select-one` Venue selector: `[Venue Name — Primary]`
  - `select-one` (unlabelled): `[Camera Name — Main Hall North]`
  - `text` (unlabelled): `T01`
  - `select-one` (unlabelled): `Main Hall`
  - `number` (unlabelled): `4`

## 5. States
Selected polygon, drawing in progress, unsaved changes warning, validation (polygon overlap, < 3 vertices), save success, delete confirmation.

## 6. Interactions and navigation
Reached from SCR-004 step 3, SCR-006 and SCR-012.

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Canvas frame identical in both themes; inspector card #1C1C1E; destructive button red 12% (intended).

| Token (measured on desktop render) | Light | Dark |
|---|---|---|
| Body text | `rgb(28, 28, 30)` | `rgb(245, 245, 247)` |
| Solid content card fill | `rgb(255, 255, 255)` | `rgb(28, 28, 30)` |
| Card border | `rgba(60, 60, 67, 0.086)` | `rgba(255, 255, 255, 0.09)` |
| Liquid-glass fill | `rgba(255, 255, 255, 0.72)` | `rgba(28, 28, 30, 0.74)` |
| Liquid-pill fill | `rgba(255, 255, 255, 0.78)` | `rgba(36, 36, 38, 0.78)` |
| Heading colour | — | — |
| Heading size | — | — |
| Secondary text | — | — |
| Primary button fill | `rgba(0, 0, 0, 0)` | `rgba(0, 0, 0, 0)` |

| Canvas | `#F2F2F7` + soft blue/green washes | `#000000` + brighter blue/green washes |
| Solid card | `#FFFFFF`, 1px rgba(60,60,67,.085) | `#1C1C1E`, 1px rgba(255,255,255,.09) |
| Inset field | `#F2F2F7` | `#2C2C2E` |
| Secondary label | `#636366` | `#AEAEB2` |
| Accent | `#007AFF` | `#0A84FF` (text accents `#409CFF`) |

The theme is switched with the `dark` class on `<html>` plus `dark-canvas` on `<body>`. A Reduce Transparency solid mode also exists in the prototype (`solid-mode` class); it is not part of these PNGs.

## 8. Accessibility
Numeric vertex inputs must exist as a keyboard alternative (the prototype shows a static text stand-in).

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- Camera `[Camera Name — Main Hall North]`
- Polygons T01-T04 and their labels
- Vertex text `V1: (70, 75) ...` (same for every table)

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Camera select | Camera list | Camera endpoint | Names | On load | - |
| Canvas image | Latest snapshot frame (face-blurred) | Snapshot endpoint | Image + native resolution for coordinate scaling | On load / Refresh | Offline -> 'No frame' state |
| Polygons | TablePolygon.vertices (normalised 0-1), tableId, cameraId; ExclusionZone.vertices | Calibration endpoint | Coordinates in the image space | On load | None -> start in Draw mode |
| Inspector fields | Table.label, section, seats | Table endpoint | Section from Section list; seats 1-20 | On select | Duplicate label -> error |
| Vertex inputs | Selected polygon vertices | Local edit state | Integers or decimals per spec | On edit | Validation |
| Save Calibration | Versioned calibration + audit entry | Calibration endpoint | - | On click | Conflict if another editor saved |

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
- The prototype canvas is not interactive (no drawing or draggable handles) and the vertex text is the same for every table.
- Mode buttons only change highlight. `Delete Polygon` only toasts.
- `Table ID` is an editable input: renaming IDs is risky. CONFIRM WITH PRODUCT.
