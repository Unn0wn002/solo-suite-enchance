---
name: performance-tuning
description: Deep web performance optimization targeting Core Web Vitals (LCP, INP, CLS) and load time — render-blocking resources, JavaScript bundle size and code splitting, image and font optimization, caching and CDN strategy, critical rendering path, hydration cost, and server response time (TTFB). Use whenever the user says a site or page is slow, wants better Lighthouse/PageSpeed scores, needs to pass Core Web Vitals, mentions large bundles, slow load, jank, or layout shift. Deeper than the performance section of website-audit.
---

# Performance Tuning

Optimize what you measure, in the order the user actually feels it. The three Core Web Vitals map to three distinct problems — don't fix bundle size when the issue is a 3s server response. Always split the timeline first: **TTFB** (server) vs **render** (client) vs **interactivity** (main thread).

## Diagnose before tuning

1. Get a real measurement: Lighthouse/PageSpeed Insights for lab data, and field data (CrUX/Search Console) if available — lab and field can disagree, and Google ranks on field data.
2. Read the Network waterfall: what's the TTFB, what's render-blocking, what's the largest/slowest resource, how many requests before first paint.
3. Identify the LCP element specifically (usually the hero image or a large text block) — you optimize *that element's* delivery, not the page in general.

```bash
curl -s -o /dev/null -w "TTFB: %{time_starttransfer}s  Total: %{time_total}s  Size: %{size_download} bytes\n" URL
curl -sI URL | grep -iE "cache-control|content-encoding|cf-cache|age|vary"
```

## LCP — Largest Contentful Paint (target < 2.5s)

The LCP element should start loading as early as possible. In order of impact:
- **Slow TTFB** (server): if TTFB alone is > 0.8s, the fix is server-side — see the TTFB section; no amount of front-end work helps.
- **LCP image not prioritized**: add `fetchpriority="high"` to the hero image, `preload` it, and make sure it's **not** `loading="lazy"` (lazy-loading the LCP image is a common self-inflicted wound). Serve it in WebP/AVIF, correctly sized for the viewport (responsive `srcset`), from a CDN.
- **Render-blocking CSS/JS**: inline critical CSS, defer the rest; add `defer`/`async` to scripts; remove unused CSS. Every render-blocking resource in `<head>` delays LCP.
- **Web fonts blocking text**: `font-display: swap`, preload the primary font, subset it. Otherwise the LCP text waits for the font.

## INP — Interaction to Next Paint (target < 200ms)

Replaced FID in 2024; measures responsiveness to real interactions. Causes and fixes:
- **Long tasks blocking the main thread**: break work > 50ms into chunks, `yield` to the browser (scheduler.postTask / setTimeout / `await` in the right places), move heavy compute to a Web Worker.
- **Too much JavaScript executing**: this is usually a bundle problem — see the JS section. Less shipped JS = less parse/compile/execute = better INP.
- **Expensive event handlers / uncontrolled re-renders**: debounce/throttle input handlers; in React, memoize (`useMemo`/`useCallback`/`React.memo`), virtualize long lists, avoid re-rendering the whole tree on every keystroke.
- **Hydration cost** (SSR frameworks): large hydration blocks interactivity. Consider streaming SSR, partial/selective hydration, islands, or React Server Components to ship less client JS.

## CLS — Cumulative Layout Shift (target < 0.1)

Content jumping as the page loads. Fixes are mostly mechanical:
- Set explicit `width`/`height` (or `aspect-ratio`) on **all** images, videos, iframes, and ad slots so space is reserved.
- Reserve space for anything injected late (banners, embeds, cookie bars); don't insert content above existing content.
- Preload fonts and use `size-adjust`/`font-display: swap` to minimize reflow when the web font swaps in.
- Never animate layout properties (top/left/width/height); use `transform`/`opacity` which don't trigger layout.

## JavaScript bundle (the root cause behind most INP and slow loads)

- **Measure it**: run the bundler analyzer (`webpack-bundle-analyzer`, `vite-bundle-visualizer`, `source-map-explorer`). Find the biggest contributors.
- **Code split**: route-based splitting and dynamic `import()` for below-the-fold or interaction-triggered features. Ship the critical path only.
- **Tree-shake and trim dependencies**: replace heavyweight libs (moment → date-fns/day.js; lodash → per-method imports or native); drop unused polyfills; check for duplicate versions of the same package in the tree.
- **Modern output**: ship ES modules to modern browsers, differential loading; enable minification and compression (brotli).

## Images & media

Modern formats (AVIF/WebP with fallback), responsive `srcset`/`sizes`, correct dimensions (don't ship a 3000px image into a 400px slot), lazy-load below-the-fold (never the LCP image), and a CDN with image resizing. Video: poster images, `preload="none"` for non-critical, and don't autoplay heavy video on mobile.

## Caching & CDN

- Static assets: hashed filenames + `Cache-Control: public, max-age=31536000, immutable`.
- HTML: short/revalidate (`no-cache` or a small max-age), never long-cache HTML that references hashed bundles or users get stuck on stale versions.
- Serve from a CDN close to users; enable edge caching for cacheable responses; use `stale-while-revalidate` where it fits.
- Preconnect/dns-prefetch to critical third-party origins.

## TTFB / server response (target < 0.8s)

If the server is the bottleneck, front-end tuning can't save it:
- Slow database queries are the usual cause — hand off to **database-debug** (find the slow query) and **database-fix** (index it).
- Add server-side caching (page/fragment/object cache, Redis); avoid N+1 queries; move heavy work to background jobs.
- Consider SSG/ISR for pages that don't need per-request rendering; edge rendering for global audiences.

## Report format

Shared audit structure, but organized by **which vital each finding moves** (LCP / INP / CLS / TTFB), with the current measured value, the target, and the specific change with expected impact. Sequence fixes by impact-per-effort — usually LCP image priority and bundle splitting are the biggest early wins. Route front-end edits through **website-fix** and any server/DB causes through **database-fix**.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
