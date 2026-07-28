---
name: seo-geo
description: Generative Engine Optimization (GEO) analysis for AI Overviews, AI Mode, ChatGPT search, and Perplexity — passage-level citability scoring, structural readability, multi-modal content signals, authority and brand-mention signals, AI-crawler accessibility in robots.txt, llms.txt status, and platform-specific citation patterns, framed per Google's own stated position that GEO is SEO fundamentals applied to AI-search surfaces rather than a separate discipline. Use for "AI Overviews", "SGE", "GEO", "AEO", "AI search visibility", "llms.txt", or "AI citations" requests.
---

# AI Search / GEO Optimization

Google's own AI optimization guide states plainly that generative-AI search optimization is not a distinct discipline: "AEO and GEO are rebranded labels" for the same SEO fundamentals. AI Overviews and AI Mode are grounded in the same ranking and quality systems as classic Search, layered with retrieval-augmented generation and query fan-out. The eligibility floor is unchanged too — a page must already be indexed and snippet-eligible in classic Search to appear in any AI feature. Frame every finding this way, and when a popular GEO tactic (content "chunking," AI-specific rewriting, llms.txt as a citation lever) contradicts Google's stated position, defer to Google and say so explicitly.

Google explicitly rejects: creating `llms.txt`/AI-specific markup files, chunking content for AI, rewriting content with AI-specific phrasing, chasing inauthentic mentions across blogs/forums/videos, and over-investing in structured data specifically for AI features. What it says does matter is unique, first-hand, non-commodity content — its own contrast is a generic "7 Tips" listicle against a lived-experience account with specific, unrepeatable detail.

## Key stats worth citing

| Metric | Value | Source |
|---|---|---|
| AI Overviews reach | 2.5B+ MAU (third-party I/O coverage, not Google-confirmed), 200+ countries | I/O 2026 keynote reporting |
| AI Overviews query coverage | ~50% of queries (varies by country) | Industry measurement |
| AI Mode | 1B+ MAU (third-party-reported), runs a custom Gemini 2.5 | I/O 2026 keynote reporting / Google |
| AI-referred session growth | 527% Jan-May 2025 | SparkToro |
| ChatGPT weekly active users | 900M | OpenAI |
| Perplexity monthly queries | 500M+ | Perplexity |

## Brand mentions beat backlinks

Ahrefs' December 2025 study of 75,000 brands found brand mentions correlate roughly 3x more strongly with AI-citation visibility than backlinks (YouTube mentions ~0.737 correlation, Domain Rating only ~0.266). Only 11% of domains get cited by both ChatGPT and Google AI Overviews for the same query, so platform-specific work matters more here than in classic SEO.

## Scoring dimensions

1. **Citability (25%)** — optimal citable-passage length is 134-167 words, and roughly 44% of AI citations pull from the first 30% of a page (SE Ranking), so front-load the self-contained answer. Reward clear quotable sentences, extractable answer blocks, a direct answer in the first 40-60 words of a section, sourced claims, "X is..." definitional openers, and unique data points; penalize vague claims, unsupported opinion, and buried conclusions.
2. **Structural readability (20%)** — 92% of AI Overview citations come from top-10 pages, but 47% come from below position 5, so structure matters somewhat independent of rank. Reward clean H1→H2→H3 hierarchy, question-phrased headings, short paragraphs, tables/lists for comparative or step content, and clear FAQ Q&A formatting.
3. **Multi-modal content (15%)** — pages combining text with images, video, infographics, or interactive tools see 156% higher selection rates. Check whether supporting structured data exists for that media too.
4. **Authority & brand signals (20%)** — author byline with credentials, publish/update dates, and genuine recency (content under ~3 months old is roughly 3x more likely to be cited; pages stale 6+ months lose citation eligibility per a 1.3M-citation SE Ranking study — a scheduled refresh cadence is one of the highest-leverage GEO plays), citations to primary sources, and entity presence on Wikipedia/Wikidata/Reddit/YouTube/LinkedIn.
5. **Technical accessibility (20%)** — AI crawlers don't execute JavaScript, so server-side rendering of the actual content is non-negotiable. Check AI-crawler access in robots.txt and llms.txt presence (below).

## AI crawler access

| Crawler | Owner | Purpose | Honors robots.txt |
|---|---|---|---|
| GPTBot | OpenAI | ChatGPT web search | Yes |
| OAI-SearchBot | OpenAI | Search features | Yes |
| ChatGPT-User | OpenAI | User-triggered browsing | No (user-triggered) |
| ClaudeBot | Anthropic | Claude web features | Yes |
| PerplexityBot | Perplexity | AI search | Yes |
| CCBot | Common Crawl | Training-data feed | Yes |
| anthropic-ai | Anthropic | Claude training | Yes |
| Bytespider | ByteDance | TikTok/Douyin AI | Yes |
| Google-Extended | Google | Gemini training/grounding opt-out | Yes |
| Google-Agent | Google | Agentic browsing (Project Mariner-style) | No (user-triggered) |
| Google-NotebookLM | Google | User-added source fetch | No (user-triggered) |

