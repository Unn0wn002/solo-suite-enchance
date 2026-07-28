---
name: release-ci-setup
description: "Generate or refresh a CI pipeline (GitHub Actions) running install → lint → typecheck → tests on every PR — proposed as YAML, never pushed unconfirmed. Use when the user explicitly invokes $release-ci-setup or asks for this release ci-setup workflow."
---

# Release CI Setup

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $devops-engineer in ci-setup mode. Apply it to the user's supplied arguments and surrounding request.

Read `.solo/stack.md` (runtime, package manager, test runner) and `.solo/env-contract.md` (env-var *names* only — values belong in repository/environment secrets, referenced by name). Reuse the project's own `lint` / `typecheck` / `test` scripts from `package.json` or equivalent — don't invent parallel ones.

Propose one minimal workflow (default `.github/workflows/ci.yml`, or the provider named): on PR and the default branch — checkout → setup runtime with dependency cache → install → lint → typecheck → tests, fail fast. Optional extras only where the stack warrants them (a build step; `self_check.py` when the repo is a plugin suite like solo-suite itself). No deploy step — deploys stay with `$release-deploy-plan`.

**Propose, don't push:** show the full YAML and its path; write it only after confirmation. Suggest the branch-protection rule that makes these checks required — that's the CI backstop for `$gate-before-merge`'s types/lint/tests blockers. Log follow-ups in `.solo/tasks.md`.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
