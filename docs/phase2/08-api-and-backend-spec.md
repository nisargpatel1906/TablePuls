# TablePulse Phase 2 — API & Backend Specification

## Quick Reference
- **Base Prefix**: `/api/v1/...` (continuing v1.0's `API-001`–`API-023` with `API-024`–`API-035`).
- **Response Envelopes** (`DECIDED` — inherited from v1.0):
  - Success: `{ "success": true, "data": { ... } }`
  - Error: `{ "success": false, "error": { "code": "...", "message": "...", "fields?": { ... } } }`
- **New Error Codes**: `DUPLICATE_TABLE_CODE` (409), `TABLE_IN_USE` (409), `DUPLICATE_MENU_NAME` (409), `DUPLICATE_CATEGORY_NAME` (409), `UNSUPPORTED_MEDIA_TYPE` (400), `PAYLOAD_TOO_LARGE` (413), `QR_CODE_NOT_FOUND` (404), `QR_CODE_REVOKED` (410), `TABLE_UNAVAILABLE` (410), `CURRENCY_LOCKED` (409), `MENU_NOT_PUBLISHABLE` (422), `MEDIA_IN_USE` (409), `CATEGORY_NOT_EMPTY` (409).
- **Idempotency & Pagination**: List endpoints support `?page=1&page_size=25` (max `100`); mutating create/bulk/regenerate endpoints honor `Idempotency-Key` header (24h Valkey TTL).

---

## 1. Phase 2 Endpoint Inventory (`API-024`–`API-035`)

### A. Advanced Table Management
| ID | Method & Path | Purpose | Auth / Roles | Status Codes |
|---|---|---|---|---|
| `API-024` | `GET/POST /api/v1/venues/{v}/tables` & `PATCH/DELETE /api/v1/venues/{v}/tables/{t}` | List (searchable/filterable), create (auto-generates QR), update/rename (`version` checked), or soft-delete table (`?force=true` guard). | Read: `OWNER`, `MANAGER`, `HOST`, `VIEWER`; Write: `OWNER`, `MANAGER` | 200, 201, 400, 401, 403, 404, 409 |
| `API-025` | `POST /api/v1/venues/{v}/tables/bulk` & `PATCH /api/v1/venues/{v}/tables/bulk` | Bulk create tables by prefix/range (1–50, auto-generates QRs) or bulk update `section_name` / `is_active`. | `OWNER`, `MANAGER` | 200, 201, 400, 401, 403, 409 |

### B. Menu, Category, Item & Media Management
| ID | Method & Path | Purpose | Auth / Roles | Status Codes |
|---|---|---|---|---|
| `API-026` | `GET/POST /api/v1/venues/{v}/menus` & `PATCH/DELETE /api/v1/venues/{v}/menus/{m}` | List, create, update (name, active, default, `schedule_json`), or soft-delete menus. | Read: All venue roles; Write: `OWNER`, `MANAGER` | 200, 201, 400, 401, 403, 404, 409 |
| `API-027` | `PATCH /api/v1/venues/{v}/menu-settings` | Update `menu_public_enabled`, `show_unavailable_items_public`, `menu_tagline`, `logo_storage_key`, and `currency_code` (`OWNER` only for currency). | `OWNER`, `MANAGER` | 200, 400, 401, 403 |
| `API-028` | `GET/POST /api/v1/venues/{v}/menus/{m}/categories` & `PATCH/DELETE /categories/{c}` & `PATCH /categories/reorder` | CRUD and atomic drag-order update for menu categories. | Read: All venue roles; Write: `OWNER`, `MANAGER` | 200, 201, 400, 401, 403, 404, 409 |
| `API-029` | `GET/POST /api/v1/venues/{v}/menu-items` & `PATCH/DELETE /menu-items/{i}` & `POST /menu-items/{i}/duplicate` & `PATCH /menu-items/reorder` | Full CRUD, duplicate, and reorder for menu items (`price_minor_units`, tags, allergens, `version`). | Read: All venue roles; Write: `OWNER`, `MANAGER` | 200, 201, 400, 401, 403, 404, 409 |
| `API-030` | `PATCH /api/v1/venues/{v}/menu-items/{i}/availability` & `PATCH /menu-items/bulk-availability` | Fast 1-tap or batch toggle of `is_available` ("Quick 86"); immediately invalidates `tp:pub:menu:{v}`. | `OWNER`, `MANAGER`, `HOST` (if `allow_host_menu_availability=true`) | 200, 400, 401, 403, 404 |
| `API-031` | `POST /api/v1/venues/{v}/menu/media` & `DELETE /menu/media/{asset_id}` | Multipart upload (max 5 MB, magic-byte validated JPEG/PNG/WebP -> EXIF-stripped WebP full + 320px thumb). | `OWNER`, `MANAGER` | 201, 400, 401, 403, 413 |

### C. Table QR Code Management & Exports
| ID | Method & Path | Purpose | Auth / Roles | Status Codes |
|---|---|---|---|---|
| `API-032` | `GET /api/v1/venues/{v}/qr-codes` | List all active tables with their active QR token, public URL, scan count, and last scanned timestamp. | `OWNER`, `MANAGER`, `HOST`, `VIEWER` | 200, 401, 403 |
| `API-033` | `POST /api/v1/venues/{v}/tables/{t}/qr/regenerate` | Atomically rotate QR token (supports optional `grace_days`, `reason`, plus `POST .../qr/end-grace` and `POST .../qr/preview-link` signed 15-min test URL), purge Valkey cache, and log audit entry. | `OWNER`, `MANAGER` | 201, 401, 403, 404 |
| `API-034` | `GET /api/v1/venues/{v}/tables/{t}/qr/download` & `POST /api/v1/venues/{v}/qr/export-pdf` | Stream single QR (`?format=svg\|png&framed=true\|false`) or batch printable PDF tent-card sheet (max 100 tables). | `OWNER`, `MANAGER`, `HOST` | 200, 400, 401, 403, 404 |

### D. Customer-Facing Public Digital Menu (Unauthenticated)
| ID | Method & Path | Purpose | Auth / Roles | Status Codes |
|---|---|---|---|---|
| `API-035` | `GET /api/v1/public/menu/{qr_token}` | Public read-only menu payload for diners. Read-only via `tablepulse_public` DB role/views; Valkey-cached (60s + 24h stale-while-error fallback), ETag (`menu_revision`), strict IP rate limit (`60 req/min/IP`), async privacy-safe scan counter. | **Public (No Auth)** | 200, 304, 404, 410, 429 |

---

## 2. Key Request & Response Payload Examples

### `POST /api/v1/venues/{v}/tables/bulk` (`API-025`)
```json
// Request
{
  "prefix": "P",
  "start_number": 1,
  "count": 6,
  "zero_pad": 2,
  "section_name": "Patio",
  "min_capacity": 2,
  "seat_capacity": 4,
  "shape": "RECT",
  "is_combinable": true
}
// Response (201)
{
  "success": true,
  "data": {
    "created_count": 6,
    "tables": [
      { "id": "0193...", "table_code": "P01", "qr_token": "xK9m2...", "qr_url": "https://.../m/xK9m2..." }
    ]
  }
}
```

### `GET /api/v1/public/menu/{qr_token}` (`API-035`)
```json
// Response (200) — Strictly Whitelisted Public Fields Only
{
  "success": true,
  "data": {
    "venue": {
      "name": "Spice Courtyard",
      "tagline": "Fresh coastal kitchen",
      "logo_url": "/media/menu/v1/logo.webp",
      "currency_code": "INR"
    },
    "table": { "label": "Window Booth 4" },
    "menu_public_enabled": true,
    "show_unavailable_items": true,
    "menus": [
      {
        "id": "0193...",
        "name": "All-Day Dining",
        "description": null,
        "categories": [
          {
            "id": "0193...",
            "name": "Starters",
            "description": "Small plates to share",
            "items": [
              {
                "id": "0193...",
                "name": "Crispy Lotus Stem",
                "description": "Tossed in honey chili glaze with toasted sesame.",
                "price_minor_units": 32500,
                "compare_at_price_minor_units": null,
                "image_url": "/media/menu/v1/abc.webp",
                "thumb_url": "/media/menu/v1/abc_thumb.webp",
                "image_alt": "Crispy Lotus Stem",
                "is_available": true,
                "is_featured": true,
                "dietary_tags": ["VEG", "SPICY_MILD"],
                "allergens": ["SESAME"],
                "prep_time_minutes": 12,
                "calories_kcal": 340
              }
            ]
          }
        ]
      }
    ]
  }
}
```
