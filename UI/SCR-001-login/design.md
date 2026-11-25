# SCR-001 — Login

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-001`
- **Route (prototype):** `/login`
- **Priority tier:** P1
- **Roles with access:** Public
- **Purpose:** Authenticate existing users. Entry point for every role.
- **App chrome:** None. Standalone full-page layout

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-001-login-phone-light.png` | Phone | Light | 390 x 844 CSS px | @2x -> 780 x 1688 px |
| `SCR-001-login-phone-dark.png` | Phone | Dark | 390 x 844 CSS px | @2x -> 780 x 1688 px |
| `SCR-001-login-tablet-light.png` | Tablet | Light | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-001-login-tablet-dark.png` | Tablet | Dark | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-001-login-desktop-light.png` | Desktop | Light | 1440 x 810 CSS px | @1x -> 1440 x 810 px |
| `SCR-001-login-desktop-dark.png` | Desktop | Dark | 1440 x 810 CSS px | @1x -> 1440 x 810 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** No app shell. One card, full width minus 16px page padding (max 430px), 24px inner padding, vertically centred on a 844px minimum canvas. Stacked fields; no scroll needed.
- **Tablet (834px):** Same single card, 430px wide, centred horizontally and vertically in the 834px canvas; 32px inner padding.
- **Desktop (1440px):** Same single card, 430px wide, centred on the 1440px canvas. Background shows the two soft radial colour washes (blue top-left, green top-right).

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 844 / 844 | 1194 / 1194 | 810 / 810 |
| Horizontal-scroll containers | 0 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 3 | 3 | 3 |
| Examples under 44px | Forgot password?, Show, Sign in as Demo Manager | Forgot password?, Show, Sign in as Demo Manager | Forgot password?, Show, Sign in as Demo Manager |

## 4. Components and controls
- Brand tile 48x48, radius 16, solid #1C1C1E (light) / white (dark) with the 4-square glyph inverted.
- Title `Sign in to TablePulse` 22px/700; subtitle 13.5px secondary label colour.
- Email field: min-height 46, radius 14, fill #F2F2F7 (dark #2C2C2E), `autocomplete=username`.
- Password field with inline `Show/Hide` text toggle (right) and `Forgot password?` link above the field (-> SCR-003).
- Primary `Sign In` pill: min-height 48, #007AFF, 14.5px/600.
- Demo Mode panel (radius 18): label `Demo Mode Enabled (DEMO_MODE=true)` + `Sign in as Demo Manager` button.

**Auto-extracted from the desktop render:**
- Headings: `Sign in to TablePulse`
- Table headers: —
- Form fields:
  - `email` (unlabelled): `[user@venue-domain.example]`
  - `password` (unlabelled): `(masked)`

## 5. States
Submitting (disabled button + spinner), generic invalid-credentials banner, rate-limit (429) with retry-after, expired-session notice, password revealed, field validation.

## 6. Interactions and navigation
Sign In -> SCR-005 (all roles) · Forgot password? -> SCR-003 · Demo button -> SCR-005 as MANAGER.

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Card #1C1C1E with 9% white border and heavier shadow; fields #2C2C2E; demo panel #2C2C2E at 70%; link/accent #409CFF; page gradient washes switch to the brighter blue/green dark variants over pure #000.

| Token (measured on desktop render) | Light | Dark |
|---|---|---|
| Body text | `rgb(28, 28, 30)` | `rgb(245, 245, 247)` |
| Solid content card fill | `rgb(255, 255, 255)` | `rgb(28, 28, 30)` |
| Card border | `rgba(60, 60, 67, 0.086)` | `rgba(255, 255, 255, 0.09)` |
| Liquid-glass fill | — | — |
| Liquid-pill fill | — | — |
| Heading colour | `rgb(28, 28, 30)` | `rgb(245, 245, 247)` |
| Heading size | `22px` | `22px` |
| Secondary text | `rgb(99, 99, 102)` | `rgb(174, 174, 178)` |
| Primary button fill | `rgb(0, 122, 255)` | `rgb(0, 122, 255)` |

| Canvas | `#F2F2F7` + soft blue/green washes | `#000000` + brighter blue/green washes |
| Solid card | `#FFFFFF`, 1px rgba(60,60,67,.085) | `#1C1C1E`, 1px rgba(255,255,255,.09) |
| Inset field | `#F2F2F7` | `#2C2C2E` |
| Secondary label | `#636366` | `#AEAEB2` |
| Accent | `#007AFF` | `#0A84FF` (text accents `#409CFF`) |

The theme is switched with the `dark` class on `<html>` plus `dark-canvas` on `<body>`. A Reduce Transparency solid mode also exists in the prototype (`solid-mode` class); it is not part of these PNGs.

## 8. Accessibility
Real labels bound with `for`, Enter submits, error summary should receive focus, 44px+ targets (fields 46px, buttons 48px). `Show/Hide` is a text button but has no `aria-pressed`.

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- Email `[user@venue-domain.example]` (prefilled)
- Masked password dots (prefilled)
- `DEMO_MODE=true` label and `Sign in as Demo Manager`

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Email / password inputs | Credential (email, password) | Auth login endpoint | Email as typed; never prefilled in production | On submit | Generic error text only (no account enumeration); 429 shows retry-after |
| Demo Mode panel | Server config flag DEMO_MODE | Public runtime config | Boolean | On page load | Hidden entirely when false. MUST be false in production |
| Post-login destination | User.memberships[].role, default venue | Auth response / session | Role enum (OWNER, MANAGER, HOST, STAFF, VIEWER) | On login | If user has no venue -> onboarding (OWNER) or 'no access' state |
| Session-expired banner | Redirect reason | Query param set by session guard | Short enum | On load | Hidden when absent |

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
- Demo panel and prefilled values are prototype conveniences. Do not ship them.
- No loading, error or rate-limit state is drawn in the prototype; spec above defines them.
- Prototype has no link to Accept Invite here (invites arrive by email link only). That is fine, but confirm.
