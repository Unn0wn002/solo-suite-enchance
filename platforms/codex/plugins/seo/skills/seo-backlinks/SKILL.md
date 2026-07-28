---
name: seo-backlinks
description: Backlink profile analysis — referring-domain counts and quality, anchor-text distribution, toxic/spam link detection, top linked pages, and competitor gap analysis, scored into a confidence-weighted Backlink Health Score. Use for "backlinks", "link profile", "referring domains", "anchor text", "toxic links", "link gap", "disavow", or "link building" requests.
---

# Backlink Profile Analysis

Seven analysis sections rolled into one confidence-weighted score, since backlink data quality varies wildly by source.

## 1. Profile Overview
Referring domain count, follow/nofollow ratio, domain diversity (no single domain dominating), and trend direction.

| Metric | Good | Warning | Critical |
|---|---|---|---|
| Referring domains | >100 | 20-100 | <20 |
| Follow ratio | >60% | 40-60% | <40% |
| Domain diversity | no domain >5% of links | one domain >10% | one domain >25% |
| Trend | growing/stable | slow decline | rapid decline (>20%/quarter) |

## 2. Anchor Text Distribution
A natural link profile is dominated by branded and generic anchors, not exact-match keywords.

| Anchor type | Healthy range | Over-optimization signal |
|---|---|---|
| Branded | 30-50% | <15% |
| URL/naked link | 15-25% | — |
| Generic ("click here", "learn more") | 10-20% | — |
| Exact-match keyword | 3-10% | >15% |
| Partial-match keyword | 5-15% | >25% |
| Long-tail/natural | 5-15% | — |

Flag exact-match anchors above 15% as a manual-review heuristic for unnatural link patterns, not an automatic penalty.

## 3. Referring Domain Quality
Check TLD mix (.edu/.gov/.org skew high-authority; heavy .xyz/.info skews low-quality), country distribution against the target market (80%+ irrelevant-geo links is a private-blog-network signal), authority-tier spread, and whether high-value domains only nofollow (limiting their SEO value).

## 4. Toxic Link Detection
High-risk (flag immediately): known PBN domains, anchor text that's 100% exact-match from one domain, links from penalized/deindexed sites, mass directory submissions (50+), link farms, sitewide paid-link patterns (footer/sidebar links repeated across a domain's whole site).

Medium-risk (review manually): links from unrelated niches, reciprocal-link patterns, thin-content donor pages (<100 words), more than 50 backlinks from a single domain.

## 5. Top Pages by Backlinks
Identify link magnets, pages with zero backlinks (internal-linking opportunities), and 404s that still hold backlink equity worth reclaiming with a redirect.

## 6. Competitor Gap Analysis
Domains linking to a competitor but not the target = link-building targets. Domains linking to both = validate the relationship still holds. Domains linking only to the target = a competitive advantage worth defending.

## 7. Link Velocity (new/lost)
Point-in-time snapshots can't show change over time — this needs a paid time-series API (see Connector mode). A sudden spike in new links can indicate a negative-SEO attack; a sudden loss can indicate a penalty or content removal; declining velocity over 3+ months suggests content has stopped attracting links.

## Backlink Health Score

Weight each factor by confidence in its data source — a score built on all 7 factors from a paid API means something different from one built on 2 factors of free data, and presenting both the same way is misleading.

| Factor | Weight |
|---|---|
| Referring domain count | 20% |
| Domain quality distribution | 20% |
| Anchor text naturalness | 15% |
| Toxic link ratio | 20% |
| Link velocity trend | 10% |
| Follow/nofollow ratio | 5% |
| Geographic relevance | 10% |

**Data sufficiency gate**: count how many of the 7 factors actually have data behind them.
- 4+ factors scored → produce a numeric 0-100 score (redistribute missing weights proportionally), tag each factor with its source and confidence.
- Fewer than 4 → do not produce a numeric score at all; report `INSUFFICIENT DATA (X/7 factors scored)` with whatever factor scores are available, each source-labeled. A number built on under half the model is worse than no number — it reads as "poor health" when the truth is "no data."

## Output

### Backlink Health Score: XX/100 (or INSUFFICIENT DATA)

| Section | Status | Score | Data Source |
|---|---|---|---|
| Profile Overview | pass/warn/fail | XX/100 | … |
| Anchor Distribution | pass/warn/fail | XX/100 | … |
| Referring Domain Quality | pass/warn/fail | XX/100 | … |
| Toxic Links | pass/warn/fail | XX/100 | … |
| Top Pages | info | N/A | … |
| Link Velocity | pass/warn/fail or N/A | XX/100 | … |

Critical Issues / High Priority / Medium Priority / Link Building Opportunities (top 10), each with a named data source.

## Connector mode (optional)

Full backlink analysis — referring-domain counts, DA/PA-style authority scores, spam scoring, anchor-text distribution, link velocity — is fundamentally a paid-API capability (DataForSEO, Moz, Ahrefs-class tools). If a backlink/SEO data MCP connector is available in this environment, use it explicitly and say so in the Data Source column.

**Manual mode (no connector)**: without a paid API there is no reliable way to enumerate a domain's inbound links — that data isn't publicly crawlable from the target site itself. What's actually checkable:
- Fetch the target site (via `<skill-root>/../../lib/url_guard.py`-guarded requests) and review on-page evidence of link relationships — testimonial/partner pages, embedded badges, syndication credits.
- Manually verify specific known/suspected backlinks still exist and still carry the expected anchor text and `rel` attribute, by fetching the linking page directly.
- Use WebSearch for brand-mention queries as a rough, low-confidence signal of who references the domain — this is not equivalent to a crawled backlink index and should be labeled as such.

State plainly in the report that referring-domain counts, DA/PA, spam scores, anchor-text distribution, and link velocity are unavailable without a connector, and skip those factors in the Health Score gate rather than guessing.

## Error handling

| Scenario | Action |
|---|---|
| No connector and no verifiable data | Report INSUFFICIENT DATA; don't publish a numeric score built on guesses. |
| Target URL unreachable | Report the connection error; don't infer link status from an unreachable page. |
| Known backlink no longer resolves | Distinguish "link removed", "page is JS-rendered so unverifiable", and "domain gone" — never call a JS-rendered page a confirmed link removal. |
| Suspected reciprocal link pattern | Check whether the target's own outbound links point back to the same domain before flagging. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.

## Explicit workflow behavior

When explicitly invoked as `$seo-backlinks`, apply this entrypoint behavior:

Analyze the referring-domain profile, anchor-text distribution, and toxic-link
risk for this domain, then compare against a competitor if one is given. State
plainly whether results came from a live connector or degraded manual-mode
checks.

## Output
See the seo-backlinks skill's Output section, then close with the seo
orchestrator's evidence-based footer.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
