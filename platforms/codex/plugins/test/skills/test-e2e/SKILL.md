---
name: test-e2e
description: "Write end-to-end tests for the critical user journeys through the whole stack Use when the user explicitly invokes $test-e2e or asks for this test e2e workflow."
---

# Test E2E

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $qa-engineer in e2e-test mode for the user's supplied arguments and surrounding request.

Read .solo/prd.md for the real user stories. Test only high-value journeys (e2e is slow/
brittle - stay selective, keep the pyramid bottom-heavy): the happy path plus important
failure paths (bad login, declined payment, validation errors). Test what the user sees;
use stable selectors and sensible waits so the suite isn't a maintenance sink.

Base the E2E cases on the $acceptance-criteria-writer criteria recorded in `.solo/`.


Record what was tested and the results in **`.solo/tests.md`**.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
