---
name: seo-flow
description: Apply the FLOW methodology (Find → Leverage → Optimize → Win) as an evidence-led operating loop across a site's other SEO work — naming which search surface (organic, AI answer, local pack, community, paid, sales-assisted) a page is competing on, separating verified evidence from assumption, and connecting visibility metrics to business outcomes. Use when the user says "FLOW", "FLOW framework", "evidence-led SEO", "find leverage optimize win", or wants a stage-by-stage plan tying SEO work to business impact rather than a single-skill checklist.
---

# FLOW: Find → Leverage → Optimize → Win

FLOW is a lightweight operating loop for treating classic rankings, AI citations, local visibility, and sales evidence as one connected system rather than separate channels to optimize in isolation. It doesn't replace the suite's other SEO skills — it's the sequencing layer that decides which of them to run next and what "done" means.

## Why the loop matters

Search no longer resolves to one results page and one click path. Industry CTR studies through late 2025 have shown meaningfully lower click-through for position-one organic results when an AI Overview is present on the same query, and separate citation studies have found a real share of pages cited by AI answer engines carry little or no classic organic visibility. Practically: a page can "win" on rankings and still lose the business outcome if the AI surface, the local pack, or the sales conversation is where the actual decision happens. The FLOW loop forces a decision about *which* surface can move the next business outcome before spending effort on any of them equally.

## The four stages

**Find** — identify demand: keyword research, SERP gap analysis, intent mapping. Route the deep work to **seo-cluster** for topic/SERP-overlap clustering and **seo-content-brief** for a specific page's competitive brief.

**Leverage** — build distributed, off-site evidence: backlinks, citations, third-party corroboration of brand claims. Route to **seo-backlinks** for the actual profile data.

**Optimize** — make the owned asset easy to extract and trust: on-page structure, technical health, schema, content depth. Route to **seo-technical**, **seo-content**, **seo-schema**, and **seo-page** depending on what's actually blocking — don't run all of them reflexively; pick 2-3 based on what Find/Leverage already surfaced (e.g., a technical crawl issue found upstream routes to seo-technical; an E-E-A-T gap routes to seo-content).

**Win** — connect discovery to revenue: conversion-focused page structure, bottom-of-funnel content, and a scorecard that pairs visibility metrics with business metrics. Route to **seo-sxo** for persona-level scoring of why a well-optimized page still isn't converting, and **seo-competitor-pages** for comparison/alternatives pages that target late-stage intent directly.

Local-specific work (GBP, NAP, citations, local landing pages) isn't a separate FLOW stage in this port — it's Optimize/Leverage work for a local business, and the suite's **seo-local** and **seo-maps** skills cover it directly.

## How to apply it

1. State the business outcome before picking a tactic — a page meant to generate a qualified call shouldn't be judged on impressions alone, and vice versa.
2. Inventory the evidence already available: customer language, query data, reviews, analytics, sales-call notes, and any public source that can support a claim.
3. Decide which stage is actually the bottleneck. Demand language unclear → back to Find. Brand not corroborated off-site → work Leverage. Owned asset hard to extract or trust → Optimize. Traffic exists but business impact is weak → move to Win.
4. Don't rewrite from a blank page — organize the evidence into a source table first, then draft.
5. Review the result against three readers: the buyer, the search engine, and the AI agent that may summarize or compare the page later — meaning: clear headings, a direct answer near the top, tables for comparative data, and no hidden dependency on private/internal examples the reader can't verify.

## Measurement

Track visibility indicators (rankings, impressions, local-pack presence, backlink/citation counts, AI mentions) alongside business indicators (qualified leads, calls, form completions, opportunities, assisted conversions, recurring sales objections) — a visibility win that never shows up in a business indicator isn't yet a Win-stage result. If the page or profile in question isn't currently measured at all, treat adding that measurement event as the first fix, before judging performance.

## Common failure modes to flag

- A statistic published because it "sounds right" rather than because a dated source was actually checked.
- Treating AI-search visibility as a formatting trick while ignoring the underlying brand evidence and off-site corroboration that actually drives citation.
- Structuring pages around what the business wants to say instead of the buyer's actual question and decision risk.
- Optimizing for traffic without ever defining the next qualified action the visitor should take.
- Reusing stale examples/data when a fresh, generic example would be both cleaner and more durable.

## Output

For a given URL or topic, tag the finding with its FLOW stage, name the search surface it's competing on, list the evidence checked (or the gap in evidence), and state the next 2-3 concrete actions with which sub-skill each routes to. Close with the balanced scorecard: current visibility indicators vs. current business indicators, and what's missing from either side.

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.
