---
name: solo-full-team-dev
description: "Run the complete profile-aware full-team development cycle through the authoritative Codex AgentRoom flow. Use when the user explicitly invokes $solo-full-team-dev or asks for this solo full-team-dev workflow."
---

# Solo Full Team Dev

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

`$full-team-orchestrator` owns the full-team schedule and execution contract.
This compatibility skill delegates immediately to the same AgentRoom rather than
maintaining a second checklist.

Invoke `$full-team-orchestrator` and follow its generated
`references/authoritative-flow.md` and `references/seat-stage-map.md`. The
authoritative source is
`plugins/ai/skills/agent-room-templates/agentsrooms/full-team-website.json`;
`preflight.py`, `prepare_run.py`, and `run_room.py` are the only accepted
coordination path. The runner emits the next task, binds it to the selected
profile/commit/environment, records each seat result, and validates gate
transitions. The hardening stage explicitly runs both `$site-doctor-animation`
and `$seo-audit` in addition to the Site Doctor SEO pass.

If the full-team plugin is unavailable, stop with a degraded-mode report that
names the missing plugin and lost checks. Do not silently substitute an
unsupervised sequence of specialist skills. A single-agent fallback may use
the same room runner with one explicit adapter, but it still follows the JSON
stage order and evidence rules.

All profile-conditional work must be explicit. In particular, run the five
`$stack-audit-*` provider tasks only when `.solo/stack.md` records Vercel,
Supabase, Cloudflare, analytics tags, or payments; otherwise record an
evidence-backed N/A for each provider. Manual-only browser, sync, deployment,
secret, migration, and production actions remain preview/confirmation-gated.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
