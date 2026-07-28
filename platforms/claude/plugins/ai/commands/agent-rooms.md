---
description: Set up a multi-agent room from a template
argument-hint: [room: planning | build | qa | hardening | launch]
---
Use the **agent-room-templates** skill. $ARGUMENTS

Pick the room (Planning, Build, QA, Hardening, Launch — or recommend one from `.solo/` state). If a ready-made template fits, load it from the skill's `agentsrooms/` folder (full-team-website, site-doctor-audit, production-release, bug-fix-loop) and adapt; on request, export the room as `solo-suite/agentroom-v1` JSON. Then output each seat with: role, model suggestion (`/ai:compare-models`), the exact `.solo/` files it reads, the commands it runs, its deliverable, and its handoff (checked by `/ai:handoff-check`). Enforce one writer per artifact per stage; a declared later stage may update that artifact sequentially. End with the room's exit gate.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
