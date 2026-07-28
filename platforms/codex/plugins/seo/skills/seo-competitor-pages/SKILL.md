---
name: seo-competitor-pages
description: Plan and generate SEO-optimized competitor comparison and alternatives pages — "X vs Y" layouts, "alternatives to X" pages, roundups, and feature-matrix comparison tables — with schema recommendations, keyword targeting, and conversion-focused layout guidance. Use for "comparison page", "vs page", "alternatives page", "competitor comparison", "X vs Y", "versus", "compare competitors", or "alternative to" requests.
---

# Competitor Comparison & Alternatives Pages

Builds comparison and alternatives pages that target competitive-intent keywords while staying accurate and defensible about what's claimed.

## Page types

- **"X vs Y"** — direct head-to-head, balanced feature-by-feature, a clear verdict with justification. Targets `[Product A] vs [Product B]`.
- **"Alternatives to X"** — a list of alternatives, each with a summary, pros/cons, and best-for use case. Targets `[Product] alternatives`, `best alternatives to [Product]`.
- **"Best [category] tools" roundup** — a curated, criteria-stated ranking. Targets `best [category] tools [year]`.
- **Comparison table page** — a feature matrix across multiple products, sortable/filterable if interactive. Targets `[category] comparison`.

## Feature matrix

```
| Feature          | Your Product | Competitor A | Competitor B |
|------------------|:------------:|:------------:|:------------:|
| Feature 1        | yes          | yes          | no           |
| Feature 2        | yes          | partial      | yes          |
| Pricing (from)   | $X/mo        | $Y/mo        | $Z/mo        |
| Free Tier        | yes          | no           | yes          |
```

Every feature claim must trace to a public source; every price needs an "as of [date]" note; review the table quarterly or whenever a competitor ships a major change; link to the source for each competitor data point where one exists.

## Schema recommendations

Adapt whichever type fits the page:

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "[Product Name]",
  "brand": {"@type": "Brand", "name": "[Brand Name]"},
  "aggregateRating": {"@type": "AggregateRating", "ratingValue": "[Rating]", "reviewCount": "[Count]", "bestRating": "5", "worstRating": "1"}
}
```

```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "[Software Name]",
  "applicationCategory": "[Category]",
  "offers": {"@type": "Offer", "price": "[Price]", "priceCurrency": "USD"}
}
```

```json
{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "name": "Best [Category] Tools [Year]",
  "itemListElement": [{"@type": "ListItem", "position": 1, "name": "[Product Name]", "url": "[Product URL]"}]
}
```

See **seo-schema** for validation and current rich-result status of each type before shipping.

## Keyword targeting

| Pattern | Example | Volume signal |
|---|---|---|
| `[A] vs [B]` | "Slack vs Teams" | High |
| `[A] alternative` | "Figma alternatives" | High |
| `[A] alternatives [year]` | "Notion alternatives 2026" | High |
| `best [category] tools` | "best project management tools" | High |
| `[A] vs [B] for [use case]` | "AWS vs Azure for startups" | Medium |
| `[A] review [year]` | "Monday.com review 2026" | Medium |
| `is [A] better than [B]` | "is Notion better than Confluence" | Medium |

Title formulas: X vs Y → `[A] vs [B]: [Key Differentiator] ([Year])`; alternatives → `[N] Best [A] Alternatives in [Year] (Free & Paid)`; roundup → `[N] Best [Category] Tools in [Year], Compared & Ranked`. Match the H1 to the title's intent, keep it under 70 characters, and work the primary keyword in naturally.

## Conversion layout

Place a brief comparison summary with a primary CTA above the fold, a "try [product] free" CTA right after the comparison table, and a final recommendation-plus-CTA at the bottom — but keep CTAs out of the competitor-description sections themselves, where they read as pushy and cost trust. Back the page with social proof relevant to the comparison criteria (testimonials, G2/Capterra/Trustpilot ratings with source links, "switched from [competitor]" case studies), a clear pricing table that highlights value rather than just lowest price and calls out hidden costs (setup fees, per-user pricing, overage charges), and trust signals: a visible "last updated" date, an author with relevant expertise, a stated comparison methodology, and a clear disclosure of which product is the site's own.

## Fairness guidelines

Every competitor claim must be verifiable from a public source — no defamatory or misleading statements. Cite sources (competitor site, review platform, documentation), refresh the page when a competitor ships something major, disclose the site's own product affiliation clearly, acknowledge real competitor strengths, date-stamp all pricing, and verify features directly where possible rather than taking marketing copy at face value.

## Internal linking

Link to the site's own product/service pages from the comparison. Cross-link related comparisons (an "A vs B" page linking to "A vs C"), link to feature-specific pages when a feature comes up, run a Home > Comparisons > [Page] breadcrumb, and close with a related-comparisons section and links to any case studies or testimonials referenced.

## Output

Produce a ready-to-implement page structure with the feature matrix, a content outline with per-section word-count targets (1,500 words minimum), primary/secondary/long-tail keyword strategy, the generated JSON-LD, and content-gap notes versus the existing competitor pages found during research.

## Connector mode (optional)

If a DataForSEO-style or similar SERP/keyword connector is available, use it for real search volume, difficulty, and current SERP composition on the target comparison keywords instead of estimating. Without one, fetch competitor pages through `<skill-root>/../../lib/url_guard.py`-guarded requests for the feature/pricing data, mark volume/difficulty estimates as qualitative, and say so.

## Error handling

| Scenario | Action |
|---|---|
| Competitor URL unreachable | Report which competitor URLs failed; proceed with available data and note the gap. |
| Insufficient competitor data (pricing, features unavailable) | Flag the missing data points; use "Not publicly available" in the table rather than guessing. |
| No real product/service overlap | Report that the products serve different markets; suggest a closer competitor or pivot to a category roundup. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.

## Explicit workflow behavior

When explicitly invoked as `$seo-competitor-pages`, apply this entrypoint behavior:

If no topic, product, or URL was provided, ask for it. Pick the right page
type (X vs Y, alternatives, roundup, comparison table), build the feature
matrix and schema, and apply the fairness/accuracy guidelines to every claim.

## Output
See the seo-competitor-pages skill's Output section, then close with the seo
orchestrator's evidence-based footer.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
