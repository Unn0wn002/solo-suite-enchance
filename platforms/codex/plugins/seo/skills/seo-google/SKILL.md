---
name: seo-google
description: Connector-mode-only access to Google's own SEO field data — Search Console (Search Analytics, URL Inspection, Sitemap status), PageSpeed Insights/CrUX Core Web Vitals field data, Indexing API, and GA4 organic traffic — for indexation truth, real Chrome user metrics, and search performance that no crawl-based check can produce. Use when the user says "search console", "GSC", "PageSpeed", "CrUX", "field data", "indexing API", "GA4 organic", "URL inspection", or "real CWV data", and only produces output when a Google Search Console/Analytics/PageSpeed connector or MCP tool is already available and authenticated in the environment.
---

# Google SEO APIs (Connector Mode Only)

This skill has no manual fallback and bundles no OAuth client, credential store, or setup flow of its own. It exists purely to consume Google's own field data through whatever Search Console / Google Analytics / PageSpeed connector or MCP tool is already configured and authenticated in the environment.

**Before doing anything else: check whether such a connector is actually available and authenticated.** If it is, use it and say so explicitly, citing which surface (GSC, PSI/CrUX, GA4, Indexing API) the data came from. If it is not, say plainly that no Google connector is available, do not attempt any credential setup or ask the user to paste API keys or tokens here, and redirect to **seo-technical**'s Core Web Vitals section, which runs on lab-data estimates instead of field data — that's the correct fallback path, not a degraded version of this skill.

## What this covers when a connector is present

**Core Web Vitals field data (PageSpeed/CrUX).** Real 28-day Chrome User Experience Report field data at the 75th percentile, distinct from a one-off Lighthouse lab run — report both if the connector returns both, and label which is which. CrUX tries URL-level data first and falls back to origin-level when a specific URL doesn't have enough traffic; a CrUX miss (404-equivalent) means insufficient Chrome traffic for that URL, not an auth failure. History views (trailing ~25 weeks) show whether a metric is improving, stable, or degrading rather than just a snapshot.

**Search Console.** Search Analytics gives clicks, impressions, CTR, and position — useful for quick-win detection (queries sitting at position 4-10 with real impressions are the highest-leverage target). Treat the query-level rows and the dimensionless site-wide total as two different numbers; low-volume query rows can be anonymized out of the query-level view even though they count in the total. URL Inspection returns the actual Google-side verdict for a URL: coverage state, indexing state, canonical selection, mobile usability, and rich-result eligibility — this is the authoritative source for "is this URL actually indexed," not the sitemap submission report. Sitemap status from GSC shows submitted/error/warning counts only; URL Inspection is still the indexation truth for any specific URL.

**Indexing API.** Google restricts this API to JobPosting and BroadcastEvent/VideoObject pages — say so plainly whenever this comes up, since it's a common point of confusion. Daily quota is 200 publish requests.

**GA4 organic traffic.** Daily sessions, users, pageviews, bounce/engagement rate filtered to the Organic Search channel group, plus a top-organic-landing-pages view.

## Facts worth carrying into every report

- INP replaced FID as the responsiveness metric in field tools on March 12, 2024 — never reference FID.
- CrUX CLS values are string-encoded (e.g., `"0.05"`); don't misread the type.
- `round_trip_time` replaced `effectiveConnectionType` in CrUX as of February 2025.
- Search Analytics data carries a 2-3 day lag; don't expect same-day numbers.
- A GSC logging error made impressions, CTR, and average position unreliable for the window 2025-05-13 through 2026-04-27 (clicks were unaffected, and the fix was forward-only with no backfill). Flag any trend spanning that window with that caveat, and expect an apparent impressions drop right after the fix date that isn't a real traffic change.
- GSC's dedicated Generative AI performance report (launched 2026-06-03) covers AI Overviews + AI Mode visibility specifically — impressions only, no clicks/CTR/position, dimensioned by Page/Country/Device/Date in Pacific Time, 1,000-row cap, newest data preliminary. Separately, AI Mode traffic already rolls into the standard Performance report's Web totals, so clicks and impressions from AI Mode are already counted there — you cannot cleanly split "classic" vs "AI" traffic from the standard totals alone; use the Generative AI report for that split.
- GA4 added a native "AI Assistants" Default Channel Group (live ~2026-05-13): sessions referred by a recognized AI assistant (ChatGPT, Gemini, Claude, Deepseek, Copilot, Grok) get `medium=ai-assistant`. It excludes Google AI Overviews/AI Mode by design, likely misses Perplexity unless verified separately, and most AI-referred sessions still arrive without a referrer and land in Direct — so treat this channel as an undercount of real AI-driven traffic, not a complete picture.

## Rate limits (for setting expectations on how much to pull per call)

| API | Per-minute | Per-day |
|---|---|---|
| PageSpeed Insights v5 | 240 | 25,000 |
| CrUX + History (shared) | 150 | Unlimited |
| GSC Search Analytics | 1,200/site | 30M |
| GSC URL Inspection | 600 | 2,000/site |
| Indexing API | 380 | 200 publish/day |
| GA4 Data API | 10 concurrent | ~25K tokens/day |

## Output

Traffic-light each Core Web Vitals metric (Good / Needs Improvement / Poor), present performance data in a sortable table, and always state the data-freshness window and which connector/surface it came from. Close with the standard evidence-based footer from the **seo** orchestrator.

## Cross-skill integration

- **seo-technical** uses this skill's CWV field data when available, and its own lab-data fallback when not.
- **seo-content** and **seo-content-brief** can use GSC query data to inform keyword targeting when this connector is present.
- **seo-sitemap** defers to this skill's URL Inspection data for indexation truth over its own submitted-count check.
- **seo-geo** should reference the Generative AI performance report and the AI Mode/AI Overviews inclusion caveats above when assessing AI-search visibility.

## Error handling

| Scenario | Action |
|---|---|
| No Google connector configured or authenticated | State that plainly. Do not attempt setup, and do not request credentials in chat. Point to **seo-technical**'s lab-data Core Web Vitals section as the correct fallback. |
| Connector present but lacks GSC property access | Report the access error and that the service account/connector identity needs to be added as a GSC user for that property — without walking through credential setup yourself. |
| CrUX data unavailable for a URL | Report insufficient Chrome traffic for that URL; suggest lab data (via **seo-technical**) as the fallback for that specific page. |
| GA4 property not resolvable | Report the error; don't guess at a property ID. |
| Indexing API quota exceeded | Report the 200/day limit; suggest prioritizing the most important URLs for the remaining quota. |
| Rate limit (429) from any surface | Report which surface hit the limit; don't silently retry in a loop. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.

## Explicit workflow behavior

When explicitly invoked as `$seo-google`, apply this entrypoint behavior:

This only produces output when a Google Search Console / Analytics /
PageSpeed connector or MCP tool is already available and authenticated in
this environment. If none is available, say so plainly and point to
`$seo-technical` for the lab-data Core Web Vitals fallback instead — do not
attempt credential setup here.

## Output
See the seo-google skill's Output section, then close with the seo
orchestrator's evidence-based footer.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
