---
description: Create testable pass/fail acceptance criteria
argument-hint: <feature or brief>
---
Use the **acceptance-criteria-writer** skill in acceptance mode. $ARGUMENTS

Write Given/When/Then criteria that are objectively pass/fail, covering the happy path plus invalid input, empty/loading/error states, and permissions. Tie each to a stable `.solo/tasks.md` T-ID and note which `/test:e2e` will prove.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
