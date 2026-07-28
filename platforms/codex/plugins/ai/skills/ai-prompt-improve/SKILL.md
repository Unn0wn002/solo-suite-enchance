---
name: ai-prompt-improve
description: "Rewrite vague coding prompts into precise agent instructions. Use when the user explicitly invokes $ai-prompt-improve or asks for this ai prompt-improve workflow."
---

# AI Prompt Improve

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $ai-output-auditor in prompt-improve mode. Apply it to the user's supplied arguments and surrounding request.

Rewrite into precise instructions: goal, relevant files/context, hard constraints, acceptance criteria (pass/fail), and the exact expected output format. Remove ambiguity that invites guessing.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
