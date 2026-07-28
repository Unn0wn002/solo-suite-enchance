---
description: Plan a safe, ordered, low-risk deployment with post-deploy verification
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

## Plan-only safety boundary

This skill may inspect evidence and write a deployment **plan only**. It must not deploy, run a migration, shift traffic, execute production commands, publish artifacts, or cause any external side effect. Plan approval is not execution authorization. If execution is requested, stop after producing the plan and create a separate handoff that names the environment, exact proposed actions, prerequisites, risks, verification, and rollback trigger. Production execution requires a distinct explicit user confirmation after that handoff and a separately authorized execution workflow or tool.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
