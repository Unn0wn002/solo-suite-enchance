---
name: solo-end-session
description: "End a session - save progress, blockers, decisions, stack changes, and the next task into memory Use when the user explicitly invokes $solo-end-session or asks for this solo end-session workflow."
---

# Solo End Session

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $project-memory-manager in end-session mode. Apply it to the user's supplied arguments and surrounding request.

Close out the session cleanly. Look at what actually happened, then: update task statuses
in .solo/tasks.md (move to Done with date, or Blocked with the reason), append any unlogged
decisions to .solo/decisions.md, record blockers explicitly, and - if the stack changed this
session (new provider, swapped tool, new service added) - update .solo/stack.md and log the
change in decisions.md. Finally rewrite .solo/handoff.md fresh (done this session / current
state / next steps in order / gotchas), ending with the single next task so the next
$solo-start-session resumes instantly. This is the counterpart to $solo-start-session.

After saving, if the user mirrors their project to Obsidian or Grafana, offer to run $solo-sync-obsidian and/or $solo-sync-grafana to reflect the just-saved state outward (don't do it unprompted).

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
