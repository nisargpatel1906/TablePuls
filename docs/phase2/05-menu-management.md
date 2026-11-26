# TablePulse Phase 2 — Menu Management System Specification

## Quick Reference
- **Hierarchy**: `Venue` -> `Menu` (1..N, e.g., Main, Lunch, Drinks) -> `Menu Category` (1..N, ordered) -> `Menu Item` (0..N, ordered) (`DECIDED` / `PROPOSED`).
- **Pricing**: Stored as integer `price_minor_units` (paise/cents) + venue ISO-4217 `currency_code` (`DEC-011`) to avoid floating-point drift.
- **Practical Real-World Operations**: 1-tap item availability ("86 / Sold Out") toggle, item duplication, drag/numeric category & item reordering, dietary/allergen tagging, server-validated WebP image pipeline, and live mobile menu preview (`SCR-021`).
- **Functional Requirements Covered**: `FR-029`, `FR-030`, `FR-031`, `FR-032`, `FR-033`.

---

## 1. Menus (`FR-029`)
- **Multi-Menu Support**: A venue can define multiple menus (e.g., `All-Day Dining`, `Lunch Specials`, `Beverages & Cocktails`, `Desserts`). One menu may be flagged `is_default = true`.
- **Optional Time-of-Day Scheduling (`schedule_json`)**:
  - Schema (`v1`): `{ "v": 1, "windows": [{ "days": [1,2,3,4,5], "start": "11:30", "end": "15:00" }] }` evaluated in `venue.timezone` (ISO weekday `1=Mon`..`7=Sun`).
  - If `schedule_json IS NULL`, the menu is shown whenever `is_active = true`.
  - If `schedule_json` is set, the public QR menu automatically shows the menu only during its active time window(s) (eliminating manual lunch/dinner swapping!).
- **Venue-Level Menu Settings** (managed in `SCR-018` settings popover):
  - `menu_public_enabled` (master publish toggle — turning off shows a friendly "Menu temporarily unavailable" screen on `SCR-022`).
  - `show_unavailable_items_public` (show sold-out items dimmed with "Currently Unavailable" badge vs. hide them completely).
  - `currency_code` (`INR`, `USD`, `EUR`, `GBP`, etc.), `menu_tagline`, and optional venue logo upload.

---

## 2. Menu Categories (`FR-030`)
- **Fields**: `name` (1–100 chars, unique per menu case-insensitively among non-deleted rows), `description` (optional, max 300 chars), `is_active` (default `true`), `sort_order` (integer).
- **Reordering**: `PATCH /api/v1/venues/{v}/menus/{m}/categories/reorder` accepts an ordered array of `category_id`s and updates `sort_order` atomically in one transaction.
- **Deletion Rule**: Soft-deleting a category with active items requires explicit confirmation in UI (warns "X items inside this category will also be archived") or lets the manager move items to another category first. Soft-delete cascades `deleted_at` to child items inside one transaction.

---

## 3. Menu Items (`FR-031`, `FR-033`)
- **Fields**:
  - `name` (required, 1–120 chars), `description` (optional, max 500 chars).
  - `price_minor_units` (required integer `0..100000000`; `0` allowed for complimentary items / "Market Price" when noted).
  - `compare_at_price_minor_units` (optional original price for strike-through specials; must be `> price_minor_units`).
  - `is_available` (boolean, default `true`) — **1-Tap Quick 86 Toggle** directly on each item row in `SCR-018` so staff/managers can mark an item sold out in under 2 seconds during dinner rush.
  - `is_featured` (boolean, default `false`) — surfaces a "Chef's Pick / Popular" badge on `SCR-022`.
  - `dietary_tags`: curated enum array (`VEG`, `NON_VEG`, `VEGAN`, `GLUTEN_FREE`, `DAIRY_FREE`, `NUT_FREE`, `SPICY_MILD`, `SPICY_MEDIUM`, `SPICY_HOT`, `CHEF_SPECIAL`).
  - `allergens`: curated array (`NUTS`, `PEANUTS`, `DAIRY`, `GLUTEN`, `SOY`, `SHELLFISH`, `FISH`, `EGGS`, `SESAME`).
  - `prep_time_minutes` (optional `1–240`), `calories_kcal` (optional `0–10000`), `image_asset_id`, `image_alt`.
