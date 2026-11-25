# TablePulse — Global Design System (iOS 26 Liquid Glass, Light & Dark)

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## Two-layer hierarchy
- **Control layer (floating liquid glass):** sidebar, header pill, filter bars, bottom dock, sheets. Light `rgba(255,255,255,.72)` / dark `rgba(28,28,30,.74)`, blur 28px, saturate 195%, 1px specular edge (white 78% light / 13% dark), radius 28 (panels) or full pill.
- **Content layer (solid):** KPI cards, tables, floor map, forms. Light `#FFFFFF`, dark `#1C1C1E`, radius 24, inner tiles 16.
- **Reduce Transparency:** `solid-mode` replaces glass with solid `#FFFFFF` / `#1C1C1E` and removes blur.

## Colour tokens
| Token | Light | Dark |
|---|---|---|
| Canvas | #F2F2F7 | #000000 |
| Surface | #FFFFFF | #1C1C1E |
| Inset field | #F2F2F7 | #2C2C2E |
| Label primary | #1C1C1E | #F5F5F7 |
| Label secondary | #636366 | #AEAEB2 |
| Separator | rgba(60,60,67,.12) | rgba(255,255,255,.12) |
| Accent | #007AFF | #0A84FF |

## Semantic table states (never colour only)
| State | Hex | Border pattern | Icon |
|---|---|---|---|
| FREE | #34C759 (text #146C2E) | solid | check |
| OCCUPIED | #FF3B30 (text #B42318) | solid | person |
| NEEDS_CLEANING | #D97706 (text #92400E) | dashed | sparkle |
| NEEDS_SERVICE | #FF9500 (text #9A4E00) | solid + pulsing ring | bell |
| RESERVED | #007AFF (text #0055B8) | dotted | bookmark |
| UNKNOWN | #8E8E93 (text #48484A) | dashed + diagonal hatch | help |
| OFFLINE | #FF3B30 icon on grey | double | camera-off |

## Typography
`-apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, system-ui, sans-serif` (exports used Inter). Page title 22px/700, section 17px/700, body 14px/500, caption 12px/600, tabular numerals for all numbers.

## Responsive behaviour (measured in the exports)
| | Phone 390 | Tablet 834 | Desktop 1440 |
|---|---|---|---|
| Navigation | Header pill + bottom dock (Floor, Alerts, Waitlist, More); More opens a full glass menu | Same as phone | Sticky 256px glass sidebar |
| Breakpoints used | below 640 | 640-1023 (sm, md) | 1280+ (lg, xl) |
| KPI grid | 2 x 2 | 2 x 2 | 4 across |
| Floor | Card grid (no map) | Spatial map | Spatial map + side panel (8/4) |
| Two-column pages | Stacked | Stacked | Side by side |
| Sheet (SCR-007) | Bottom sheet, max 92% height | Right sheet 440px | Right sheet 440px |

Tablet in landscape (1194px wide) would use the sidebar layout. It is not captured.

## Motion
Press feedback scale .975 / 120ms; needs-service ring pulse 2.2s (disabled for reduced motion).
