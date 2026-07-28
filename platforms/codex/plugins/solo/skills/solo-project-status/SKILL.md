---
name: solo-project-status
description: "Roll up project status - progress, blockers, decisions, risks, next step Use when the user explicitly invokes $solo-project-status or asks for this solo project-status workflow."
---

# Solo Project Status

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $project-memory-manager in project-status mode. Apply it to the user's supplied arguments and surrounding request.

Read .solo/ (tasks, prd, decisions, handoff). Report done/doing/blocked counts and
highlights, completion estimate against PRD scope, recent decisions, risks (stale blocked
tasks, drift between the PRD and what's actually being built), and the recommended next
step. Suitable to paste into a standup or to re-orient after time away.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
