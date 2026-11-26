# TablePulse Phase 2 — Security, Validation & Edge Cases

> **Quick reference**
> - Phase 2 adds the project's **first anonymous surface** and **first file uploads**. Everything else follows Phase 1 security specification (`docs/08-security-and-privacy.md`).
> - Top risks: token enumeration/abuse of the public API, malicious/oversized image uploads, cross-tenant leakage via the public path, CSV/formula & stored-XSS injection, QR sticker tampering, privilege creep through new permissions.
> - Controls: random 128-bit tokens, read-only DB role + views + RLS policies, strict CSP/no cookies, rate limits + caching, re-encoded images, allow-list serializers, field-level authorization, re-auth for destructive actions, full audit.

## 1. Threat model
| # | Threat | Asset | Mitigation | Residual / test |
|---|---|---|---|---|
| T1 | Brute-force/enumerate QR tokens to view other restaurants' menus | Public menu | 2^128 token; per-IP rate limit; invalid-flood block; identical 404 bodies | Low; `API-035` rate-limit test |
| T2 | Data leak through public endpoint (notes, ids, drafts, other tenants) | Staff-only data | Allow-list serializer; views only expose public columns; RLS `public_read` policies; schema + UUID-scan tests | Low; `API-035` schema allow-list test |
| T3 | Public endpoint DoS / scraping | Availability | Caching (30 s), stale-while-error, breaker >5k rps, rate limits, small payload, static shell | Medium at huge scale; load test |
| T4 | Malicious file upload (SVG-XSS, polyglot, decompression bomb, EXIF GPS) | Server, users | Magic-byte sniff, JPEG/PNG/WebP only, pixel cap, Pillow decode+re-encode, strip metadata, hash-named storage, `nosniff`, no originals | Low |
| T5 | Stored XSS via names/descriptions/translations | Customers, admins | Plain text only; React text rendering; CSP `script-src 'self'`; no HTML/Markdown; server rejects control chars/`<script` is **not** filtered (escaping is the control) | Low |
| T6 | CSV injection (export opened in Excel) / import abuse | Admin users | Prefix `'` on export; import size/row caps; no URL fetching | Low |
| T7 | SSRF via image URL import | Server | Feature absent: server never fetches URLs | None |
| T8 | Privilege escalation through new permissions/flags | RBAC | Owner-only flags + re-auth; effective-permission single function; field-level checks; API keys can't hold new perms; matrix tests | Low |
| T9 | Cross-tenant/venue access in admin API | Tenant data | Phase-1 RLS + 404 on cross-tenant; scope resolver per route; fuzz tests | Low |
| T10 | QR sticker overlay (quishing) | Customers | Visible short URL on print; venue+table label shown on page; revoke; guidance | Medium (operational) |
| T11 | Host-header poisoning generating wrong QR URL | QR integrity | URL from config only | None |
| T12 | Preview-token abuse | Draft menus | HMAC-signed, 15-min expiry, single venue, not counted, revocable by rotating secret | Low |
| T13 | Token leakage via logs/referrer/analytics | Capability | Logs truncated; `Referrer-Policy: no-referrer`; no third-party calls | Low |
| T14 | Replay/double-submit of bulk ops | Data integrity | Idempotency keys; advisory locks | Low |
| T15 | Clickjacking/embed of customer page | Customers | `frame-ancestors 'none'` | None |
| T16 | Menu defacement by a compromised admin | Reputation | Audit with before/after; least privilege (strict `OWNER`/`MANAGER` RBAC + audit logs); restore from soft delete; optional approval workflow `DEFERRED` | Medium |
| T17 | Phishing via menu text (fake URLs/phone numbers in descriptions) | Customers | Plain text only → URLs not auto-linked; `tel:`/`mailto:` not generated | Low |
| T18 | Supply-chain risk in new libs (segno, Pillow, ReportLab, dnd-kit) | Build | Licence + vulnerability scan in CI; pin versions; Pillow security updates tracked | Low |
| T19 | Disk exhaustion via media | Availability | Quotas, size caps, GC, `DISK_LOW` alert | Low |
| T20 | Scan-count privacy (re-identification) | Privacy | Aggregate counts, discarded daily salt, no IP/UA stored | Low |

