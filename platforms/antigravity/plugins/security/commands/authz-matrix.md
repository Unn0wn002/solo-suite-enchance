---
description: Build a role-permission matrix and check enforcement
argument-hint: [optional roles/resources]
---
Use the **authz-security-reviewer** skill in authz-matrix mode. $ARGUMENTS

Build a role × resource × action matrix and verify each allowed action is enforced **server-side** with deny-by-default and ownership/tenant checks. Flag any client-only gating as critical.

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
