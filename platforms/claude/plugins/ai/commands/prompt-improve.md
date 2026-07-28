---
description: Rewrite a vague prompt into precise agent instructions
argument-hint: <prompt>
---
Use the **ai-output-auditor** skill in prompt-improve mode. $ARGUMENTS

Rewrite into precise instructions: goal, relevant files/context, hard constraints, acceptance criteria (pass/fail), and the exact expected output format. Remove ambiguity that invites guessing.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
