---
name: test-unit
description: "Write unit tests covering logic branches and edge inputs, asserting on behavior Use when the user explicitly invokes $test-unit or asks for this test unit workflow."
---

# Test Unit

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $qa-engineer in unit-test mode for the user's supplied arguments and surrounding request.

Match the project's test framework. Cover every logic branch and edge inputs
(null/empty/zero/negative, boundaries, malformed, unicode). Assert on behavior/outcomes
(not implementation) so tests survive refactoring. Fast, isolated, deterministic; one
clear thing per test with a readable name.


Record what was tested and the results in **`.solo/tests.md`**.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
