---
description: Review AI code for hallucinations and missing files
argument-hint: [optional files/diff]
---
Use the **ai-output-auditor** skill in review-output mode (ground it with **repo-analyzer**). $ARGUMENTS

Hunt hallucinated APIs / fake imports, missing or half-created files and broken imports, unsafe assumptions (invented env vars, assumed schema, skipped auth/validation, hard-coded secrets), whether it matches the request, and whether it actually builds/runs. Report each with severity and fix.

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
