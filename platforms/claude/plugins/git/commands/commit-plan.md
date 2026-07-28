---
description: Propose clean, atomic Conventional-Commit commits
argument-hint: [optional path or scope]
---
Use the **git-workflow-manager** skill in commit-plan mode. $ARGUMENTS

Inspect `git status`/`git diff`, group the changes into logical atomic commits with Conventional-Commit messages, and flag anything that must not be committed (secrets, `.env`, build output, large binaries). Give copy-paste `git add`/`commit` commands. Don't commit unless asked.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
