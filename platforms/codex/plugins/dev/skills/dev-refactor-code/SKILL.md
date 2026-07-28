---
name: dev-refactor-code
description: "Refactor safely without changing behavior - small steps behind a test net Use when the user explicitly invokes $dev-refactor-code or asks for this dev refactor-code workflow."
---

# Dev Refactor Code

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $fullstack-developer in refactor mode for the user's supplied arguments and surrounding request.

Behavior must not change. Ensure tests cover current behavior first (add characterization
tests if missing), then make one kind of change at a time in small commits, verifying
behavior is identical after each. Target real problems (duplication, unclear names, long
functions, coupling, dead code), not cosmetic churn. If it reveals a design issue, raise
it with software-architect. Note structural changes in .solo/decisions.md.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
