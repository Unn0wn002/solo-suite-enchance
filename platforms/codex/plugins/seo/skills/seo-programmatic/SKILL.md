---
name: seo-programmatic
description: Plan and audit SEO pages generated at scale from structured data sources (CSV/JSON/API/database-driven templates). Covers data-source quality checks, template uniqueness, URL pattern rules, internal linking automation, thin-content quality gates, canonical strategy, sitemap integration, and index-bloat prevention. Use for "programmatic SEO", "pages at scale", "dynamic pages", "template pages", "generated pages", or "data-driven SEO" requests.
---

# Programmatic SEO Analysis & Planning

Audits and plans SEO pages generated at scale from a data source, with the core goal of stopping thin-content and index-bloat penalties before they happen rather than after Google notices.

## Data source assessment

Whatever feeds the templates — CSV/JSON export, API, or database query — check three things: row/record count and whether each record has enough distinct attributes to produce genuinely different content; duplicate or near-duplicate records (flag >80% field overlap); and freshness, since stale source data quietly produces stale pages.

## Template quality

A template should make every generated page read as a standalone resource, not a "mad-libs" page that just swaps a city or product name into identical boilerplate. Split content into static blocks (shared, fine to repeat) and dynamic blocks (must add real information — a stat, a spec, a locally-relevant detail — not just a keyword variation). Use conditional logic to hide sections when the underlying data is missing rather than rendering an empty or placeholder-filled section.

## URL patterns

Common shapes: `/tools/[tool-name]`, `/[city]/[service]`, `/integrations/[platform]`, `/glossary/[term]`, `/templates/[template-name]`. Rules: lowercase hyphenated slugs derived from the data, a hierarchy that matches real site architecture, enforced uniqueness at generation time, no query parameters on primary content URLs, under ~100 characters, and consistent trailing-slash usage matching the rest of the site.

## Internal linking automation

Use a hub/spoke model — category hub pages link down to individual generated pages. Auto-link 3-5 related pages per page based on shared data attributes (same category, same city, same feature), generate `BreadcrumbList` schema from the URL hierarchy, and cross-link pages that share attributes. Vary anchor text; avoid repeating the exact-match keyword. Target the same density as regular content: roughly 3-5 internal links per 1,000 words.

## Thin-content quality gates

| Metric | Threshold | Action |
|---|---|---|
| Pages published without content review | 100+ | Warning — require a content audit before publishing more |
| Pages published without justification | 500+ | Hard stop — require explicit user approval plus a thin-content audit |
| Unique content per page | <40% | Flag as thin (penalty risk) |
| Word count per page | <300 | Flag for review |

**Enforcement context.** Google's Scaled Content Abuse policy (introduced March 2024) saw a real enforcement escalation through 2025: a June 2025 wave of manual actions against sites running AI-generated content at scale, and community reporting through August 2025 of stronger SpamBrain detection for AI-generated link/content farms. Google has reported a 45% reduction in low-quality, unoriginal search results following the March 2024 enforcement. Practical implications for a programmatic rollout:

- Target ≥30-40% genuinely unique content between any two pages in the set — not just a swapped city or keyword string.
- Human-review a 5-10% sample of generated pages before publishing.
- Roll out in batches of 50-100 pages, watch indexing and rankings for 2-4 weeks, then expand. Never push 500+ programmatic pages live in one shot without an explicit quality review.
- Standalone-value test for every page: would this be worth publishing if no sibling pages existed?
- Treat third-party/hosted programmatic content as a site-reputation-abuse risk area (Google clarified this policy language 2024-11-19).

Given that enforcement trend, treat the <40% WARNING gate as a floor, not a target, and consider a hard stop at <30% unique content.

**Generally safe at scale:** integration pages with real setup docs and screenshots; template/tool pages with downloadable content and usage instructions; glossary pages with 200+ word definitions, examples, and related terms; product pages with unique specs/reviews/comparison data; data pages with unique per-record statistics or analysis.

**Penalty risk at scale:** location pages with only the city name swapped into identical text; "best [tool] for [industry]" pages with no industry-specific substance; "[competitor] alternative" pages with no real comparison data; AI-generated pages published without human review or added value; any page where >60% of the content is shared template boilerplate.

Uniqueness = (words unique to this page) / (total words on the page) × 100, measured against the rest of the programmatic set, excluding shared header/footer/nav but including template boilerplate text.

## Canonical strategy

Every programmatic page needs a self-referencing canonical. Sort/filter parameter variations canonical to the base URL when they're duplicate or low-value. Paginated series can self-canonical if content genuinely differs page-to-page, but keep the pages crawlable. If a programmatic page overlaps a manually-written page, the manual page is canonical.

## Sitemap and index-bloat control

Auto-generate sitemap entries for the set, split at 50,000 URLs or 50MB uncompressed (whichever comes first), use a sitemap index if multiple files are needed, and set `<lastmod>` from the actual data update time, not generation time. Exclude noindexed pages. Noindex anything that fails the quality gates above rather than leaving it live and hoping it doesn't get crawled. For sites with 10k+ programmatic pages, watch crawl stats in Search Console and run a monthly audit comparing indexed count to intended count; consolidate records with insufficient data into aggregate pages instead of publishing thin singles.

## Output

### Programmatic SEO Score: XX/100

| Category | Status | Score |
|---|---|---|
| Data Quality | pass/warn/fail | XX/100 |
| Template Uniqueness | pass/warn/fail | XX/100 |
| URL Structure | pass/warn/fail | XX/100 |
| Internal Linking | pass/warn/fail | XX/100 |
| Thin Content Risk | pass/warn/fail | XX/100 |
| Index Management | pass/warn/fail | XX/100 |

Bucket findings Critical / High / Medium / Low per the seo orchestrator's priority bands, then close with data-source, template, URL-pattern, and quality-gate recommendations.

## Connector mode (optional)

If a Google Search Console connector is available (see **seo-google**), compare indexed-page counts for the programmatic URL pattern against the intended count instead of estimating from a manual sample. Without one, sample the generated set manually — fetch a handful of pages through `<skill-root>/../../lib/url_guard.py`-guarded requests — and say the uniqueness/quality figures are estimates from that sample, not a full-set measurement.

## Error handling

| Scenario | Action |
|---|---|
| URL unreachable | Report the connection error and status code; suggest verifying accessibility and auth requirements. |
| No programmatic pattern detected | State that no template-generated or data-driven page pattern was found; check for client-side rendering or confirm the URL points to the right section. |
| Thin-content threshold exceeded | Trigger the quality-gate warning, report the unique-content percentage, and require acknowledgment before proceeding. |
| Hard-stop threshold hit (500+ unjustified pages or <30% unique) | Halt analysis, present findings, and require explicit user approval to continue. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.

## Explicit workflow behavior

When explicitly invoked as `$seo-programmatic`, apply this entrypoint behavior:

If no URL was provided, ask for it (or a description of the planned template
and data source). Check data-source quality, template uniqueness, URL
patterns, internal linking, and the thin-content quality gates before
producing a score.

## Output
See the seo-programmatic skill's Output section, then close with the seo
orchestrator's evidence-based footer.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
