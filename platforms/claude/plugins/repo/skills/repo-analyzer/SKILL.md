---
name: repo-analyzer
description: Understand a whole codebase before editing it. Use for mapping structure, entry points, and key files; finding risky/fragile/complex areas and missing tests; showing internal module/service dependencies; finding dead code (unused files, exports, routes, components, packages); and generating a new-developer onboarding guide from the actual code. Use when the user says map the repo, risk map, dependency map, dead code, onboarding, "understand this codebase", or before implementing/reviewing a change. Read-only — it inspects and reports, it never edits.
---

# Repo Analyzer

**AgentRoom proposal mode:** this role remains read-only over the repository. Any memory finding/task/decision whose target appears under the trusted seat's `proposes` goes to `.solo/proposals/<seat>-<run_id>.md`, with target and proposed entries, and never directly into the target. Only the memory steward merges; missing seat/run identity is a stop condition.

Read before you write. This skill builds an accurate picture of the codebase so edits are safe and reviews are grounded. **Don't guess from filenames — open files, follow imports, and respect the framework's conventions.** Use any repo tooling that exists (package scripts, lockfiles, tsconfig, framework config) as ground truth. It has five modes.

## Mode: map (`/repo:map`)
Produce a structural map: languages/frameworks, entry points (server, client, CLI, workers), routing (pages/API routes), config and env files, build/deploy setup, and what each top-level folder is *for*. Call out where the important logic lives (auth, data access, payments) and how a request flows end to end.

## Mode: risk-map (`/repo:risk-map`)
Find where breakage and bugs concentrate: large/God files, deep nesting and high branching, duplicated logic, security-sensitive code (auth, payments, file upload, raw SQL), areas with no tests, and fragile glue (implicit contracts, magic strings, timezone/money handling). Rank by likelihood × blast radius. Pair with `/repo:find-dead-code` and `/security:threat-model`.

## Mode: dependency-map (`/repo:dependency-map`)
Show internal dependencies — which modules/services import which — and surface import cycles, layering violations (UI importing DB directly), and hub files that everything depends on. Distinguish internal deps from third-party packages.

## Mode: find-dead-code (`/repo:find-dead-code`)
Find unused files, unexported/unused exports, unreachable routes, orphan components, and unused packages. **Be conservative:** dynamic imports, reflection, framework auto-loading, and string-based routing can make code look dead when it isn't — flag candidates with a confidence level and the reason, and never delete; suggest removals as tasks for human confirmation.

## Mode: onboarding (`/repo:onboarding`)
Generate a new-developer guide from the *actual* codebase: how to run it locally, required env vars (cross-check `.solo/` env contract if present), the folder tour, the main flows, where to add a typical feature, testing, and the gotchas from the risk map. Written so a new dev is productive on day one.

## Working with other skills
`/dev:implement-feature` and `/dev:code-review` should call this first for context. Feeds `/repo:risk-map` into `/security:threat-model` and `/gate:*`. Uses `.solo/architecture.md` when present to confirm intended vs actual structure.

## Output
End every run with these seven sections:
1. **Summary** — what was checked or created.
2. **Findings / Work done** — what was found, changed, or decided.
3. **Risks** — anything uncertain, dangerous, incomplete, or blocked.
4. **Required fixes** — must-fix items before moving forward.
5. **Suggested tasks** — concrete entries for `.solo/tasks.md`, each with a stable T-ID.
6. **Verification** — how to prove the result works.
7. **Next command** — the exact next slash command to run.

## Session lifecycle
Runs inside a session the solo plugin bookends: `/solo:start-session` restores `.solo/` context at the start and `/solo:end-session` saves it at the end. Read `.solo/` before acting; write findings, decisions, and tasks back (stable T-IDs) so the next command — or the next agent — picks up cleanly.

## Stack awareness
Check `.solo/stack.md` first and tailor everything to the real stack. For vendor depth the `/stack:audit-*` skills go further: Cloudflare, Vercel, Supabase, analytics/tags, payments. If a sibling skill or connector isn't installed, do a lighter inline version and say so.
