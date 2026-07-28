---
name: seo-sitemap
description: Analyze existing XML sitemaps or generate new ones. Validates format, URL health, and structure against current limits. Use for "sitemap", "generate sitemap", "sitemap issues", or "XML sitemap" requests.
---

# Sitemap Analysis & Generation

## Mode 1: Analyze an existing sitemap

Run the bundled discovery/validation script first:

```bash
python3 "<skill-root>/scripts/sitemap_check.py" https://example.com
```
> If `python3` isn't on PATH, use `python` instead.

It checks every `Sitemap:` line in robots.txt (fetched through `<skill-root>/../../lib/url_guard.py`), falls back to the conventional paths if the declared one is stale or invalid, and reports URL-count/size-cap violations, non-HTTPS entries, duplicate `<loc>`s, and suspect `<lastmod>` values. Only treat an entry as working once it's actually been fetched successfully — a robots.txt reference alone isn't proof. Use its output as the factual base, then apply judgment below.

**Validation checks:**
- Valid XML; per-file limit is ≤50,000 URLs **and** ≤50MB uncompressed, whichever comes first
- URLs return 200 (not redirected, not 404, not noindexed)
- `<lastmod>` is a valid date and reflects a real content change (not a boilerplate/copyright-line edit) — warn if values look suspiciously uniform or newer than the page's actual content, since Google only trusts `<lastmod>` when it's consistently accurate
- `<priority>`/`<changefreq>` are ignored by Google — flag their presence as informational cleanup, not an error
- Sitemap is referenced in robots.txt
- Cross-check crawled pages against sitemap entries and flag gaps either direction

**Common issues, ranked:**

| Issue | Severity |
|---|---|
| Over the 50k-URL / 50MB cap in one file | Critical — split with a sitemap index |
| Non-200 URLs included | High |
| Noindexed URLs included | High |
| Redirected (non-final) URLs included | Medium |
| All `lastmod` values identical | Low |
| `priority`/`changefreq` present | Info only |

**Specialized sitemaps** have their own rules — validate per type and re-check current Google docs before citing a specific removal date:
- **Image**: only `<image:image>`/`<image:loc>` remain valid (max 1,000 images per `<url>`); caption/geo/title/license sub-tags are deprecated.
- **Video**: requires `<video:video>` with thumbnail, title, description, and either a content or player location.
- **News**: cap is 1,000 `<news:news>` entries per file (not 50k), and only articles from roughly the last 2 days belong in it — apply this cap instead of the generic one whenever a `news:` namespace is present.

## Mode 2: Generate a new sitemap

1. Confirm business type (auto-detect from the site if possible).
2. Plan the structure with the user before generating anything.
3. Apply quality gates: **warn** at 30+ near-identical location/programmatic pages (require 60%+ unique content per page); **hard stop** at 50+ such pages unless the user explicitly justifies it.
4. Generate valid XML, splitting at the 50k-URL/50MB limit with a sitemap index if needed.
5. Document the resulting structure.

Safe to scale: integration pages with real setup docs, template/tool pages with real downloadable content, glossary entries with substantive (200+ word) definitions, product pages with unique specs/reviews, genuine user-generated profile pages.

Risky at scale (thin/duplicate-content and spam risk): city-name-swapped location pages with no real local content, "best X for Y" pages with no category-specific value, "X alternative" pages without an actual comparison, and AI-generated pages shipped without human review or unique value.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page</loc>
    <lastmod>2026-01-01</lastmod>
  </url>
</urlset>
```

For a sitemap index (used once a single file would exceed the limit), each `<sitemap>` entry just points to one of the split files with its own `<lastmod>`.

## Output

**Analysis**: `VALIDATION-REPORT.md` with the issues table above and page-specific recommendations.
**Generation**: `sitemap.xml` (or split files + index), `STRUCTURE.md` describing the architecture, and a URL-count summary.

## Error handling

| Scenario | Action |
|---|---|
| URL unreachable | Report the status code, suggest checking the site is live. |
| No sitemap found | Only report "not found" after checking robots.txt declarations and the conventional path. |
| Invalid XML | Report the specific parse error with line number. |
| Rate limited | Back off, report partial results, note when to retry. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.

## Explicit workflow behavior

When explicitly invoked as `$seo-sitemap`, apply this entrypoint behavior:

If analyzing, discover and validate the sitemap per the skill's checks. If
generating, confirm business type and structure with the user before writing
XML, and apply the location-page quality gates.

## Output
See the seo-sitemap skill's Output section, then close with the seo
orchestrator's evidence-based footer.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
