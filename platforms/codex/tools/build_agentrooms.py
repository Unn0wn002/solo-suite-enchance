#!/usr/bin/env python3
"""Build the strict Solo Suite AgentRoom v1 templates deterministically."""

from __future__ import annotations

import importlib.util
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ROOM_ROOT = ROOT / "plugins" / "ai" / "skills" / "agent-room-templates"
FULL_TEAM_REFERENCE_ROOT = (
    ROOT / "plugins" / "full-team" / "skills" / "full-team-orchestrator" / "references"
)
VALIDATOR_PATH = ROOM_ROOT / "scripts" / "validate_rooms.py"
PHASE_EVIDENCE_FIELDS = [
    "schema", "room_digest", "run_id", "gate_id", "project", "commit_sha", "environment",
    "timestamp", "expires_at", "reviewer", "decision", "checks", "blockers",
]
SCORE_EVIDENCE_FIELDS = [
    "schema", "run_id", "gate_id", "project", "commit_sha", "environment",
    "timestamp", "expires_at", "reviewer", "categories", "total_score",
    "normalized_score", "assessment_status", "risks",
]
PRODUCTION_EVIDENCE_FIELDS = [
    "schema", "room_digest", "run_id", "gate_id", "project_profile",
    "profile_artifact", "profile_artifact_digest", "project", "commit_sha", "environment",
    "timestamp", "expires_at", "reviewer", "categories", "total_score",
    "normalized_score", "launch_status", "blockers", "warnings",
]
EVIDENCE_CONTRACTS = {
    "$gate-before-code": (
        "solo-suite/phase-gate-evidence-v1", PHASE_EVIDENCE_FIELDS, "decision"),
    "$gate-before-merge": (
        "solo-suite/phase-gate-evidence-v1", PHASE_EVIDENCE_FIELDS, "decision"),
    "$gate-before-deploy": (
        "solo-suite/phase-gate-evidence-v1", PHASE_EVIDENCE_FIELDS, "decision"),
    "$gate-score-project": (
        "solo-suite/score-evidence-v1", SCORE_EVIDENCE_FIELDS,
        "assessment_status"),
    "$gate-production-ready": (
        "solo-suite/gate-evidence-v1", PRODUCTION_EVIDENCE_FIELDS,
        "launch_status"),
}
VENDOR_AUDIT_COMMANDS = {
    "$stack-audit-vercel": "Vercel",
    "$stack-audit-supabase": "Supabase",
    "$stack-audit-cloudflare": "Cloudflare",
    "$stack-audit-tags": "Analytics/tag",
    "$stack-audit-payments": "Payments",
}


