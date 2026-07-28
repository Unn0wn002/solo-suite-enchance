---
name: seo-schema
description: Detect, validate, and generate Schema.org structured data (JSON-LD preferred). Use for "schema", "structured data", "rich results", "JSON-LD", or "markup" requests.
---

# Schema Markup Analysis & Generation

## Detect

Run the bundled extractor first:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/seo-schema/scripts/schema_check.py" https://example.com/page
```
> If `python3` isn't on PATH, use `python` instead.

It parses every JSON-LD block (including `@graph` members), reports detected `@type`s, flags missing `@context`/`@type`, relative URLs in `url`/`logo`/`image`, and a small deprecated/no-rich-result type list — treat that list as a snapshot and verify current status before citing a date in the report. It does not see Microdata (`itemscope`/`itemprop`) or RDFa (`typeof`/`property`); grep the raw HTML for those separately and recommend migrating to JSON-LD when found, since that's Google's stated preferred format.

## Validate

Check required properties per type against Google's currently-supported rich-result types; flag missing `@context`, invalid `@type`, wrong data types, obvious placeholder text, relative URLs (must be absolute), and invalid date formats. Structured data injected via JavaScript can face delayed processing — for time-sensitive markup (Product/Offer especially), it should ship in the initial server-rendered HTML, not be injected client-side.

## Schema status — check before recommending anything

Keep this current; verify against Google's own documentation before citing a specific date, since this changes over time.

- **Safe to recommend freely**: Organization, LocalBusiness, Product/Offer, ProductGroup, Service, Article/BlogPosting/NewsArticle, Review/AggregateRating, BreadcrumbList, WebSite/WebPage, Person, VideoObject/ImageObject, Event, JobPosting, Course, DiscussionForumPosting, and video/specialized types (BroadcastEvent, Clip, SeekToAction, SoftwareSourceCode).
- **No SERP rich-result benefit, but not harmful to keep**: `FAQPage` — Google retired FAQ rich results for all sites in mid-2026. Flag existing FAQPage markup as informational, not a defect, and don't recommend removing it or adding new FAQPage markup for a rich-result payoff. For genuine user Q&A, use `QAPage` instead.
- **Deprecated — never recommend**: `HowTo` (rich results removed 2023), and a handful of narrow types (course-info/salary/learning-video/claim-review/vehicle-listing/practice-problem/book-actions variants) that Google has progressively retired from rich results — verify current status before flagging any of these as still-active.
- **Niche but still valid**: `Dataset` (feeds Google Dataset Search, not a Search rich result — don't say it was killed), `QAPage`/`DiscussionForumPosting`/education Q&A types (still supported), and e-commerce adult-content flagging via `hasAdultConsideration` where applicable.

## Generate

Identify the page type from its actual content, pick the matching schema type(s), fill in every required property plus the high-value recommended ones, use only truthful/verifiable data (clearly-marked placeholders for anything the user must fill in), and validate the output before presenting it.

### Minimal templates to adapt

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "[Company Name]",
  "url": "[Website URL]",
  "logo": "[Logo URL]",
  "contactPoint": {"@type": "ContactPoint", "telephone": "[Phone]", "contactType": "customer service"},
  "sameAs": ["[Social Profile URLs]"]
}
```

```json
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "[Business Name]",
  "address": {"@type": "PostalAddress", "streetAddress": "[Street]", "addressLocality": "[City]", "addressRegion": "[State]", "postalCode": "[ZIP]", "addressCountry": "[Country]"},
  "telephone": "[Phone]",
  "openingHours": "[Mo-Fr 09:00-17:00]",
  "geo": {"@type": "GeoCoordinates", "latitude": "[Lat]", "longitude": "[Long]"}
}
```

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "[Title]",
  "author": {"@type": "Person", "name": "[Author]"},
  "datePublished": "[YYYY-MM-DD]",
  "dateModified": "[YYYY-MM-DD]",
  "image": "[Image URL]",
  "publisher": {"@type": "Organization", "name": "[Publisher]", "logo": {"@type": "ImageObject", "url": "[Logo URL]"}}
}
```

## Output

Write `SCHEMA-REPORT.md` (detection/validation results) and `generated-schema.json` (ready-to-use JSON-LD).

| Schema | Type | Status | Issues |
|---|---|---|---|
| … | … | pass/warn/fail | … |

Then list missing-schema opportunities, validation fixes needed, and the generated code.

## Error handling

| Scenario | Action |
|---|---|
| URL unreachable | Report the status code; suggest checking whether the page needs authentication. |
| No schema found | State that clearly; recommend types based on actual page-content analysis, not guesswork. |
| Invalid JSON-LD | Report the specific syntax error and provide corrected JSON-LD. |
| Deprecated type detected | Flag it, note its retirement, and recommend the current alternative or removal if none exists. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.
