---
name: deployment-review
description: Review a deployment pipeline and release process — CI/CD configuration, build reproducibility, environment parity (dev/staging/prod), rollback safety, zero-downtime deployment strategy, database migration handling in releases, secrets in pipelines, and release gates. Use whenever the user wants to review their CI/CD, deploy process, release workflow, GitHub Actions/GitLab CI/Jenkins config, asks "is my deploy safe", "how do I do zero-downtime deploys", worries about breaking prod on release, or is setting up a pipeline. Complements infrastructure-audit and database-fix.
---

# Deployment Review

The deploy is where working code meets production reality — and where most outages are born, because most incidents follow a change. A good pipeline makes releases boring: reproducible, reversible, and safe to run while users are live. Review the pipeline config and the release process for those three properties.

## Setup

Get the CI/CD config (`.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, CircleCI, etc.), the deploy target (which infra), and how migrations and env config are handled at release time. Understand what "deploy" actually does today before judging it.

## 1. Build & CI

- **Reproducible builds**: pinned dependency versions (lockfile committed and used — `npm ci` not `npm install`), pinned tool/runtime versions, pinned base images. A build that pulls "latest" of anything isn't reproducible and will surprise you.
- **Quality gates before deploy**: tests run and must pass; linting/type-checking; a build step that actually catches breakage. A pipeline that deploys without running tests is deploying blind.
- **Security in CI**: dependency audit (`npm audit`/`pip-audit`) and secret scanning run in the pipeline; SAST if the stakes justify it (hand off to dependency-audit / security-review).
- **Fast enough to be used**: if CI takes 40 minutes, people batch changes and skip it — cache dependencies, parallelize, so the pipeline is run per-change.

## 2. Secrets in the pipeline

- Secrets injected from the CI provider's secret store or a secrets manager — **never** hardcoded in workflow YAML, never echoed to logs, never committed.
- Least-privilege deploy credentials (a scoped deploy token/role, not an admin key); different credentials per environment; secrets masked in log output.
- Third-party actions/plugins pinned to a SHA (not a moving tag) so a compromised action can't inject code into your build — a real supply-chain vector.

## 3. Environment parity (dev / staging / prod)

- Environments as similar as practical — same runtime version, same major dependency versions, same-ish data shape. "Works in staging, breaks in prod" is almost always a parity gap (config, env vars, data volume, Node version, case-sensitive filesystem).
- **Config via environment, not code**: 12-factor style — the same build artifact promoted across environments with config injected, rather than rebuilding per environment. Rebuilding per env means you never tested exactly what ships.
- A real staging environment that mirrors prod and gets deployed to first; smoke tests run there before promoting.

## 4. Rollback safety (the thing people skip until they need it)

- **A tested, fast rollback path**: can you revert to the previous version in minutes, and has it actually been tried? Blue-green / canary / keeping the last artifact ready all give this. "Roll forward with a hotfix" is not a rollback plan when prod is down.
- **Migrations must be backward-compatible** so a rollback doesn't strand the schema ahead of the reverted code — this is the #1 rollback trap. Use expand → migrate → contract (add columns, dual-write, switch, remove later) so old and new code both work during the window. Hand off to database-fix for the migration mechanics.
- Rollback restores the artifact AND is safe with the current database state — think about both together.

## 5. Zero-downtime deployment

- **Strategy fits the stakes**: rolling / blue-green / canary rather than stop-old-start-new (which is a visible outage every deploy). Health checks gate traffic shifting so a broken new version doesn't receive requests.
- **Graceful shutdown**: old instances drain in-flight requests before terminating (connection draining, SIGTERM handling) — no dropped requests mid-deploy.
- Backward-compatible releases so old and new versions coexist during the rollout (the whole point of rolling deploys); feature flags to decouple deploy from release where useful.
- **Database migrations run safely against live traffic**: no long exclusive locks during peak, additive-first, run before or separately from the code that needs them (again → database-fix).

## 6. Release process & readiness

- Deploys are automated and consistent, not a manual sequence of steps someone remembers (or forgets) — the manual runbook is where human error enters.
- Post-deploy verification: automated smoke tests / health checks after release; monitoring watched during and after (hand off to observability); ability to detect a bad deploy fast via error-rate and latency alerts tied to release version.
- Deploy timing/approvals appropriate (avoid Friday-5pm deploys with no one around); a changelog or deploy log so you know what shipped when — most incident diagnosis starts with "what changed."

## Report format

Shared audit structure (Summary → Scorecard → Findings → Fix order), grouped **Build/CI / Secrets / Parity / Rollback / Zero-downtime / Process**. Each finding names the pipeline file/step and the concrete fix. Rank by risk of causing or prolonging an outage — no tested rollback and backward-incompatible migrations top the list. Route migration specifics to database-fix, infra specifics to infrastructure-audit, and post-deploy monitoring to observability.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
