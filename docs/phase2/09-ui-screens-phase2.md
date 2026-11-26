# TablePulse Phase 2 — UI Screens & UX Specification (`SCR-017`–`SCR-022`)

## Quick Reference
- **Design Continuity Rule (`DECIDED`)**: Strictly inherit TablePulse v1.0's **Apple iOS 26+ / iPadOS Liquid Glass** visual language from `UI/` — floating translucent glass navigation/toolbars over crisp solid content cards, concentric corner radii, SF Pro / Inter typography, Light/Dark mode + Glass/Solid (Reduce Transparency) toggle, and zero "AI-generated" visual tropes (no purple-blue gradients, no rainbow KPI numbers, no raw unicode emoji glyphs).
- **Mockup Placeholder Convention**: When generating visual reference assets into `UI/SCR-017-*.png` through `UI/SCR-022-*.png`, use bracketed `[Placeholder]` tokens (e.g., `[Venue Name]`, `[Dish Name]`, `[Table 04]`) so Antigravity binds every field to live API data instead of hardcoding mock strings.
- **Navigation Integration**: Adds 3 items to the existing v1.0 Left Navigation Rail (for authorized roles): **Menu** (`SCR-018`) in Primary Nav, plus **Tables** (`SCR-017`) and **QR Codes** (`SCR-020`) in Admin Nav. Existing screens `SCR-001`–`SCR-016` are NOT redesigned.

---

> **Visual Assets:** See `UI/PHASE-2-ASSETS.md` for priority order, breakpoint targets, and a ready-to-paste UI-generation prompt for `SCR-017`–`SCR-022`.

## 1. Phase 2 Screen Inventory (`SCR-017`–`SCR-022`)

| Screen ID | Screen Name | Route | Roles | Asset Target Path (`UI/`) |
|---|---|---|---|---|
| `SCR-017` | Table Management & Configuration | `/venues/:venueId/settings/tables` | `OWNER`, `MANAGER` (read: `HOST`, `VIEWER`) | `UI/SCR-017-table-management.png` |
| `SCR-018` | Menu & Category Management | `/venues/:venueId/menu` | `OWNER`, `MANAGER` (read/86: `HOST`, read: `STAFF`/`VIEWER`) | `UI/SCR-018-menu-management.png` |
| `SCR-019` | Menu Item Editor Drawer | Slide-over on `SCR-018` | `OWNER`, `MANAGER` | `UI/SCR-019-menu-item-editor.png` |
| `SCR-020` | Table QR Code Manager & Print Center | `/venues/:venueId/settings/qr-codes` | `OWNER`, `MANAGER` (view/dl: `HOST`) | `UI/SCR-020-qr-manager.png` |
| `SCR-021` | Live Mobile Menu Preview Modal | Modal on `SCR-018` | `OWNER`, `MANAGER` | `UI/SCR-021-menu-preview.png` |
| `SCR-022` | Customer-Facing Digital Menu | `/m/:qrToken` | **Public (Unauthenticated Diners)** | `UI/SCR-022-public-digital-menu.png` |

---

## 2. Detailed Screen Specifications

### `SCR-017` — Table Management & Configuration
- **Purpose & Users**: Add, bulk-create, edit, rename, configure, deactivate, and soft-delete restaurant tables (`OWNER`, `MANAGER`).
- **Layout & Regions**:
  - **Top Summary Strip** (solid cards): `Total Active Tables`, `Total Seat Capacity`, `Camera-Mapped Tables`, `Inactive Tables`.
  - **Floating Glass Action Bar**: Search by Table Code/Name, Section filter dropdown, Status filter (`Active`, `Inactive`, `All`), Calibration filter (`Mapped`, `Unmapped`), **+ Bulk Add Tables** button, primary **+ Add Table** CTA.
  - **Main Content Table** (responsive card list on mobile): Columns — Checkbox (for bulk actions), `Table Code` + `Display Name`, `Section`, `Capacity (Min–Max)`, `Shape / Combinable`, `Camera Status` (`Mapped` link to `SCR-013` vs. `Manual Mode`), `QR Status` (1-click preview/download), `Active` toggle, Actions (`Edit`, `Delete`).
  - **Bulk Selection Floating Bar** (appears when `>=1` row checked): `Move to Section`, `Deactivate`, `Reactivate`, `Download QRs PDF`.
  - **Add/Edit Table Modal** & **Bulk Add Modal**: Live preview of generated table codes (`P01, P02, ... P06`) before submitting.
