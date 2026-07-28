---
name: release-deploy-plan
description: "Plan a safe, ordered, low-risk deployment with post-deploy verification Use when the user explicitly invokes $release-deploy-plan or asks for this release deploy-plan workflow."
---

# Release Deploy Plan

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $devops-engineer in deploy-plan mode for the user's supplied arguments and surrounding request.

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

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
