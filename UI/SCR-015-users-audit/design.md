# SCR-015 — Users, Roles & Audit Log Admin

> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

## 1. Overview
- **Screen ID:** `SCR-015`
- **Route (prototype):** `/org/users`
- **Priority tier:** P2
- **Roles with access:** OWNER, MANAGER
- **Purpose:** Manage team members and read the audit log.
- **App chrome:** Floating liquid-glass shell: sidebar (>=1024px) or header pill + bottom dock (<1024px)

## 2. Assets (6 files)
| File | Device | Theme | Size | Pixel output |
|---|---|---|---|---|
| `SCR-015-users-audit-phone-light.png` | Phone | Light | 390 x 844 CSS px | @2x -> 780 x 1688 px |
| `SCR-015-users-audit-phone-dark.png` | Phone | Dark | 390 x 844 CSS px | @2x -> 780 x 1688 px |
| `SCR-015-users-audit-tablet-light.png` | Tablet | Light | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-015-users-audit-tablet-dark.png` | Tablet | Dark | 834 x 1194 CSS px | @2x -> 1668 x 2388 px |
| `SCR-015-users-audit-desktop-light.png` | Desktop | Light | 1440 x 810 CSS px | @1x -> 1440 x 810 px |
| `SCR-015-users-audit-desktop-dark.png` | Desktop | Dark | 1440 x 810 CSS px | @1x -> 1440 x 810 px |

- Capture: real headless Chrome at the exact device viewport; touch + mobile emulation on phone and tablet; full-page height (viewport grown to the full content height, minimum = device base height).
- Preview bar, toasts and live pulse phase were fixed so frames are reproducible. Font: Inter (stand-in for SF Pro).

## 3. Layout architecture per device
- **Phone (390px):** App shell. Title + `+ Invite User`; tab switch; table card whose table is wider than the screen, so it scrolls horizontally inside the card (measured: 1 scroll container). Page stays 844px.
- **Tablet (834px):** Table fits (min 620px) without scrolling.
- **Desktop (1440px):** Sidebar + full-width table card.

### Measured from the rendered page
| Measured | Phone | Tablet | Desktop |
|---|---|---|---|
| Page height (light / dark) | 844 / 844 | 1194 / 1194 | 810 / 810 |
| Sidebar visible | no | no | yes |
| Bottom dock visible | yes | yes | no |
| Hamburger visible | yes | yes | no |
| Horizontal-scroll containers | 1 | 0 | 0 |
| Page overflows horizontally | no | no | no |
| Interactive elements under 44px high | 9 | 9 | 10 |
| Examples under 44px | Open navigation menu, 4, Toggle theme, Team Members | Open navigation menu, 4, Toggle theme, Team Members | [Venue Name — Primary] [Venue Name — Sec, Sign Out, 4, Toggle theme |

## 4. Components and controls
- `+ Invite User` (opens modal).
- Segmented tabs `Team Members` / `Audit Log`.
- Members table: Name, Email (mono), Role chip, Status, `Revoke`.
- Audit table (second tab): Timestamp, Actor, Action chip, Detail.

**Auto-extracted from the desktop render:**
- Headings: `Users, Roles & Audit Log`
- Table headers: `Name`, `Email`, `Role`, `Status`, `Actions`
- Form fields:
  - `select-one` Venue selector: `[Venue Name — Primary]`

## 5. States
Empty team, invite sending/success/error, revoke confirmation, audit paging and filters, loading.

## 6. Interactions and navigation
-

## 7. Light vs dark
Layout, spacing and copy are identical in both themes. Only colour, elevation and glass tokens change.

**This screen:** Header row #2C2C2E; dividers white 7%; role chip blue 12% (intended) with #409CFF text.

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
Tables use `th scope=col`; destructive action is a red text button.

## 9. REAL DATA BINDING
> **SEED DATA ONLY.** Every name, number, timer, percentage, ID, date, URL, count and chart value visible in the PNGs is prototype placeholder data. Do **not** copy it into the product and do not treat it as a requirement. Render live data from the database / API. The PNGs define layout, hierarchy, styling and behaviour only.

**Sample values seen in the PNGs (all SEED):**
- Four sample members with bracketed names/emails
- Statuses Active/Pending
- Three audit rows with `[YYYY-MM-DD HH:MM:SS]`

**Binding table** (entity and endpoint names are ASSUMED. CONFIRM WITH BACKEND):

| UI element | Entity.field | Source | Format | Refresh | Empty / loading / error |
|---|---|---|---|---|---|
| Members rows | Membership.user.name, email, role, venueScope, status, lastLoginAt | Members endpoint, scoped to the viewer's permissions | Role enum; last login relative + absolute | On load | Empty -> 'Invite your first teammate' |
| Invite | Invitation create (email, role, venueScope) | Invitation endpoint | Role select required | On submit | Duplicate email -> error |
| Revoke | Revoke sessions and/or membership | Admin endpoint | - | On click | Confirm dialog; audit entry |
| Audit rows | AuditLog.timestamp, actor, action, target, detail | Audit endpoint, append-only, paged | UTC stored, shown in venue timezone | On load + page | Immutable: no edit or delete |
| Visibility | Viewer role (OWNER, MANAGER) | Session | - | On load | Others get 'no access' |

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
- Invite modal has only an email field (no role or venue scope).
- `Revoke` has no confirmation and does not distinguish sessions from membership.
- Personal data (names, emails): follow the retention and access policy.
