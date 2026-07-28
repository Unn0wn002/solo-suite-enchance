---
description: Plan a safe, ordered deploy with verification
argument-hint: [release + target environment]
---
Use the devops-engineer skill in deploy-plan mode for: $ARGUMENTS

Read .solo/architecture.md for what's deployed where. Produce ordered steps: backup ->
migrate (backward-compatible, before/separate from dependent code) -> deploy -> verify
health -> shift traffic -> smoke test. Prefer simple + safe (rolling/blue-green/platform-
managed) over stop-start; graceful shutdown; migrations safe against live traffic; sane
timing. Specify exactly what to check post-deploy. Deep mechanics -> site-doctor
deployment-review. Record what shipped in .solo/.


Record the plan in **`.solo/release.md`**.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
