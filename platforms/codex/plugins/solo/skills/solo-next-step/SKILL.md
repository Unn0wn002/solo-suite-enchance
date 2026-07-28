---
name: solo-next-step
description: "Recommend the single highest-leverage next action, with reasoning Use when the user explicitly invokes $solo-next-step or asks for this solo next-step workflow."
---

# Solo Next Step

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $project-memory-manager in next-step mode. Apply it to the user's supplied arguments and surrounding request.

Read .solo/handoff.md, tasks.md, prd.md, architecture.md. Recommend ONE next action:
prefer unblocking blocked work, then finishing Doing before starting Todo, then the task
that most de-risks the project (riskiest assumption first). Name the exact task ID, the
first concrete step, and which skills to use (e.g. "T15 -> $dev-implement-feature").

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
