---
name: dev-implement-feature
description: "Build a feature end to end from the spec, with edge cases and tests Use when the user explicitly invokes $dev-implement-feature or asks for this dev implement-feature workflow."
---

# Dev Implement Feature

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $fullstack-developer in implement-feature mode for the user's supplied arguments and surrounding request.

Read .solo/ (handoff, tasks, prd, architecture, design). Match the existing codebase's
conventions and libraries. Build vertical slices (data -> logic -> UI) to the design and
architecture, handle unhappy paths (validation, errors, empty/loading states) as you go,
and test the acceptance criteria. Move the task to Doing then Done in .solo/tasks.md and
log decisions.

First use $repo-analyzer (`$repo-map`) to understand the codebase before writing, and check the feature's acceptance criteria in `.solo/`.


Log significant implementation decisions to **`.solo/decisions.md`**.

## Output
After implementation, always output:
- **Files changed**
- **Feature behavior added**
- **Acceptance criteria covered**
- **Tests added or missing**
- **Security concerns**
- **Edge cases handled**
- **Manual verification steps**
- **Suggested tasks** → `.solo/tasks.md` (stable T-IDs)
- **Next skill** — `$dev-code-review` or `$test-integration`

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