Recommend allowing GPTBot, OAI-SearchBot, ClaudeBot, and PerplexityBot for AI-search visibility; blocking CCBot and pure-training crawlers is a defensible choice for a site opting out of model training specifically. User-triggered fetchers (Google-Agent, Google-NotebookLM, ChatGPT-User) ignore robots.txt by design — they can only be controlled server-side. Note the emerging **Web Bot Auth** (RFC 9421) standard, letting some of these bots authenticate via a signed header instead of relying purely on reverse-DNS verification.

## llms.txt: report presence, assign no ranking weight

Google's AI optimization guide states explicitly that Google Search — including its generative features — ignores `/llms.txt`; it "won't harm (nor help)" visibility. John Mueller has separately called the discovery use-case "a dead end." A 300k-domain SE Ranking study found only one of the top 50 AI-cited domains had a `/llms.txt`, and server-log analysis put AI-bot traffic to the file at roughly 0.1% of requests. Treat this as settled: **report whether `/llms.txt` exists, but never score it or recommend it as a Google citation lever.** It can still be worth publishing defensively for non-Google AI services (some coding-agent tooling consumes library-level llms.txt files), at effectively zero cost.

## RSL 1.0

A December-2025 standard for machine-readable AI licensing terms, backed by Reddit, Yahoo, Medium, Quora, Cloudflare, Akamai, and Creative Commons. Check for implementation and note it as an emerging, optional signal.

## Platform-specific notes

| Platform | Primary citation sources | Focus |
|---|---|---|
| Google AI Overviews | Strongly rank-correlated | Classic SEO + passage optimization |
| Google AI Mode (Gemini 2.5) | Weakly rank-correlated, broader pool (~9 domains/query, Ahrefs) | Freshness, entity authority, citable passages beyond position 5 |
| ChatGPT | Wikipedia (47.9%), Reddit (11.3%) | Entity presence, authoritative sources |
| Perplexity | Reddit (46.7%), Wikipedia | Community validation |
| Bing Copilot | Bing index | Bing SEO, IndexNow |

Treat AI Overviews and AI Mode as two separate citation engines even after Google unified the *experience* at I/O 2026 — Ahrefs found they reach the same conclusion ~86% of the time but cite the same URL only 13.7% of the time. Score both rather than assuming one covers the other.

Newer citation-surface controls worth checking: **Preferred Sources** (site-picked "preferred" badge, all-languages since April 2026, moving toward becoming a ranking signal — a genuine quick win to promote to the client's audience), **Highly Cited** badges for original reporting, **Community Perspectives** elevating Reddit/forum content, and inline Link Previews/carousels. There's no AI-specific opt-out file — appearance in AI features is governed by the same `nosnippet`/`data-nosnippet`/`max-snippet`/`noindex` directives as regular Search.

## Output

Deliver a GEO readiness score (0-100), a platform breakdown (Google AIO / AI Mode / ChatGPT / Perplexity), AI-crawler access status, llms.txt status, a brand-mention presence summary (Wikipedia/Reddit/YouTube/LinkedIn), passage-level citability findings against the 134-167-word target, an SSR/JS-dependency check, and the top 5 highest-impact changes plus schema and content-reformatting suggestions.

## Quick wins / medium effort / high impact

- **Quick**: add a "What is [topic]?" definition in the first 60 words; build 134-167 word self-contained answer blocks; use question-phrased H2/H3s; cite specific statistics with sources; add publish/update dates; add Person schema for authors; allow the key AI crawlers in robots.txt.
- **Medium**: publish `/llms.txt` (optional, ignored by Google, may help others); add author bios with credentials and Wikipedia/LinkedIn links; ensure SSR for key content; build Reddit/YouTube presence; add comparison tables; add structured FAQ sections — not schema, since FAQPage rich results are retired (see **seo-schema**).
- **High**: original research/surveys; Wikipedia presence for the brand or key people; a YouTube channel with content mentions; comprehensive `sameAs` entity linking; unique tools/calculators.

## Connector mode (optional)

If a DataForSEO-style AI-visibility connector is available, use it to check what ChatGPT web search actually returns for target queries and to track brand-mention share across AI platforms — state clearly that the finding used live data. Without one, score citability, structure, authority, and technical accessibility qualitatively from the page itself and say so; brand-mention presence can still be checked manually via direct lookups on Wikipedia, Reddit, and YouTube.

## Error handling

| Scenario | Action |
|---|---|
| URL unreachable | Report the error; don't guess content; ask the user to verify. |
| AI crawlers blocked | Report exactly which are blocked/allowed and give the specific robots.txt lines to fix it. |
| No llms.txt found | Note the absence as informational (optional file, Google ignores it) and offer a minimal template for non-Google use. |
| No structured data | Report the gap with concrete Article/Organization/Person recommendations. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.
