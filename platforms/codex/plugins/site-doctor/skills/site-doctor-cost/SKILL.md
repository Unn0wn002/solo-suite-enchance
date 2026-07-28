---
name: site-doctor-cost
description: "Find and reduce cloud/hosting/database cost without hurting reliability Use when the user explicitly invokes $site-doctor-cost or asks for this site-doctor cost workflow."
---

# Site Doctor Cost

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $cost-optimization on the user's supplied arguments and surrounding request.

If no info was provided, ask for the cost breakdown and workload shape. Find
waste across Compute / Database / Storage / Network / Managed services. Lead
each finding with estimated monthly savings and a risk rating; flag zero-risk
wins first; never trade reliability for savings.

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
