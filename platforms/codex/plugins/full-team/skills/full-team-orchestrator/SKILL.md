---
name: full-team-orchestrator
description: "Coordinate all 18 Solo Suite component plugins as one profile-aware Codex delivery team, using the authoritative AgentRoom contract, centralized project memory, and evidence gates. Use when the user explicitly invokes $full-team-orchestrator or asks for full-team development, whole-product delivery, or a complete team installation check."
---

# Full Team Orchestrator

This is the authoritative full-team entrypoint. The executable contract is
`plugins/ai/skills/agent-room-templates/agentsrooms/full-team-website.json`;
the durable lifecycle is implemented by its `run_room.py` runner. Read the
generated [`authoritative-flow.md`](references/authoritative-flow.md) and
[`seat-stage-map.md`](references/seat-stage-map.md) for the current stage and
seat map. Do not maintain or follow a second hand-written phase schedule.

## Fail-closed preflight

Run the native preflight before preparing or starting a room. Use the same
Python interpreter that will run the room:

```text
<python> <skill-root>/scripts/preflight.py \
  <suite-root>/plugins/ai/skills/agent-room-templates/agentsrooms/full-team-website.json \
  --suite-root <suite-root>
```

The preflight enforces every component's `minimum_version`, representative
skill, every skill invocation declared by the selected room, and the complete
AgentRoom validator contract. A `FAIL` result stops the run; report the exact
missing plugin, version, skill, or room command and the Codex install command
needed to repair it. `$full-team-verify` is only the reporting wrapper around
this same script.

## One authoritative execution path

After a passing preflight:

1. Select exactly one recognized project profile and run `prepare_run.py`.
2. Initialize the prepared room with `run_room.py init` using the exact commit,
   environment, and prepared-room digest.
3. Create only tasks emitted by `run_room.py next`. Execute seats through Codex
   collaboration tooling or an explicit `run_room.py execute --seat <seat>
   --adapter ...` adapter.
4. Record every result, route shared-memory proposals through the single
   `memory_steward`, and call `advance` only after all current-stage tasks are
   recorded and validated.
5. Let the runner validate gate evidence and route transitions. Before-merge
   or before-deploy `NO-GO` enters the bounded repair/retest loop declared in
   the JSON; prose handoffs cannot bypass it.
6. Stop unless the exact-run, exact-commit, exact-environment production result
   is `SAFE TO LAUNCH`.

`$solo-full-team-dev` is a compatibility invocation. When it is invoked, it
delegates to this orchestrator and reports this room's state; it must not run a
parallel schedule or claim a different authoritative phase order.

## Conditional provider work

The Site Doctor seat declares dedicated animation and SEO audits in addition to
the Site Doctor SEO pass, plus tasks for Vercel, Supabase, Cloudflare, analytics
tags, and payments. Each `$stack-audit-*` task runs only when `.solo/stack.md`
records that provider. If the provider is absent, record a provider-specific,
profile/stack-backed N/A artifact and explain why; never silently skip the task
or turn an inapplicable check into a pass. Growth and other profile-conditional
work follows the same evidence-backed N/A rule.

Keep mutation-capable work explicit: preview external sync, deployment,
migration, browser submission, Git publication, and production operations;
require confirmation before acting. This orchestrator does not publish,
deploy, merge, or submit merely because the room reaches that stage.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
