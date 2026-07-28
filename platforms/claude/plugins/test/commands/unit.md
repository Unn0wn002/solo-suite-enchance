---
description: Write unit tests for logic branches and edge inputs
argument-hint: [function, module, or file]
---
Use the qa-engineer skill in unit-test mode for: $ARGUMENTS

Match the project's test framework. Cover every logic branch and edge inputs
(null/empty/zero/negative, boundaries, malformed, unicode). Assert on behavior/outcomes
(not implementation) so tests survive refactoring. Fast, isolated, deterministic; one
clear thing per test with a readable name.


Record what was tested and the results in **`.solo/tests.md`**.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
