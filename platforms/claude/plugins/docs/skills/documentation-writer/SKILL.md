---
name: documentation-writer
description: Act as the documentation writer for a solo developer — keep the README and project docs current, document the API, and write a setup/getting-started guide someone can actually follow. Use when the user wants docs written or updated, a README, API documentation, a setup/installation/onboarding guide, or asks "document this", "write the docs", "explain how to run this". Reads .solo/ (prd, architecture) so docs match reality; distinct from in-code comments.
---

# Documentation Writer

**AgentRoom proposal mode:** when the trusted seat contract lists a `.solo/` target under `proposes`, record the intended target and patch/entries in `.solo/proposals/<seat>-<run_id>.md` rather than editing it. Only the memory steward merges; stop if seat/run identity is unavailable. Repository documentation in the seat's direct `writes` remains a normal direct write.

Solo developers skip docs because they hold everything in their head — until they don't (three months later, or the day someone else needs to run the project, or when they open-source it). This skill writes documentation that's accurate, followable, and worth maintaining: enough to onboard a stranger (or forgetful-future-you) without over-documenting things that'll just go stale. Good docs are the difference between a project others can use and a black box.

## Memory & context first

Read `.solo/prd.md` (what the project *is* and who it's for — shapes the framing) and `architecture.md` (stack, how it's structured, API surface — the source material for technical docs). **Docs must match reality**: read the actual code/config for real commands, real env vars, real endpoints — never document aspirational or assumed behavior. If docs and `.solo/` disagree with the code, the code wins; flag the drift.

## Principle: right-sized, accurate, current

- **Accurate over comprehensive**: wrong docs are worse than none — they actively mislead. Every command and example must actually work; test them.
- **Followable**: written for someone without your context. Assume no tribal knowledge; spell out prerequisites and steps; a stranger should get from zero to running by following along.
- **Maintainable**: document what's stable and load-bearing; don't over-document volatile internals that'll drift out of date. Docs you won't keep current shouldn't exist.
- **Skimmable**: clear headings, short paragraphs, code blocks for anything typed, examples over prose.

## Mode: README / docs update (`/docs:update`)

Create or refresh the README and core docs. A good solo-project README covers:
- **What it is** — one or two sentences: what it does and who it's for (pull from the PRD).
- **Status** — if relevant (WIP, alpha), so expectations are set.
- **Quick start** — the shortest path to running it (points to the setup guide for detail).
- **Key features / usage** — what it does and how to use the main bits, with examples.
- **Tech stack** — briefly, so a reader knows what they're dealing with.
- **Project structure** — a short orientation to where things live, if non-obvious.
- **Links** — to setup guide, API docs, contributing notes if any.
When updating, reconcile against the current code and `.solo/` — fix anything that's drifted (old commands, renamed things, changed config). Keep a changelog if the project warrants one.

## Mode: API docs (`/docs:api`)

Document the API so someone can call it without reading the source. Derive from `architecture.md` and the actual route/handler code. Per endpoint/operation:
- Method + path (or operation name), what it does.
- Auth required; parameters (path/query/body) with types and which are required.
- Request example and response example (real shapes, real values).
- Status codes / error responses and what they mean.
- Notes: rate limits, pagination, gotchas.
Keep it consistent and example-driven. (This pairs with site-doctor's `api-audit`, which checks the API's design/security — docs and audit reinforce each other.) Generate from an OpenAPI/GraphQL schema if one exists rather than hand-maintaining.

## Mode: setup guide (`/docs:setup-guide`)

The "get it running from scratch" guide — the highest-value doc for a solo project going public or onboarding help. Walk through, in order, tested end-to-end:
- **Prerequisites**: exact tools and versions (runtime, database, package manager, accounts/keys needed).
- **Installation**: clone, install dependencies — real commands, copy-pasteable.
- **Configuration**: every required env var (name, what it's for, example/how to get it); config files to create; where secrets come from. Don't leave a hidden required variable undocumented — that's the #1 setup-guide failure.
- **Database/services setup**: migrations to run, seed data, any external service setup.
- **Running it**: the actual command(s) to start it; how to verify it's working (what you should see).
- **Common problems**: the errors a new setup hits and their fixes — this is where you save the reader (and future-you) hours.
Test the whole path as if you'd never seen the project; a setup guide with a missing step is worse than none.

## Mode: runbook (`/docs:runbook`)
Write an operational runbook for a recurring task or service: what it does and when to run it, prerequisites and access, the exact step-by-step procedure (copy-pasteable commands), how to verify success, common failures and their fixes, rollback/recovery, and escalation. Keep it usable at 3am under pressure.

## Working with other skills & plugins

Source material comes from **product-manager** (the what/why) and **software-architect** (the how); docs are a checklist item in **devops-engineer**'s `/release:preflight`. Your API docs complement **site-doctor**'s `api-audit`, and its `content-audit` can later check your docs for staleness and broken links. Keep docs in sync with `.solo/` and the code, and note significant doc updates in `handoff.md` so their state is part of project memory.

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
