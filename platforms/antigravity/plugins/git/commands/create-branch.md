---
description: Create a safe branch name and the exact git command
argument-hint: [optional task/T-ID or description]
---
Use the **git-workflow-manager** skill in create-branch mode. $ARGUMENTS

Derive a safe `type/scope-desc` branch name from the current `.solo/tasks.md` task (or the provided text), confirm the base branch, and output the exact `git checkout -b` command. Don't switch branches or run git for the user unless asked.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
