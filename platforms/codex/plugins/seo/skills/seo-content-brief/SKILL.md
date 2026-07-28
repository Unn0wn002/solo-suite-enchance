---
name: seo-content-brief
description: Generate a competitive SEO content brief — SERP competitor scoring, gap analysis, per-section word counts and keyword placement, page-type-specific outlines, meta tag rules, and E-E-A-T/information-gain requirements — for either a new page or an improve-existing-page rewrite. Use for "content brief", "write a brief", "content outline", "blog brief", "service page brief", "brief for", "writing brief", "content plan", or "outline for" requests.
---

# SEO Content Brief Generator

Produces a research-backed brief a writer can execute against to outrank the current top results — competitor scoring with gap analysis, a section-by-section outline with word counts, keyword placement rules, and a page-type template — rather than a generic "write about X" prompt.

## 1. Pick the mode

**Improve mode** (an existing page URL is given): fetch the page, note what's already strong and should be kept, identify what's missing/thin/outdated, and mark each outline section as keep-strengthen vs add-new. Don't recommend a full rewrite when targeted fixes will win.

**New page mode** (keyword/topic only): use the target site's homepage or sitemap purely for business context, and build the brief from the competitive gaps a new page can fill.

## 2. Fetch context

Fetch the target URL or homepage to understand the business, and fetch the sitemap to see existing pages/categories/services. This context drives the relevance rule below — skip it and the brief will recommend content the site can't actually deliver.

## 3. Analyze the SERP

Identify the top 5 ranking pages, then filter out non-competitors before scoring: general encyclopedias/reference sites (Wikipedia, health/dictionary references), social platforms, blogging/content platforms, search engines themselves, marketplaces and e-commerce aggregators, forums/Q&A sites, major news/media outlets, data/research aggregators, directories/review/comparison sites, job boards, SEO-tool blogs, AI chat platforms, and any `.gov`/`.edu` domain — plus URL paths like `/tag/`, `/author/`, `/login`, `/cart`, `/terms`, `/sitemap` even on an otherwise-valid competitor domain. If fewer than 3 real competitors remain after filtering, say so explicitly rather than padding the table.

Score each real competitor on Depth, Formatting, SEO, and UX (1-10 each), and classify gaps into three types: **topic gaps** (subtopics competitors skip entirely), **depth gaps** (covered but shallow), and **quality gaps** (outdated, no expert perspective, poor formatting). Prioritize gaps by `Impact × Competitive Advantage / Effort`.

## 4. Classify intent

Informational (learn), commercial (researching before buying), transactional (ready to act), or navigational (looking for a specific site) — and identify which SERP format Google is rewarding for this query: long-form guide, listicle, comparison table, landing page, FAQ, video, or local pack.

## 5. Build the brief

Start from the matching page-type template, then customize based on the actual competitor gaps and intent found in steps 3-4.

## Two rules that override everything else

**Website relevance.** Every heading, subtopic, keyword, and FAQ suggested must be something the target site can credibly deliver on based on what it actually offers — don't borrow a competitor's structure if it covers something this business doesn't do. Before each suggestion: "can this site actually deliver this content?" If no, cut it.

**Site structure coverage.** For a hub/overview/category/"types of" page, the outline must reference every relevant product category or sub-page that actually exists on the site (no inventing categories, no leaving real ones out), each as its own section with an internal-link suggestion — the page needs to function as a real hub. Non-hub pages (single service page, blog post) use the site structure for internal-link suggestions but don't need to force every category into the outline.

Also: never name the research methods, tools, or frameworks behind a suggestion in the output — it should read as plain professional advice to a business owner or writer, not SEO-academic jargon.

## Page-type templates

| Page type | Goal | Core sections |
|---|---|---|
| Service page | Convert to enquiry/booking | What it is, who needs it, how it works, pricing, outcomes, why this brand, FAQ, CTA |
| Blog post | Rank informational, funnel to service | Direct answer (snippet target), context, 3-5 H2 subtopics, common mistakes, FAQ, contextual CTA |
| Case study | Build trust with real outcomes | Outcome summary up top, client situation, challenge, approach, result with figures, takeaways, cross-sell CTA |
| Category/hub page | Rank broad term, funnel to sub-pages | Scope overview, one section per sub-page (every real sub-page, linked), who it's for, process, FAQ |
| Landing page | Single conversion action | Hero offer+CTA, problem, benefits, social proof, how it works, objection handling, final CTA |
| FAQ page | Capture PAA/snippet traffic | 8-15 questions grouped by subtopic, 40-60 words each, CTA after the last one |
| Location page | Rank `[service] + [city]` | Local relevance, service areas, why local matters, local team, local reviews, FAQ, local CTA |
| About page | Site-wide E-E-A-T support | Who we are, story, team bios with credentials, values, awards, media mentions, CTA |
| Homepage | Brand authority, funnel out | Hero, services overview, differentiators, social proof, service area, GEO-facing FAQ, CTA |

