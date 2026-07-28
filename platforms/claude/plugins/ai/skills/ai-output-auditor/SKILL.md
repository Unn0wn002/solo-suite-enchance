---
name: ai-output-auditor
description: Work safely with AI coding agents — sharpen vague prompts, check whether one agent's output is a clean handoff to the next, review AI-generated code for hallucinations and missing files, decide which model should handle a task, and repair failed AI output. Use when the user says improve this prompt, handoff, review AI code, which model, or "the AI output failed". Focuses on catching fake imports, missing files, and unsafe assumptions.
---

# AI Output Auditor

**AgentRoom proposal mode:** an audit finding destined for a memory target under the trusted seat's `proposes` goes to `.solo/proposals/<seat>-<run_id>.md`, with its target and proposed entry, never directly to that target. Only the memory steward merges; missing seat/run identity is a stop condition.

Solo devs orchestrate multiple coding agents; this skill keeps that loop trustworthy. Five modes.

## Mode: prompt-improve (`/ai:prompt-improve`)
Rewrite a vague request into precise agent instructions: the goal, the relevant files/paths and context, hard constraints (stack, style, don't-touch areas), the acceptance criteria (pass/fail), and the exact expected output format. Remove ambiguity that invites guessing.

## Mode: handoff-check (`/ai:handoff-check`)
Given one agent's output that another agent (or a future session) must continue, check it's a clean handoff: is the intent clear, are the changed files and decisions stated, is anything assumed-but-unstated, and is there enough context to continue without re-deriving it? Point out exactly what to add — ideally into `.solo/handoff.md`.

## Mode: review-output (`/ai:review-output`)
Audit AI-generated code for the failure modes models actually have:
- **Hallucinated APIs / fake imports** — libraries, functions, or options that don't exist in the installed versions.
- **Missing files** — references to files it claimed to create but didn't; broken imports; half-applied changes.
- **Unsafe assumptions** — invented env vars, assumed schema/columns, ignored auth/validation, secrets hard-coded.
- **Does it match the request** and did it actually run/build? Flag "looks plausible" code that was never verified.
Report each with severity and the fix.

## Mode: compare-models (`/ai:compare-models`)
Recommend which agent should take a task — e.g. Claude, Codex, or Gemini/Antigravity — based on task type (deep reasoning/refactor/ambiguous vs. boilerplate/scaffolding vs. very large context), not hype. Give a short rationale and note it's a judgment call, not a guarantee; suggest a fallback.

## Mode: repair-cycle (`/ai:repair-cycle`)
Take failed AI output, diagnose *why* it failed (missing context? ambiguous ask? wrong model? unstated constraint?), and produce a rewritten prompt that removes that root cause — so the next attempt succeeds instead of failing the same way.

## Working with other skills
Pairs with `repo-analyzer` (real file/context grounding for reviews) and `.solo/handoff.md` (the handoff artifact). `/gate:before-merge` should not pass AI-written changes that `review-output` flags as critical.

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
