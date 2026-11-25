# SCR-016 — System Health, Model Registry & Privacy

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-016`
- **Route (prototype):** `/org/system`
- **Priority tier:** P2
- **Roles with access:** OWNER
- **Purpose:** Owner-only system health, model registry, AI kill switch and retention.
- **App chrome:** Floating liquid-glass shell: sidebar (>=1024px) or header pill + bottom dock (<1024px)

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-016-system-health-phone-light.png` | Phone | Light | 390 x 1491 CSS px | @2x -> 780 x 2982 px |
| `SCR-016-system-health-phone-dark.png` | Phone | Dark | 390 x 1491 CSS px | @2x -> 780 x 2982 px |
| `SCR-016-system-health-tablet-light.png` | Tablet | Light | 834 x 1362 CSS px | @2x -> 1668 x 2724 px |
| `SCR-016-system-health-tablet-dark.png` | Tablet | Dark | 834 x 1362 CSS px | @2x -> 1668 x 2724 px |
| `SCR-016-system-health-desktop-light.png` | Desktop | Light | 1440 x 810 CSS px | @1x -> 1440 x 810 px |
| `SCR-016-system-health-desktop-dark.png` | Desktop | Dark | 1440 x 810 CSS px | @1x -> 1440 x 810 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** App shell. Four cards stack. Health tiles in 2 columns. Page 1491px.
- **Tablet (834px):** Same stacking (two columns from 1024px). Page 1362px.
- **Desktop (1440px):** Sidebar + 2x2 card grid.

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 1491 / 1491 | 1362 / 1362 | 810 / 810 |
| Sidebar visible | no | no | yes |
| Bottom dock visible | yes | yes | no |
| Hamburger visible | yes | yes | no |
| Horizontal-scroll containers | 0 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 5 | 5 | 6 |
| Examples under 44px | Open navigation menu, 4, Toggle theme, Switch / Rollback Model | Open navigation menu, 4, Toggle theme, Switch / Rollback Model | [Venue Name — Primary] [Venue Name — Sec, Sign Out, 4, Toggle theme |

## 4. Components and controls
- Service & Worker Health: five tiles (API, PostgreSQL/Timescale, Redis, MediaMTX, CV worker) with status and metric.
- ML Model Registry: active model id, dataset version, deployed date, `Offline Macro-F1` and `Guest Count MAE` tiles showing `NOT YET MEASURED` and `—`, `Switch / Rollback Model`.
- AI Pipeline Kill Switch card (red outline): description + red `Pause All AI Inference — Manual Mode Only` (green resume when paused).
- Privacy & Data Retention: `ENFORCED` blur, snapshot retention 7 days, analytics 365 days, `Purge All Snapshots Now`.

**Auto-extracted from the desktop render:**
- Headings: `System Health, Model Registry & Privacy`, `Service & Worker Health`, `ML Model Registry & Evaluation`, `AI Pipeline Kill Switch`, `Privacy & Data Retention`
- Table headers: —
- Form fields:
  - `select-one` Venue selector: `[Venue Name — Primary]`

## 5. States
Degraded/down services, kill switch engaged (header shows `AI Paused`), rollback dialog, purge confirmation and progress.

## 6. Interactions and navigation
-

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Kill-switch card keeps a 30% red border; healthy text #30D158; tiles #2C2C2E at 80%.

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
Status is text with colour; destructive buttons labelled in full.

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- Service names and numbers (p95 18ms, Pool 8/40, 3/4 streams)
- `[active-detector-model-id]`, `[dataset-version-id]`, `[YYYY-MM-DD]`
- Retention 7 and 365 days

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Service tiles | Health checks per service: status, p95 latency or pool | Health endpoint | Status enum + metric text | Poll 10-30s | Unknown -> 'No data', never green by default |
| `3/4 streams` | count(streams up) / count(cameras) | Derived | `n/total` | Realtime | - |
| Model registry | ModelVersion.id, datasetVersion, deployedAt, status | Registry endpoint | ISO date in venue timezone | On load | - |
| Macro-F1 / MAE | Offline evaluation results | Eval store | Number or `NOT YET MEASURED` | On load | Keep honest empty state until real evaluation exists |
| Rollback | Activate previous ModelVersion | Registry endpoint | - | On confirm | Confirm dialog + audit |
| Kill switch | SystemFlag.aiInferenceEnabled | Flag endpoint | Boolean | On click | Requires confirmation; audit; propagates to all venues |
| Retention values | RetentionPolicy.snapshotDays, analyticsDays | Policy endpoint | Days | On load | Editing out of scope in prototype |
| Purge snapshots | Bulk delete job | Admin endpoint | - | On confirm | Typed confirmation + audit |

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
- Kill switch and purge fire immediately in the prototype with no confirmation. Real build needs confirmation and audit.
- Service list is hardcoded; derive it from actual health data.
- Rollback only shows a toast.
