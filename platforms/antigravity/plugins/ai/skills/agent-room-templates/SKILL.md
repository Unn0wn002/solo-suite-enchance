---
name: agent-room-templates
description: Ready-made multi-agent "room" templates for running a phase of work with several AI coding agents in parallel or sequence — who's in the room, what context each agent gets from .solo/, what each produces, and how the handoff works. Use when the user says agent rooms, AgentRooms, multi-agent workflow, "set up a room", parallel agents, or wants to split a phase across Claude/Codex/Gemini-style agents cleanly.
---

# Agent Room Templates

A "room" is a small, purpose-built team of AI agents working one phase together: each seat has a role, a context package (the exact `.solo/` files it reads), a deliverable, and a handoff target. Rooms keep multi-agent work from turning into contradictory edits — one writer per artifact per stage, everything flowing through `.solo/`.

> Interpretation note: this implements "AgentRooms" as reusable multi-agent workflow templates. If AgentRooms is a specific product/tool you use, say so — the templates port to it directly.

## Room rules (all templates)
- **One writer per artifact per stage** — two seats never edit the same `.solo/` file or code area concurrently in one stage. A declared later stage may update the same artifact sequentially.
- **Context is explicit** — each seat is handed named `.solo/` files, not "the whole repo, good luck".
- **Every seat ends with a handoff** — checked by `/ai:handoff-check` before the next seat starts.
- **Model routing** — pick who sits where with `/ai:compare-models`; audit anything produced with `/ai:review-output`.

## The templates

### 1. Planning Room
Seats: **PM agent** (reads `project.md`, writes `prd.md` — `/project:prd`, `/spec:feature-brief`) → **Architect agent** (reads `prd.md`, writes `architecture.md`, `api-contract.md`, `data-contract.md`, `env-contract.md` — `/project:architecture`, `/spec:*`) → **Criteria agent** (writes acceptance criteria into the PRD — `/spec:acceptance`). Exit gate: `/gate:before-code`.

### 2. Build Room
Seats: **Implementer** (reads `tasks.md` + contracts, builds one task — `/dev:implement-feature`, logs to `decisions.md`) → **Reviewer** (independent agent, ideally a different model — `/dev:code-review`, `/ai:review-output`). Sequence per task: implement → review → fix. Exit gate: `/gate:before-merge`.

### 3. QA Room
Seats: **Test writer** (writes/executes `/test:unit`, `/test:integration`, `/test:e2e` → `tests.md`) ∥ **Browser QA** (`/browser:console-errors`, `/browser:visual-check`, `/browser:mobile-test` → `bugs.md`). Runs in parallel; both feed `bugs.md`/`tasks.md`. `/browser:smoke-test` and `/browser:form-submit-test` are state-changing, manual-only commands: Browser QA may return an exact human test handoff but never places either command in its agent command list or invokes it.

### 4. Hardening Room
Seats: **Security agent** runs static `/security:threat-model` and
`/security:authz-matrix` → `risks.md`. Live `/security:rls-test` is manual-only:
the agent may prepare a disposable-test-tenant plan but must hand invocation
to the human; it never runs automatically in the room. **Auditor agent** runs
`/site-doctor:full-checkup`, `/stack:audit-*` → `tasks.md`. Exit: findings
triaged, criticals fixed.

### 5. Launch Room
Seats: **Release agent** (`/release:preflight`, `/release:deploy-plan`, `/release:rollback-plan`, `/site-doctor:monitoring`, then `/gate:before-deploy` → `release.md` + `monitoring.md`) → **Docs agent** (`/docs:update`, `/docs:setup-guide`, `/docs:runbook`, `/git:release-notes`; in a stewarded room it submits a handoff proposal) → **Memory steward** runs `/solo:handoff-memory` after docs and BEFORE the freeze (a compact non-stewarded room instead lets docs update its declared handoff directly) → *orchestrator freeze: commit everything, record FINAL_SHA in untracked `.solo/run-state/`* → **Evidence Finalization Coordinator** verifies the freeze and returns the structured `human_handoff`, then PAUSES while the user invokes manual-only `/gate:finalize-evidence`, reviews its preview, and separately confirms execution → coordinator verifies all 14 records → **Gatekeeper** (`/gate:production-ready`, OUTPUT-ONLY). Nothing ships on a BLOCKED verdict.

## Ready-made JSON templates (`agentsrooms/`)
Four machine-readable room files ship with this skill, one per common job. **They are validated work-order specifications, not an executable runtime** — execution is documented in `references/runner.md`: drive them with the shipped Claude Code agent definitions (`plugins/ai/agents/room-*.md`, one per seat role) or any external orchestrator, pasting a seat's entry as that agent's work order:

- `agentsrooms/full-team-website.json` — idea → launch, 21 staged seats across 15 stages (discovery → architecture → design → build → **integrate** → review → AI review → qa → hardening → growth → merge → release → docs → **finalize** → launch-gate) plus the stage-independent memory steward — 22 seat definitions total; the /solo:full-team-dev flow's 17 specialist roles plus the mechanical integrator, code-review, evidence-finalization coordinator and output-only gatekeeper seats; every staged seat maps to a shipped `room-*` agent and the steward's structured cutoff is `active_through_stage: "docs"`
- `agentsrooms/site-doctor-audit.json` — parallel site + vendor audit, then triage into a fix order (exit gate: `/gate:score-project`)
- `agentsrooms/production-release.json` — preflight + plans + monitoring → deploy gate → docs → orchestrator freeze (structured `evidence.freeze` contract) → evidence-finalization coordinator → explicit user preview/confirmation handoff → OUTPUT-ONLY launch gate
- `agentsrooms/bug-fix-loop.json` — reproduce → fix → verify, **looping** until the repro dies (with an /ai:repair-cycle escape hatch)

