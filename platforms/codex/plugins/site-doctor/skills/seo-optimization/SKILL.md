---
name: seo-optimization
description: Advanced technical and on-page SEO beyond a basic tag check — crawlability and indexation, structured data (JSON-LD/schema.org), Core Web Vitals impact on ranking, internal linking and site architecture, canonicalization, hreflang/i18n, XML sitemaps, robots directives, duplicate content, and AI-answer-engine visibility (GEO/AEO). Use whenever the user wants to improve search rankings, "get found on Google", fix indexation problems, add schema markup, do keyword-to-content mapping, or optimize for AI search (ChatGPT/Perplexity/Google AI). Deeper than the SEO section of website-audit.
---

# SEO Optimization

Rankings follow from three things search engines actually reward: they can **crawl** it, they can **understand** it, and users **have a good experience** with it. Organize every recommendation under one of those, and tie each to the specific page or template it applies to.

## Run the meta extractor first

```bash
python3 "<skill-root>/scripts/extract_meta.py" https://example.com --max-pages 25
```
> **Running helpers:** `<resolved-plugin-root>` is set by Codex to this plugin's installed root, so the command works from any working directory. If `python3` is not on PATH, use `python` (macOS/Linux/Windows) (Windows launcher) instead.

Stdlib-only crawl that pulls titles, descriptions, canonicals, H1s, robots directives, OG tags, and structured-data presence per page, and flags duplicates and gaps. Use its table as the factual base, then apply judgment below.

## 1. Crawlability & Indexation (fix these first — nothing else matters if pages can't be indexed)

- **robots.txt**: not blocking anything important; references the sitemap. A staging `Disallow: /` leaking to production is a catastrophe that hides the whole site — check explicitly.
- **Meta robots / X-Robots-Tag**: no accidental `noindex` on money pages. Grep templates and check the header on live pages.
- **Indexation reality**: compare `site:domain.com` count to the real page count. Huge gaps mean crawl/index problems; huge excess means thin/duplicate pages getting indexed.
- **Crawl budget waste**: infinite faceted-filter URLs, session IDs in URLs, calendar traps. Canonicalize or block them.
- **Status codes**: real 404s return 404 (not 200 soft-404s); redirects are 301 and chains are ≤1 hop; no important pages behind 5xx intermittently.
- **JS rendering**: if content is client-rendered, confirm the rendered HTML contains the content and links (view rendered source, not just view-source). SSR/SSG or prerendering for critical pages when Googlebot-rendered HTML is thin.

## 2. Understanding (help engines parse meaning)

- **Titles**: unique, < ~60 chars, primary term near the front, brand at the end. No two pages sharing a title (the extractor flags this).
- **Meta descriptions**: unique, ~150–160 chars, compelling (drives CTR even though it's not a ranking factor).
- **Heading hierarchy**: exactly one meaningful `<h1>`, logical `<h2>`/`<h3>` nesting that maps the content outline.
- **Structured data (JSON-LD)**: add schema.org types that fit — `Article`/`BlogPosting`, `Product` + `Offer` + `AggregateRating`, `Organization`, `BreadcrumbList`, `FAQPage`, `LocalBusiness`, `Event`. Validate against Google's Rich Results requirements (required vs recommended properties). This is often the highest-ROI technical SEO work because it unlocks rich results.
- **Canonicalization**: every page reachable via multiple URLs (trailing slash, params, http/https, www) declares one canonical; canonicals are self-referential on the primary URL and absolute.
- **Semantic HTML & content depth**: real content in real elements, descriptive anchor text (not "click here"), content that actually answers the query intent rather than keyword-stuffing.

## 3. Experience (Core Web Vitals are a ranking signal)

Search ranking is affected by LCP < 2.5s, INP < 200ms, CLS < 0.1, plus HTTPS and mobile-friendliness. Diagnose and fix the vitals themselves via the **performance-tuning** skill; here, confirm they're within thresholds on key templates and treat failures as SEO findings, not just perf findings. Mobile usability (tap target size, no horizontal scroll, readable font) is table stakes under mobile-first indexing.

## 4. Architecture & Internal Linking

- **Depth**: important pages reachable within ~3 clicks of the homepage. Orphan pages (no internal links in) rarely rank — the extractor's link map surfaces candidates.
- **Link equity flow**: link from high-authority pages to priority pages with descriptive anchors; hub/spoke or topic-cluster structure for content.
- **Breadcrumbs**: implemented and marked up with `BreadcrumbList`.
- **Sitemap.xml**: lists canonical, indexable URLs only (no noindex/redirect/404 entries), accurate `lastmod`, split if > 50k URLs, referenced in robots.txt and submitted in Search Console.

## 5. Internationalization (multi-language/region sites)

- **hreflang**: reciprocal tags on every language/region variant, correct ISO codes, includes an `x-default`. Errors here scatter the wrong pages into the wrong markets.
- Locale-specific URLs (subdirectory/subdomain/ccTLD) consistent; no auto-redirect that traps Googlebot in one locale.

## 6. AI Answer-Engine Visibility (GEO / AEO)

Increasingly, users get answers from ChatGPT, Perplexity, and Google AI Overviews rather than clicking. To be citable:
- Clear, self-contained, factual passages that directly answer likely questions (question-shaped H2s with concise answers underneath).
- Strong entity signals: consistent NAP/brand info, `Organization`/`Person` schema, authoritative external references.
- `FAQPage`/`HowTo` structured data where it fits; content that's easy to extract as a standalone answer.
- Don't block the AI crawlers in robots.txt unless that's a deliberate policy choice — decide intentionally.

## Keyword-to-content mapping (when the ask is content strategy)

Map target queries to a single canonical page each (avoid two pages competing for the same term — cannibalization). Group by intent (informational/commercial/transactional), match page type to intent, and flag gaps where there's demand but no page and overlaps where multiple pages fight for one query.

## Report format

Shared audit structure (Summary → Scorecard → Findings → Fix order). Bucket findings under Crawl / Understand / Experience so priorities are obvious, and for each give the exact page or template plus the concrete change (the tag, the schema block, the redirect). Hand vitals fixes to **performance-tuning** and any tag/redirect/sitemap edits to **website-fix**.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `$solo-next-step` and `$release-preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `$solo-start-session` restores project context at the start (reading `.solo/`), and `$solo-end-session` saves progress, blockers, decisions, and the next task at the end. `$solo-run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `$stack-intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `$stack-intake` first. For vendor-specific depth, the stack plugin adds `$stack-audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.

## Script safety (url_guard)

The bundled script(s) route every outbound request through `<skill-root>/../../lib/url_guard.py` (shipped at `plugins/site-doctor/lib/url_guard.py` in the source tree): HTTPS-first scheme policy (http only where auditing it is the point), refusal of loopback/private/link-local/CGNAT/reserved/multicast and cloud-metadata targets — every DNS answer and every redirect hop is re-validated — plus a hard response-size cap. A refused target prints `BLOCKED unsafe target: <reason>` instead of being fetched.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
