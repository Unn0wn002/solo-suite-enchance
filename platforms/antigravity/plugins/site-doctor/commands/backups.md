---
description: Audit or design backups and disaster recovery
argument-hint: "[audit | design] [current setup or targets]"
---
Use the backup-recovery skill for: $ARGUMENTS

Frame with RTO/RPO first. For an audit, check coverage, 3-2-1, frequency,
restore-testing, mechanism, and runbook - flag "never restore-tested" and
"backups in the same place as production" as critical. For design, produce a
plan meeting the user's RTO/RPO. The key action is usually: run a real restore
test now.

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
