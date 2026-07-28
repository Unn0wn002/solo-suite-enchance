---
name: seo-content
description: Content quality and E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) analysis with AI-citation readiness. Use for "content quality", "E-E-A-T", "thin content", "readability", or "content audit" requests.
---

# Content Quality & E-E-A-T

## Start with Google's own heuristic

Before scoring anything, answer Google's three questions from its helpful-content guidance for the page under review:

| Question | Look for |
|---|---|
| **Who** created it? | Visible byline, author bio, credentials — non-negotiable on YMYL topics. |
| **How** was it created? | Disclosed process, especially for AI-assisted content; first-hand evidence or original research where it matters. |
| **Why** does it exist? | To genuinely help the reader, not to chase search clicks — watch for word-count padding, content churned purely for freshness, or a niche entry with no real expertise behind it. |

Weak answers on all three put the page at risk under Google's core-ranking helpfulness signals (the standalone Helpful Content System was folded into core ranking in the March 2024 update — same principles, continuous enforcement now rather than separate updates).

## E-E-A-T scoring

- **Experience** — original research, case studies, before/after results, first-hand photos/video, proprietary data.
- **Expertise** — author credentials and relevant background, technical depth matched to the audience, sourced claims.
- **Authoritativeness** — external citations and backlinks from credible sources, recognition in the field, being cited by other experts.
- **Trustworthiness** — visible contact info, privacy/terms pages, real reviews, transparent dates and corrections, HTTPS.

Google states trust matters most but publishes no numeric weighting — score out of 100 with Trust weighted heaviest (suggested split: Trust 30 / Expertise 25 / Authoritativeness 25 / Experience 20) and say plainly in the report that this split is this skill's own model, not a Google-published formula. Don't default to an even 25/25/25/25 split — that contradicts Google's own stated priority.

## Content depth and readability

Treat word-count minimums as **topical-coverage floors, not targets** — Google has said word count is not a direct ranking factor, and a shorter page that fully answers the query beats a padded longer one. As a rough adequacy check: homepage ~500 words, service page ~800, blog post ~1,500, product page 300–400+, location page 500–600.

Flesch Reading Ease (~60–70 for a general audience) is a content-quality proxy, not a ranking signal Google uses directly — treat it the same way. Also check heading hierarchy (H1→H2→H3, scannable, logical), primary keyword placement without stuffing (natural density, present in title/H1/opening), internal linking density (roughly 3–5 relevant links per 1,000 words, descriptive anchors, no orphans), sourced external links, and content freshness (visible publish/update dates; flag anything 12+ months stale on fast-moving topics).

## AI-generated content

Google's raters evaluate low-quality, scaled, or copied content patterns — not AI authorship as such. AI-assisted content is fine when it demonstrates real E-E-A-T, adds unique value, and had human review; it's a problem when it's generic, repetitive across pages, unattributed, or factually shaky. Note in the report: third-party SEO tools (this one included) have no access to Google's internal ranking signals, so treat these scores as heuristics and point to Search Console as the first-party source of truth.

## AI citation readiness (GEO)

For visibility in AI Overviews/AI Mode, ChatGPT, Perplexity, and Copilot: write clear, quotable, self-contained statements (especially stats and facts), keep a strong heading hierarchy, answer likely questions directly near the top, use tables/lists for comparative data, cite sources, and mark up entities (Organization/Person schema) so brand and authors are unambiguous. Google's own guidance frames AEO/GEO as SEO applied to AI-search surfaces, not a separate discipline — the same fundamentals (quotability, attribution, topical authority, freshness) carry over. Cross-reference **seo-geo** for the fuller workflow. `FAQPage` no longer produces Google rich results (retired May 2026) — don't recommend it for that purpose; use `QAPage` for genuine user Q&A instead.

## Output

### Content Quality Score: XX/100

| E-E-A-T Factor | Score | Key signals |
|---|---|---|
| Experience | XX/20 | … |
| Expertise | XX/25 | … |
| Authoritativeness | XX/25 | … |
| Trustworthiness | XX/30 | … |

### AI Citation Readiness: XX/100

List issues found and concrete recommendations, each tied to a specific page/template.

## Connector mode (optional)

If a keyword-data connector (e.g. DataForSEO-style MCP) is available, use it for real search-volume, difficulty, and intent classification instead of qualitative estimates, and say so explicitly. Without one, keep recommendations qualitative and evidence-based rather than inventing numbers.

## Error handling

| Scenario | Action |
|---|---|
| URL unreachable | Report the error, don't guess content, ask the user to verify the URL. |
| Content behind a paywall/login wall | Analyze only what's publicly visible (meta tags, headers) and say so. |
| Very thin retrievable content | Report as-is; flag possible JS-rendering or gating rather than assuming the page is genuinely thin. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.

## Explicit workflow behavior

When explicitly invoked as `$seo-content`, apply this entrypoint behavior:

If no URL was provided, ask for it. Apply the Who/How/Why test, score
E-E-A-T, check content depth and readability as coverage floors (not
targets), and assess AI-citation readiness.

## Output
See the seo-content skill's Output section, then close with the seo
orchestrator's evidence-based footer.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
