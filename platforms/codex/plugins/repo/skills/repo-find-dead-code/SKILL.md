---
name: repo-find-dead-code
description: "Find unused files, exports, routes, components, and packages. Use when the user explicitly invokes $repo-find-dead-code or asks for this repo find-dead-code workflow."
---

# Repo Find Dead Code

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $repo-analyzer in find-dead-code mode. Apply it to the user's supplied arguments and surrounding request.

Read the code (don't guess from names); use existing project tooling as ground truth. Be conservative — dynamic imports and framework auto-loading can hide usage; flag candidates with a confidence level and reason, never delete, and suggest removals as tasks.

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
