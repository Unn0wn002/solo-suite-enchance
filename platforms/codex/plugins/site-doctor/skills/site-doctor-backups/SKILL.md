---
name: site-doctor-backups
description: "Audit or design backup and disaster recovery (coverage, restore testing, RTO/RPO) Use when the user explicitly invokes $site-doctor-backups or asks for this site-doctor backups workflow."
---

# Site Doctor Backups

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $backup-recovery for the user's supplied arguments and surrounding request.

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

## Next Recommended Skill
No follow-up skill is implied here; choose the next validated skill for the current workflow.
```

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
