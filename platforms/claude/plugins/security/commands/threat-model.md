---
description: Map assets, attackers, trust boundaries, attack paths
argument-hint: [optional scope]
---
Use the **security-review** skill (site-doctor) to build a threat model — do a lighter inline version following the same priorities if site-doctor isn't installed, and say so. $ARGUMENTS

Enumerate assets worth protecting, likely attackers and goals, trust boundaries and entry points, and concrete attack paths — then map each to a mitigation. Pull risky areas from `/repo:risk-map` when available.


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
