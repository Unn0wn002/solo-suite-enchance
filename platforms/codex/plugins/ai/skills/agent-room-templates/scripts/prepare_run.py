#!/usr/bin/env python3
"""Instantiate and validate a declarative AgentRoom template.

This adapter prepares a run plan; it never starts agents or writes to external
systems. Codex must still create subagents stage by stage and enforce locks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from runtime_trust import TrustError, suite_trust
from state_journal import JournalError, registry_dir
from validate_rooms import find_suite, is_windows_safe_run_id, validate_files


PROFILES = (
    "public-marketing-site",
    "saas-application",
    "e-commerce",
    "internal-application",
    "api-service",
    "library-package",
)


def namespace_path(value: object, run_id: str) -> object:
    """Namespace runner-owned worktrees and artifacts by the unique run id."""
    if not isinstance(value, str):
        return value
    for prefix in ("artifacts", "worktrees"):
        marker = prefix + "/"
        if value.startswith(marker):
            remainder = value[len(marker):]
            if remainder.startswith("runs/"):
                parts = remainder.split("/", 2)
                remainder = parts[2] if len(parts) == 3 else ""
            return "%s/runs/%s/%s" % (prefix, run_id, remainder)
    return value


def namespace_room(room: dict, run_id: str) -> None:
    """Rewrite every executable path field that can collide between runs."""
    for workspace in room.get("workspaces", []):
        if isinstance(workspace, dict):
            workspace["path"] = namespace_path(workspace.get("path"), run_id)
    for lock in room.get("artifact_locks", []):
        if isinstance(lock, dict):
            lock["artifact"] = namespace_path(lock.get("artifact"), run_id)
    for seat in room.get("seats", []):
        if not isinstance(seat, dict):
            continue
        for field in ("reads", "writes", "proposals"):
            if isinstance(seat.get(field), list):
                seat[field] = [namespace_path(path, run_id)
                               for path in seat[field]]
    for gate in room.get("gates", []):
        if not isinstance(gate, dict):
            continue
        for prerequisite in gate.get("prerequisites", []):
            if isinstance(prerequisite, dict):
                prerequisite["artifact"] = namespace_path(
                    prerequisite.get("artifact"), run_id)
        evidence = gate.get("evidence")
        if isinstance(evidence, dict):
            evidence["artifact"] = namespace_path(
                evidence.get("artifact"), run_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("template", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--profile", choices=PROFILES, required=True,
        help="bind the prepared room to one explicitly selected project profile",
    )
    parser.add_argument("--suite", default=None)
    parser.add_argument(
        "--project-root", type=Path, default=Path.cwd(),
        help="project root used for the case-insensitive run-id registry",
    )
    args = parser.parse_args()
    if not is_windows_safe_run_id(args.run_id):
        parser.error(
            "--run-id must be a Windows-safe 3-64 character path segment")
    template = args.template.resolve()
    output = args.output.resolve()
    if output == template:
        print("FAIL output must not overwrite the template")
        return 1
    if output.exists():
        print("FAIL output already exists; choose a new run-plan path")
        return 1
    room = json.loads(template.read_text(encoding="utf-8"))
    if room.get("prepared") is not False:
        print("FAIL template must declare prepared=false")
        return 1
    template_profile = room.get("profile")
    if (template_profile != "profile-selected-at-runtime" and
            template_profile != args.profile):
        print("FAIL --profile does not match the template's fixed profile")
        return 1
    room["prepared"] = True
    room["run_id"] = args.run_id
    room["profile"] = args.profile
    namespace_room(room, args.run_id)
    detected_suite = args.suite or find_suite(str(template.parent))
    if not detected_suite:
        print("FAIL cannot prepare a runnable room without a suite root")
        return 1
    suite_root = Path(detected_suite).resolve()
    try:
        room["runtime_trust"] = suite_trust(suite_root)
    except TrustError as exc:
        print("FAIL cannot establish suite trust: %s" % exc)
        return 1
    try:
        registry = registry_dir(args.project_root)
        registry.mkdir(parents=True, exist_ok=True)
        # Recheck after creation so a pre-existing redirected component cannot
        # be hidden by mkdir's normal follow-link behavior.
        registry = registry_dir(args.project_root)
    except (JournalError, OSError) as exc:
        print("FAIL run registry is not a controlled project path: %s" % exc)
        return 1
    claim = registry / (args.run_id.casefold() + ".lock")
    try:
        with claim.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write("PREPARING\n")
    except FileExistsError:
        print("FAIL run id is already registered for this project")
        return 1
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(room, indent=2, ensure_ascii=False) + "\n")
        problems = validate_files([str(output)], suite_root=str(suite_root))
    except Exception:
        output.unlink(missing_ok=True)
        claim.unlink(missing_ok=True)
        raise
    if problems:
        output.unlink(missing_ok=True)
        claim.unlink(missing_ok=True)
        for problem in problems:
            print(f"FAIL {problem}")
        return 1
    claim_data = {
        "schema": "solo-suite/agentroom-run-claim-v1",
        "run_id": args.run_id,
        "profile": args.profile,
        "plan": str(output),
        "plan_digest": "sha256:" + hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    claim_tmp = claim.with_suffix(claim.suffix + ".tmp")
    try:
        with claim_tmp.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(claim_data, sort_keys=True) + "\n")
        claim_tmp.replace(claim)
    except Exception:
        output.unlink(missing_ok=True)
        claim_tmp.unlink(missing_ok=True)
        claim.unlink(missing_ok=True)
        raise
    print(f"Prepared {output} for run {args.run_id}")
    for stage in room["stages"]:
        active = [seat for seat in stage["seats"] if seat != "memory_steward"]
        print(f"STAGE {stage['id']}: {', '.join(active)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
