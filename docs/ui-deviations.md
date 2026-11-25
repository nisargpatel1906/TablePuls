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
