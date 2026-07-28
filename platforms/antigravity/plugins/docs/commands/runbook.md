---
description: Write an ops runbook - failures, rollback, escalation
argument-hint: <task or service>
---
Use the **documentation-writer** skill in runbook mode. $ARGUMENTS

Produce an operational runbook: what it does and when to run it, prerequisites/access, exact step-by-step operating procedure, how to verify success, common failures and their fixes, rollback/recovery, and escalation. Keep steps copy-pasteable.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
