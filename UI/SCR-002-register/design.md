# SCR-002 — Accept Invite / Register

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-002`
- **Route (prototype):** `/register`
- **Priority tier:** P2
- **Roles with access:** Public (Invite)
- **Purpose:** Complete account setup from an emailed invitation link.
- **App chrome:** None. Standalone full-page layout

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-002-register-phone-light.png` | Phone | Light | 390 x 844 CSS px | @2x -> 780 x 1688 px |
| `SCR-002-register-phone-dark.png` | Phone | Dark | 390 x 844 CSS px | @2x -> 780 x 1688 px |
| `SCR-002-register-tablet-light.png` | Tablet | Light | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-002-register-tablet-dark.png` | Tablet | Dark | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-002-register-desktop-light.png` | Desktop | Light | 1440 x 810 CSS px | @1x -> 1440 x 810 px |
| `SCR-002-register-desktop-dark.png` | Desktop | Dark | 1440 x 810 CSS px | @1x -> 1440 x 810 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** No shell. Card full width minus 16px (max 460px), 24px padding; 4 fields + strength meter + button stack; ends near 844px, no scroll at base height.
- **Tablet (834px):** Card 460px wide centred; same stack.
- **Desktop (1440px):** Card 460px wide centred.

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 844 / 844 | 1194 / 1194 | 810 / 810 |
| Horizontal-scroll containers | 0 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 0 | 0 | 0 |
| Examples under 44px | — | — | — |

## 4. Components and controls
- Blue pill `Invitation Verified`; title `Accept Invitation`; sentence naming venue and assigned role in bold.
- Read-only `Invited Email` (lower-contrast fill), `Full Name`, `Password (min 12 characters)`, `Confirm Password`.
- Strength meter: four 6px segments + word label (`Strong`), `aria-live=polite`.
- Primary `Create Account` pill.

**Auto-extracted from the desktop render:**
- Headings: `Accept Invitation`
- Table headers: —
- Form fields:
  - `email` (unlabelled): `[invited@venue-domain.example]`
  - `text` [Enter Full Name]: `—`
  - `password` (unlabelled): `(masked)`
  - `password` (unlabelled): `(masked)`

## 5. States
Validating token, invalid/expired token card, password too short/weak, mismatch, submitting, success redirect.

## 6. Interactions and navigation
Create Account -> SCR-004 in the prototype.

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Same dark card/inset tokens as SCR-001; read-only field uses white 6% fill with #AEAEB2 text; strength green #30D158.

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
Strength is also text (`Strong`); live region announces changes. Inputs min-height 44.

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- `[Venue Name — Primary]`, `[Assigned Role]`, `[invited@venue-domain.example]`
- Prefilled masked passwords
- Meter fixed at 3 of 4 segments / `Strong`

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Venue name + assigned role sentence | Invitation.venue.name, Invitation.role | Invitation lookup by token in URL | Role shown as human label | On load | Invalid/expired token -> error card, no form |
| Invited email (read-only) | Invitation.email | Same lookup | As stored | On load | - |
| Full name | User.name | Account create endpoint | Free text, trimmed | On submit | Inline validation |
| Password + strength meter | Password policy (min length 12, rules from server) | Policy from config; strength computed client-side from the typed value | Segments 0-4 + label | On every keystroke | Never prefilled |
| Post-create redirect | User role | Account create response | - | On success | See gap |

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
- Meter is hardcoded to 3 of 4 / Strong. It must reflect the typed password.
- Prototype always sends the user to SCR-004 (onboarding), which is OWNER-only. Non-owners should go to SCR-005. CONFIRM WITH PRODUCT.
