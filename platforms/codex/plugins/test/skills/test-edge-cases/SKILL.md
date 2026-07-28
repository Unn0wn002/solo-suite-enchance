---
name: test-edge-cases
description: "Hunt the edge cases the happy path misses - a prioritized break-it list Use when the user explicitly invokes $test-edge-cases or asks for this test edge-cases workflow."
---

# Test Edge Cases

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $qa-engineer in edge-case mode for the user's supplied arguments and surrounding request.

Systematically probe input (empty/null/huge/negative/malformed/injection/unicode/
boundaries), state (empty/first-run, concurrent, double-submit, out-of-order, stale,
session expiry), environment (network failure, dependency down, timeout, partial
failure), and failure modes (what if each external call fails - graceful or corrupt?).
Deliver a list prioritized by likelihood x impact. Route concurrency/limits to
site-doctor load-testing, security to security-review.


Record what was tested and the results in **`.solo/tests.md`**.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
