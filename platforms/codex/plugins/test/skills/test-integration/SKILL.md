---
name: test-integration
description: "Write integration tests for the seams where components and services meet Use when the user explicitly invokes $test-integration or asks for this test integration workflow."
---

# Test Integration

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $qa-engineer in integration-test mode for the user's supplied arguments and surrounding request.

Test pieces working together: endpoint -> service -> database round-trips against a real
test database (so schema/query bugs surface), module contracts, and external-integration
failure handling (timeouts, errors, bad responses - mock the third party, test your
handling). Cover data integrity and auth enforcement across boundaries.


Record what was tested and the results in **`.solo/tests.md`**.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
