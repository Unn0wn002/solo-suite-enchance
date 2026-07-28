---
name: site-doctor-audit-analytics
description: "Audit analytics/tracking - tag firing, event & conversion coverage, GA4 setup, data quality, consent Use when the user explicitly invokes $site-doctor-audit-analytics or asks for this site-doctor audit-analytics workflow."
---

# Site Doctor Audit Analytics

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $analytics-audit on the user's supplied arguments and surrounding request.

If no info was provided, ask for the analytics stack and the business questions
the data should answer. Check installation/firing (watch for double-counting
tags), event & conversion coverage, data-quality/naming consistency, consent
integration, and reporting usefulness. Rank by how badly each issue corrupts
decision-making.

## Output — evidence-based audit format
Never just "good" or "bad" — every claim names its proof. If nothing was actually inspected for an area, say "not checked", don't guess. End with exactly:

```
## Status
PASS / WARNING / FAIL

## Evidence Checked
- File: …
- Config: …
- Page: …
- Command output: …
- Screenshot: …
- Connector data: …
(only the lines that apply — but at least one; no evidence, no finding)

## Findings
1. …
2. …

## Risk Level
Low / Medium / High / Critical

## Required Fixes
1. …

## Suggested Tasks
→ `.solo/tasks.md` entries with stable T-IDs

## Verification Steps
1. …

## Next Recommended Skill
No follow-up skill is implied here; choose the next validated skill for the current workflow.
```

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
