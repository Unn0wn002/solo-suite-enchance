---
description: Gate before merge - tests, types, review, security
argument-hint: [PR or branch]
---
Use the **quality-gatekeeper** skill in before-merge mode. $ARGUMENTS

**Block the merge if ANY is true:** tests missing/failing · types or lint failing (run them; paste the output as evidence) · code review not recorded for the change (`/dev:code-review` or `/git:pr-review` verdict) · acceptance criteria for the change not demonstrated passing (`.solo/tests.md`) · security pass not done on the change (`/git:pr-review` security section or `/security:*` evidence), or an open security issue in it · console error on affected pages (`/browser:console-errors`) · DB migration not reviewed · no rollback note. Critical `/ai:review-output` findings also block. One failed check = NO-GO with the exact blocker.

## Output
End with exactly:
- **Verdict** — GO / NO-GO (one missing blocker = NO-GO; never averaged away)
- **Blockers** — each failed check, with its evidence and the command that clears it
- **Passed checks** — with the evidence for each
- **Nits** — non-blocking improvements
- **Suggested tasks** → `.solo/tasks.md` (stable T-IDs); record open blockers in `.solo/risks.md`
- **Next command** — what clears the top blocker, or the next phase command on GO
