---
description: Save a handoff so the next session resumes instantly
argument-hint: [optional notes about this session]
---
Use the project-memory-manager skill in handoff mode. $ARGUMENTS

Look at what actually happened this session (files changed, tasks progressed, decisions
made). Rewrite .solo/handoff.md fresh (done this session / current state / next steps in
order / gotchas), update task statuses in .solo/tasks.md, and append any unlogged
decisions to .solo/decisions.md. Be concrete in next steps - the reader is a cold-start
future session. If .solo/ doesn't exist, offer to initialize it.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