- **States**: Loading skeletons, Empty ("No tables yet — add your first table or bulk-generate a floor"), Conflict error (`409 DUPLICATE_TABLE_CODE` or `409 TABLE_IN_USE` with force-delete confirmation modal), Permission-denied read-only mode for `HOST`/`VIEWER`.
- **Accessibility**: Full keyboard navigation, confirmation dialogs with focus traps for delete/deactivate, `aria-live` announcements for bulk results.

### `SCR-018` — Menu & Category Management
- **Purpose & Users**: Manage venue menus, categories, item ordering, and rapid 1-tap availability ("86") toggles (`OWNER`, `MANAGER`; read-only / optional Quick-86 for `HOST`).
- **Layout & Regions**:
  - **Top Menu Bar**: Menu selector tabs (`All-Day Dining`, `Lunch Specials`, `Drinks`, `+ New Menu`), Publish status pill (`Public Menu: LIVE` / `UNPUBLISHED`), **Menu Settings** button (currency, tagline, logo, show-unavailable toggle), **Preview Mobile Menu** button (`SCR-021`), primary **+ Add Item** CTA.
  - **Two-Column Workspace** (stacked accordion on mobile):
    - **Left Rail (280px, solid card)**: Ordered list of Categories with item counts, active/inactive toggle, drag-handle + up/down keyboard reorder buttons, `+ Add Category` CTA.
    - **Right Main Pane**: Search items, filter (`All`, `Available`, `Unavailable / 86'd`, Dietary tag), bulk-select availability actions, and ordered Item Cards/Rows showing WebP thumbnail, Name, Price (formatted in venue currency), Dietary badges, **1-Tap Available Switch**, `Duplicate`, `Edit` (`SCR-019`), `Delete`.
- **States**: Loading skeletons, Empty Venue ("Create your first menu to activate table QR menus"), Empty Category ("No items in Starters yet"), Optimistic switch with rollback + error toast if `PATCH /availability` fails, Concurrency `409` refresh prompt.
- **Accessibility**: Keyboard-accessible reorder controls (Up/Down buttons alongside drag-and-drop), `role="switch"` with `aria-checked` on availability toggles, >=44×44px touch targets.

### `SCR-019` — Menu Item Editor Drawer
- **Purpose & Users**: Create or edit a single food/beverage item (`OWNER`, `MANAGER`).
- **Layout & Regions**: Slide-over right drawer (480px wide on desktop/tablet; full-screen sheet on mobile) matching `SCR-007`'s exact drawer pattern.
- **Visible Content & Controls**:
  - Image upload dropzone (shows WebP preview, 5 MB limit hint, upload progress bar, Remove button).
  - Item Name, Category selector, Description textarea (500-char counter).
  - Price input (formatted decimal input converted cleanly to `price_minor_units` integer) + optional Compare-At Price.
  - Availability switch (`Available now`) & Featured toggle (`Highlight as Popular`).
  - Multi-select Dietary Tag chips (`Veg`, `Non-Veg`, `Vegan`, `Gluten-Free`, `Spicy`, etc.) and Allergen chips (`Nuts`, `Dairy`, `Gluten`, `Soy`, etc.).
  - Optional Prep Time (mins) & Calories (kcal).
  - Sticky footer: `Cancel`, `Save Item`.
- **States**: Image uploading spinner, `413`/`400` inline image error ("Only JPEG, PNG, or WebP up to 5 MB"), Field validation errors, Unsaved changes guard on close.
- **Accessibility**: Focus trapped inside drawer, `Esc` closes with unsaved-changes confirmation, proper `<label>` + `aria-describedby` on all fields.

