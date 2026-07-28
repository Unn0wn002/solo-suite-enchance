---
name: seo-page
description: Deep single-page SEO analysis covering on-page elements, content quality basics, technical meta tags, schema presence, and image handling, scored into one page-level report. Use when the user says "analyze this page", "check page SEO", "single URL", "check this page", "page analysis", or hands over one URL for review — the fast single-page counterpart to the full-site seo-technical/seo-content audits.
---

# Single Page Analysis

A focused, single-URL pass. For a full-site or multi-category audit use the **seo** orchestrator and its sub-skills directly; this skill is the quick one-page version that still checks every major surface.

## On-page SEO

Title tag: 50-60 characters, unique, includes the primary keyword. Meta description: 150-160 characters, compelling, keyword-inclusive. Exactly one H1 matching page intent. H2-H6 in logical hierarchy with no skipped levels. URL short, descriptive, hyphenated, parameter-free. Internal links sufficient and relevantly anchored, no orphaned pages. External links to authoritative sources in reasonable number.

## Content quality (quick check)

Word count against the page type's rough floor, Flesch Reading Ease/grade level as a readability proxy, natural keyword density (1-3%) with semantic variation present, basic E-E-A-T signals (author bio, credentials, first-hand-experience markers), and visible publish/updated dates. For the full E-E-A-T scoring model and AI-citation-readiness pass, use **seo-content** — this check is a lighter pass meant to flag if something's clearly missing.

## Technical elements

Canonical tag present and correct (self-referencing or intentionally pointing elsewhere). Meta robots set to index/follow unless deliberately blocked. Open Graph (`og:title`, `og:description`, `og:image`, `og:url`) and Twitter Card (`twitter:card`, `twitter:title`, `twitter:description`) tags present. Hreflang correct if the page is part of a multi-language set (see **seo-hreflang** for depth).

## Schema markup

Detect all types present (JSON-LD preferred), validate required properties, and flag missing opportunities. Never recommend `HowTo` (rich results removed) or `FAQPage` for a rich-result payoff (retired from Google rich results May 2026 — existing FAQPage markup doesn't need removal, it's just no longer a ranking lever); use `QAPage` for genuine user Q&A instead. Full detection/validation/generation logic lives in **seo-schema** — this check just confirms presence and flags anything obviously broken.

## Images

Alt text present, descriptive, keyword-inclusive where natural. File size: flag >200KB as a warning, >500KB as critical. Format: recommend WebP/AVIF over JPEG/PNG. Width/height set to prevent layout shift. For lazy loading, report the actual mechanism per image (native `loading="lazy"`, or a JS lazy-loader like Perfmatters/EWWW/lazysizes) rather than flagging "not lazy-loaded" — JS lazy-loaders intentionally strip the native attribute and use `data-src` placeholders, so their presence is correct behavior, not a defect.

## Core Web Vitals (reference only — not measurable from static HTML)

Flag likely LCP risk (oversized hero images, render-blocking resources), likely INP risk (heavy JS, missing async/defer), and likely CLS risk (missing image dimensions, content injected after load). Treat these as directional flags, not measured scores — see Connector mode below for real field data.

## Output

### Page Score: XX/100

| Category | Status | Score |
|---|---|---|
| On-Page SEO | pass/warn/fail | XX/100 |
| Content Quality | pass/warn/fail | XX/100 |
| Technical | pass/warn/fail | XX/100 |
| Schema | pass/warn/fail | XX/100 |
| Images | pass/warn/fail | XX/100 |

Issues bucketed Critical → High → Medium → Low, each with a specific, actionable fix and its expected impact, plus ready-to-use JSON-LD for any detected schema opportunity.

## Connector mode (optional)

If a Google Search Console/PageSpeed/CrUX connector is available (see **seo-google**), use its live field data for real SERP position, indexation status, and Core Web Vitals instead of the directional HTML-only flags above, and say explicitly that the numbers are live. If a DataForSEO-style connector is available, use it for backlink/spam-score context. Without either, run everything through `${CLAUDE_PLUGIN_ROOT}/lib/url_guard.py`-guarded requests against the page itself and say the CWV flags are estimates, not field data.

## Error handling

| Scenario | Action |
|---|---|
| URL unreachable (DNS failure, connection refused) | Report the error clearly; don't guess page content; suggest verifying the URL. |
| Page requires authentication (401/403) | Report it's behind auth; suggest the user provide rendered HTML directly or a public URL. |
| JavaScript-rendered content (empty body in raw HTML) | Note key content may be client-side rendered; analyze what's available and flag results may be incomplete; suggest a browser-rendered snapshot if one's available. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.
