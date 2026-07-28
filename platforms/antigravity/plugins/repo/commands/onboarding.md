---
description: Generate an onboarding guide from the codebase
argument-hint: [optional path or area]
---
Use the **repo-analyzer** skill in onboarding mode. $ARGUMENTS

Read the code (don't guess from names); use existing project tooling as ground truth.

Expected output: run-it-locally steps (install, env-var names, start command), where the entry points live, a folder-by-folder tour, and the first three files a new developer should read.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
