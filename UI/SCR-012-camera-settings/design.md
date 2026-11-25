# SCR-012 — Camera & RTSP Stream Management

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-012`
- **Route (prototype):** `/venues/:venueId/settings/cameras`
- **Priority tier:** P2
- **Roles with access:** MANAGER, OWNER
- **Purpose:** Manage cameras and RTSP endpoints.
- **App chrome:** Floating liquid-glass shell: sidebar (>=1024px) or header pill + bottom dock (<1024px)

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-012-camera-settings-phone-light.png` | Phone | Light | 390 x 1278 CSS px | @2x -> 780 x 2556 px |
| `SCR-012-camera-settings-phone-dark.png` | Phone | Dark | 390 x 1278 CSS px | @2x -> 780 x 2556 px |
| `SCR-012-camera-settings-tablet-light.png` | Tablet | Light | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-012-camera-settings-tablet-dark.png` | Tablet | Dark | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-012-camera-settings-desktop-light.png` | Desktop | Light | 1440 x 810 CSS px | @1x -> 1440 x 810 px |
| `SCR-012-camera-settings-desktop-dark.png` | Desktop | Dark | 1440 x 810 CSS px | @1x -> 1440 x 810 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** App shell. Title + `+ Add Camera`; camera cards in one column (URL wraps with break-all). Page 1278px.
- **Tablet (834px):** Two columns of cards (md).
- **Desktop (1440px):** Sidebar + two columns of cards.

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 1278 / 1278 | 1194 / 1194 | 810 / 810 |
| Sidebar visible | no | no | yes |
| Bottom dock visible | yes | yes | no |
| Hamburger visible | yes | yes | no |
| Horizontal-scroll containers | 0 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 11 | 11 | 12 |
| Examples under 44px | Open navigation menu, 4, Toggle theme, Test | Open navigation menu, 4, Toggle theme, Test | [Venue Name — Primary] [Venue Name — Sec, Sign Out, 4, Toggle theme |

## 4. Components and controls
- Header with `+ Add Camera` (opens modal).
- Camera card: name, masked mono URL `rtsp://***@[camera-ip-01]:554/stream1`, status chip (Online green / Offline red), mapped tables, target FPS, privacy blur text, `Test` and `Calibrate Polygons`.

**Auto-extracted from the desktop render:**
- Headings: `Camera & RTSP Stream Management`
- Table headers: —
- Form fields:
  - `select-one` Venue selector: `[Venue Name — Primary]`

## 5. States
Online/offline, testing in progress and result, add-camera modal, validation errors, delete confirmation.

## 6. Interactions and navigation
Calibrate Polygons -> SCR-013.

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Cards #1C1C1E; online chip #30D158; offline #FF6961; mono URL #AEAEB2.

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
Credentials masked; status uses text; buttons 38px high (below the 44px target).

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- Camera names and placeholder IPs
- Mapped counts 6/2/2/2, FPS 3-4
- Status values

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Camera card | Camera.id, name, status, mappedTableCount, targetFps, blurEnabled | Camera list endpoint | Text / integers | On load + heartbeat | Zero cameras -> empty state with `Add Camera` |
| Masked URL | Camera.rtspUrl with credentials removed server-side | Camera endpoint | Host and path only; secrets never sent to the browser | On load | - |
| Status | Heartbeat age / stream state | Health data | Online / Offline | Realtime | - |
| Test | Connection probe result | Probe endpoint | Latency, resolution, error reason | On click | Failure message with hint |
| Add Camera modal | Camera create (name, rtspUrl, username, password, fps) | Camera endpoint | Secrets write-only | On submit | Validation |

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
- Add Camera modal in the prototype has a single name field and no URL/credentials/FPS. It must be completed.
- Blur is shown as text only; the earlier design had a per-camera switch. CONFIRM (blur should likely be enforced globally, SCR-016).
- Buttons are 38px high (touch target below 44px).
