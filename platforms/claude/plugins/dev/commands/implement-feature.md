---
description: Build a feature end to end from the spec, with tests
argument-hint: [feature name or task ID]
---
Use the fullstack-developer skill in implement-feature mode for: $ARGUMENTS

Read .solo/ (handoff, tasks, prd, architecture, design). Match the existing codebase's
conventions and libraries. Build vertical slices (data -> logic -> UI) to the design and
architecture, handle unhappy paths (validation, errors, empty/loading states) as you go,
and test the acceptance criteria. Move the task to Doing then Done in .solo/tasks.md and
log decisions.

First use **repo-analyzer** (`/repo:map`) to understand the codebase before writing, and check the feature's acceptance criteria in `.solo/`.


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
- **Next command** — `/dev:code-review` or `/test:integration`
