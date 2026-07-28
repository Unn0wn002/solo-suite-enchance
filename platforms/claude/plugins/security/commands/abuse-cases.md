---
description: Find ways users could abuse the app without "hacking" it.
argument-hint: [optional feature]
---
Use the **security-review** skill (site-doctor) to find abuse cases — do a lighter inline version following the same priorities if site-doctor isn't installed, and say so. $ARGUMENTS

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

## Next Recommended Command
/…
```
