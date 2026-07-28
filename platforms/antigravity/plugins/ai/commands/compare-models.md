---
description: Choose Claude, Codex, or Gemini for a task
argument-hint: <task>
---
Use the **ai-output-auditor** skill in compare-models mode. $ARGUMENTS

Recommend which agent fits by task type (deep reasoning/refactor/ambiguous vs boilerplate/scaffolding vs very large context), with a short rationale and a fallback. Frame it as a judgment call, not a guarantee.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
