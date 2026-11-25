# SCR-006 — Live Camera Wall & AI Overlay

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-006`
- **Route (prototype):** `/venues/:venueId/cameras/live`
- **Priority tier:** P1
- **Roles with access:** MANAGER, OWNER, HOST
- **Purpose:** Live multi-camera wall with table overlays and privacy badge.
- **App chrome:** Floating liquid-glass shell: sidebar (>=1024px) or header pill + bottom dock (<1024px)

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-006-live-camera-wall-phone-light.png` | Phone | Light | 390 x 1658 CSS px | @2x -> 780 x 3316 px |
| `SCR-006-live-camera-wall-phone-dark.png` | Phone | Dark | 390 x 1658 CSS px | @2x -> 780 x 3316 px |
| `SCR-006-live-camera-wall-tablet-light.png` | Tablet | Light | 834 x 2369 CSS px | @2x -> 1668 x 4738 px |
| `SCR-006-live-camera-wall-tablet-dark.png` | Tablet | Dark | 834 x 2369 CSS px | @2x -> 1668 x 4738 px |
| `SCR-006-live-camera-wall-desktop-light.png` | Desktop | Light | 1440 x 973 CSS px | @1x -> 1440 x 973 px |
| `SCR-006-live-camera-wall-desktop-dark.png` | Desktop | Dark | 1440 x 973 CSS px | @1x -> 1440 x 973 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** App shell (header + dock). Toolbar wraps (grid selector, 3 overlay toggles). Cameras stack 1 per row, each a card with title, stats, `Calibrate Polygons` and a 16:9 feed. Page 1658px.
- **Tablet (834px):** Same, but default 2x2 mode is 1 column at this width (2 columns start at 1024px). Page 2369px.
- **Desktop (1440px):** Sidebar + 2-column grid in 2x2 mode (1 / 2 / 3 columns for 1x1 / 2x2 / 3x3 modes at xl).

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 1658 / 1658 | 2369 / 2369 | 973 / 973 |
| Sidebar visible | no | no | yes |
| Bottom dock visible | yes | yes | no |
| Hamburger visible | yes | yes | no |
| Horizontal-scroll containers | 0 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 14 | 14 | 15 |
| Examples under 44px | Open navigation menu, 4, Toggle theme, 1x1 | Open navigation menu, 4, Toggle theme, 1x1 | [Venue Name — Primary] [Venue Name — Sec, Sign Out, 4, Toggle theme |

## 4. Components and controls
- Toolbar: grid segmented control `1x1 / 2x2 / 3x3`; overlay chips `Table Polygons`, `Counts & Timers`, `Face Blur Badge`.
- Camera card: name, `4 FPS · Latency 44ms · 6 tables mapped`, `Calibrate Polygons` button.
- Feed (16:9, radius 16, always dark): lens vignette, table rectangles, polygons coloured by state (dashed for cleaning), pill labels `T04 · 4/4 · 05:42`, timestamp chip, green `Privacy Blur: ON` badge.
- Offline card: red camera-off icon, `Stream Offline · Reconnecting`, last seen text, `Retry Stream`.

**Auto-extracted from the desktop render:**
- Headings: —
- Table headers: —
- Form fields:
  - `select-one` Venue selector: `[Venue Name — Primary]`

## 5. States
Connecting, live, offline/reconnecting, overlay toggles on/off, grid modes, latency warnings.

## 6. Interactions and navigation
Calibrate Polygons -> SCR-013 (with that camera selected).

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Page chrome follows dark tokens; feeds are identical in both themes (#1C1F26 floor, #16181D letterbox); chips use brighter blue on dark.

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
Overlay toggles are real buttons with visible on/off colour; feed needs a text alternative (table states list) since video is not accessible.

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- Camera names `[Camera Name — ...]`
- FPS 3-4, latency 44-51ms, mapped counts
- Timestamp `[YYYY-MM-DD HH:MM:SS]`
- Table labels/timers drawn inside the feed

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Camera list | Camera.name, status, targetFps, mappedTableCount | Camera list endpoint | Text / integer | On load + heartbeat | Zero cameras -> empty state linking SCR-012 |
| Live feed | WebRTC stream via media gateway, face-blurred at the server | Stream URL per camera | Video | Continuous | Retry with backoff; show offline card |
| Latency / FPS | Stream stats | Gateway stats | `44ms`, `4 FPS` | Every 5s | Show `-` when offline |
| Overlay polygons + labels | TablePolygon + current TableState + dwell | Calibration + table-state events | Coordinates normalised 0-1, scaled to the video | Realtime | Hidden when no polygons |
| Privacy Blur badge | PrivacyPolicy.faceBlurEnforced / Camera.blurEnabled | Policy | Boolean | On load | Must reflect the real server state |
| Last seen (offline) | Camera.lastFrameAt | Heartbeat | Relative + absolute time in venue timezone | On change | - |

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
- `Face Blur Badge` toggle only hides the badge. Blur itself must always be enforced by the server and must not be user-toggleable here.
- `1x1` mode still lists all cameras in the prototype (grid-cols-1). Intended single-camera focus view is not implemented.
- Feed is a vector illustration, not a video. Timing/latency numbers are seed.
