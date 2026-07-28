---
name: seo-sxo
description: Search Experience Optimization — reads the live Google SERP for a target keyword backwards to detect page-type mismatches (e.g. a blog post competing against product pages), derives user stories from PAA/ad-copy/related-search signals, and scores the page from multiple search-intent personas. Explains why a technically well-optimized page still fails to rank. Use for "SXO", "search experience", "page type mismatch", "why isn't my page ranking", "intent mismatch", or "wireframe" requests.
---

# Search Experience Optimization (SXO)

Technical SEO checks whether a page is healthy. SXO asks a different question: does this page deserve to rank for this keyword, given what Google is actually rewarding in the SERP right now? A page can score 95/100 on technical SEO and still never break through if it's the wrong *type* of page — no amount of on-page polish turns a blog post into a product page when the SERP is eight product pages and two comparisons.

## Step 1: Read the target page
Fetch the URL and extract title, H1, meta description, heading hierarchy, word count, schema, CTAs, and media. If no keyword is given, derive one from the overlap between the title tag and H1.

## Step 2: Read the SERP backwards
Search the target keyword and, for the top 10 organic results, record: domain authority tier (brand / niche authority / unknown), page type, content format (long-form/listicle/how-to/comparison/tool/video), rough word count, structured-data types present, and media signals. Also capture SERP features: featured snippet format, PAA questions, ad copy themes, related searches, knowledge panel/local pack/shopping results, and AI Overview presence.

From this, determine SERP consensus: a dominant page type at >60% agreement is strong consensus, 40-60% is mixed, under 40% is fragmented (which is itself useful — it signals room to differentiate rather than a mismatch to fix).

## Step 3: Page-type mismatch detection
Classify the target page's type and compare it to the SERP's dominant type.

| Target is | SERP wants | Severity | Fix |
|---|---|---|---|
| Blog post | Product pages | Critical | Build a dedicated product page |
| Blog post | Comparison content | High | Restructure as a comparison with a feature matrix |
| Product page | Informational content | High | Add an educational content layer |
| Landing page | Tool/calculator | High | Build an interactive tool |
| Service page | Local pack results | Medium | Add location signals and local schema |
| Matches | — | Aligned | Focus on depth and UX, not page type |

## Step 4: User stories from SERP signals
PAA questions reveal what users don't yet understand; ad copy reveals commercial triggers and value props; related searches reveal the surrounding search journey; the featured-snippet format reveals the expected answer shape; an AI Overview reveals what Google currently treats as the canonical answer. Turn 3-5 of these signal clusters into stories: *As a [persona], I want to [goal], because [driver from ad copy/PAA tone], but I'm blocked by [barrier from PAA/related searches].*

## Step 5: Gap analysis (0-100 SXO score)
| Dimension | Points |
|---|---|
| Page type match | 15 |
| Content depth (word count, heading depth, topic coverage) | 15 |
| UX signals (CTA clarity, above-fold content, mobile layout) | 15 |
| Schema markup vs SERP expectation | 15 |
| Media richness vs SERP norm | 15 |
| Authority signals (E-E-A-T markers, social proof, credentials) | 15 |
| Freshness (last-updated, recency signals) | 10 |

Lower total = bigger gap between the page and what the SERP expects.

## Step 6: Persona scoring
Derive 4-7 personas by clustering PAA questions, segmenting ad copy by apparent audience, and mapping related searches to journey stages. Score the target page per persona on four 25-point dimensions: Relevance (does it address this persona's need at all), Clarity (can they find their answer in ~10 seconds), Trust (adequate trust signals for this persona specifically), Action (a clear next step). Sort the recommendations by weakest persona first — that's the biggest available lift.

## Step 7: Wireframe (optional, on request)
Sketch the current-state (IST) structure from the parsed page, then a target-state (SOLL) structure driven by SERP consensus, gap findings, and persona weaknesses. Placeholders must be concrete enough to hand to a designer as-is — not "add a CTA here" but "add a pricing CTA with an annual-savings badge below the hero, linking to /pricing#enterprise."

## SXO score vs SEO Health Score
These are deliberately separate numbers: SEO Health Score measures technical compliance, SXO score measures alignment with what the SERP is rewarding. A page can be 95 SEO / 30 SXO — technically flawless, strategically pointed at the wrong target. Report both together whenever both are available; neither substitutes for the other.

## Output

```
## SXO Analysis: [URL] — Target Keyword: [keyword]

### SERP Landscape
Dominant page type, consensus %, SERP features present, content-depth norm, schema expectation.

### Page-Type Alignment
Target type vs SERP-expected type, verdict (aligned/mismatch + severity), impact.

### User Stories
3-5 stories, each citing the SERP signal it came from.

### Gap Analysis (SXO Score: XX/100)
7-dimension breakdown.

### Persona Scores
4-7 persona cards, 4-dimension scores each, concrete fixes.

### Priority Actions
Fix any page-type mismatch first, then the weakest persona gaps.

### Limitations
What couldn't be assessed and why.
```

## Connector mode (optional)

If a SERP/DataForSEO-style MCP connector is available, use it for precise SERP positions, features, and snippet text, and say so. Without one, use WebSearch for the SERP read — note that fewer than 5 usable organic results (e.g. an all-ads SERP) means analyzing ad copy themes only, and that a JS-rendered target page limits the on-page read to whatever's in the initial HTML.

## Error handling

| Scenario | Action |
|---|---|
| URL fetch fails | Report the error, suggest checking accessibility. |
| No keyword given or derivable | Ask the user for the target keyword. |
| WebSearch returns under 5 results | Proceed, but note the sample is limited. |
| SERP is all ads, no organic results | Analyze ad copy only, note a highly commercial SERP. |
| Target page is JS-rendered | Note the limitation; work from what's in the initial HTML. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.

## Explicit workflow behavior

When explicitly invoked as `$seo-sxo`, apply this entrypoint behavior:

If no URL was provided, ask for it. Read the live SERP for the target keyword,
check for a page-type mismatch, derive user stories, and score the page
against SERP-derived personas.

## Output
See the seo-sxo skill's Output section, then close with the seo
orchestrator's evidence-based footer.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
