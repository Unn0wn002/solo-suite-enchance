---
name: solo-handoff-memory
description: "Save a session handoff into project memory so the next session resumes instantly Use when the user explicitly invokes $solo-handoff-memory or asks for this solo handoff-memory workflow."
---

# Solo Handoff Memory

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $project-memory-manager in handoff mode. Apply it to the user's supplied arguments and surrounding request.

Look at what actually happened this session (files changed, tasks progressed, decisions
made). Rewrite .solo/handoff.md fresh (done this session / current state / next steps in
order / gotchas), update task statuses in .solo/tasks.md, and append any unlogged
decisions to .solo/decisions.md. Be concrete in next steps - the reader is a cold-start
future session. If .solo/ doesn't exist, offer to initialize it.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
