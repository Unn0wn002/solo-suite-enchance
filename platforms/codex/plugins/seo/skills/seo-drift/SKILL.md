---
name: seo-drift
description: SEO drift monitoring — captures a baseline snapshot of SEO-critical page elements (title, meta description, canonical, robots directives, headings, schema, Open Graph tags, Core Web Vitals, status code) and diffs later fetches against it to catch regressions, classified Critical/Warning/Info. Use for "SEO drift", "baseline", "did anything break", "SEO regression", "before and after", or "deployment check" requests.
---

# SEO Drift Monitor

Version control for on-page SEO: capture a known-good baseline, then diff future fetches against it instead of re-auditing from scratch every time.

## What a baseline captures
Title tag, meta description, canonical URL, robots meta directives, H1/H2/H3 arrays, JSON-LD schema, Open Graph tags, Core Web Vitals, HTTP status code, and a content hash of the HTML body plus a separate hash of just the schema block (so a schema-only change is distinguishable from a copy edit).

## Baseline
Fetch and parse the page, capture every field above, hash the HTML and schema separately, and store the snapshot keyed to a normalized form of the URL (lowercase scheme/host, default ports stripped, query params sorted, UTM stripped, trailing slash removed) so re-fetches of the "same" page always match the same baseline regardless of incidental URL variation.

## Compare
Fetch the current page, load the most recent baseline (or a specified one), and diff every tracked field. Classify each change:

| Severity | Meaning | Response time |
|---|---|---|
| Critical | SEO-breaking change, likely traffic loss | Immediate |
| Warning | Potential impact, needs investigation | Within a week |
| Info | Awareness only, may be intentional | Whenever convenient |

Typical critical-tier changes: canonical removed or changed, noindex added, status code moved to an error range, schema removed. Typical warning-tier: CWV regression, heading structure changed, title/meta changed materially. Typical info-tier: OG tags changed, minor copy edits reflected only in the content hash.

## History
List all baselines and comparisons stored for a URL, newest first, so a specific traffic-drop investigation can be narrowed to a date range before digging into the diff itself.

## Where findings route
| Finding | Follow up with |
|---|---|
| Schema removed or modified | **seo-schema** for full validation |
| CWV regression | **seo-technical** for a performance audit |
| Title/meta changed | On-page content review |
| Canonical changed or removed | **seo-technical** for an indexability check |
| Noindex added | **seo-technical** for a crawlability audit |
| Heading structure changed | Content-quality/E-E-A-T review |
| Status code moved to an error | **seo-technical** for full diagnostics |

## Typical workflows
Pre/post-deploy: baseline right before a deploy, compare right after. Ongoing: baseline once, compare periodically (weekly/monthly), pull history when investigating a slow decline. Traffic-drop investigation: compare first to see what changed, then pull history to date it.

## Output

Baseline runs report what was captured and when. Comparisons report every triggered rule with old value, new value, severity, and the recommended follow-up skill. History runs report a timeline of baselines and comparison summaries.

## Storage

Keep baselines and comparisons in a local project-scoped store (e.g. `.solo/seo-drift/<normalized-url-hash>.json` or an equivalent file) rather than anything that leaves the machine — this is regression-tracking data, not something that needs a service.

## Connector mode (optional)

Core Web Vitals in the baseline can come from a Google/CrUX-style MCP connector if one is available (field data, a more reliable regression signal) — say so explicitly when used. Without one, use lab data from an available Lighthouse-equivalent tool and label it as a lab estimate, or store `null` for CWV fields and skip CWV-based drift rules entirely rather than comparing lab-to-lab noise as if it were a regression.

## Error handling

| Scenario | Action |
|---|---|
| URL unreachable | Report the fetch error; don't guess at page state. |
| No baseline exists yet | Say so, suggest capturing one first. |
| CWV fetch fails | Store null for CWV fields, skip CWV rules in the comparison. |
| Page returns 4xx/5xx | Still capture it as a baseline — status code is itself a tracked field. |
| Multiple baselines exist | Use the most recent unless a specific one is requested. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.

## Explicit workflow behavior

When explicitly invoked as `$seo-drift`, apply this entrypoint behavior:

If no URL was provided, ask for it. Capture a baseline snapshot, or compare
the current page against the most recent stored baseline and classify any
changes Critical/Warning/Info.

## Output
See the seo-drift skill's Output section, then close with the seo
orchestrator's evidence-based footer.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
