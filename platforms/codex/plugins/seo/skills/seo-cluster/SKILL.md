---
name: seo-cluster
description: SERP-overlap-based topic clustering for content architecture — expands a seed keyword into variants, groups them by actual shared Google top-10 results (not text similarity), classifies intent, designs a hub-and-spoke content structure with an internal link matrix, and produces an interactive cluster map. Use for "topic cluster", "content cluster", "pillar page", "hub and spoke", "content architecture", "keyword grouping", or "cluster plan" requests.
---

# Semantic Topic Clustering

Clusters keywords by what Google's own top-10 results say they're about, not by string similarity — "dog training tips" and "dog training classes" can be near-identical text and still deserve separate pages if their SERPs barely overlap.

## Step 1: Keyword expansion
Expand the seed keyword to 30-50 variants using WebSearch: related searches, "People Also Ask" questions, common modifiers (best, how to, vs, for beginners, tools, examples, guide, checklist), who/what/when/where/why/how variants, and commercial modifiers (pricing, review, alternative, comparison, free, top). Normalize (lowercase, strip articles) and dedupe. If expansion yields fewer than ~15 variants, run a second pass seeded from the PAA questions themselves.

## Step 2: SERP overlap clustering
For each keyword, capture the top 10 organic results only (exclude ads, featured snippets, PAA, knowledge panels), normalized (strip protocol/trailing slash/most query params). For each candidate pair, count shared URLs and apply:

| Shared results (of 10) | Relationship | Action |
|---|---|---|
| 7-10 | Same post | Merge into one target page, keep the higher-volume keyword as primary |
| 4-6 | Same cluster | Group under one spoke cluster (separate posts unless volumes are close) |
| 2-3 | Interlink | Adjacent clusters, cross-link them |
| 0-1 | Separate | Different cluster or exclude |

Full pairwise comparison is O(n²) — for 40 keywords that's 780 SERP fetches. Cut the cost: pre-group by intent guess first (comparisons only run within a group), assume same-cluster for long-tail variants of the same head term sharing intent without checking, and spot-check roughly 20% of skipped pairs to validate the assumption. Cache every SERP fetch within a session and reuse it across comparisons involving that keyword. For scores landing in the ambiguous 3-4 zone, break the tie using domain overlap, intent alignment, and volume ratio (a keyword with 10x the volume of its pair usually earns its own post) — when still unclear, default to same cluster.

Treat ubiquitous domains (Wikipedia, Reddit, and similar) with caution — they show up across unrelated SERPs and can inflate overlap scores if not filtered or down-weighted.

## Step 3: Intent classification
| Intent | Signal words | Include? |
|---|---|---|
| Informational | how, what, why, guide, tutorial, learn | Yes |
| Commercial | best, top, review, comparison, vs, alternative | Yes |
| Transactional | buy, price, discount, coupon, sign up | Yes |
| Navigational | brand names, specific product/login pages | No — exclude |

Mixed-intent keywords ("best CRM software") classify by dominant intent; flag genuinely ambiguous ones for manual review.

## Step 4: Hub-and-spoke architecture
Pick the pillar keyword (highest volume, broadest intent, most SERP overlap with the rest of the set). Group the remainder into 2-5 subtopic clusters of 2-4 spoke posts each (5-21 total posts including the pillar).

| | Pillar | Spoke |
|---|---|---|
| Word count | 2,500-4,000 | 1,200-1,800 |
| Coverage | Broad overview of every subtopic | Deep dive into one subtopic, more detail than the pillar gives it |
| Must link to | Every spoke | The pillar, plus 2-3 sibling spokes in its own cluster |
| Schema | Article + BreadcrumbList + ItemList | Article + BreadcrumbList |

Match each post's format to its intent — informational-broad reads as a guide, informational-how as step-by-step instructions, informational-list as a numbered rundown, commercial-compare as a side-by-side, commercial-evaluate as a single-item review, commercial-rank as a best-of list, transactional as a conversion-focused landing page. Prefer whichever format the actual SERP results for that keyword are already using.

**Cannibalization check**: no two posts share a primary keyword. If two keywords score 7+ overlap, that's a signal to merge them into one post rather than let them compete.

## Step 5: Internal link matrix
- Every spoke → pillar, and pillar → every spoke: mandatory, non-negotiable.
- Spoke ↔ spoke within the same cluster: 2-3 links per post, contextual anchors in body copy (not a "related posts" widget).
- Cross-cluster spoke links: 0-1, only where there's a genuine topical bridge.
- Every post needs at least 3 incoming internal links; no page should be more than 2 clicks from the pillar; no single anchor text should account for more than 40% of the links into a page.

Represent the plan as a simple adjacency list (from/to/type/anchor) so the link requirements can be checked mechanically once content ships.

## Step 6: Cluster map
Produce a single self-contained HTML file visualizing the pillar, its clusters, and the link matrix (nodes for pillar/spoke posts, edges for the mandatory and recommended links, color-coded by cluster) so the architecture can be reviewed before writing begins. Keep it dependency-free — no CDN scripts — since it may be opened offline.

## Cluster scorecard
Run this after content is drafted to check the plan was actually followed:

| Metric | Target |
|---|---|
| Coverage | 100% of planned posts written |
| Link density | 3+ internal links per post |
| Orphan pages | 0 |
| Cannibalization | 0 duplicate primary keywords |
| Pillar links | 100% (every spoke links to pillar and back) |
| Cross-links | 80%+ of recommended spoke-to-spoke links implemented |

## Output

A cluster plan (pillar + clusters + posts + link matrix + SERP overlap notes) plus the HTML cluster map — and, on a re-run against existing content, the scorecard comparing plan to what actually got written.

## Connector mode (optional)

SERP overlap scoring needs real top-10 result sets per keyword. If a SERP/DataForSEO-style MCP connector is available, use it for consistent, precise result sets and say so. Without one, fall back to WebSearch per keyword — note explicitly that WebSearch result sets can vary run-to-run and session-to-session, so treat overlap scores from it as directional rather than exact, and consider re-running a borderline pair before committing to a merge/split decision.

## Error handling

| Scenario | Action |
|---|---|
| No seed keyword given | Ask for one before proceeding. |
| Expansion yields under 15 keywords | Run a second expansion pass seeded from PAA questions. |
| SERP data unavailable (WebSearch and connector both failing) | Retry once; if still failing, fall back to intent-only clustering and say the result is lower-confidence. |
| Cannibalization detected after clustering | Merge the conflicting posts or differentiate them by intent/format. |
| Orphan page detected | Add links from the nearest cluster siblings before finalizing the plan. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.

## Explicit workflow behavior

When explicitly invoked as `$seo-cluster`, apply this entrypoint behavior:

Expand the seed keyword, cluster by real SERP overlap (not text similarity),
classify intent, and design a pillar/spoke content plan with an internal link
matrix and cluster map.

## Output
See the seo-cluster skill's Output section, then close with the seo
orchestrator's evidence-based footer.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
