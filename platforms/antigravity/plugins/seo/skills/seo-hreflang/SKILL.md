---
name: seo-hreflang
description: Hreflang and international SEO — validates self-referencing tags, bidirectional return-tag pairs, x-default, ISO 639-1/3166-1 language and region codes, canonical alignment, and protocol/cross-domain consistency; generates correct hreflang in HTML, HTTP header, or XML sitemap form; assesses cultural adaptation and content parity across language versions. Use for "hreflang", "i18n SEO", "international SEO", "multi-language", "multi-region", or "language tags" requests.
---

# Hreflang & International SEO

## Validation checks

**Self-reference** — every page needs an hreflang entry pointing at itself, matching its own canonical exactly. Missing this causes Google to disregard the entire hreflang set for that page, not just the missing entry.

**Return tags** — if A declares hreflang to B, B must declare hreflang back to A; check that the full set forms a complete mesh. A missing return tag invalidates the relationship for both pages, not just the incomplete direction.

**x-default** — recommended whenever a selector or fallback page exists; points at the fallback/selector or default-language version; only one per set; needs return tags from every other language version like any other entry.

**Language codes** — ISO 639-1 two-letter only (`en`, `fr`, `de`, `ja`). `eng` (ISO 639-2) and `jp` (wrong code for Japanese) are common errors. Script is handled by an optional ISO 15924 subtag — `zh-Hant`/`zh-Hans` — which can combine with a region (`zh-Hans-US` is valid); bare `zh` is valid but ambiguous when a script-specific page exists.

**Region codes** — ISO 3166-1 Alpha-2, lowercase language + uppercase region (`en-US`, `pt-BR`). A region code can never stand alone without a language prefix — Google's own cautionary example is `be`, which reads as the Belarusian *language* code, not Belgium. `en-uk` (not a valid region — it's `en-GB`), `EU`/`UN` as a region, and `es-LA` (Latin America isn't a country) are common errors.

**Canonical alignment** — hreflang only counts on canonical URLs; if a page's canonical points elsewhere, its hreflang tags are ignored; the hreflang URL and canonical URL must match exactly, including trailing slash.

**Protocol consistency** — every URL in a set uses the same protocol; after an HTTPS migration, hreflang tags need updating too, not just the canonical.

**Cross-domain** — hreflang works across separate domains (example.com / example.de) as long as return tags exist on both; sitemap-based implementation is the practical choice at that scale.

**Geo-targeting signal hierarchy** (a heuristic, not a confirmed Google ranking order): ccTLD > hreflang > server location/IP > address/language/currency/Business Profile signals. hreflang is a hint, not a directive — Google ignores geotargeting meta tags and HTML attributes entirely. Search Console's International Targeting report and manual country-targeting setting were also removed in 2022; hreflang is the only lever left.

| Issue | Severity |
|---|---|
| Missing self-reference | Critical |
| Missing return tag | Critical |
| Invalid language code | High |
| Invalid region code | High |
| Hreflang on non-canonical URL | High |
| Missing x-default where a fallback exists | Medium |
| HTTP/HTTPS mismatch within a set | Medium |
| Trailing-slash inconsistency | Medium |
| Hreflang duplicated in both HTML and sitemap | Low |
| Language without region where geo-targeting is intended | Low |

## Implementation methods

| Method | Best for | Trade-off |
|---|---|---|
| HTML `<link>` tags | <50 variants per page | Visible in source, bloats `<head>` at scale |
| HTTP headers | Non-HTML files (PDFs) | Works where there's no `<head>`, but invisible and config-heavy |
| XML sitemap | Large or cross-domain sites | Scalable and centralized, but not visible on the page itself |

```html
<link rel="alternate" hreflang="en-US" href="https://example.com/page" />
<link rel="alternate" hreflang="fr" href="https://example.com/fr/page" />
<link rel="alternate" hreflang="x-default" href="https://example.com/page" />
```

Sitemap form needs the `xmlns:xhtml` namespace, and every `<url>` entry — including each alternate's own entry — must list the complete alternate set, itself included:

```xml
<url>
  <loc>https://example.com/page</loc>
  <xhtml:link rel="alternate" hreflang="en-US" href="https://example.com/page" />
  <xhtml:link rel="alternate" hreflang="fr" href="https://example.com/fr/page" />
  <xhtml:link rel="alternate" hreflang="x-default" href="https://example.com/page" />
</url>
```

Split sitemap files at whichever limit comes first: 50,000 URLs or 50MB uncompressed.

## Generation workflow
Detect language signals (URL path, subdomain, TLD, `lang` attribute) → map equivalent pages across languages → validate every code against ISO 639-1/3166-1 → generate tags including self-reference → verify the mesh is fully bidirectional → set x-default → output in whichever method fits the site's scale.

## Cultural adaptation
Beyond technical correctness, check whether translated pages are actually adapted for their market: CTA style (direct vs. indirect, per-culture expectations), locale-appropriate trust signals (certifications, legal pages), no stray references to the wrong country's brands, and consistent number/date/currency formatting for that locale. Score each language version 0-100 with specific findings; treat cultural-adaptation gaps as Medium severity, distinct from the hreflang-correctness findings above.

## Content parity
Across language versions, check: does every page exist in every declared language, does section structure roughly match (H2/H3 counts), do SEO elements (title/meta/schema) exist in localized form, is the word-count ratio sane for the language pair (German commonly runs 25-35% longer than English for the same content, Japanese 10-25% shorter), and are any translations visibly stale relative to their source (via last-modified timestamps). Flag foreign-brand references or untranslated fragments as parity defects, not just missing pages.

## Locale formatting
Check number format (`1.000,00` not `1,000.00` on `de-DE`), date format, currency symbol and placement, and phone numbers in international format with the correct country code, against the target locale's actual convention.

## Output

### Summary
Pages scanned, language variants detected, issues found by severity.

### Validation results
| Language | URL | Self-Ref | Return Tags | x-default | Status |
|---|---|---|---|---|---|

### Generated tags
HTML/header/sitemap form, whichever method applies.

### Recommendations
Missing implementations, codes to fix, and any method-migration suggestion (e.g. HTML → sitemap once the site outgrows manual maintenance).

## Error handling

| Scenario | Action |
|---|---|
| URL unreachable | Report the error; don't guess at site structure. |
| No hreflang tags found | Report the absence; check for other i18n signals (subdirectories, subdomains, ccTLDs) and recommend a method. |
| Invalid codes detected | List each with its correct replacement and a ready-to-use corrected tag set. |
| No cultural profile available for a language | Use general adaptation heuristics and say the assessment isn't backed by a pre-built profile. |
| Content-parity source is empty | Report that nothing was found; confirm the directory/URL is correct. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.
