---
name: seo-plan
description: Strategic SEO planning for a new or existing site — discovery, competitor and keyword-gap analysis, information architecture and content-pillar design, a phased 12-month implementation roadmap, and industry-flavored guidance for SaaS, local-service, e-commerce, publisher, and agency businesses. Use for "SEO plan", "SEO strategy", "content strategy", "site architecture", or "SEO roadmap" requests.
---

# Strategic SEO Planning

Produces a phased SEO strategy for a new or existing site — discovery, competitive analysis, architecture, content strategy, technical foundation, and a 12-month roadmap — rather than a page-level audit.

## Discovery

Establish business type, target audience, top competitors, goals, budget/timeline constraints, and KPIs before designing anything. If a live site exists, assess it first; if not, proceed in new-site mode and skip anything that needs a live URL.

## Competitive analysis

Identify the top 5 competitors and assess their content strategy, schema usage, technical setup, apparent E-E-A-T signals, and estimated domain authority. Turn this into concrete keyword and content gaps, not a generic "they're doing X" summary.

## Architecture

Design the URL hierarchy and content pillars, plan internal linking, and lay out the sitemap structure, applying the same quality gates the **seo orchestrator** uses for large sitemaps (see **seo-sitemap**). Design for real user journeys, not just crawl efficiency.

## Content strategy

Map content gaps against competitors, estimate page counts by type, set a blog/resource publishing cadence, and build an E-E-A-T plan (author bios, credentials, demonstrated first-hand experience) alongside a prioritized content calendar.

## Technical foundation

Set hosting/performance requirements, a schema plan per page type (hand off to **seo-schema** for the actual markup), Core Web Vitals baseline targets, AI-search readiness requirements (hand off to **seo-geo**), and mobile-first constraints.

## Implementation roadmap

Four phases across roughly a year:

| Phase | Timeframe | Focus |
|---|---|---|
| 1. Foundation | Weeks 1-4 | Technical setup, core pages (home/about/contact/services), essential schema, analytics |
| 2. Expansion | Weeks 5-12 | Primary-page content, blog launch, internal linking, local SEO setup if applicable |
| 3. Scale | Weeks 13-24 | Advanced content, link building/outreach, GEO optimization, performance work |
| 4. Authority | Months 7-12 | Thought leadership, PR/media mentions, advanced schema, continuous optimization |

## Industry-flavored guidance

Tailor page types, content cadence, and technical priorities to the detected business type rather than one generic template:

- **SaaS**: feature/comparison/integration pages, docs, a pricing page built for both users and SEO, trial-funnel content.
- **Local service**: service-area pages per location (with the doorway-page guardrails in **seo-local**), GBP optimization, review-generation cadence.
- **E-commerce**: category/product page architecture, faceted-navigation indexation control, product schema (see **seo-ecommerce**).
- **Publisher**: topic clusters and pillar pages (see **seo-cluster**), author authority pages, editorial cadence.
- **Agency**: case-study depth, service pages per offering, portfolio/proof-of-work content.
- **Generic**: fall back here when the vertical doesn't cleanly match any of the above.

## Output

Produce `SEO-STRATEGY.md`, `COMPETITOR-ANALYSIS.md`, `CONTENT-CALENDAR.md`, `IMPLEMENTATION-ROADMAP.md`, and `SITE-STRUCTURE.md`, plus a KPI table:

| Metric | Baseline | 3mo | 6mo | 12mo |
|---|---|---|---|---|
| Organic traffic | ... | ... | ... | ... |
| Keyword rankings | ... | ... | ... | ... |
| Domain authority | ... | ... | ... | ... |
| Indexed pages | ... | ... | ... | ... |
| Core Web Vitals | ... | ... | ... | ... |

Each phase needs measurable goals, defined resource requirements, explicit dependencies, and named risks.

## Connector mode (optional)

If a DataForSEO-style connector is available, use it for real competitor-domain intersection and traffic estimation, keyword-volume/difficulty data, and local business-listing data instead of estimating these qualitatively — say so explicitly. Without one, build the competitive and keyword picture from manual site review and public SERP inspection, and clearly label the results as estimates.

## Error handling

| Scenario | Action |
|---|---|
| Unrecognized business type | Fall back to the generic template and tell the user no vertical-specific template matched. |
| No website URL provided | Proceed in new-site planning mode; skip current-site assessment and competitive gap analysis that need a live URL. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.
