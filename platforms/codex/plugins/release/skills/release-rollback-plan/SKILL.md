---
name: release-rollback-plan
description: "Prepare a rollback plan BEFORE deploying - fast revert, data safety, triggers Use when the user explicitly invokes $release-rollback-plan or asks for this release rollback-plan workflow."
---

# Release Rollback Plan

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $devops-engineer in rollback-plan mode for the user's supplied arguments and surrounding request.

Write this before deploying. Cover: the exact fast path back (and how long it takes),
data safety on rollback (backward-compatible migrations so reverting code doesn't strand
the schema; handling data the new version wrote), the specific triggers that mean "roll
back now" (error spike, key flow broken, health failing), and how to verify recovery.
Include lighter mitigations (feature-flag off, scale up). Pairs with site-doctor
incident-response.


Record the plan in **`.solo/release.md`**.

## Plan-only safety boundary

This skill may inspect evidence and write a rollback **plan only**. It must not revert a deployment, run database recovery, change traffic, execute production commands, publish artifacts, or cause any external side effect. Plan approval is not execution authorization. If execution is requested, stop after producing the plan and create a separate handoff that names the environment, exact proposed actions, data-safety prerequisites, risks, recovery verification, and abort condition. Production rollback execution requires a distinct explicit user confirmation after that handoff and a separately authorized execution workflow or tool.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
