---
description: Recommend the highest-leverage next action
argument-hint: [optional focus area]
---
Use the project-memory-manager skill in next-step mode. $ARGUMENTS

Read .solo/handoff.md, tasks.md, prd.md, architecture.md. Recommend ONE next action:
prefer unblocking blocked work, then finishing Doing before starting Todo, then the task
that most de-risks the project (riskiest assumption first). Name the exact task ID, the
first concrete step, and which skill/command to use (e.g. "T15 -> /dev:implement-feature").

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
