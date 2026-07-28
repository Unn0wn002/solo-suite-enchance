---
description: Map codebase structure, entry points, and key files
argument-hint: [optional path or area]
---
Use the **repo-analyzer** skill in map mode. $ARGUMENTS

Read the code (don't guess from names); use existing project tooling as ground truth.

Expected output: entry points and how a request flows, routing, config/env loading, and the main folders with what owns what — each claim naming the file/path that proves it.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