## 2. Validation catalogue (server is authoritative; client mirrors)
| Input | Rule |
|---|---|
| All strings | NFC, trim, no C0 controls/DEL, no lone surrogates; max lengths per field (`08-api-and-backend-spec.md`); empty after trim → required-field error |
| Table label | `^[A-Za-z0-9 -]{1,12}$`, no leading/trailing space, case-insensitive unique among active |
| `capacity` | int 1–40; `min_capacity` ≤ capacity |
| `tags` | ≤ 10 × `^[a-z0-9_-]{1,24}$`, de-duplicated |
| `config` | JSON schema v1, `additionalProperties:false` |
| IDs | UUID format; foreign ids must be same venue/org |
| Price | `price_minor` int 0–100,000,000; no floats/strings |
| Currency | ISO-4217 from allow-list; exponent table for minor-unit conversion |
| Schedule | days ⊂ 1..7, `HH:MM` 24 h, valid tz from venue; overlapping schedules allowed |
| `unavailable_until` | future, ≤ 30 days |
| Variants | ≤ 8, unique names, price ≥ 0 |
| Enums (diet, allergens, tags, price_mode, status) | exact match from constants |
| Image | ≤ 5 MB, JPEG/PNG/WebP by magic bytes, ≤ 25 MP, ≥ 200×200 px; alt ≤ 140 |
| CSV | UTF-8 (BOM tolerated), ≤ 2 MB, ≤ 2000 rows, header required, per-cell ≤ 1000 chars |
| QR format/size | `svg|png`, size 128–2048 |
| Query params | whitelisted; `limit` ≤ 200; unknown params ignored (public) / rejected (admin) |
| Token | `^[A-Za-z0-9_-]{22}$` else 404 immediately (no DB hit) |
| Headers | `Idempotency-Key` UUID; `If-Match` ISO timestamp |

## 3. Public-surface controls (checklist)
- [ ] Route registry marks `API-035` (`GET /api/v1/public/menu/{qr_token}`) as the sole new `public` Phase 2 route; CI fails otherwise.
- [ ] Methods other than GET/HEAD/OPTIONS → 405.
- [ ] No `Set-Cookie`; no `Authorization` parsing; no CSRF surface (no state changes except aggregate counter).
- [ ] Response built via explicit `PublicMenuResponse` (`extra='forbid'`); unit test asserts exact key set at every level.
- [ ] DB role/view/policy test (`03-database-schema-extensions.md` §4).
- [ ] CSP/Referrer/nosniff/`X-Robots-Tag`/`Permissions-Policy` (camera, mic, geolocation disabled) headers on `/m/*` and `/api/v1/public/*`.
- [ ] Rate limiting keyed on client IP from the trusted proxy header only (Caddy sets `X-Forwarded-For`; API trusts only the proxy network).
- [ ] Constant-shape errors; no stack traces; `request_id` included.
- [ ] Cache poisoning guard: cache key = token + lang + menu-set hash; `Vary: Accept-Language`; never cache responses for `Authorization`-bearing requests (n/a) or with `p=` preview param.
- [ ] Health/metrics endpoints not reachable via public path.

## 4. Upload pipeline security (see `05-menu-management.md`)
Reject at the first failed check; do not echo user filenames; temp files in a private dir with `0600`, deleted in `finally`; process with strict Pillow `MAX_IMAGE_PIXELS` (25M px) and 5 MB request size cap; Pillow `Image.MAX_IMAGE_PIXELS` set; no ICC/EXIF in output; output only WebP; content-type served by Caddy from extension map (`.webp`) with `X-Content-Type-Options: nosniff`; separate path prefix `/media/` with `Content-Security-Policy: default-src 'none'; sandbox`.

