---
name: agent-room-templates
description: "Prepare, execute, resume, and validate bounded Codex multi-agent workflows with explicit stages, isolated worktrees, artifact locks, one memory steward, gate evidence, and bounded loops. Use for agent rooms, full-team parallel work, multi-agent planning, bug-fix loops, production-release rooms, or Site Doctor audit rooms."
---

# Run AgentRoom workflows

Treat `agentsrooms/*.json` as immutable orchestration contracts. Use the bundled state-machine runner to emit and verify tasks; it coordinates Codex collaboration or an explicit adapter but never invents agents, deploys, merges, or publishes. Read `references/codex-runner-adapter.md` before starting seats.

Validate all bundled rooms:

```text
<python> <skill-root>/scripts/validate_rooms.py --suite <suite-root>
```

Instantiate one room with a unique run ID:

```text
<python> <skill-root>/scripts/prepare_run.py <template.json> <run.json> --run-id <unique-lowercase-id> --profile <profile> --suite <suite-root> --project-root <project-root>
```

Initialize and drive the prepared room:

```text
<python> <skill-root>/scripts/run_room.py init <run.json> --project-root <project-root> --suite <suite-root> --commit <sha> --environment <name>
<python> <skill-root>/scripts/run_room.py next <run.json> --project-root <project-root>
<python> <skill-root>/scripts/run_room.py record <run.json> <result.json> --project-root <project-root>
<python> <skill-root>/scripts/run_room.py advance <run.json> --project-root <project-root>
```

Use `status` to resume and `retry` only after a persisted BLOCKED result. Always call `next` before `record`; it issues an immutable task contract and lease against one project baseline. Write only beneath the task's private `artifact_root` and echo its `lease_id` in the result; the runner atomically promotes declared artifacts. After integrating worker commits, use `rebind --commit <new-head>` before the next task; this verifies ancestry and tracked bytes, recreates the worktrees, and restarts exact-commit evidence collection without resetting loop exhaustion. `execute --seat <seat> --adapter <command...>` may run a trusted local adapter inside the declared workspace; adapters can overlap, but hostile executables still require an OS/container sandbox. Prefer `next` plus Codex collaboration tools when Codex supplies the workers.

Available templates:

- `full-team-website.json`: all product, architecture, design, frontend, backend, database, QA, browser QA, security, DevOps, release, documentation, Git/PR, repo-analysis, AI-review, growth, and Site Doctor roles; profile-aware checks; fail-closed before-code, before-merge, before-deploy, and 14-category production gates.
- `bug-fix-loop.json`: reproduce, fix, verify, review, security, and before-merge evidence with a maximum of three repair iterations.
- `site-doctor-audit.json`: parallel site and provider audit followed by centralized triage and scoring.
- `production-release.json`: collect all 14 category records, prepare a preview-only release plan and documentation in dependency order, pass before-deploy, and then run the production gate.

Keep exactly one `memory-steward` seat. All other seats propose shared-memory changes; only the steward writes `.solo/tasks.md`, `.solo/decisions.md`, `.solo/handoff.md`, or other `.solo/` files and allocates stable task IDs.

Use only an instantiated plan with `prepared: true` and an explicitly bound profile. Preparation fingerprints every skill, both gate validators, and the complete runner dependency chain; initialization installs those exact bytes, pins filtered tracked-file manifests for the project/worktrees, and creates an append-only digest-chained state journal. The runner binds immutable tasks, baselines, unredirected lease-private outputs, runner/adapter process identities, live artifact provenance, frozen gate bundles, transitions, and loop counters. It rejects Gitlinks/submodules, hidden Git index flags, tracked-byte drift, preseeded/redirected control paths, forged or independently rolled-back state projections, cross-seat writes, changed/deleted promoted artifacts, substituted runtime code, missing/stale evidence, identity mismatches, unknown statuses, and exhausted loops. Coordinated rollback of all same-user journal authorities requires an OS-protected or remote monotonic anchor. `commands_executed` remains an adapter/worker attestation until a trusted receipt implementation verifies individual commands; never describe it as cryptographic execution proof. Production additionally requires the prepared profile contract and independently revalidated before-deploy `GO`. Do not deploy, merge, submit forms, or perform external writes merely because a room names that workflow; those actions remain explicit and confirmation-gated.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
