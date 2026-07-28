---
name: seo-technical
description: Technical SEO audit across crawlability, indexability, security headers, URL structure, mobile/page-experience, Core Web Vitals, structured-data presence, JS-rendering risk, and IndexNow support. Use for "technical SEO", "crawl issues", "robots.txt", "Core Web Vitals", "site speed", or "security headers" requests deeper than a single-page check.
---

# Technical SEO Audit

Nine categories, each scored pass/warn/fail with evidence, rolled into one Technical score.

## 1. Crawlability
Check robots.txt exists, is valid, and doesn't block anything important — a staging `Disallow: /` that leaked to production is the catastrophic case, check it explicitly. Confirm the XML sitemap is discoverable (referenced in robots.txt or at the conventional path) and not stale. Distinguish intentional noindex from accidental. Flag important pages more than ~3 clicks from the homepage, and flag JS-dependent critical content (view rendered source, not view-source).

**Googlebot's HTML fetch is capped near 2MB** (uncompressed) — bloated inline base64/CSS/JS or oversized nav can push structured data past that cap and out of the index; keep key content and JSON-LD early in the document. Crawl rate is auto-adjusted by Google based on server responsiveness; there's no manual crawl-rate dial, so influence it through sitemap accuracy and server speed instead.

**AI crawlers** are a distinct, now-standard robots.txt decision, separate from search crawling: OpenAI's `GPTBot` (training) and `ChatGPT-User` (live browsing), Anthropic's `ClaudeBot`, `PerplexityBot`, ByteDance's `Bytespider`, Google's `Google-Extended` (Gemini training only — does not affect Search or AI Overviews, which use plain `Googlebot`), and `CCBot` (Common Crawl, feeds many third-party models). Blocking a training crawler doesn't block that company's live-browsing agent, and vice versa — treat them as independent decisions. Note for the user that being cited by AI answer engines has real referral/brand value before recommending a blanket block; cross-reference **seo-geo** for the full picture. Some newer Google fetchers (agentic-browsing/Project Mariner-style, NotebookLM) are user-triggered and explicitly cannot be blocked via robots.txt — access control for those has to happen server-side.

## 2. Indexability
Canonical tags self-referencing and non-conflicting with noindex; near-duplicate and parameter-URL duplication; www vs non-www consistency; thin content below a reasonable word-count floor for its page type; correct pagination signals; correct hreflang on multi-region sites (see **seo-hreflang** for depth); index bloat from low-value pages eating crawl budget.

## 3. Security
HTTPS enforced end to end, valid cert, no mixed content. Security headers: CSP, HSTS (and preload-list inclusion for high-security sites), X-Frame-Options, X-Content-Type-Options, Referrer-Policy. Also flag **back-button hijacking** — pages that trap the Back button via `history.pushState`/`replaceState`, including scripts injected by third-party ad/library platforms — Google treats this as a spam-policy violation subject to manual action; treat any instance as Critical.

## 4. URL Structure
Descriptive, hyphenated, parameter-free URLs for content pages; a folder hierarchy that reflects real site architecture; redirects that are 301 and single-hop (no chains); flag URLs over ~100 characters; consistent trailing-slash handling.

## 5. Mobile & Page Experience
Responsive layout with a real viewport meta tag; touch targets ≥48×48px with adequate spacing; base font size ≥16px; no horizontal scroll. Google's primary crawler is the mobile (smartphone) Googlebot — a mobile-broken site can still get indexed, but the real cost is **content/parity loss**, so the highest-value mobile check is **mobile/desktop parity**: same primary content, same robots meta, same titles/descriptions, same structured data, nothing critical hidden behind lazy-load-on-interaction. Flag intrusive interstitials, standalone consent-redirect pages, and heavy ad density (small banners and standard consent/legal dialogs are fine). Keep key content visible on load rather than behind tabs/accordions, and don't hijack scroll position or break URL hash fragments. Page experience overall is a *guidance* signal, not a unified ranking system — only Core Web Vitals feeds ranking directly, and HTTPS is a light, confirmed signal — so don't over-weight header/interstitial findings relative to CWV and content quality.