Match schema to page type (Service/LocalBusiness, Article, WebPage, Organization, etc. — see **seo-schema**). `FAQPage` schema has no confirmed Google rich-result or AI-citation benefit as of its May 2026 retirement from rich results; don't recommend adding it purely for SERP visibility even on FAQ-shaped pages.

## Keyword placement

Not a density quota — a placement checklist. The primary keyword **must** appear in: the title tag (near the front), the H1 (near the front), the URL slug, the meta description, the first paragraph/first 100 words, and at least one image alt text. It does **not** need to appear in every H2/H3 or every paragraph — forcing it there reads as stuffing. Spread it evenly through the piece rather than front-loading the intro. Use 5-8 closely related secondary terms distributed through body copy and subheadings, plus 10-15 broader semantic terms for concept coverage; synonyms improve readability and don't count toward density. For each outline section, specify which keyword belongs in the heading and whether the body needs the primary term or a natural variation.

## Meta tag rules

- **Title:** 50-60 characters, primary keyword near the front, brand name last, separated by the site's existing pipe/dash convention, leading with a number or outcome when possible.
- **Meta description:** 130-150 characters, active voice, states a USP beyond the title, ends with a call to action, no brand name (redundant with the title), no quotation marks (Google truncates at them).

## Information gain (non-negotiable)

State exactly what new value this page adds that no current top-5 page has — proprietary data, a real case study, an expert quote or first-hand experience, an original framework. "More detail" or "better formatting" is not information gain.

## E-E-A-T requirements

List the specific trust signals the page needs: author credentials/bio relevant to the topic, expert quotes or citations, dated cited studies/stats, a visible last-updated date — treat all of this as non-optional on YMYL topics (health, finance, legal, safety).

## Internal linking

3-5 specific opportunities with anchor text and target URL, drawn from the real sitemap — and state whether this page is a hub (links out to cluster pages) or a spoke (links up to a pillar page).

## Output format

```
## Content Brief: [Primary Keyword]

### Search Intent
[Intent type, rewarded SERP format, audience/knowledge level — 3-4 lines]

### Competitor Analysis
| # | URL | Key H2 Sections | Est. Words | Score | Main Gap |
|---|-----|-----------------|------------|-------|----------|

### Content Gaps and Opportunities
[topic / depth / quality gaps, with specifics]

### Winning Outline
**H1:** ... **URL Slug:** /... **Target Word Count:** ~X (competitor avg: ~X)
[Full H2/H3 outline: word count per section, format notes, snippet targets, per-section keyword guidance]

### Recommended Meta Tags
**Title** / **Meta Description**

### Unique Angle and Information Gain
[specific paragraph]

### E-E-A-T Requirements
[bullet list]

### Internal Linking Opportunities
[3-5 with anchor text + target URL]
```

**Outline-only mode:** if the user just wants an outline, drop the Competitor Analysis, Content Gaps, Information Gain, and E-E-A-T sections and output only the H1/slug/word-count header plus the full outline with a one-to-two-sentence writing note per section.

## Connector mode (optional)

If a DataForSEO-, Ahrefs-, or similar SERP/keyword connector is available, use it for real SERP composition, keyword volume, difficulty scoring, intent classification, and competitor content parsing instead of qualitative estimates — say so explicitly. Without one, fetch the target and competitor pages through `<skill-root>/../../lib/url_guard.py`-guarded requests, keep volume/difficulty qualitative, and say so.

## Error handling

| Scenario | Action |
|---|---|
| Target URL unreachable | Report the error; don't guess page content; ask the user to verify the URL. |
| No competitors left after filtering | Broaden to partial-match competitors; note the thin competitive landscape. |
| Sitemap not found | Proceed without site-structure context; note internal-linking suggestions may be incomplete. |
| Page type not specified | Auto-detect from keyword intent and SERP format; state the detected type. |
| Target word count not specified | Use the competitor average as baseline and note it. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.

## Explicit workflow behavior

When explicitly invoked as `$seo-content-brief`, apply this entrypoint behavior:

If no keyword, topic, or URL was provided, ask for it. Determine improve-mode
vs new-page mode, score the real competitors, and build the section-by-section
outline with keyword placement and meta tag guidance.

## Output
See the seo-content-brief skill's Output section, then close with the seo
orchestrator's evidence-based footer.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
