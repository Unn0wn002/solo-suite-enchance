---
description: End a session - save progress, blockers, and next task
argument-hint: [optional notes about this session]
---
Use the project-memory-manager skill in end-session mode. $ARGUMENTS

Close out the session cleanly. Look at what actually happened, then: update task statuses
in .solo/tasks.md (move to Done with date, or Blocked with the reason), append any unlogged
decisions to .solo/decisions.md, record blockers explicitly, and - if the stack changed this
session (new provider, swapped tool, new service added) - update .solo/stack.md and log the
change in decisions.md. Finally rewrite .solo/handoff.md fresh (done this session / current
state / next steps in order / gotchas), ending with the single next task so the next
/solo:start-session resumes instantly. This is the counterpart to /solo:start-session.

After saving, if the user mirrors their project to Obsidian or Grafana, offer to run /solo:sync-obsidian and/or /solo:sync-grafana to reflect the just-saved state outward (don't do it unprompted).

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
