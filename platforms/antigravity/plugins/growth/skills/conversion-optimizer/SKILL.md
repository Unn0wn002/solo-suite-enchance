---
name: conversion-optimizer
description: Audit the conversion funnel and find where users drop off and why — CRO for a solo builder. Use when the user says conversion, funnel, drop-off, sign-up rate, CRO, "why aren't people converting", or landing-page/checkout friction. Evidence-based — it checks whether the funnel is even measured and delegates the measurement depth to the site-doctor analytics and forms audits.
---

# Conversion Optimizer

**AgentRoom proposal mode:** when `.solo/tasks.md` or another target is declared under the trusted seat's `proposes`, write the prioritized fixes to `.solo/proposals/<seat>-<run_id>.md` with the intended target, not to the target itself. Only the memory steward merges; stop if seat/run identity is missing. Single-agent runs keep direct memory updates.

Traffic without conversion is a leak. This skill finds the leaks and prioritizes fixes by impact — grounded in evidence, not opinion. It states assumptions rather than inventing numbers, and it isn't financial advice.

## What it does
1. **Map the funnel** — the steps from arrival to the goal (e.g. land → view → sign up → activate → purchase). Name each step and the intended action.
2. **Is it even measured?** — a funnel you can't see, you can't fix. Check that steps are tracked; delegate the depth to `/site-doctor:audit-analytics` (events, goals, attribution). If it's untracked, that's finding #1.
3. **Find friction at each step**:
   - **Clarity**: is the value proposition and next action obvious above the fold?
   - **CTA**: one clear primary action, or competing buttons?
   - **Forms**: length, required fields, error handling — hand deep form checks to `/site-doctor:audit-forms`.
   - **Trust**: social proof, security/payment cues, no dead links.
   - **Speed & mobile**: slow loads and broken mobile layouts kill conversion — pair with `/site-doctor:perf` and `/browser:mobile-test`.
4. **Prioritize** — rank fixes by impact × effort; propose the one or two highest-leverage changes first, and (where relevant) an A/B test to validate rather than guess.

## Working with other skills
Delegates measurement to `/site-doctor:audit-analytics` and form friction to `/site-doctor:audit-forms`; pairs with `/site-doctor:perf` and `/browser:mobile-test`. Writes prioritized fixes to `.solo/tasks.md`.

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
