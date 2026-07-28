---
description: Review CI/CD - build, rollback, env parity, downtime
argument-hint: [pipeline config path or description]
---
Use the deployment-review skill on: $ARGUMENTS

If no target was provided, ask for the CI/CD config and deploy target. Review
build/CI, secrets in pipeline, environment parity, rollback safety, zero-downtime
strategy, and release process. Rank findings by risk of causing or prolonging
an outage.

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
