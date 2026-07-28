---
name: git-workflow-manager
description: Manage git and repository workflow — safe branch names, clean grouped commits, PR review, release notes, and syncing tasks to GitHub issues. Use when the user says create a branch, commit, plan commits, review a PR, write release notes, or sync issues. Proposes commands and diffs and asks before anything that writes; never runs destructive git (force-push, hard reset, history rewrite) without explicit confirmation.
---

# Git Workflow Manager

**AgentRoom proposal mode:** when a trusted seat lists a local memory target under `proposes`, put the intended target and idempotent patch/entries in `.solo/proposals/<seat>-<run_id>.md`; never edit the target directly. Only the memory steward merges, and missing seat/run identity stops the local update. This does not bypass the separate user-confirmation boundary for GitHub or git writes.

Keeps version control clean and safe for a solo dev moving fast. **Default to read/plan; confirm before writing.** Never force-push, hard-reset, rebase published history, or delete branches without the user explicitly asking and confirming. Five modes.

## Mode: create-branch (`/git:create-branch`)
Derive a safe branch name from the current task (prefer a `.solo/tasks.md` T-ID if present): `type/scope-short-desc` (e.g. `feat/auth-magic-link`, `fix/T031-cart-total`). Keep it lowercase, hyphenated, no spaces. Confirm the base branch, then give the exact `git checkout -b` command.

## Mode: commit-plan (`/git:commit-plan`)
Review changed files (`git status`/`git diff`) and propose a small set of logical, atomic commits with Conventional-Commit messages (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`). Flag anything that shouldn't be committed — secrets, `.env`, build output, large binaries. Give copy-paste `git add`/`git commit` commands per group; don't commit for the user unless asked.

## Mode: pr-review (`/git:pr-review`)
Review a PR (or a branch diff) across five axes: correctness (logic, edge cases), security (authz, input validation, secrets — lean on `authz-security-reviewer` / `security-review` when available), tests (coverage of the change), docs (updated?), and risk (blast radius, migrations, rollback). Use `repo-analyzer` for context. Verdict: approve / approve-with-nits / request-changes, with specific line-level asks.

## Mode: release-notes (`/git:release-notes`)
Generate two views from commits since the last tag plus `.solo/decisions.md` and Done tasks: **user-facing** (plain-language what's new / fixed / changed) and **technical** (notable changes, migrations, breaking changes, upgrade steps). Group by type; call out anything users must act on.

## Mode: sync-issues (`/git:sync-issues`)
Bridge `.solo/tasks.md` and GitHub issues via `connector-auditor`. Map tasks to issues (create missing ones, one issue per T-ID, keep the T-ID in the title/body for idempotency), and/or pull issue status back into `tasks.md`. Confirm before creating or closing anything; report a diff first (would-create / would-update / would-close).

## Working with other skills
`sync-issues` and `pr-review` (live PR data) use `connector-auditor` for GitHub. `pr-review` uses `repo-analyzer`, `authz-security-reviewer`, and the `test`/`docs` plugins. `create-branch` reads the current task from `.solo/tasks.md`.

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
