---
description: Write integration tests for component seams
argument-hint: [the integration or boundary to test]
---
Use the qa-engineer skill in integration-test mode for: $ARGUMENTS

Test pieces working together: endpoint -> service -> database round-trips against a real
test database (so schema/query bugs surface), module contracts, and external-integration
failure handling (timeouts, errors, bad responses - mock the third party, test your
handling). Cover data integrity and auth enforcement across boundaries.


Record what was tested and the results in **`.solo/tests.md`**.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
