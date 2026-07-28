---
description: Plan a load test or interpret results and capacity
argument-hint: "[plan | interpret] [target or results]"
disable-model-invocation: true
---
Use the load-testing skill for: $ARGUMENTS

Only test systems the user owns, against a staging/production-like environment.
For planning, define the question, a realistic load model, thresholds, and test
type. For interpreting, report throughput/latency-percentiles/error-onset/
breaking-point, identify the bottleneck with evidence, and give capacity/scaling
recommendations.

SAFETY: manual-only (can generate production-scale traffic and side effects). Target staging by default; production load tests require explicit confirmation, a traffic budget, and an abort plan.

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
