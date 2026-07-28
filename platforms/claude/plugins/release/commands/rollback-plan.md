---
description: Prepare a rollback plan before deploying
argument-hint: [the release being deployed]
---
Use the devops-engineer skill in rollback-plan mode for: $ARGUMENTS

Write this before deploying. Cover: the exact fast path back (and how long it takes),
data safety on rollback (backward-compatible migrations so reverting code doesn't strand
the schema; handling data the new version wrote), the specific triggers that mean "roll
back now" (error spike, key flow broken, health failing), and how to verify recovery.
Include lighter mitigations (feature-flag off, scale up). Pairs with site-doctor
incident-response.


Record the plan in **`.solo/release.md`**.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
