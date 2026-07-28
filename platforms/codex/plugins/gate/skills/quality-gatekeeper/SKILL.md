---
name: quality-gatekeeper
description: Decide whether work is ready to continue coding, ready to merge, or ready to deploy — a GO / NO-GO checkpoint. Use when the user says gate, ready to merge, ready to deploy, "can I ship this", or before starting code. Returns a clear verdict plus the exact blockers; hard-blocks on critical gaps rather than averaging them away.
---

# Quality Gatekeeper

**AgentRoom proposal mode:** gate evidence/verdicts remain in output or declared direct artifacts. Any blocker task, risk, or other memory target under the trusted seat's `proposes` must be written to `.solo/proposals/<seat>-<run_id>.md`, not the target. Only the steward merges; missing seat/run identity is a stop condition.

A gate is a decision, not a vibe: **GO** or **NO-GO**, with the specific blockers when it's no-go. It hard-blocks on critical failures (a great average doesn't cancel a missing backup or committed secret). Reads `.solo/` and delegates the deep checks to the specialist plugins. Three modes (a fourth, full-readiness scoring, lives in `production-readiness-reviewer` behind `$gate-production-ready`).

## Mode: before-code (`$gate-before-code`)
Don't let coding start on sand. **Block coding if ANY of these is true:**
- no PRD (`.solo/prd.md` missing or empty)
- no acceptance criteria for what's being built
- no architecture (`.solo/architecture.md`)
- no API/data contract (`.solo/api-contract.md` / `.solo/data-contract.md`) for work that touches API or schema
- no env contract (`.solo/env-contract.md`) for work that needs config/secrets
- no UX flow/design doc (`.solo/design.md`) for user-facing work
- unclear task scope (the `.solo/tasks.md` task has no crisp definition of done)

One missing item = **NO-GO**. Route each blocker to its fix: `$project-prd`, `$spec-acceptance`, `$project-architecture`, `$spec-api-contract`, `$spec-data-contract`, `$spec-env-contract`, `$design-ux-flow`, `$project-task-breakdown`.

## Mode: before-merge (`$gate-before-merge`)
**Block the merge if ANY of these is true:**
- tests missing for the change (or failing) — `$test-*`, `.solo/tests.md`
- code review not recorded for the change — `$dev-code-review` verdict or `$git-pr-review`
- acceptance criteria for the change not demonstrated passing — `.solo/tests.md` against the PRD's criteria
- types/lint failing (run the project's own typecheck/lint; evidence = the command output)
- security pass not done on the change, or an issue found in it (committed secret, missing authz, unvalidated input) — `$security-*` evidence or the `$git-pr-review` security section
- a console error exists on affected pages — `$browser-console-errors`
- a DB migration in the change is not reviewed (forward-safe? reversible?)
- no rollback note (how to undo this change if it breaks)

One failed check = **NO-GO**, with the exact blocker and the command that clears it. AI-written changes flagged critical by `$ai-review-output` also block.

## Mode: before-deploy (`$gate-before-deploy`)
Final pre-flight. **Block the deploy if ANY of these is true:**
- env vars missing in the target environment (check against `.solo/env-contract.md`)
- the stack audits haven't been run for this release — Vercel / Supabase / Cloudflare, plus tags / payments where `.solo/stack.md` says they're in play (`$stack-audit-*`, evidence in `.solo/`)
- no backup (and tested restore path) for the data this deploy touches
- no monitoring (error tracking + uptime) live on the target — `.solo/monitoring.md`
- no rollback plan — `$release-rollback-plan`, `.solo/release.md`

One missing item = **NO-GO**. Record open blockers in `.solo/risks.md` so the next session sees them.

## Verdict rules
State **GO** or **NO-GO** up front. List blockers (must-fix) separately from nits (nice-to-have). Never soften a critical gap; if in doubt, NO-GO and say what would flip it.

## Working with other skills
Orchestrates the specialist plugins: `spec`, `project`, `design`, `dev`, `test`, `security`, `docs`, `release`, `site-doctor`, and `browser`. `$gate-production-ready` uses `production-readiness-reviewer` for the full scored checklist.

## Output
End every run with these seven sections:
1. **Summary** — what was checked or created.
2. **Findings / Work done** — what was found, changed, or decided.
3. **Risks** — anything uncertain, dangerous, incomplete, or blocked.
4. **Required fixes** — must-fix items before moving forward.
5. **Suggested tasks** — concrete entries for `.solo/tasks.md`, each with a stable T-ID.
6. **Verification** — how to prove the result works.
7. **Next skill** — the exact next skill invocation to run.

## Session lifecycle
Runs inside a session the solo plugin bookends: `$solo-start-session` restores `.solo/` context at the start and `$solo-end-session` saves it at the end. Read `.solo/` before acting; write findings, decisions, and tasks back (stable T-IDs) so the next skill — or the next agent — picks up cleanly.

## Stack awareness
Check `.solo/stack.md` first and tailor everything to the real stack. For vendor depth the `$stack-audit-*` skills go further: Cloudflare, Vercel, Supabase, analytics/tags, payments. If a sibling skill or connector isn't installed, do a lighter inline version and say so.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
