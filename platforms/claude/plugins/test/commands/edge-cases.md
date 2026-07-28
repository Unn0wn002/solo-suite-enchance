---
description: Hunt the edge cases the happy path misses
argument-hint: [feature or area to probe]
---
Use the qa-engineer skill in edge-case mode for: $ARGUMENTS

Systematically probe input (empty/null/huge/negative/malformed/injection/unicode/
boundaries), state (empty/first-run, concurrent, double-submit, out-of-order, stale,
session expiry), environment (network failure, dependency down, timeout, partial
failure), and failure modes (what if each external call fails - graceful or corrupt?).
Deliver a list prioritized by likelihood x impact. Route concurrency/limits to
site-doctor load-testing, security to security-review.


Record what was tested and the results in **`.solo/tests.md`**.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