### `SCR-020` — Table QR Code Manager & Print Center
- **Purpose & Users**: Inspect every table's unique QR code, download individual SVGs/PNGs, export printable batch PDF tent-card sheets, and regenerate compromised QR codes (`OWNER`, `MANAGER`; view/download for `HOST`).
- **Layout & Regions**:
  - **Top Toolbar**: Search table, Section filter, Print Layout selector (`A4 4-Up`, `A4 6-Up`, `Letter 4-Up`), **Select All Active**, primary **Export Selected as PDF** CTA.
  - **Responsive QR Card Grid** (3–4 cols desktop, 2 cols tablet, 1 col mobile): Each solid card displays:
    - Checkbox, Table Label (`Table 04 — Main Hall`), scannable SVG QR preview, short URL display, 7-day / total scan count, Last Scanned time.
    - Actions: `Download PNG`, `Download SVG`, `Open Public Link` (new tab -> `SCR-022`), and `Regenerate` (destructive-styled icon button for `OWNER`/`MANAGER` only).
- **States**: Loading skeletons, PDF generating progress toast, Regenerate confirmation modal ("Previous printed QR will stop working immediately"), Empty (no active tables -> link to `SCR-017`).
- **Accessibility**: QR SVGs include `aria-label="QR code for Table [table_code]"`, clear confirmation dialogs.

### `SCR-021` — Live Mobile Menu Preview Modal
- **Purpose & Users**: Lets `OWNER`/`MANAGER` verify how the customer digital menu looks on a smartphone before publishing (`SCR-018` toolbar trigger).
- **Layout & Regions**: Centered modal containing a 390×844 mobile viewport frame rendering the exact `SCR-022` component in Light/Dark preview toggle + Sample Table selector.
- **States**: Live refresh when menu settings change; Banner if `menu_public_enabled=false` ("Currently unpublished — only visible in preview").

### `SCR-022` — Customer-Facing Digital Menu (`/m/:qrToken`)
- **Purpose & Users**: Zero-login, mobile-first public digital menu for seated restaurant guests scanning a table QR code.
- **Layout & Regions** (Mobile-first 360px–430px primary; cleanly centered max-width 680px column on tablet/desktop):
  - **Venue Hero Header**: Venue Logo (optional), Venue Name, Tagline, and crisp **Table Badge** (e.g., `Table 04` or `Window Booth 4`) — zero admin buttons, zero login links.
  - **Sticky Floating Glass Bar**:
    - Menu Switcher pills (only rendered if `>1` active menu is currently scheduled, e.g., `All-Day` / `Drinks`).
    - Search input (`Search dishes...`) + horizontal scrollable **Dietary Filter Chips** (`Veg`, `Vegan`, `Gluten-Free`, `Chef's Special`).
    - Horizontal scrollable **Category Jump Pills** (`Starters`, `Mains`, `Breads`, `Desserts`) synced with scroll position (scroll-spy).
  - **Menu Item Feed**: Grouped by category heading + optional description. Each solid item card shows:
    - Left: Dish Name, Dietary indicator dot/badge, 2-line truncated description, formatted Price (with strike-through compare-at price if set), `Unavailable` pill if `is_available=false`.
    - Right: Crisp 88×88px rounded WebP thumbnail (`loading="lazy"`, omitted cleanly if item has no photo so layout stays balanced).
  - **Item Detail Bottom Sheet** (opens on card tap): Full-width WebP photo, full description, dietary tags, explicit Allergen list, prep time, calories, and availability status.
  - **Minimal Footer**: Standard allergen disclaimer text + subtle `"Powered by TablePulse"` (configurable).
- **States**:
  - *Loading*: Instant clean card shimmer (`<= 1.5s` FCP on 4G).
  - *Empty Search/Filter*: "No dishes match your filter" + **Clear Filters** button.
  - *QR Revoked (`410`)*: Clean full-screen card — "This table QR code has been updated. Please ask your server for the current menu."
  - *Table Unavailable (`410`)*: Clean card — "This table is currently unavailable. Please ask a host or server for assistance."
  - *Not Found (`404`)*: Generic "Menu not found" card.
  - *Offline / Network Error*: Friendly retry button.
- **Accessibility**: WCAG 2.1 AA contrast in both Light and Dark mode, `prefers-reduced-motion` honored, semantic headings (`h1` venue -> `h2` category -> `h3` item), `aria-modal` bottom sheet with `Esc`/swipe-down close, large readable body typography (`>= 16px` base).
