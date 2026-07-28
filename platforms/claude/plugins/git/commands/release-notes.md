---
description: Generate user-facing and technical release notes
argument-hint: [optional tag or range]
---
Use the **git-workflow-manager** skill in release-notes mode. $ARGUMENTS

From commits since the last tag plus `.solo/decisions.md` and Done tasks, produce two views: **user-facing** (new / fixed / changed, plain language) and **technical** (notable changes, migrations, breaking changes, upgrade steps).

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
