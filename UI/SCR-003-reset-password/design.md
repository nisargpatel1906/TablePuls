# SCR-003 — Forgot & Reset Password

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-003`
- **Route (prototype):** `/reset-password`
- **Priority tier:** P2
- **Roles with access:** Public
- **Purpose:** Self-service password recovery: request a reset link, then set a new password.
- **App chrome:** None. Standalone full-page layout

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-003-reset-password-phone-light.png` | Phone | Light | 390 x 844 CSS px | @2x -> 780 x 1688 px |
| `SCR-003-reset-password-phone-dark.png` | Phone | Dark | 390 x 844 CSS px | @2x -> 780 x 1688 px |
| `SCR-003-reset-password-tablet-light.png` | Tablet | Light | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-003-reset-password-tablet-dark.png` | Tablet | Dark | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-003-reset-password-desktop-light.png` | Desktop | Light | 1440 x 810 CSS px | @1x -> 1440 x 810 px |
| `SCR-003-reset-password-desktop-dark.png` | Desktop | Dark | 1440 x 810 CSS px | @1x -> 1440 x 810 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** No shell. Card full width minus 16px (max 430px); title row has a `Switch: Confirm/Request` chip at the right; one or two fields + primary + text link.
- **Tablet (834px):** Card 430px centred.
- **Desktop (1440px):** Card 430px centred.

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 844 / 844 | 1194 / 1194 | 810 / 810 |
| Horizontal-scroll containers | 0 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 2 | 2 | 2 |
| Examples under 44px | Switch: Confirm, Back to Sign In | Switch: Confirm, Back to Sign In | Switch: Confirm, Back to Sign In |

## 4. Components and controls
- Title (`Reset Password` / `Set New Password`) with a small `Switch` chip that flips between the two sub-states.
- Request state: email field + `Send Reset Link`. Confirm state: `New Password`, `Confirm New Password` + `Reset Password`.
- `Back to Sign In` text button.

**Auto-extracted from the desktop render:**
- Headings: `Reset Password`
- Table headers: —
- Form fields:
  - `email` (unlabelled): `[user@venue-domain.example]`

## 5. States
Request submitted (enumeration-safe message), token invalid/expired/used, mismatch, weak password, submitting, success -> sign-in.

## 6. Interactions and navigation
Submit or Back -> SCR-001.

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Card #1C1C1E, inputs #2C2C2E, secondary text #AEAEB2.

| Token (measured on desktop render) | Light | Dark |
|---|---|---|
| Body text | `rgb(28, 28, 30)` | `rgb(245, 245, 247)` |
| Solid content card fill | `rgb(255, 255, 255)` | `rgb(28, 28, 30)` |
| Card border | `rgba(60, 60, 67, 0.086)` | `rgba(255, 255, 255, 0.09)` |
| Liquid-glass fill | — | — |
| Liquid-pill fill | — | — |
| Heading colour | `rgb(28, 28, 30)` | `rgb(245, 245, 247)` |
| Heading size | `21px` | `21px` |
| Secondary text | `rgb(99, 99, 102)` | `rgb(174, 174, 178)` |
| Primary button fill | `rgb(0, 122, 255)` | `rgb(0, 122, 255)` |

| Canvas | `#F2F2F7` + soft blue/green washes | `#000000` + brighter blue/green washes |
| Solid card | `#FFFFFF`, 1px rgba(60,60,67,.085) | `#1C1C1E`, 1px rgba(255,255,255,.09) |
| Inset field | `#F2F2F7` | `#2C2C2E` |
| Secondary label | `#636366` | `#AEAEB2` |
| Accent | `#007AFF` | `#0A84FF` (text accents `#409CFF`) |

The theme is switched with the `dark` class on `<html>` plus `dark-canvas` on `<body>`. A Reduce Transparency solid mode also exists in the prototype (`solid-mode` class); it is not part of these PNGs.

## 8. Accessibility
Labels present; the Switch chip is a prototype control with no accessible explanation.

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- Prefilled `[user@venue-domain.example]`
- Toast copy `Reset link sent if account exists`

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Email field | Credential.email | Password-reset request endpoint | As typed | On submit | Always answer with the same generic message |
| New password fields | Reset token (from emailed link) + new password | Password-reset confirm endpoint | Policy from server | On submit | Expired token -> message with 'request a new link' |
| Sub-state (request vs confirm) | URL: token present or not | Router | - | On load | - |

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
- The `Switch` chip is a design-review shortcut. In production the confirm state is reached only through the emailed link.
- Confirm-state fields have no password-strength indicator (SCR-002 has one). CONFIRM WITH PRODUCT.
