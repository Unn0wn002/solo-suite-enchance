---
name: ai-compare-models
description: "Decide whether Claude, Codex, or Gemini/Antigravity should handle a task. Use when the user explicitly invokes $ai-compare-models or asks for this ai compare-models workflow."
---

# AI Compare Models

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $ai-output-auditor in compare-models mode. Apply it to the user's supplied arguments and surrounding request.

Recommend which agent fits by task type (deep reasoning/refactor/ambiguous vs boilerplate/scaffolding vs very large context), with a short rationale and a fallback. Frame it as a judgment call, not a guarantee.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
