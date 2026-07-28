---
description: Gate before coding - PRD, criteria, architecture, design
argument-hint: [optional feature]
---
Use the **quality-gatekeeper** skill in before-code mode. $ARGUMENTS

**Block coding if ANY is true:** no PRD · no acceptance criteria · no architecture · no API/data contract (for API/schema work) · no env contract (for config/secret work) · no UX flow/design doc (`.solo/design.md`) for user-facing work · unclear task scope. Verify each against the actual `.solo/` files (name the file checked as evidence). One missing item = NO-GO, routed to its fix command.

## Output
End with exactly:
- **Verdict** — GO / NO-GO (one missing blocker = NO-GO; never averaged away)
- **Blockers** — each failed check, with its evidence and the command that clears it
- **Passed checks** — with the evidence for each
- **Nits** — non-blocking improvements
- **Suggested tasks** → `.solo/tasks.md` (stable T-IDs); record open blockers in `.solo/risks.md`
- **Next command** — what clears the top blocker, or the next phase command on GO
