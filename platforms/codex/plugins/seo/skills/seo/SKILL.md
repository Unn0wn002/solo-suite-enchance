---
name: seo
description: SEO specialist orchestrator — routes a full-site audit across the dedicated seo-technical, seo-content, seo-schema, seo-sitemap, seo-images, seo-geo, seo-local, seo-hreflang, seo-backlinks, seo-cluster, seo-sxo, seo-drift, seo-ecommerce, and seo-google sub-skills, scores the result, and produces one prioritized action plan. Use for a comprehensive SEO audit heavier than site-doctor's seo-optimization single-page check — full-site crawls, industry-specific verticals (local/ecommerce/i18n), or when the user wants an SEO health score.
---

# SEO Specialist Orchestrator

This is the deep-audit counterpart to **site-doctor's seo-optimization** skill. Reach for seo-optimization for a fast single-page/single-template check; reach for this orchestrator when the ask is a full-site audit, an industry-specific vertical (local, ecommerce, multi-language), or a scored health report.

## Routing

1. **Detect business type** from homepage signals: SaaS (pricing/features/docs/trial), local service (phone/address/service-area/map embed), e-commerce (product/cart/checkout), publisher (blog/article schema/author pages), agency (case studies/portfolio).
2. **Always run**: seo-technical, seo-content, seo-schema, seo-sitemap, seo-sxo.
3. **Run when relevant**: seo-images and seo-geo (nearly always worth it), seo-local (local service detected), seo-ecommerce (e-commerce detected), seo-hreflang (multiple language/region variants detected), seo-cluster (blog/pillar-page/topic-cluster content strategy detected).
4. **Connector-mode only, ask first**: seo-backlinks and seo-google — both explicitly state whether they ran with live data or degraded to manual/free-source mode; never silently skip them without saying so.
5. **Repeat audits**: if `.solo/handoff.md` or the skill's own baseline file shows a prior run for this URL, use seo-drift to report what changed instead of re-explaining unchanged findings.
6. Collect every sub-skill's findings and **score** (see below) before writing the combined report.

## SEO Health Score (0–100)

Weight each category's own PASS/WARNING/FAIL findings and combine:

| Category | Weight |
|---|---|
| Technical SEO (crawl, index, security headers, CWV) | 22% |
| Content Quality (E-E-A-T, thin/duplicate content) | 23% |
| On-Page SEO (titles, meta, headings, internal links) | 20% |
| Schema / Structured Data | 10% |
| Performance (Core Web Vitals) | 10% |
| AI Search Readiness (GEO) | 10% |
| Images | 5% |

A category scored "not checked" is excluded from the denominator rather than counted as a zero — state which categories were skipped and why, the same N/A-aware approach `$gate-production-ready` uses.

## Priority bands

- **Critical** — blocks indexing or risks a penalty; fix immediately.
- **High** — meaningfully affects rankings; fix within a week.
- **Medium** — real opportunity; fix within a month.
- **Low** — backlog.

## Report format

Produce one combined report: Executive Summary (score, business type, top 5 critical issues, top 5 quick wins) → per-category findings bucketed the same way each sub-skill buckets them → a single dependency-ordered action plan (do X before Y because Y assumes X is fixed) → the standard evidence-based footer below.

## Output — evidence-based audit format
Never just "good" or "bad" — every claim names its proof. If a category wasn't actually checked, say so; don't guess.

```
## Status
PASS / WARNING / FAIL

## Evidence Checked
- Page: …
- Command output: …
- Connector data: …
(only the lines that apply — but at least one; no evidence, no finding)

## SEO Health Score
NN/100 (categories excluded from scoring: …)

## Findings
1. …

## Risk Level
Low / Medium / High / Critical

## Required Fixes
1. …

## Suggested Tasks
→ `.solo/tasks.md` entries with stable T-IDs

## Verification Steps
1. …

## Next Recommended Skill
Choose the next validated skill for the current workflow.
```

## Project memory integration (solo-team)

If `.solo/` exists at the project root, read `handoff.md` and `tasks.md` before starting so the audit builds on prior context, then write the prioritized fix list into `.solo/tasks.md` (stable T-IDs), append notable findings or accepted risks to `.solo/decisions.md`, and note what ran in `handoff.md`. **AgentRoom proposal mode**: when a trusted seat lists a memory target under `proposes`, write to `.solo/proposals/<seat>-<run_id>.md` instead of editing the target directly — only the memory steward merges it. If `.solo/` doesn't exist, proceed normally.

## Stack awareness

Read `.solo/stack.md` before auditing if it exists, and tailor recommendations to the project's actual hosting/CDN/analytics stack rather than generic advice.

## Script safety (url_guard)

Every sub-skill's outbound fetch routes through `<skill-root>/../../lib/url_guard.py`: HTTPS-first, refuses loopback/private/link-local/CGNAT/cloud-metadata targets on every DNS answer and redirect hop, and caps response size. A refused target prints `BLOCKED unsafe target: <reason>` instead of being fetched.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