def load_validator():
    spec = importlib.util.spec_from_file_location("room_validator", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load AgentRooms validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_validator()
PRODUCTION_CATEGORIES = list(VALIDATOR.PRODUCTION_CATEGORIES)


def worker(
    seat_id: str,
    role: str,
    commands: list[str],
    reads: list[str],
    writes: list[str],
    deliverable: str,
    *,
    kind: str = "worker",
    model: str = "balanced",
    proposals: list[str] | None = None,
) -> dict[str, Any]:
    proposal_set = set(proposals or [])
    for command in commands:
        proposal_set.update(VALIDATOR.implicit_writes(command))
    proposal_set.update(VALIDATOR.implicit_writes("$ai-handoff-check"))
    return {
        "id": seat_id,
        "kind": kind,
        "persistent": False,
        "role": role,
        "model_hint": model,
        "workspace": f"{seat_id}_workspace",
        "memory_access": "propose-only",
        "reads": sorted(set(reads)),
        "writes": sorted(set(writes)),
        "proposals": sorted(proposal_set),
        "commands": commands,
        "deliverable": deliverable,
        "handoff_to": None,
        "handoff_check": "$ai-handoff-check",
        "task_ids": [],
    }


def gate(
    gate_id: str,
    command: str,
    stage: str,
    seat_id: str,
    prerequisites: list[tuple[str, str]],
    evidence_artifact: str,
    *,
    routes: list[dict[str, Any]],
    max_age_hours: int = 24,
    required_gate_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    evidence_schema, required_fields, status_field = EVIDENCE_CONTRACTS[command]
    result = {
        "id": gate_id,
        "command": command,
        "stage": stage,
        "seat": seat_id,
        "prerequisites": [
            {"category": category, "artifact": artifact}
            for category, artifact in prerequisites
        ],
        "evidence": {
            "artifact": evidence_artifact,
            "schema": evidence_schema,
            "required_fields": required_fields,
            "freshness": {
                "run_id": "exact",
                "commit": "exact",
                "environment": "exact",
                "max_age_hours": max_age_hours,
            },
        },
        "transitions": {
            "status_field": status_field,
            "routes": routes,
            "default_action": "stop",
        },
    }
    if required_gate_results:
        result["required_gate_results"] = required_gate_results
    return result


def build_room(
    *,
    name: str,
    description: str,
    profile: str,
    stage_specs: list[tuple[str, list[dict[str, Any]]]],
    gates: list[dict[str, Any]],
    exit_gate: str | None,
    exit_criteria: str,
    based_on: str,
    extra_rules: list[str] | None = None,
    loop: dict[str, Any] | None = None,
) -> dict[str, Any]:
    seats = [seat for _, stage_seats in stage_specs for seat in stage_seats]
    ids = [seat["id"] for seat in seats]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate seat in {name}")

    # Bind every gate prerequisite to the exact command set of its one
    # declared producer. Runtime evidence must reproduce this mapping instead
    # of substituting an unrelated artifact or plausible-looking $skill name.
    producers: dict[str, list[dict[str, Any]]] = {}
    for seat in seats:
        for artifact in seat["writes"]:
            producers.setdefault(artifact, []).append(seat)
    for gate_spec in gates:
        for prerequisite in gate_spec["prerequisites"]:
            matches = producers.get(prerequisite["artifact"], [])
            if len(matches) != 1:
                raise ValueError(
                    f"gate prerequisite {prerequisite['artifact']} in {name} "
                    f"must have exactly one producer"
                )
            commands = sorted(set(matches[0]["commands"]))
            if not commands:
                raise ValueError(
                    f"gate prerequisite {prerequisite['artifact']} in {name} "
                    "has no producing commands"
                )
            prerequisite["producer_commands"] = commands

    # Workers hand off to the next stage. Gatekeepers route only through their
    # machine-readable transitions, and a loop source routes only through the
    # explicit bounded loop block.
    gate_seats = {gate_spec["seat"] for gate_spec in gates}
    loop_source = loop.get("from_stage") if isinstance(loop, dict) else None
    for index, (stage_id, stage_seats) in enumerate(stage_specs):
        if index + 1 < len(stage_specs):
            next_ids = [seat["id"] for seat in stage_specs[index + 1][1]]
            target: str | list[str] = next_ids[0] if len(next_ids) == 1 else next_ids
            for seat in stage_seats:
                seat["handoff_to"] = (
                    None if seat["id"] in gate_seats or stage_id == loop_source
                    else target
                )
        else:
            for seat in stage_seats:
                seat["handoff_to"] = None

    all_solo = {
        artifact
        for seat in seats
        for field in ("reads", "proposals")
        for artifact in seat[field]
        if artifact.startswith(".solo/")
    }
    all_solo.update({".solo/tasks.md", ".solo/decisions.md", ".solo/handoff.md"})
    steward = {
        "id": "memory_steward",
        "kind": "memory-steward",
        "persistent": True,
        "role": "Memory Steward",
        "model_hint": "strong-reasoning",
        "workspace": "shared_memory",
        "memory_access": "direct",
        "reads": sorted(all_solo),
        "writes": sorted(all_solo),
        "proposals": [],
        "commands": [],
        "deliverable": (
            "Allocate unique task IDs; merge proposals into tasks, decisions, and "
            "handoffs; reject conflicting shared-memory updates."
        ),
        "handoff_to": None,
        "handoff_check": None,
        "task_ids": [],
    }

    workspaces = [
        {"id": "shared_memory", "type": "shared-memory", "path": ".solo/",
         "owner": "memory_steward"}
    ] + [
        {"id": seat["workspace"], "type": "worktree",
         "path": f"worktrees/{name}/{seat['id']}", "owner": seat["id"]}
        for seat in seats
    ]

    locks: dict[str, str] = {artifact: "memory_steward" for artifact in all_solo}
    for seat in seats:
        for artifact in seat["writes"]:
            owner = locks.setdefault(artifact, seat["id"])
            if owner != seat["id"]:
                raise ValueError(f"unsafe simultaneous writers for {artifact}")
    for gate_spec in gates:
        evidence = gate_spec["evidence"]["artifact"]
        owner = gate_spec["seat"]
        if evidence not in locks:
            locks[evidence] = owner

    rules = [
        "Replace the template run_id with a unique run id before execution.",
        "Only memory_steward writes .solo files; every other seat submits declared proposals.",
        "Run seats in isolated worktrees and enforce every artifact lock.",
        "Require exact run, commit, and environment matches; reject expired gate evidence.",
        "Evaluate gate transitions from validated machine-readable status fields; unknown or missing statuses stop the run.",
        "Execute provider-specific checks only when .solo/stack.md records that provider.",
        "For profile-inapplicable work, record an evidence-backed N/A reason instead of silently skipping it.",
    ]
    rules.extend(extra_rules or [])

    room = {
        "$schema": "../schema/agentroom-v1.schema.json",
        "schema": "solo-suite/agentroom-v1",
        "name": name,
        "version": 1,
        "prepared": False,
        "run_id": f"template-{name}-v1",
        "description": description,
        "based_on_room": based_on,
        "profile": profile,
        "memory_dir": ".solo/",
        "rules": rules,
        "memory_steward": {
            "seat_id": "memory_steward",
            "task_id_pattern": "^T[0-9]+$",
            "proposal_merge_policy": (
                "Allocate task IDs centrally and merge conflict-free proposals after "
                "each stage while preserving append-only decisions."
            ),
            "conflict_policy": (
                "Stop the stage and require an explicit resolution before any "
                "conflicting shared-memory proposal is committed."
            ),
        },
        "tasks": [],
        "workspaces": workspaces,
        "artifact_locks": [
            {"artifact": artifact, "owner": owner}
            for artifact, owner in sorted(locks.items())
        ],
        "stages": [
            {"id": stage_id,
             "seats": ["memory_steward"] + [seat["id"] for seat in stage_seats]}
            for stage_id, stage_seats in stage_specs
        ],
        "seats": [steward] + seats,
        "gates": gates,
        "exit_gate": exit_gate,
        "exit_criteria": exit_criteria,
    }
    if loop is not None:
        room["loop"] = loop
    return room


def _room_json_bytes(room: dict[str, Any]) -> bytes:
    """Return the exact deterministic representation written for a room."""

    return (json.dumps(room, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _room_digest(room: dict[str, Any]) -> str:
    return hashlib.sha256(_room_json_bytes(room)).hexdigest()


def _seat_index(room: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(seat["id"]): seat
        for seat in room.get("seats", [])
        if isinstance(seat, dict) and isinstance(seat.get("id"), str)
    }


def render_full_team_seat_stage_map(room: dict[str, Any]) -> str:
    """Render the human-readable seat/stage map from the room contract.

    The JSON remains authoritative.  This generated document is intentionally
    boring: it exposes every stage, seat, role, and command so a reviewer can
    inspect the actual execution contract without hand-maintained summaries.
    """

    seats = _seat_index(room)
    digest = _room_digest(room)
    lines = [
        "# Full-team AgentRoom seat/stage map",
        "",
        "> Generated by `tools/build_agentrooms.py`; do not edit by hand.",
        "> The JSON room and `run_room.py` are authoritative for execution.",
        "",
        f"- Source: `plugins/ai/skills/agent-room-templates/agentsrooms/{room['name']}.json`",
        f"- Room JSON SHA-256: `{digest}`",
        f"- Stages: **{len(room.get('stages', []))}**",
        f"- Seats (including the memory steward): **{len(room.get('seats', []))}**",
        "",
        "| Stage | Seat | Role | Commands | Handoff check |",
        "|---|---|---|---|---|",
    ]
    for stage in room.get("stages", []):
        stage_id = str(stage.get("id"))
        stage_seats = stage.get("seats", [])
        for seat_id in stage_seats:
            seat = seats.get(str(seat_id), {})
            role = str(seat.get("role", "(missing seat definition)"))
            commands = seat.get("commands", [])
            rendered = "<br>".join(f"`{command}`" for command in commands) or "(steward)"
            handoff = seat.get("handoff_check")
            rendered_handoff = f"`{handoff}`" if handoff else "-"
            lines.append(
                f"| `{stage_id}` | `{seat_id}` | {role} | {rendered} | {rendered_handoff} |"
            )
    lines.extend([
        "",
        "## Execution notes",
        "",
        "- Every stage includes the single `memory_steward`; worker seats submit proposals and do not write shared `.solo/` memory directly.",
        "- A seat is executed through Codex collaboration tooling or `run_room.py execute --seat <seat> --adapter ...`; this package has no per-seat agent files.",
        "- Commands beginning with `$stack-audit-` are conditional: run them only when `.solo/stack.md` records the provider; otherwise record an evidence-backed N/A artifact for that provider.",
        "- The runner emits the next task, records the result, and validates the gate transition. A prose phase list cannot replace the runner state.",
        "",
    ])
    return "\n".join(lines)


def render_full_team_authoritative_flow(room: dict[str, Any]) -> str:
    """Render the single authoritative full-team flow from the room JSON."""

    digest = _room_digest(room)
    seats = _seat_index(room)
    lines = [
        "# Authoritative full-team flow",
        "",
        "> Generated by `tools/build_agentrooms.py`; do not edit by hand.",
        "> `$full-team-orchestrator` is the canonical entrypoint. `$solo-full-team-dev` is a compatibility alias that delegates here; it owns no separate schedule.",
        "",
        f"The authoritative contract is `plugins/ai/skills/agent-room-templates/agentsrooms/{room['name']}.json` (SHA-256 `{digest}`). The executable lifecycle is:",
        "",
        "1. Run the Full Team preflight (`plugins/full-team/skills/full-team-orchestrator/scripts/preflight.py`) against the selected room and suite root.",
        "2. Prepare the room with `prepare_run.py`, selecting exactly one recognized project profile and recording the prepared-room digest.",
        "3. Use `run_room.py init`, then emit only tasks returned by `run_room.py next`; execute each seat through Codex collaboration or an explicit adapter.",
        "4. Record every seat result, merge shared-memory proposals through `memory_steward`, and call `advance` only after the current stage is complete.",
        "5. Let the runner validate gate evidence and route the next stage. A failed before-merge/before-deploy gate enters the bounded repair/retest loop in the JSON contract.",
        "6. Stop at the production gate unless the exact-run, exact-commit, exact-environment result is `SAFE TO LAUNCH`.",
        "",
        "## Stage order",
        "",
    ]
    for index, stage in enumerate(room.get("stages", []), start=1):
        stage_id = str(stage.get("id"))
        names = []
        for seat_id in stage.get("seats", []):
            seat = seats.get(str(seat_id), {})
            role = str(seat.get("role", seat_id))
            names.append(f"`{seat_id}` ({role})")
        lines.append(f"{index}. **{stage_id}** - " + ", ".join(names))
    lines.extend([
        "",
        "## Profile-conditional provider work",
        "",
        "The Site Doctor seat declares one task for each provider audit. `$stack-audit-vercel`, `$stack-audit-supabase`, `$stack-audit-cloudflare`, `$stack-audit-tags`, and `$stack-audit-payments` run only when `.solo/stack.md` records that provider. For an absent provider, the seat records a profile/stack-backed N/A artifact; it does not silently skip the task or claim a pass.",
        "",
        "## Entrypoints",
        "",
        "- `$full-team-orchestrator` - authoritative coordinator and preflight owner.",
        "- `$solo-full-team-dev` - legacy/compatibility invocation; immediately delegates to the same authoritative room and reports the room runner's state.",
        "- `$full-team-verify` - reporting wrapper around the native preflight; it does not maintain a second dependency or stage implementation.",
        "",
    ])
    return "\n".join(lines)


def write_full_team_docs(room: dict[str, Any], *, check: bool = False) -> None:
    """Write (or verify) generated full-team reference documents."""

    expected = {
        FULL_TEAM_REFERENCE_ROOT / "seat-stage-map.md": render_full_team_seat_stage_map(room),
        FULL_TEAM_REFERENCE_ROOT / "authoritative-flow.md": render_full_team_authoritative_flow(room),
    }
    failures: list[str] = []
    if not check:
        FULL_TEAM_REFERENCE_ROOT.mkdir(parents=True, exist_ok=True)
    for path, text in expected.items():
        data = text.encode("utf-8")
        if check:
            if not path.is_file() or path.read_bytes() != data:
                failures.append(str(path))
        else:
            path.write_bytes(data)
    if failures:
        raise RuntimeError(
            "generated full-team documentation is stale: " + ", ".join(failures)
        )


def full_team() -> dict[str, Any]:
    base = "artifacts/full-team"
    category = {name: f"{base}/categories/{name.lower()}.json"
                for name in PRODUCTION_CATEGORIES}
    web = {
        "accessibility": f"{base}/accessibility.json",
        "browser": f"{base}/browser-qa.json",
        "contracts": f"{base}/contract-verification.json",
        "dependencies": f"{base}/dependency-sbom.json",
        "environment": f"{base}/environment-readiness.json",
        "forms_privacy": f"{base}/forms-privacy.json",
        "lint_types": f"{base}/lint-types.json",
        "migration": f"{base}/migration-verification.json",
        "performance_load": f"{base}/performance-load.json",
        "visual_cross_browser": f"{base}/visual-cross-browser.json",
        "vendor_audits": {
            command: f"{base}/vendor-audits/{provider.lower().replace('/', '-')}.json"
            for command, provider in VENDOR_AUDIT_COMMANDS.items()
        },
    }
    repo = worker("repo_analyst", "Repo Analyst",
                  ["$repo-map", "$repo-risk-map", "$repo-dependency-map"],
                  [".solo/handoff.md"], [f"{base}/repo-analysis.md"],
                  "Repository map, risk map, and implementation constraints.")
    pm = worker("product_manager", "Product Manager",
                ["$stack-intake", "$stack-connector-check", "$project-prd",
                 "$spec-feature-brief", "$spec-acceptance",
                 "$project-task-breakdown"],
                [".solo/project.md", ".solo/stack.md"],
                [category["Product"], f"{base}/project-profile.json"],
                "Stack intake, product evidence, acceptance criteria, project profile, and scoped tasks.")
    architect = worker("software_architect", "Software Architect",
                       ["$project-architecture", "$spec-api-contract", "$spec-env-contract"],
                       [category["Product"], f"{base}/repo-analysis.md"],
                       [category["Architecture"]],
                       "Architecture evidence with boundaries, contracts, and risks.",
                       model="deep-reasoning")
    database = worker("database_engineer", "Database Engineer",
                      ["$spec-data-contract", "$site-doctor-audit-db"],
                      [category["Product"], category["Architecture"]],
                      [category["Database"], web["migration"]],
                      "Database schema, integrity, index, backup, and migration dry-run/rollback evidence; record a profile-backed N/A when no database exists.")
    ux = worker("ui_ux_designer", "UI/UX Designer",
                ["$design-ux-flow", "$design-component-system"],
                [category["Product"], category["Architecture"]],
                [f"{base}/design-spec.json"],
                "Pre-code UX flows, states, accessibility constraints, and component plan.")
    before_code = worker(
        "before_code_gatekeeper", "Before-Code Gatekeeper", ["$gate-before-code"],
        [category["Product"], category["Architecture"], f"{base}/design-spec.json"],
        [f"artifacts/gates/{base.split('/')[-1]}-before-code.json"],
        "GO or NO-GO tied to product, architecture, and design evidence.",
        kind="gatekeeper", model="deep-reasoning")
    frontend = worker("frontend_developer", "Frontend Developer",
                      ["$dev-implement-feature", "$browser-smoke-test"],
                      [category["Architecture"], f"{base}/design-spec.json"],
                      [category["Frontend"]],
                      "Frontend implementation evidence and affected-flow inventory.",
                      model="strong-coding")
    backend = worker("backend_developer", "Backend Developer",
                     ["$dev-implement-feature", "$test-integration"],
                     [category["Architecture"], category["Database"],
                      ".solo/api-contract.md", ".solo/data-contract.md",
                      ".solo/env-contract.md"],
                     [category["Backend"], web["contracts"]],
                     "Backend implementation evidence plus API, data, and environment contract verification; record a profile-backed N/A for a frontend-only site.",
                     model="strong-coding")
    design_review = worker("design_reviewer", "UI/UX Designer - Implementation Review",
                           ["$design-ui-review"],
                           [f"{base}/design-spec.json", category["Frontend"]],
                           [category["Design"]],
                           "Post-implementation UI/UX review evidence.")
    ai_review = worker("ai_agent_reviewer", "AI Agent Reviewer",
                       ["$ai-review-output", "$dev-code-review"],
                       [category["Frontend"], category["Backend"]],
                       [f"{base}/ai-code-review.json"],
                       "Independent code and AI-output review with hallucination checks.",
                       model="deep-reasoning")
    qa = worker("qa_engineer", "QA Engineer",
                ["$test-unit", "$test-integration", "$test-e2e", "$test-edge-cases"],
                [category["Frontend"], category["Backend"], f"{base}/ai-code-review.json"],
                [category["Testing"], web["lint_types"]],
                "Test evidence mapped to acceptance criteria and edge cases, plus repository-defined lint and static-type command results.",
                model="strong-coding")
    browser = worker("browser_qa_engineer", "Browser QA Engineer",
                     ["$browser-smoke-test", "$browser-console-errors",
                      "$browser-mobile-test", "$browser-visual-check"],
                     [category["Frontend"], f"{base}/design-spec.json"],
                     [web["browser"], web["visual_cross_browser"]],
                     "Safety-scoped smoke, console, viewport, visual-regression, and supported-browser evidence using synthetic data and no production writes.")
    security = worker("security_engineer", "Security Engineer",
                      ["$security-threat-model", "$security-authz-matrix", "$security-rls-test"],
                      [category["Architecture"], category["Backend"], category["Database"]],
                      [category["Security"]],
                      "Threat, authorization, secret, and data-access evidence.",
                      model="deep-reasoning")
    doctor = worker("site_doctor", "Site Doctor",
                    ["$site-doctor-full-checkup", "$site-doctor-a11y",
                     "$site-doctor-audit-forms", "$site-doctor-compliance",
                     "$site-doctor-audit-deps", "$site-doctor-perf",
                     "$site-doctor-load-test", "$site-doctor-animation",
                     "$site-doctor-seo", "$seo-audit",
                     "$stack-audit-vercel", "$stack-audit-supabase",
                     "$stack-audit-cloudflare", "$stack-audit-tags",
                     "$stack-audit-payments"],
                    [category["Frontend"], category["Backend"], ".solo/stack.md"],
                    [category["Performance"], category["SEO"], web["accessibility"],
                     web["dependencies"], web["forms_privacy"],
                     web["performance_load"], *web["vendor_audits"].values()],
                    "Mandatory profile-aware accessibility, forms/privacy, dependency/SBOM, performance/load, animation, and SEO evidence. Run both the Site Doctor animation audit and the dedicated SEO audit, plus one explicit Vercel, Supabase, Cloudflare, tag, and payments task. Run each provider task only when .solo/stack.md records that provider; otherwise record an evidence-backed N/A artifact.")
    devops = worker("devops_engineer", "DevOps Engineer",
                    ["$release-ci-setup", "$release-preflight",
                     "$release-deploy-plan", "$release-rollback-plan",
                     "$site-doctor-monitoring"],
                    [category["Architecture"], category["Testing"], ".solo/stack.md",
                     ".solo/env-contract.md"],
                    [category["Deployment"], category["Monitoring"],
                     f"{base}/rollback.json", web["environment"]],
                    "Exact-environment readiness, deployment, monitoring, backup, and rollback evidence without launching.")
    growth = worker("growth_conversion_reviewer", "Growth/Conversion Reviewer",
                    ["$growth-conversion-audit", "$analytics-audit"],
                    [category["Product"], category["Frontend"], f"{base}/project-profile.json"],
                    [category["Analytics"]],
                    "Conversion and analytics evidence, or an evidence-backed profile N/A reason.")
    before_merge = worker(
        "before_merge_gatekeeper", "Before-Merge Gatekeeper", ["$gate-before-merge"],
        [f"{base}/ai-code-review.json", category["Security"], category["Testing"],
         f"{base}/rollback.json", web["accessibility"], web["browser"],
         web["contracts"], web["dependencies"], web["forms_privacy"],
         web["lint_types"], web["migration"], web["performance_load"],
         web["visual_cross_browser"], *web["vendor_audits"].values()],
        ["artifacts/gates/full-team-before-merge.json"],
        "GO or NO-GO tied to review, security, testing, browser, web-quality, contract, migration, and rollback evidence.",
        kind="gatekeeper", model="deep-reasoning")
    docs = worker("documentation_writer", "Documentation Writer",
                  ["$docs-update", "$docs-setup-guide", "$docs-runbook"],
                  [category["Architecture"], category["Testing"], category["Deployment"]],
                  [category["Documentation"]],
                  "Documentation evidence verified against the implementation.")
    git_manager = worker("git_pr_manager", "Git/PR Manager",
                         ["$git-commit-plan", "$git-pr-review",
                          "$git-release-notes"],
                         [f"{base}/ai-code-review.json", category["Testing"], category["Security"]],
                         [f"{base}/pr-release.json"],
                         "PR and release-note evidence without publishing or merging.")
    release_manager = worker("release_manager", "Release Manager",
                             ["$release-preflight"],
                             [category["Deployment"], category["Monitoring"],
                              f"{base}/rollback.json", f"{base}/pr-release.json",
                              web["environment"]],
                             [f"{base}/release-management.json"],
                             "Release sequencing, ownership, and rollback go/no-go evidence.")
    handoff_coordinator = worker(
        "handoff_coordinator", "Project Handoff Coordinator",
        ["$solo-handoff-memory"],
        [category["Product"], category["Architecture"], category["Testing"],
         category["Security"], category["Deployment"], category["Monitoring"],
         category["Documentation"], f"{base}/pr-release.json"],
        [f"{base}/handoff-finalization.json"],
        "A pre-freeze project-memory handoff proposal covering completed work, open tasks, decisions, risks, tests, release state, and next ownership; the memory steward performs the shared .solo/ merge.")
    deploy_prereqs = [
        ("Before-merge gate", "artifacts/gates/full-team-before-merge.json"),
        ("Accessibility", web["accessibility"]),
        ("Browser QA", web["browser"]),
        ("Contracts", web["contracts"]),
        ("Dependency and SBOM", web["dependencies"]),
        ("Forms and privacy", web["forms_privacy"]),
        ("Lint and types", web["lint_types"]),
        ("Migration verification", web["migration"]),
        ("Performance and load", web["performance_load"]),
        ("Visual and cross-browser", web["visual_cross_browser"]),
        *[(f"{VENDOR_AUDIT_COMMANDS[command]} audit", artifact)
          for command, artifact in web["vendor_audits"].items()],
        ("Security", category["Security"]),
        ("Testing", category["Testing"]),
        ("Deployment", category["Deployment"]),
        ("Monitoring", category["Monitoring"]),
        ("Rollback", f"{base}/rollback.json"),
        ("Environment", web["environment"]),
        ("Release", f"{base}/release-management.json"),
        ("Project handoff", f"{base}/handoff-finalization.json"),
    ]
    before_deploy = worker(
        "before_deploy_gatekeeper", "Before-Deploy Gatekeeper",
        ["$gate-before-deploy"], [artifact for _, artifact in deploy_prereqs],
        ["artifacts/gates/full-team-before-deploy.json"],
        "GO or NO-GO from exact-commit, exact-environment deployment evidence; no deploy action is performed.",
        kind="gatekeeper", model="deep-reasoning")
    repair = worker(
        "repair_retest_coordinator", "Repair and Retest Coordinator",
        ["$ai-repair-cycle", "$dev-fix-bug"],
        ["artifacts/gates/full-team-before-merge.json",
         "artifacts/gates/full-team-before-deploy.json", category["Testing"],
         web["browser"], web["lint_types"]],
        [f"{base}/repair-retest-plan.json"],
        "A minimal owner-assigned repair plan, or proof that all current gate evidence is GO; never exceed the declared loop bound.",
        model="deep-reasoning")
    profile_artifact = f"{base}/project-profile.json"
    prod_prereqs = [(name, category[name]) for name in PRODUCTION_CATEGORIES]
    production_contract_prereqs = prod_prereqs + [
        ("Project profile", profile_artifact),
    ]
    prod_gate = worker(
        "production_gatekeeper", "Production Readiness Gatekeeper",
        ["$gate-production-ready"],
        [artifact for _, artifact in production_contract_prereqs] +
        ["artifacts/gates/full-team-before-deploy.json"],
        ["artifacts/gates/full-team-production.json"],
        "BLOCKED, SAFE WITH WARNINGS, or SAFE TO LAUNCH with all 14 categories.",
        kind="gatekeeper", model="deep-reasoning")

    before_code_gate = gate(
        "before_code", "$gate-before-code", "before_code", "before_code_gatekeeper",
        [("Product", category["Product"]), ("Architecture", category["Architecture"]),
         ("Design", f"{base}/design-spec.json")],
        "artifacts/gates/full-team-before-code.json",
        routes=[
            {"statuses": ["GO"], "next_stage": "implementation"},
            {"statuses": ["NO-GO"], "action": "stop"},
        ])
    before_merge_gate = gate(
        "before_merge", "$gate-before-merge", "before_merge", "before_merge_gatekeeper",
        [("Review", f"{base}/ai-code-review.json"),
         ("Security", category["Security"]), ("Testing", category["Testing"]),
         ("Rollback", f"{base}/rollback.json"),
         ("Accessibility", web["accessibility"]),
         ("Browser QA", web["browser"]),
         ("Contracts", web["contracts"]),
         ("Dependency and SBOM", web["dependencies"]),
         ("Forms and privacy", web["forms_privacy"]),
         ("Lint and types", web["lint_types"]),
         ("Migration verification", web["migration"]),
         ("Performance and load", web["performance_load"]),
         ("Visual and cross-browser", web["visual_cross_browser"])] +
        [(f"{VENDOR_AUDIT_COMMANDS[command]} audit", artifact)
         for command, artifact in web["vendor_audits"].items()],
        "artifacts/gates/full-team-before-merge.json",
        routes=[
            {"statuses": ["GO"], "next_stage": "release_and_docs"},
            {"statuses": ["NO-GO"], "next_stage": "repair_retest"},
        ])
    before_deploy_gate = gate(
        "before_deploy", "$gate-before-deploy", "before_deploy",
        "before_deploy_gatekeeper", deploy_prereqs,
        "artifacts/gates/full-team-before-deploy.json",
        routes=[
            {"statuses": ["GO"], "next_stage": "production"},
            {"statuses": ["NO-GO"], "next_stage": "repair_retest"},
        ], max_age_hours=12)
    production_gate = gate(
        "production", "$gate-production-ready", "production", "production_gatekeeper",
        production_contract_prereqs, "artifacts/gates/full-team-production.json",
        routes=[
            {"statuses": ["SAFE TO LAUNCH"], "action": "complete"},
            {"statuses": ["SAFE WITH WARNINGS"], "action": "stop"},
            {"statuses": ["BLOCKED"], "action": "stop"},
        ],
        required_gate_results=[{
            "gate_id": "before_deploy",
            "status": "GO",
            "freshness": {
                "run_id": "exact", "commit": "exact",
                "environment": "exact", "latest": True,
            },
        }],
        max_age_hours=12)
    return build_room(
        name="full-team-website",
        description=(
            "Profile-aware full-team delivery from discovery through a 14-category "
            "production gate, with isolated worktrees and centralized memory writes."
        ),
        profile="profile-selected-at-runtime",
        stage_specs=[
            ("discovery", [repo, pm]),
            ("architecture", [architect]),
            ("database_architecture", [database]),
            ("design", [ux]),
            ("before_code", [before_code]),
            ("implementation", [frontend, backend]),
            ("post_implementation_review", [design_review, ai_review]),
            ("qa", [qa, browser]),
            ("hardening", [security, doctor, devops, growth]),
            ("before_merge", [before_merge]),
            ("release_and_docs", [docs, git_manager]),
            ("release_management", [release_manager, handoff_coordinator]),
            ("before_deploy", [before_deploy]),
            ("repair_retest", [repair]),
            ("production", [prod_gate]),
        ],
        gates=[before_code_gate, before_merge_gate, before_deploy_gate,
               production_gate],
        exit_gate="$gate-production-ready",
        exit_criteria=(
            "All 14 production categories have current evidence from the exact commit "
            "and environment, the exact-current before-deploy result is GO, and the "
            "production result is SAFE TO LAUNCH."
        ),
        based_on="Solo Suite full-team development workflow",
        extra_rules=[
            "Run $design-ui-review after implementation, not only during planning.",
            "Run $ai-review-output between implementation and QA.",
            "Run growth review only for conversion-oriented profiles; otherwise record N/A evidence.",
            "Run each $stack-audit-* provider task only when .solo/stack.md records that provider; otherwise emit a provider-specific, evidence-backed N/A artifact and never silently skip the task.",
            "Accessibility, visual/cross-browser, forms/privacy, dependency/SBOM, and performance/load checks are mandatory; use an evidence-backed N/A only when the selected profile proves a check structurally inapplicable.",
            "A before-merge or before-deploy NO-GO routes to the bounded repair/retest decision; never continue to production with stale or failed evidence.",
            "Every production category record must cite the detailed web evidence artifacts and their exact-commit digests where relevant.",
        ],
        loop={
            "from_stage": "repair_retest",
            "to_stage": "implementation",
            "max_iterations": 3,
            "trigger": {
                "gate_ids": ["before_merge", "before_deploy"],
                "statuses": ["NO-GO"],
                "match": "any",
            },
            "exit": {
                "gate_ids": ["before_merge", "before_deploy"],
                "statuses": ["GO"],
                "match": "all",
            },
            "until": (
                "Before-merge and before-deploy evidence are GO for the exact commit "
                "and environment, and every mandatory profile-aware web check passes "
                "or has an approved evidence-backed N/A."
            ),
            "on_exhaustion": (
                "Set production status to BLOCKED, preserve all evidence and open "
                "owner-assigned tasks; do not deploy, merge, or publish."
            ),
            "on_exhaustion_action": "stop",
        },
    )


def production_release() -> dict[str, Any]:
    base = "artifacts/production-release"
    profile_artifact = f"{base}/project-profile.json"
    categories = [(name, f"{base}/categories/{name.lower()}.json")
                  for name in PRODUCTION_CATEGORIES]
    collector = worker(
        "evidence_collector", "Release Evidence Collector",
        [
            "$stack-intake", "$spec-acceptance", "$project-architecture",
            "$design-ui-review", "$browser-smoke-test", "$api-audit",
            "$database-audit", "$security-review", "$test-unit",
            "$site-doctor-perf", "$site-doctor-seo", "$analytics-audit",
            "$release-preflight", "$observability", "$docs-update",
            "$gate-score-project",
        ],
        [".solo/project.md", ".solo/stack.md", ".solo/tests.md", ".solo/release.md"],
        [artifact for _, artifact in categories] + [profile_artifact],
        "A project-profile applicability contract and fourteen normalized category evidence records tied to run, commit, and environment.")
    devops = worker(
        "devops_engineer", "DevOps Engineer",
        ["$release-preflight", "$release-deploy-plan", "$release-rollback-plan"],
        [artifact for _, artifact in categories],
        [f"{base}/release-plan.json", f"{base}/rollback.json"],
        "Preview-only release and rollback plans with owners and verification.")
    docs = worker(
        "documentation_writer", "Documentation Writer",
        ["$docs-update", "$docs-runbook", "$git-release-notes"],
        [f"{base}/release-plan.json"], [f"{base}/release-docs.json"],
        "Release documentation checked against the exact artifact set.")
    before_deploy_prereqs = [
        ("Release plan", f"{base}/release-plan.json"),
        ("Rollback", f"{base}/rollback.json"),
        ("Release documentation", f"{base}/release-docs.json"),
        ("Security", f"{base}/categories/security.json"),
        ("Testing", f"{base}/categories/testing.json"),
        ("Deployment", f"{base}/categories/deployment.json"),
        ("Monitoring", f"{base}/categories/monitoring.json"),
    ]
    before_deploy = worker(
        "before_deploy_gatekeeper", "Before-Deploy Gatekeeper",
        ["$gate-before-deploy"],
        [artifact for _, artifact in before_deploy_prereqs],
        ["artifacts/gates/production-release-before-deploy.json"],
        "GO or NO-GO from exact-run, exact-commit, exact-environment release evidence.",
        kind="gatekeeper", model="deep-reasoning")
    gatekeeper = worker(
        "production_gatekeeper", "Production Readiness Gatekeeper",
        ["$gate-production-ready"],
        [artifact for _, artifact in categories] + [profile_artifact] +
        ["artifacts/gates/production-release-before-deploy.json"],
        ["artifacts/gates/production-release.json"],
        "One of BLOCKED, SAFE WITH WARNINGS, or SAFE TO LAUNCH.",
        kind="gatekeeper", model="deep-reasoning")
    before_deploy_gate = gate(
        "before_deploy", "$gate-before-deploy", "before_deploy",
        "before_deploy_gatekeeper", before_deploy_prereqs,
        "artifacts/gates/production-release-before-deploy.json",
        routes=[
            {"statuses": ["GO"], "next_stage": "production_gate"},
            {"statuses": ["NO-GO"], "action": "stop"},
        ], max_age_hours=12)
    gate_spec = gate(
        "production", "$gate-production-ready", "production_gate",
        "production_gatekeeper", categories + [("Project profile", profile_artifact)],
        "artifacts/gates/production-release.json",
        routes=[
            {"statuses": ["SAFE TO LAUNCH"], "action": "complete"},
            {"statuses": ["SAFE WITH WARNINGS"], "action": "stop"},
            {"statuses": ["BLOCKED"], "action": "stop"},
        ],
        required_gate_results=[{
            "gate_id": "before_deploy", "status": "GO",
            "freshness": {
                "run_id": "exact", "commit": "exact",
                "environment": "exact", "latest": True,
            },
        }],
        max_age_hours=12)
    return build_room(
        name="production-release",
        description="Collect and validate release evidence without deploying or publishing.",
        profile="profile-selected-at-runtime",
        stage_specs=[("collect_evidence", [collector]),
                     ("release_planning", [devops]),
                     ("release_documentation", [docs]),
                     ("before_deploy", [before_deploy]),
                     ("production_gate", [gatekeeper])],
        gates=[before_deploy_gate, gate_spec],
        exit_gate="$gate-production-ready",
        exit_criteria=(
            "All 14 categories use fresh exact-run, exact-commit, and "
            "exact-environment evidence; before-deploy is GO and production is "
            "SAFE TO LAUNCH."
        ),
        based_on="Solo Suite release and production-readiness rooms",
    )


def site_doctor_audit() -> dict[str, Any]:
    base = "artifacts/site-doctor-audit"
    site = worker(
        "site_auditor", "Site Doctor", ["$site-doctor-full-checkup"],
        [".solo/stack.md", ".solo/handoff.md"], [f"{base}/site-audit.json"],
        "Website, API, database, security, performance, and SEO audit evidence.")
    stack = worker(
        "stack_auditor", "Stack Auditor",
        ["$stack-connector-check", "$stack-audit-vercel", "$stack-audit-supabase",
         "$stack-audit-cloudflare", "$stack-audit-tags", "$stack-audit-payments"],
        [".solo/stack.md", ".solo/handoff.md"], [f"{base}/stack-audit.json"],
        "Provider evidence only for providers recorded in .solo/stack.md.")
    triager = worker(
        "triager", "Audit Triage Lead", ["$ai-review-output"],
        [f"{base}/site-audit.json", f"{base}/stack-audit.json"],
        [f"{base}/triage.json"],
        "Deduplicated severity-ranked findings and conflict-checked task proposals.")
    gatekeeper = worker(
        "score_gatekeeper", "Project Score Gatekeeper", ["$gate-score-project"],
        [f"{base}/site-audit.json", f"{base}/stack-audit.json", f"{base}/triage.json"],
        ["artifacts/gates/site-doctor-score.json"],
        "Evidence-backed project score without a launch action.",
        kind="gatekeeper", model="deep-reasoning")
    gate_spec = gate(
        "score", "$gate-score-project", "score", "score_gatekeeper",
        [("Site audit", f"{base}/site-audit.json"),
         ("Stack audit", f"{base}/stack-audit.json"),
         ("Triage", f"{base}/triage.json")],
        "artifacts/gates/site-doctor-score.json",
        routes=[
            {"statuses": ["SCORED"], "action": "complete"},
            {"statuses": ["INSUFFICIENT EVIDENCE"], "action": "stop"},
        ])
    return build_room(
        name="site-doctor-audit",
        description="Run site and provider audits in parallel, then triage through one memory steward.",
        profile="profile-selected-at-runtime",
        stage_specs=[("audit", [site, stack]), ("triage", [triager]),
                     ("score", [gatekeeper])],
        gates=[gate_spec],
        exit_gate="$gate-score-project",
        exit_criteria="All findings are deduplicated, evidenced, prioritized, and proposed with unique task IDs.",
        based_on="Solo Suite Site Doctor and stack audit rooms",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-docs", action="store_true",
        help="fail if generated full-team reference documents are stale",
    )
    args = parser.parse_args()
    rooms = {
        "full-team-website.json": full_team(),
        "production-release.json": production_release(),
        "site-doctor-audit.json": site_doctor_audit(),
    }
    output = ROOM_ROOT / "agentsrooms"
    stale_rooms: list[str] = []
    for filename, room in rooms.items():
        destination = output / filename
        data = _room_json_bytes(room)
        if args.check_docs:
            if not destination.is_file() or destination.read_bytes() != data:
                stale_rooms.append(str(destination))
        else:
            destination.write_bytes(data)
    if stale_rooms:
        raise RuntimeError(
            "generated AgentRoom JSON is stale: " + ", ".join(stale_rooms)
        )
    write_full_team_docs(rooms["full-team-website.json"], check=args.check_docs)
    action = "Verified" if args.check_docs else "Built"
    print(f"{action} {len(rooms)} strict AgentRoom templates")


if __name__ == "__main__":
    main()
