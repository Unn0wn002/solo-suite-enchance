---
description: Reduce cloud and database cost without risking uptime
argument-hint: [billing breakdown or infra description]
---
Use the cost-optimization skill on: $ARGUMENTS

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

## Next Recommended Command
/…
```
