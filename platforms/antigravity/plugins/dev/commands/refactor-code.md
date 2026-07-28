---
description: Refactor safely behind tests, without behavior change
argument-hint: [what to refactor and why]
---
Use the fullstack-developer skill in refactor mode for: $ARGUMENTS

Behavior must not change. Ensure tests cover current behavior first (add characterization
tests if missing), then make one kind of change at a time in small commits, verifying
behavior is identical after each. Target real problems (duplication, unclear names, long
functions, coupling, dead code), not cosmetic churn. If it reveals a design issue, raise
it with software-architect. Note structural changes in .solo/decisions.md.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