## 5. Edge-case catalogue (each has a test in `11-testing-and-acceptance-criteria.md`)
| ID | Scenario | Expected behaviour |
|---|---|---|
| E-01 | Two admins create "T07" simultaneously | One 201, one 409 `DUPLICATE_TABLE_CODE` |
| E-02 | Create table when venue has 500 | 422 `LIMIT_EXCEEDED` |
| E-03 | Archive table while customers are on its menu | Next refresh (≤ 60 s) → retired page; open page keeps working until reload |
| E-04 | Archive occupied table | 409 `TABLE_IN_USE` unless `force` + re-auth + reason |
| E-05 | Restore table whose label is taken | Must supply a new label |
| E-06 | Rename table to a label used by an archived table | Allowed |
| E-07 | Purge table with sessions | 409 `TABLE_HAS_HISTORY` |
| E-08 | Delete venue (Phase 1) | All QR → retired; menus soft-deleted with venue; media GC |
| E-09 | Regenerate QR twice quickly | Second call supersedes; at most one active; first becomes revoked immediately (grace not stacked beyond latest) |
| E-10 | Regenerate while token in grace | Old grace token stays until its grace_until or 0 if "end grace" |
| E-11 | Customer scans an old (grace-ended) code | 410 revoked page |
| E-12 | Customer scans code printed for another restaurant of the same install | Shows that restaurant's menu (by design); label mismatch is visible to staff |
| E-13 | Menu published without categories | 422 `MENU_NOT_PUBLISHABLE` |
| E-14 | Last published menu archived | `no_menu` page |
| E-15 | Two schedules overlap | Both shown as tabs in order |
| E-16 | Schedule overnight (22:00–02:00) | Active across midnight, evaluated in venue tz incl. DST-free zones; DST zones tested |
| E-17 | Price changed while another admin edits | 409 `VERSION_CONFLICT` |
| E-18 | Currency change with priced items | 409 `CURRENCY_LOCKED`; owner may override with re-auth |
| E-19 | Image upload fails mid-way | Item saved without image; media row `failed`; retry button |
| E-20 | Same image uploaded twice | Deduplicated by hash; second returns existing asset |
| E-21 | Delete image used by 5 items | 409 `MEDIA_IN_USE` unless detach |
| E-22 | Category deleted with items without strategy | 409 `CATEGORY_NOT_EMPTY` |
| E-23 | Item `unavailable_until` passes | Shows available automatically (read-time) |
| E-24 | Huge menu (1000 items) | Editor virtualised; public payload size guard → lazy mode if > 400 KB |
| E-25 | Public DB down | Stale cache ≤ 24 h with `X-Stale`; else 503 friendly page |
| E-26 | Valkey down | In-process LRU 30 s; rate limiting fails open for public GET |
| E-27 | Media volume full | Uploads 422 `MEDIA_QUOTA_EXCEEDED`/503; public pages show placeholders |
| E-28 | `PUBLIC_APP_URL` misconfigured (http in prod) | API refuses to start in prod mode / QR endpoints return 503 `CONFIG_INVALID` |
| E-29 | Table moved to another venue | **Not supported** (create new; archive old) |
| E-30 | Merging/splitting tables (FR-C11) | Not affected; archived tables can't be merged |
| E-31 | Table with no camera in setup wizard | Wizard still requires cameras (unchanged) |
| E-32 | Vision worker loads layout containing archived/unmapped tables | Impossible by construction; test with null geometry fixtures |
| E-33 | Customer language not enabled | Default language |
| E-34 | Emoji/Devanagari/RTL text in names | Stored/rendered correctly; CSV round-trip preserved (UTF-8 BOM on export for Excel) |
| E-35 | Item with price 0 | Allowed with warning; displayed per OQ-P2-10 |
| E-36 | Duplicate SKU on import | Row error; no partial import unless `skip_invalid` |
| E-37 | Import commit after expiry | 410 `IMPORT_EXPIRED` |
| E-38 | Admin disabled by policy mid-session | Next write 403 `POLICY_DISABLED`; UI refreshes permissions via `/auth/me` revalidate on 403 |
| E-39 | Manager of venue A edits venue B | 404 |
| E-40 | Host attempts POST to menu endpoints | 403 |
| E-41 | Browser back after create | No duplicate (idempotency) |
| E-42 | Clock skew on `unavailable_until`/schedules | Server time only |
| E-43 | Token in URL contains `/` or padding | Not matching regex → 404 |
| E-44 | Org deletion (DSR) | Cascade; media files purged; tokens deleted → invalid |
| E-45 | Backup restore after QR regenerated | Tokens revert to backup state → documented in runbook: "after restore, regenerate affected QR codes if the backup predates a revocation" |
