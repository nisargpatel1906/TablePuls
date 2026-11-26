# UI Assets for Phase 2 (`SCR-017`–`SCR-022`)

> Does not modify Phase 1's `UI/README.md`. Save generated 2x PNG mockups in `UI/` using the exact filenames below. If an asset is missing when Stage 12/13 starts, the coding agent builds from `docs/phase2/09-ui-screens-phase2.md` using existing design tokens and marks `// TODO(ui-asset): SCR-XXX`.

## 1. Priority Asset Checklist (6 New Screens)

| Priority | Screen ID | Screen Name | Target Filename (`UI/`) | Breakpoints |
|---|---|---|---|---|
| **P1** | `SCR-022` | Customer Digital Menu (`/m/:qrToken`, zero-login) | `UI/SCR-022-customer-digital-menu.png` | Phone (375px primary), Tablet (768px) + revoked/unavailable state |
| **P1** | `SCR-017` | Advanced Table Management & Bulk Add | `UI/SCR-017-table-management.png` | Desktop (1440px), Phone cards (375px) |
| **P1** | `SCR-018` | Menu & Category Management (incl. Quick-86) | `UI/SCR-018-menu-management.png` | Desktop (1440px), Tablet (768px) |
| **P1** | `SCR-019` | Menu Item Editor Drawer (incl. Variants & Image) | `UI/SCR-019-menu-item-editor.png` | Desktop drawer, Phone |
| **P1** | `SCR-020` | Table QR Code Manager & Batch Print Center | `UI/SCR-020-qr-manager.png` | Desktop (1440px) + Regenerate grace modal |
| **P2** | `SCR-021` | Live Customer Menu Mobile Preview Modal | `UI/SCR-021-menu-preview.png` | Desktop modal wrapping 375px frame |

## 2. Ready-to-Paste Prompt for Your UI Generator

```text
Design 6 new screens that seamlessly extend the existing TablePulse v1.0 web app (see attached docs/phase2/09-ui-screens-phase2.md).
Reuse the exact existing visual design language (Apple HIG / Liquid Glass surfaces, typography, spacing, corner radii, buttons, inputs, tables, drawers, chips, and light/dark tokens) — do not invent a new style.
Screens to generate (2x PNG):
- SCR-022 Customer Digital Menu (mobile-first 375px primary + tablet; venue header, Table badge, menu tabs, search, Veg/Non-Veg/Vegan/GF chips, item cards with prices & photos, item detail bottom sheet with allergens; NO login, NO cart, NO order buttons, NO admin links)
- SCR-017 Table Management + Bulk Add modal (desktop 1440px + mobile cards)
- SCR-018 Menu & Category Management with 1-tap Quick-86 availability toggles & drag-reorder handles (desktop)
- SCR-019 Menu Item Editor Drawer with minor-unit price input, variants list, dietary/allergen chips & WebP image uploader
- SCR-020 QR Code Manager & Batch Print Center with status chips (Active/Grace/Revoked), scan counts, Download SVG/PNG/PDF & Regenerate confirmation modal
- SCR-021 Live Mobile Menu Preview modal
Use realistic restaurant sample data (tables T01–T20, Indian dishes with INR prices, veg/non-veg indicators). Status chips must always pair text + icon, never color alone.
```
