---
description: Show internal module/service dependencies and import cycles.
argument-hint: [optional path or area]
---
Use the **repo-analyzer** skill in dependency-map mode. $ARGUMENTS

Read the code (don't guess from names); use existing project tooling as ground truth.

Expected output: the most-depended-on modules (hubs), any import cycles with the exact files in the loop, and layering violations (e.g. UI importing data-access directly).

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
