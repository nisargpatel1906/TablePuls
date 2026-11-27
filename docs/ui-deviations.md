# UI Deviations & Implementation Notes

This document logs deliberate implementation choices comparing the built Next.js App Router frontend (`frontend/src/`) against the static design renders in `UI/`.

1. **System Font Stack & Offline Air-Gapped Safety (`frontend/src/styles/tokens.css`, `app/layout.tsx`)**
   - Uses system `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", system-ui, sans-serif` instead of downloading runtime fonts from Google Fonts CDNs so air-gapped hospitality deployments render zero external network calls cleanly.
2. **2D Floor Canvas & Polygon Editor Dynamic Hydration (`components/FloorCanvas.tsx`, `components/PolygonEditorCanvas.tsx`)**
   - `react-konva` `<Stage>` and `<Layer>` are dynamically imported with `{ ssr: false }` to ensure clean Next.js 15 App Router production builds without native `canvas` bindings during SSR, paired with an accessible HTML `List` view toggle on `SCR-005` and numeric vertex coordinate inputs (`X`/`Y` `0.00–1.00`) on `SCR-013` for full keyboard accessibility.
3. **Zero Fabricated Placeholder Data**
   - All bracketed prototype numbers from `UI/SCR-*/*.png` (occupancy numbers, wait times, agreement %) are replaced strictly with live API queries or explicit empty/unmeasured indicators (`NOT YET MEASURED` on `SCR-016` and `SCR-011` until an evaluation report or review sample exists).
4. **Live Camera Feeds (`SCR-006`) & Anonymized Review Crops (`SCR-011`)**
   - Rather than exposing raw RTSP streams directly, `SCR-006` fetches signed short-lived MediaMTX WHEP tokens (`POST .../stream-token`) and server-side face-blurred JPEG previews (`POST .../test`), never leaking camera credentials to the browser.
5. **Dual Theme + High-Contrast Accessibility**
   - Implemented Light/Dark `.dark` switching and Reduce Transparency `.solid-mode` toggle inside `AppShell` + `tokens.css` per `UI/DESIGN-SYSTEM.md`.
   - Adjusted primary interactive button fill (`--tp-accent` / `--accent-primary`) from `#007AFF` (`4.01:1` contrast with white text, flagged by `@axe-core/playwright`) to `#0062CC` (`5.88:1` contrast) to strictly pass WCAG 2.1 AA `4.5:1` contrast on all primary buttons across all 16 screens.
6. **Phase 2 Self-Designed Screens (`SCR-017`–`SCR-022`, `UI/phase2/*.png`)**
   - Static reference PNGs did not exist prior to Stage N5–N8, so `SCR-017`–`SCR-022` were designed directly from `UI/DESIGN-SYSTEM.md`, `tokens.css`, and `AppShell` patterns and verified with Playwright screenshots (`UI/phase2/SCR-017..022-*.png`) and `@axe-core/playwright` (`0` critical/serious WCAG 2.1/2.2 AA violations across Light & Dark).
   - Added `[data-theme="dark"]` alongside `html.dark` in `tokens.css` + `@custom-variant dark` in `globals.css` (recomputing `--bg-canvas`, `--surface-solid`, `--text-primary`, `--text-secondary`, `--border-subtle`, `--accent-primary`) so the isolated customer menu (`SCR-022`) and `MenuPreviewModal` (`SCR-021`) switch cleanly between Light & Dark themes independently of the host shell.
   - Replaced semi-transparent status badges (`bg-emerald-500/20`, `bg-amber-600`, card-wide `opacity-70` dimming) on `SCR-018` / `SCR-022` with high-contrast solid/tinted semantic pills (`bg-emerald-800`, `bg-amber-800`, `bg-emerald-100/900`, `bg-red-100/900`) after live `@axe-core/playwright` flagged contrast ratios below `4.5:1`.
   - Rendered `SCR-021` (`MenuPreviewModal.tsx`) directly via isolated `<PublicDigitalMenu />` inside a `390×844` phone bezel frame instead of `<iframe>`, preserving strict `X-Frame-Options: DENY` and `Content-Security-Policy: frame-ancestors 'none'` clickjacking protection on all `/m/*` routes.
