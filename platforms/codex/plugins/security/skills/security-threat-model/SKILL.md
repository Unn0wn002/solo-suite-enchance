---
name: security-threat-model
description: "Identify assets, attackers, trust boundaries, and attack paths. Use when the user explicitly invokes $security-threat-model or asks for this security threat-model workflow."
---

# Security Threat Model

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $security-review (site-doctor) to build a threat model — do a lighter inline version following the same priorities if site-doctor isn't installed, and say so. Apply it to the user's supplied arguments and surrounding request.

Enumerate assets worth protecting, likely attackers and goals, trust boundaries and entry points, and concrete attack paths — then map each to a mitigation. Pull risky areas from `$repo-risk-map` when available.


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