Schema (`solo-suite/agentroom-v1`, formal contract in `schema/agentroom-v1.schema.json` — applied FIRST by the validator, so malformed root/seat/stage/run/profile/gate-map/loop types come back as validation errors, never crashes): `stages` (objects `{id, seats[]}` with unique ids; seats sharing a stage run in parallel; legacy list-of-lists still accepted), `seats[]` each with `role`, `model_hint`, `reads`/`writes` (exact `.solo/` files), optional `proposes` (shared-memory proposals for the steward), optional `workspace` (owned worktree), optional `applies_to`, agent-invokable `commands`, optional structured `human_handoff` (manual-only command, `executor: user`, mandatory preview and confirmation, explicit resume condition), `deliverable`, `handoff_to`, and `handoff_check`; room-level `memory_steward`, `locks`, required `run`, profiles/rules, gate contracts, optional bounded loops, and the `worktrees` execution contract. A manual-only command is invalid in `commands`; it may appear only in `human_handoff`, where the runner must pause.

**Graph model (the one documented model).** Nodes are the seats active for the profile under evaluation (a seat with `applies_to` is skipped for other profiles; an UNSTAGED memory steward is out-of-band and excluded). Edges are `handoff_to` targets, contracted through skipped seats. Entry = the active seats of the first active stage; exit = **the single seat whose `commands` contain the `exit_gate`** (exactly one executor is required — there is no last-stage fallback). Every active seat must be reachable from an entry seat AND reach the exit seat, for the profile-free pass and for every declared profile; only the exit seat may have a null `handoff_to`. Handoffs point strictly forward; repetition is declared only via the explicit bounded `loop` block; a null `exit_gate` requires an `exit_gate_note`.

**Worktree execution contract (`worktrees`).** Claude worktree agents branch from the **default branch**, not the parent session HEAD — so any room with `workspace: "worktree:…"` seats must declare: `base_sha` (recorded only through `update_run_state.py`, never by typing JSON), `builder_payload` (worktree_path, branch, clean commit_sha, tests, proposal), `proposal_transport` (the canonical `.solo/proposals/<seat>-<run_id>.json` payload is committed inside the builder branch; the integrator reads it with `git show`, merges the exact payload SHA, and only then can the steward consume it), `integration`, and `verify_at_integration_sha`. Rooms with an evidence lifecycle also declare `verify_at_final_sha` for the coordinator and gatekeeper. The bug-fix room's verifier tests the fixer's exact commit, never the unchanged main workspace.

**Gate evidence producers are category-specific, but manual authority stays with the user.** With exit gate `/gate:production-ready`, `gate_evidence_map` covers all 14 categories and the room carries an `evidence` lifecycle block plus a real `room-evidence-finalizer` coordinator. The coordinator has `commands: []` and an exact `human_handoff` for `/gate:finalize-evidence`; it verifies the freeze, returns the invocation inputs, and pauses. The user-invoked command owns its own preview → explicit confirmation → execution boundary and creates every concrete `.solo/gate-evidence/<category>.json`. The coordinator then verifies those stage outputs before the gatekeeper runs. No other seat writes records mid-flow, and the steward cutoff remains strictly before finalize.

**Implicit writes and proposal mode are validated.** The validator knows which suite commands write shared memory as a side effect (site-doctor audits write tasks/decisions/handoff; `/dev:implement-feature` writes tasks/decisions; project, QA, browser, security, release, docs, repo, growth, and gate commands declare their lifecycle effects). A direct implicit effect counts as an effective write. When a trusted seat declares that same target under `proposes`, the command and every transitive skill switch to AgentRoom proposal mode: create a proposal payload for `.solo/proposals/<seat>-<run_id>.md` with the intended target and patch/entries, never mutate the steward-owned target. A write-capable seat may persist that file itself; a least-privilege read-only seat returns the exact structured payload and the trusted runner materializes it verbatim before the steward runs. The runner never invents or edits proposal content. The validator rejects undeclared effects, proposals without a steward, proposals for targets the steward does not own, direct writes to steward-owned paths, same-stage direct collisions, and metadata-marked manual-only commands in executable seat `commands`. The steward's duplicate-T-ID contract is checkable with `check_tasks_file()`.

To customize: copy a file, edit seats/stages, keep one-writer-per-artifact-per-stage true, then re-run `python3 "${CLAUDE_PLUGIN_ROOT}/skills/agent-room-templates/scripts/validate_rooms.py"` (stdlib; uses the `jsonschema` library when installed, otherwise a built-in strict evaluator; use `python` if `python3` is missing) — it applies the JSON Schema first, then checks seat/stage placement, entry→exit reachability per profile, the single exit-gate executor, per-stage writers (declared + implicit), steward/proposal discipline, locks, workspaces, the worktrees execution contract, category-specific gate-evidence producers, bounded loops, and that every referenced command exists.

## Output of this skill
When asked for a room, output: the template name, each seat with (role, model suggestion, exact `.solo/` context files, commands to run, deliverable), the sequence/parallelism, and the exit gate — ready to paste into each agent's first prompt.

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
