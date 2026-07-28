---
description: Find unused files, exports, routes, and packages
argument-hint: [optional path or area]
---
Use the **repo-analyzer** skill in find-dead-code mode. $ARGUMENTS

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

## Next Recommended Command
/…
```
