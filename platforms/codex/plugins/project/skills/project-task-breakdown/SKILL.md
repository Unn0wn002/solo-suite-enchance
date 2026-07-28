---
name: project-task-breakdown
description: "Break the PRD/architecture into an ordered, right-sized task list Use when the user explicitly invokes $project-task-breakdown or asks for this project task-breakdown workflow."
---

# Project Task Breakdown

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $product-manager in task-breakdown mode for the user's supplied arguments and surrounding request.

Read .solo/prd.md and .solo/architecture.md. Write .solo/tasks.md using the shared
format (stable T-IDs; Doing/Todo/Blocked/Done). Tasks are vertical slices, sized to one
focused session, ordered by dependency and risk (unblockers and risky assumptions
first), each mapped back to a user story. This feeds $solo-next-step.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
