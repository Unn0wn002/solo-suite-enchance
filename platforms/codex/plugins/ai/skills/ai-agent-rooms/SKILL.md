---
name: ai-agent-rooms
description: "Set up a multi-agent room from a template — seats, context packages, deliverables, handoffs, and the exit gate. Use when the user explicitly invokes $ai-agent-rooms or asks for this ai agent-rooms workflow."
---

# AI Agent Rooms

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $agent-room-templates. Apply it to the user's supplied arguments and surrounding request.

Pick the room (Planning, Build, QA, Hardening, Launch — or recommend one from `.solo/` state). If a ready-made template fits, load it from the skill's `agentsrooms/` folder (full-team-website, site-doctor-audit, production-release, bug-fix-loop) and adapt; on request, export the room as `solo-suite/agentroom-v1` JSON. Then output each seat with: role, model suggestion (`$ai-compare-models`), the exact `.solo/` files it reads, the skills it invokes, its deliverable, and its handoff (checked by `$ai-handoff-check`). Enforce one writer per artifact per stage; a declared later stage may update that artifact sequentially. End with the room's exit gate.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
