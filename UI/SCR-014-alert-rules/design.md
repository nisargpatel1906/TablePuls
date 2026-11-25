# SCR-014 — Alert Rules & Threshold Settings

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-014`
- **Route (prototype):** `/venues/:venueId/settings/alerts`
- **Priority tier:** P2
- **Roles with access:** MANAGER, OWNER
- **Purpose:** Configure alert delays, notification channels and quiet hours.
- **App chrome:** Floating liquid-glass shell: sidebar (>=1024px) or header pill + bottom dock (<1024px)

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-014-alert-rules-phone-light.png` | Phone | Light | 390 x 856 CSS px | @2x -> 780 x 1712 px |
| `SCR-014-alert-rules-phone-dark.png` | Phone | Dark | 390 x 856 CSS px | @2x -> 780 x 1712 px |
| `SCR-014-alert-rules-tablet-light.png` | Tablet | Light | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-014-alert-rules-tablet-dark.png` | Tablet | Dark | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-014-alert-rules-desktop-light.png` | Desktop | Light | 1440 x 810 CSS px | @1x -> 1440 x 810 px |
| `SCR-014-alert-rules-desktop-dark.png` | Desktop | Dark | 1440 x 810 CSS px | @1x -> 1440 x 810 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** App shell. Title; tabs scroll horizontally if needed; settings card with each rule as a stacked block (label above slider + number). Page 856px.
- **Tablet (834px):** Settings card max 760px, rule rows put label left and controls right (row from 640px).
- **Desktop (1440px):** Same card, left-aligned in the content column.

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 856 / 856 | 1194 / 1194 | 810 / 810 |
| Sidebar visible | no | no | yes |
| Bottom dock visible | yes | yes | no |
| Hamburger visible | yes | yes | no |
| Horizontal-scroll containers | 1 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 10 | 10 | 11 |
| Examples under 44px | Open navigation menu, 4, Toggle theme, Thresholds | Open navigation menu, 4, Toggle theme, Thresholds | [Venue Name — Primary] [Venue Name — Sec, Sign Out, 4, Toggle theme |

## 4. Components and controls
- Tabs: `Thresholds`, `Notification Channels`, `Quiet Hours`.
- Thresholds: four rules with slider + number input (Unattended Service, Dirty Table, Debounce, Low-Confidence Escalation).
- Channels (not captured): webhook URL, Slack URL, `Send Test Webhook`. Quiet hours (not captured): start/end time.
- `Save Changes` button.

**Auto-extracted from the desktop render:**
- Headings: `Alert Rules & Threshold Settings`
- Table headers: —
- Form fields:
  - `select-one` Venue selector: `[Venue Name — Primary]`
  - `range` (unlabelled): `5`
  - `number` (unlabelled): `5`
  - `range` (unlabelled): `2`
  - `number` (unlabelled): `2`
  - `range` (unlabelled): `10`
  - `number` (unlabelled): `10`
  - `range` (unlabelled): `30`
  - `number` (unlabelled): `30`

## 5. States
Unsaved changes, saving, validation (range limits), test webhook result, last saved by/at.

## 6. Interactions and navigation
-

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Rule rows #2C2C2E at 80%; slider accent #007AFF.

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
Each rule pairs a range input with a number input; both need the same label.

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- Defaults 5 min, 2 min, 10 s, 30 s
- Webhook `https://[webhook-endpoint.example]/tablepulse`
- Quiet hours 23:30 to 08:00

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Threshold sliders and numbers | AlertRule.serviceDelayMin, dirtyDelayMin, debounceSec, lowConfidenceEscalationSec | AlertRule endpoint (per venue) | Ranges 1-30, 0-15, 3-60, 10-120 | On load / Save | Show validation |
| Webhook URL | NotificationChannel.url + HMAC secret | Channel endpoint | URL; secret write-only | On load / Save | Test result inline |
| Slack URL | NotificationChannel.slackWebhook | Channel endpoint | Treated as a secret: show masked | On load / Save | - |
| Quiet hours | AlertRule.quietStart, quietEnd + venue timezone | AlertRule endpoint | HH:MM in venue timezone | On load / Save | Overnight ranges supported |
| Save | Versioned update + audit | AlertRule endpoint | - | On click | Conflict handling |

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
- Slider and number inputs are not linked to each other or to state in the prototype; Save only shows a toast.
- Quiet-hours default (23:30-08:00) differs from the onboarding hours placeholder. CONFIRM.
