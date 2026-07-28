---
description: Run the complete profile-aware full-team development cycle through the authoritative Codex AgentRoom flow.
argument-hint: [optional feature or project focus, optionally a profile like "profile: saas-application"]
---
`/full-team:orchestrator` owns the full-team schedule and execution contract.
This command-derived skill is retained for compatibility with the Claude-era
invocation name; it delegates immediately to the same AgentRoom rather than
maintaining a second 16-phase checklist.

Invoke `/full-team:orchestrator` and follow its generated
`references/authoritative-flow.md` and `references/seat-stage-map.md`. The
authoritative source is
`plugins/ai/skills/agent-room-templates/agentsrooms/full-team-website.json`;
`preflight.py`, `prepare_run.py`, and `run_room.py` are the only accepted
coordination path. The runner emits the next task, binds it to the selected
profile/commit/environment, records each seat result, and validates gate
transitions. Do not invent tasks from prose or continue after a failed gate.

If the full-team plugin is unavailable, stop with a degraded-mode report that
names the missing plugin and lost checks. Do not silently substitute an
unsupervised sequence of specialist skills. A single-agent fallback may use
the same room runner with one explicit adapter, but it still follows the JSON
stage order and evidence rules.

All profile-conditional work must be explicit. In particular, run the five
`/stack:audit-*` provider tasks only when `.solo/stack.md` records Vercel,
Supabase, Cloudflare, analytics tags, or payments; otherwise record an
evidence-backed N/A for each provider. Manual-only browser, sync, deployment,
secret, migration, and production actions remain preview/confirmation-gated.