## 6. Core Web Vitals
LCP ≤ 2.5s, **INP ≤ 200ms** (INP replaced FID as the responsiveness metric in field tools — never reference FID), CLS ≤ 0.1, evaluated at the 75th percentile of real-user data. Use CrUX/PageSpeed data when a Google connector is available (see **seo-google**); otherwise use lab data from an available Lighthouse-equivalent tool and say clearly that it's a lab estimate, not field data.

## 7. Structured Data
Detect JSON-LD (preferred), Microdata, or RDFa and validate against currently-supported Google types. Full analysis lives in **seo-schema** — this category just confirms presence and flags obviously broken markup.

## 8. JavaScript Rendering
Determine whether critical content and links exist in the initial HTML or require JS execution; identify CSR vs SSR/SSG. When JS is involved, check three specific failure modes that are easy to miss: (1) a canonical tag injected by JS that disagrees with the one in raw HTML — Google may use either, so they must match; (2) raw-HTML noindex that JS later removes — Google may still honor the original noindex, so serve the correct directive server-side from the start; (3) non-200 status codes never get JS-rendered by Google at all, so anything injected client-side on an error page is invisible. Time-sensitive structured data (Product markup especially) should ship in the initial server-rendered HTML rather than relying on JS injection.

## 9. IndexNow
Check whether the site pings IndexNow (Bing/Yandex/Naver honor it; Google does not) and recommend adopting it for faster non-Google indexing when it's missing.

## Agent-friendly pages (optional, informational)

AI agents increasingly navigate sites via the accessibility tree rather than pixels or raw DOM. If time allows, spot-check for real semantic elements (`<button>`/`<a>`, not `<div onclick>`), proper label associations, consistent interactive-target sizing, and layout stability. Report these as **opportunities**, never as failures that gate the audit — this is an emerging area, not an established ranking factor.

## Output

### Technical Score: XX/100

| Category | Status | Score |
|---|---|---|
| Crawlability | pass/warn/fail | XX/100 |
| Indexability | pass/warn/fail | XX/100 |
| Security | pass/warn/fail | XX/100 |
| URL Structure | pass/warn/fail | XX/100 |
| Mobile & Page Experience | pass/warn/fail | XX/100 |
| Core Web Vitals | pass/warn/fail | XX/100 |
| Structured Data | pass/warn/fail | XX/100 |
| JS Rendering | pass/warn/fail | XX/100 |
| IndexNow | pass/warn/fail | XX/100 |

Bucket findings Critical / High / Medium / Low per the seo orchestrator's priority bands.

## Connector mode (optional)

If a Google Search Console / PageSpeed / CrUX connector is available (see **seo-google**), use its field data for Core Web Vitals and indexation status instead of lab estimates, and say explicitly that the numbers are live field data. If a DataForSEO-style connector is available, its on-page/Lighthouse tools can substitute for a manual header/status-code check. Without either, run everything through `<skill-root>/../../lib/url_guard.py`-guarded stdlib fetches and say so.

## Error handling

| Scenario | Action |
|---|---|
| URL unreachable | Report the connection error and status code; suggest checking DNS and public accessibility. Don't guess at site content. |
| robots.txt missing | Note it explicitly, recommend adding one, continue the rest of the audit. |
| HTTPS not configured | Flag Critical; report whether HTTP is unredirected, mixed content exists, or the cert is missing/expired. |
| No CWV field data | Note CrUX has no data for this URL (common on low-traffic sites); fall back to lab data explicitly labeled as such. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.

## Explicit workflow behavior

When explicitly invoked as `$seo-technical`, apply this entrypoint behavior:

If no URL was provided, ask for it. Work through all nine categories and
produce the Technical Score table plus prioritized findings.

## Output
See the seo-technical skill's Output section for the score table, then close
with the seo orchestrator's evidence-based footer (Status/Evidence/Findings/
Risk/Fixes/Tasks/Verification/Next skill).

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
