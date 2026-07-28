---
description: Write end-to-end tests for critical user journeys
argument-hint: [the user journey, e.g. signup or checkout]
---
Use the qa-engineer skill in e2e-test mode for: $ARGUMENTS

Read .solo/prd.md for the real user stories. Test only high-value journeys (e2e is slow/
brittle - stay selective, keep the pyramid bottom-heavy): the happy path plus important
failure paths (bad login, declined payment, validation errors). Test what the user sees;
use stable selectors and sensible waits so the suite isn't a maintenance sink.

Base the E2E cases on the **acceptance-criteria-writer** criteria recorded in `.solo/`.


Record what was tested and the results in **`.solo/tests.md`**.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
