---
name: project-architecture
description: "Design the technical architecture - stack, components, data model, API surface Use when the user explicitly invokes $project-architecture or asks for this project architecture workflow."
---

# Project Architecture

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $software-architect for the user's supplied arguments and surrounding request.

Read .solo/prd.md first (get a PRD from $project-prd if none exists). Write
.solo/architecture.md: a maintainer-fit stack (boring, few moving parts, justified),
components with clear boundaries, a data model (prefer TEXT+CHECK over ENUMs,
app-generated UUIDs, migration-ready), and the API surface. Challenge every piece for
over-engineering. Log major choices + alternatives in .solo/decisions.md. Defer infra/
deploy/DB-migration depth to devops-engineer and site-doctor.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
