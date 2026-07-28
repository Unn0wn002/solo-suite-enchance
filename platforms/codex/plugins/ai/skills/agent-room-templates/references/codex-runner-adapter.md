# Codex AgentRoom runner contract

AgentRoom JSON is an immutable orchestration contract. `run_room.py` is its durable, fail-closed coordinator; Codex collaboration tools or an explicit local adapter provide the actual seat execution.

## Start and resume

1. Validate the template with `scripts/validate_rooms.py --suite SUITE_ROOT`.
2. Prepare it with an explicit profile: `scripts/prepare_run.py TEMPLATE OUTPUT --run-id RUN_ID --profile PROFILE --suite SUITE_ROOT --project-root PROJECT_ROOT`. Preparation namespaces every runner-owned artifact and worktree, fingerprints all discoverable `SKILL.md` files, both gate validators, the shared production `gate_policy.py`, and every Python file in the runner's executable dependency chain, then writes a digest-bound, case-folded registry claim. The isolated production validator imports that trusted policy copy, so profile applicability, score normalization, thresholds, and launch status cannot fall back to a different suite file.
3. Initialize once: `scripts/run_room.py init OUTPUT --project-root PROJECT_ROOT --suite SUITE_ROOT --commit SHA --environment NAME`. The commit must be the project root's current HEAD, tracked files must be clean, and untracked inputs outside the prepared plan plus `.solo/`, `artifacts/runs/`, and `worktrees/runs/` are rejected. Initialization rejects preseeded or redirected control roots, installs digest-pinned runtime and validator copies, creates content-level Git manifests for the project and every detached worktree, and rolls back newly created worktrees and control files on failure.
4. Use `run_room.py status` after interruption. State v2 records the exact room/runtime digests, profile, commit, environment, current stage, task leases/baselines, attempts, loop count, results, artifact ownership, command attestations, and validator transcripts. Each revision is a full append-only digest-chain entry checked against a separate project-registry head; `state.json` is only its verified projection. This detects rollback when at least one local authority remains current. Coordinated restoration of every same-user authority requires an OS-protected or remote monotonic anchor. A runner process that dies with an active adapter lease is recovered as persisted `BLOCKED`; its creation identity prevents PID reuse from suppressing recovery, its recorded adapter tree is terminated, and unprovenanced drift is retained for cleanup.
5. If worker commits change the integrated project HEAD, finish integrating every clean worker commit, then run `run_room.py rebind ROOM --project-root PROJECT_ROOT --commit NEW_SHA` before recording any task in the current stage. Rebind verifies that every worker HEAD is an ancestor of the clean project HEAD, recreates all detached worktrees at the new commit, preserves the repair-loop counter, and restarts at discovery so no old-commit evidence can reach production.

## Execute a stage

1. Run `run_room.py next ROOM --project-root PROJECT_ROOT` before dispatch or record. It revalidates the active stage's exact Git heads and tracked bytes, rejects Gitlinks/submodules and assume-unchanged/skip-worktree/fsmonitor concealment, snapshots one immutable stage baseline, and issues only currently dispatchable task leases. Baselines and task contracts are exclusive-create and digest-bound. Same-stage `execute` calls may run in parallel; the OS state lock is held only while leasing or committing state.
2. Give each seat exactly the task's reads, `workspace_root`, private per-lease `artifact_root`, commands, writes, proposal targets, lease identity, baseline digest, and deliverable. Resolve every declared write beneath `artifact_root`, not the project or adapter worktree. The runner validates that private tree and atomically promotes only that seat's declared artifacts; another seat's staged or live output is rejected. Only the memory steward may apply `.solo/` proposals.
3. Return one JSON result per task:

```json
{
  "schema": "solo-suite/agentroom-task-result-v1",
  "task_id": "run:stage:seat:1",
  "lease_id": "<32-hex>",
  "run_id": "run",
  "commit_sha": "<40-hex>",
  "stage": "stage",
  "seat": "seat",
  "status": "PASS",
  "commands_executed": ["$declared-skill"],
  "artifacts": [
    {"path": "artifacts/runs/run/output.json", "digest": "sha256:<64-hex>"}
  ],
  "proposals": [],
  "notes": "What was verified."
}
```

Every passing worker must return every declared write and the exact active `lease_id`. Commands must belong to the seat, files must exist beneath the private artifact root, digests must match, and the seat must own each artifact lock. A proposal item contains only `path`, `content`, and the SHA-256 digest of that UTF-8 content; it does not authorize the worker to write the target. `commands_executed` is still the worker/adapter's attestation: the runner binds it to declared commands and artifacts, but does not yet independently prove that an individual Codex skill ran.

4. Record results with `run_room.py record ROOM RESULT --project-root PROJECT_ROOT`. Record requires the active lease created by `next`, verifies its immutable task/baseline and unredirected private output tree, permits only already-recorded concurrent promotions, and atomically imports the result with verified reverse rollback. Current-commit promoted files are then rehashed at their live project paths. After all current-stage tasks are recorded, call `advance`; it compares the project to the stage baseline and provenance before any transition, while a premature `advance` leaves the run READY instead of poisoning it.
5. For a trusted local executable adapter, use `run_room.py execute ROOM --project-root PROJECT_ROOT --seat SEAT --adapter COMMAND...`. The runner exposes `SOLO_AGENTROOM_TASK`, `SOLO_AGENTROOM_RESULT`, `SOLO_AGENTROOM_WORKSPACE_ROOT`, and the private `SOLO_AGENTROOM_ARTIFACT_ROOT`, runs from the declared workspace, persists its pre-execution snapshot and process creation identity, and blocks invalid output or drift. Private staging and snapshots establish runner ownership; they are not a hostile-process sandbox. A same-user executable can still attempt direct filesystem access, so run untrusted code inside a separately configured OS/container sandbox.

## Gate and loop enforcement

- Phase gates are accepted only after the digest-pinned run-owned phase validator passes under isolated Python mode. Production uses the pinned production validator and independently revalidates the exact-current before-deploy `GO`.
- Gate routing never rereads a mutable live verdict. The runner freezes the exact prepared room, verdict, and transitive current-commit evidence graph into a digest-bound bundle; the validator and router consume those same bytes, and both frozen and live inputs are rehashed afterward.
- The runner additionally binds each cited prerequisite command and digest to the artifact provenance recorded from earlier seat results. A merely allowlisted but unexecuted producer cannot advance the room.
- Only the configured machine-readable status field and its single matching route may change stages. Unknown, missing, or ambiguous statuses stop the run.
- `retry` is available only from persisted BLOCKED state and creates a new attempt for the same stage. It does not erase evidence or clean up unexpected writes.
- `rebind` never relabels old evidence. A commit change restarts evidence collection with new task IDs; production provenance must therefore come from the active commit.
- Every explicit loop re-entry is counted. At `max_iterations`, the runner applies `on_exhaustion_action: stop`, preserves evidence, and refuses another transition.

The runner never grants deployment, merge, publication, production submission, or external-write authority. Those effects remain separately explicit even when a room reaches `SAFE TO LAUNCH`.
