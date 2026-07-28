---
name: site-doctor-load-test
description: "Plan a load/stress test or interpret results - scenarios, thresholds, bottlenecks, capacity Use when the user explicitly invokes $site-doctor-load-test or asks for this site-doctor load-test workflow."
---

# Site Doctor Load Test

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $load-testing for the user's supplied arguments and surrounding request.

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

## Next Recommended Skill
No follow-up skill is implied here; choose the next validated skill for the current workflow.
```

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
