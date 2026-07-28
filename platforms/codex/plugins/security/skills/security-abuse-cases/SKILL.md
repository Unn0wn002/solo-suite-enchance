---
name: security-abuse-cases
description: "Find ways users could abuse the app without \"hacking\" it. Use when the user explicitly invokes $security-abuse-cases or asks for this security abuse-cases workflow."
---

# Security Abuse Cases

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $security-review (site-doctor) to find abuse cases — do a lighter inline version following the same priorities if site-doctor isn't installed, and say so. Apply it to the user's supplied arguments and surrounding request.

Think like a rule-bending user, not an attacker: spam/abuse of free actions, quota/credit gaming, scraping, coupon/refund abuse, rate-limit gaps, and cost-amplification. For each: the impact and a mitigation.


Record open risks with severity and owner in **`.solo/risks.md`**.

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
