---
description: Audit the conversion funnel for drop-off points
argument-hint: [optional page or funnel]
---
Use the **conversion-optimizer** skill. $ARGUMENTS

Map the funnel, check whether it's even measured (delegate depth to `/site-doctor:audit-analytics`), find friction at each step (clarity, CTA, forms — see `/site-doctor:audit-forms`, trust, speed/mobile — see `/site-doctor:perf` and `/browser:mobile-test`), and prioritize fixes by impact × effort. Evidence-based; state assumptions, not invented numbers.

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
