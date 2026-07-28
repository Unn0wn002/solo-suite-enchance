---
description: Design stack, components, data model, API surface
argument-hint: [what to design, or "from the PRD"]
---
Use the software-architect skill for: $ARGUMENTS

Read .solo/prd.md first (get a PRD from /project:prd if none exists). Write
.solo/architecture.md: a maintainer-fit stack (boring, few moving parts, justified),
components with clear boundaries, a data model (prefer TEXT+CHECK over ENUMs,
app-generated UUIDs, migration-ready), and the API surface. Challenge every piece for
over-engineering. Log major choices + alternatives in .solo/decisions.md. Defer infra/
deploy/DB-migration depth to devops-engineer and site-doctor.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