- **Duplicate Item**: `POST /api/v1/venues/{v}/menu-items/{item_id}/duplicate` clones an item as `"{name} (Copy)"` in the same category (reusing `image_asset_id`) so managers can build variants (e.g., Margherita 9" / 12") rapidly.
- **Bulk Availability Toggle**: Select multiple items in `SCR-018` -> `Mark Unavailable` / `Mark Available` in one batch call.
- **Concurrency Safety**: Item edits check `version` (optimistic locking) so two managers editing the same item never silently overwrite each other (`409 VERSION_CONFLICT`).

---

## 4. Image Upload & Media Pipeline (`FR-032`)
- **No Unsigned Public Uploads (`DEC-012`)**: All uploads go through authenticated `POST /api/v1/venues/{v}/menu/media` (`OWNER`, `MANAGER` only).
- **Strict Server-Side Validation**:
  1. Max file size: `5 MB` (rejected with `413 PAYLOAD_TOO_LARGE` before full memory read).
  2. Magic-byte inspection (never trust filename extension or `Content-Type` header): allow only `JPEG`, `PNG`, `WebP`. Reject `SVG`, `GIF`, `PDF`, and polyglot payloads (`400 UNSUPPORTED_MEDIA_TYPE`).
  3. Decompression bomb check (`Pillow.Image.MAX_IMAGE_PIXELS = 25_000_000`).
  4. Strip all EXIF/GPS/IPTC metadata and transcode into two optimized WebP files:
     - Full display image: max `800×800` (aspect preserved, quality 82).
     - Thumbnail: `320×320` center-cropped (quality 78).
  5. Store under `{MENU_MEDIA_DIR}/{venue_id}/{uuid}.webp` and record metadata + `sha256` in `menu_media_assets`.
- **Orphan Cleanup**: Weekly scheduled job removes `menu_media_assets` unreferenced by any non-deleted `menu_items` or `venues.logo_storage_key` for `> 7 days`.
- **`PROFESSIONAL REVIEW` (`PRO-003`)**: Restaurants are legally responsible for the accuracy of allergen, dietary (`VEG`/`VEGAN`/`GLUTEN_FREE`), and calorie claims displayed to diners; `SCR-022` displays a subtle standard allergen disclaimer footer ("Please inform your server of any food allergies or dietary restrictions").


---

## 5. Additional Production Menu Rules (Ported from P2-06)
- **Draft vs. Published Menus**: New menus may be created in `DRAFT` status (invisible on public QR pages; previewable only via signed admin preview link) and published only when at least 1 active category with 1 item exists (else `422 MENU_NOT_PUBLISHABLE`).
- **Optional Item Variants (`variants_json`)**: Items may define up to 8 named variants (e.g., *Half / Full*, *Regular / Large*) with independent `price_minor_units` and `is_available` flags; base `price_minor_units` remains the default/starting price.
- **Overnight Schedule Windows**: Menu schedules support overnight windows such as `22:00`–`02:00` evaluated in the venue's IANA timezone (DST-safe). If two published menus are active simultaneously, both appear as selectable tabs in `sort_order`.
- **Currency-Change Lock**: Changing `venues.currency_code` when priced items already exist returns `409 CURRENCY_LOCKED` unless an `OWNER` explicitly confirms override (logged in `audit_logs`).
- **Image SHA-256 Deduplication & No URL Fetching**: Uploading an identical image (matching `sha256` within the same venue) returns the existing `menu_media_assets` record instead of duplicating files on disk. The backend NEVER fetches remote image URLs (zero SSRF surface).
- **CSV Export Formula-Injection Guard**: Any CSV export prefixes cells starting with `=`, `+`, `-`, or `@` with a single quote (`'`).
