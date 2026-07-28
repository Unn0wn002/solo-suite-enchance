---
name: ai-handoff-check
description: "Check if one agent's output is clear enough for the next agent. Use when the user explicitly invokes $ai-handoff-check or asks for this ai handoff-check workflow."
---

# AI Handoff Check

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $ai-output-auditor in handoff-check mode. Apply it to the user's supplied arguments and surrounding request.

Check the intent is clear, changed files and decisions are stated, nothing critical is assumed-but-unstated, and there's enough to continue without re-deriving. Say exactly what to add — ideally into `.solo/handoff.md`.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
