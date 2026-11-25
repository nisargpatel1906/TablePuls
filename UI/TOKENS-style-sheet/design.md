# STYLE-SHEET — Design System Style Sheet

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `STYLE-SHEET`
- **Route (prototype):** `(tokens view)`
- **Priority tier:** —
- **Roles with access:** —
- **Purpose:** Design-system reference view inside the prototype (not a product screen).
- **App chrome:** None. Standalone full-page layout

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `TOKENS-style-sheet-phone-light.png` | Phone | Light | 390 x 1403 CSS px | @2x -> 780 x 2806 px |
| `TOKENS-style-sheet-phone-dark.png` | Phone | Dark | 390 x 1403 CSS px | @2x -> 780 x 2806 px |
| `TOKENS-style-sheet-tablet-light.png` | Tablet | Light | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `TOKENS-style-sheet-tablet-dark.png` | Tablet | Dark | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `TOKENS-style-sheet-desktop-light.png` | Desktop | Light | 1440 x 810 CSS px | @1x -> 1440 x 810 px |
| `TOKENS-style-sheet-desktop-dark.png` | Desktop | Dark | 1440 x 810 CSS px | @1x -> 1440 x 810 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** Stacked cards; state swatches in 1 column. Page 1403px.
- **Tablet (834px):** State swatches in 2 columns; two sections stack. Page 1194px.
- **Desktop (1440px):** Two columns of cards in a 1180px container.

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 1403 / 1403 | 1194 / 1194 | 810 / 810 |
| Horizontal-scroll containers | 0 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 1 | 1 | 1 |
| Examples under 44px | Switch to Dark Style Sheet | Switch to Dark Style Sheet | Switch to Dark Style Sheet |

## 4. Components and controls
- Header card with the export path label and a `Switch to Dark/Light Style Sheet` button.
- `Non-Color-Only Semantic Table States`: seven swatches (icon, key, label, pattern).
- `Two-Layer Hierarchy & Concentric Radii`: sample glass panel (28px), solid card (24px), three colour chips.

**Auto-extracted from the desktop render:**
- Headings: `TablePulse Design System Style Sheet`, `Non-Color-Only Semantic Table States`, `Two-Layer Hierarchy & Concentric Radii`
- Table headers: —
- Form fields:
  - —

## 5. States
Light and dark variants only.

## 6. Interactions and navigation
Reached only from the prototype's screen switcher.

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Shows the same states with the dark tints.

| Token (measured on desktop render) | Light | Dark |
|---|---|---|
| Body text | `rgb(28, 28, 30)` | `rgb(245, 245, 247)` |
| Solid content card fill | `rgb(255, 255, 255)` | `rgb(28, 28, 30)` |
| Card border | `rgba(60, 60, 67, 0.086)` | `rgba(255, 255, 255, 0.09)` |
| Liquid-glass fill | `rgba(255, 255, 255, 0.72)` | `rgba(28, 28, 30, 0.74)` |
| Liquid-pill fill | — | — |
| Heading colour | `rgb(28, 28, 30)` | `rgb(245, 245, 247)` |
| Heading size | `24px` | `24px` |
| Secondary text | `rgb(99, 99, 102)` | `rgb(174, 174, 178)` |
| Primary button fill | `rgb(0, 122, 255)` | `rgb(0, 122, 255)` |

| Canvas | `#F2F2F7` + soft blue/green washes | `#000000` + brighter blue/green washes |
| Solid card | `#FFFFFF`, 1px rgba(60,60,67,.085) | `#1C1C1E`, 1px rgba(255,255,255,.09) |
| Inset field | `#F2F2F7` | `#2C2C2E` |
| Secondary label | `#636366` | `#AEAEB2` |
| Accent | `#007AFF` | `#0A84FF` (text accents `#409CFF`) |

The theme is switched with the `dark` class on `<html>` plus `dark-canvas` on `<body>`. A Reduce Transparency solid mode also exists in the prototype (`solid-mode` class); it is not part of these PNGs.

## 8. Accessibility
Documents the non-colour-only rule (icon + text + border pattern for every state).

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- Static documentation content. No data.

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Everything on this view | None (static reference) | - | - | - | Do not ship in the product |

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
- This view is documentation for designers and developers. It is not part of the 16-screen product.
