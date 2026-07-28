---
description: Diagnose failed AI output and rewrite the prompt
argument-hint: [optional failed output]
---
Use the **ai-output-auditor** skill in repair-cycle mode. $ARGUMENTS

Diagnose the root cause of the failure (missing context? ambiguous ask? wrong model? unstated constraint?) and produce a rewritten prompt that removes that cause so the next attempt succeeds.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
