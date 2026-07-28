---
description: Sync .solo/tasks.md with GitHub issues
argument-hint: [optional: push | pull]
disable-model-invocation: true
---
Use the **git-workflow-manager** skill in sync-issues mode with **connector-auditor** for GitHub. $ARGUMENTS

Map `.solo/tasks.md` T-IDs to GitHub issues (one issue per T-ID, T-ID kept in the title/body for idempotency) and/or pull issue status back. Show a would-create / would-update / would-close diff and confirm before writing anything.

SAFETY: manual-only (external write to GitHub). Default to a dry-run preview of creates/updates/closes; require explicit confirmation before writing; never delete issues; record what was written.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
