---
description: Check an agent's output is ready for the next agent
argument-hint: [optional output/context]
---
Use the **ai-output-auditor** skill in handoff-check mode. $ARGUMENTS

Check the intent is clear, changed files and decisions are stated, nothing critical is assumed-but-unstated, and there's enough to continue without re-deriving. Say exactly what to add — ideally into `.solo/handoff.md`.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
