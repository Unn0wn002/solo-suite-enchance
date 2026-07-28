---
description: Propose a GitHub Actions CI pipeline as YAML
argument-hint: [optional workflow name or CI provider]
---
Use the **devops-engineer** skill in ci-setup mode. $ARGUMENTS

Read `.solo/stack.md` (runtime, package manager, test runner) and `.solo/env-contract.md` (env-var *names* only — values belong in repository/environment secrets, referenced by name). Reuse the project's own `lint` / `typecheck` / `test` scripts from `package.json` or equivalent — don't invent parallel ones.

Propose one minimal workflow (default `.github/workflows/ci.yml`, or the provider named): on PR and the default branch — checkout → setup runtime with dependency cache → install → lint → typecheck → tests, fail fast. Optional extras only where the stack warrants them (a build step; `self_check.py` when the repo is a plugin suite like solo-suite itself). No deploy step — deploys stay with `/release:deploy-plan`.

**Propose, don't push:** show the full YAML and its path; write it only after confirmation. Suggest the branch-protection rule that makes these checks required — that's the CI backstop for `/gate:before-merge`'s types/lint/tests blockers. Log follow-ups in `.solo/tasks.md`.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
