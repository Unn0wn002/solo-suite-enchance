---
name: acceptance-criteria-writer
description: Turn rough product ideas into a clear feature brief and testable, pass/fail acceptance criteria. Use when the user says feature brief, acceptance criteria, "define done", user stories, or is starting a feature and needs crisp requirements before design or code. Produces criteria concrete enough to drive E2E tests and a quality gate.
---

# Acceptance Criteria Writer

Ambiguity is where solo projects stall and AI agents hallucinate. This skill makes "done" explicit *before* anyone builds. Two modes, often run back to back.

## Mode: feature-brief (`/spec:feature-brief`)
Turn a rough idea into a short, decision-ready brief: the problem, the goal, who it's for, the core user story, in-scope vs **non-goals** (equally important), constraints, and what success looks like. Keep it tight — a page, not a novel. Write it into `.solo/prd.md` (append/update the relevant feature section).

## Mode: acceptance (`/spec:acceptance`)
Convert the brief (or an existing feature) into **testable** acceptance criteria:
- Use **Given / When / Then** so each criterion is unambiguous and checkable.
- Cover the happy path **and** the edges: invalid input, empty states, loading, failure/error, permissions (who can/can't), and boundaries.
- Each criterion must be objectively pass/fail — no "works well", "fast", "intuitive" without a measurable definition.
- Tie criteria to stable `.solo/tasks.md` T-IDs and note which will be proven by `/test:e2e`.

Flag criteria you had to assume (mark them so the user can confirm), and list open questions rather than inventing answers.

## Working with other skills
Feeds `/project:prd` (the brief/criteria live in the PRD) and `/test:e2e` (criteria become test cases). `/gate:before-code` checks these exist and are clear; `/gate:production-ready` checks stories have acceptance criteria.

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
