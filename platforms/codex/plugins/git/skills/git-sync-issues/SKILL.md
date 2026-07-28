---
name: git-sync-issues
description: "Convert .solo/tasks.md into GitHub issues, or sync issue status back. Use when the user explicitly invokes $git-sync-issues or asks for this git sync-issues workflow."
---

# Git Sync Issues

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $git-workflow-manager in sync-issues mode with $connector-auditor for GitHub. Apply it to the user's supplied arguments and surrounding request.

Map `.solo/tasks.md` T-IDs to GitHub issues (one issue per T-ID, T-ID kept in the title/body for idempotency) and/or pull issue status back. Show a would-create / would-update / would-close diff and confirm before writing anything.

SAFETY: manual-only (external write to GitHub). Default to a dry-run preview of creates/updates/closes; require explicit confirmation before writing; never delete issues; record what was written.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
