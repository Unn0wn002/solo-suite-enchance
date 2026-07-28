---
name: growth-conversion-audit
description: "Audit the conversion funnel and find where users drop off and why. Use when the user explicitly invokes $growth-conversion-audit or asks for this growth conversion-audit workflow."
---

# Growth Conversion Audit

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $conversion-optimizer. Apply it to the user's supplied arguments and surrounding request.

Map the funnel, check whether it's even measured (delegate depth to `$site-doctor-audit-analytics`), find friction at each step (clarity, CTA, forms — see `$site-doctor-audit-forms`, trust, speed/mobile — see `$site-doctor-perf` and `$browser-mobile-test`), and prioritize fixes by impact × effort. Evidence-based; state assumptions, not invented numbers.

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
