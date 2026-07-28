#!/usr/bin/env python3
"""Fail-closed Full Team component, version, command, and room preflight."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Set, Tuple


VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
SKILL = re.compile(r"^\$[a-z0-9][a-z0-9-]*$")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def version_tuple(value: object) -> Tuple[int, int, int]:
    match = VERSION.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ValueError("invalid semantic version %r" % value)
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def install_command(plugin: str) -> str:
    """Return the platform-correct repair command for a missing component."""

    return f"codex plugin add {plugin}@solo-suite-codex"


def room_commands(room: Dict[str, Any]) -> Set[str]:
    commands: Set[str] = set()
    for seat in room.get("seats", []):
        if not isinstance(seat, dict):
            continue
        for command in seat.get("commands", []):
            if isinstance(command, str):
                commands.add(command)
        handoff = seat.get("handoff_check")
        if isinstance(handoff, str):
            commands.add(handoff)
    for gate in room.get("gates", []):
        if not isinstance(gate, dict):
            continue
        if isinstance(gate.get("command"), str):
            commands.add(gate["command"])
        for prerequisite in gate.get("prerequisites", []):
            if not isinstance(prerequisite, dict):
                continue
            commands.update(
                command for command in prerequisite.get("producer_commands", [])
                if isinstance(command, str)
            )
    exit_gate = room.get("exit_gate")
    if isinstance(exit_gate, str):
        commands.add(exit_gate)
    return commands


def available_skills(suite_root: Path) -> Set[str]:
    return {
        "$" + skill.parent.name
        for skill in suite_root.glob("plugins/*/skills/*/SKILL.md")
    }


def preflight(
    suite_root: Path, room_path: Path, contract_path: Path,
) -> Dict[str, Any]:
    suite = suite_root.resolve()
    room_path = room_path.resolve()
    contract_path = contract_path.resolve()
    failures: List[str] = []
    try:
        contract = read_json(contract_path)
        room = read_json(room_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"status": "FAIL", "failures": ["cannot read preflight input: %s" % exc]}
    if not isinstance(contract, dict) or not isinstance(contract.get("components"), list):
        failures.append("component contract is malformed")
        components = []
    else:
        components = contract["components"]
    if not isinstance(room, dict):
        failures.append("room contract is malformed")
        room = {}
    skills = available_skills(suite)
    seen_plugins: Set[str] = set()
    for index, component in enumerate(components):
        prefix = "components[%d]" % index
        if not isinstance(component, dict):
            failures.append(prefix + " is not an object")
            continue
        plugin = component.get("plugin")
        representative = component.get("representative_skill")
        if not isinstance(plugin, str) or not plugin:
            failures.append(prefix + " has no plugin")
            continue
        if plugin in seen_plugins:
            failures.append("component contract repeats plugin %s" % plugin)
        seen_plugins.add(plugin)
        manifest_path = suite / "plugins" / plugin / ".codex-plugin" / "plugin.json"
        try:
            manifest = read_json(manifest_path)
            if not isinstance(manifest, dict):
                failures.append(
                    f"{plugin} manifest is malformed; repair with {install_command(plugin)}"
                )
                continue
            if manifest.get("name") != plugin:
                failures.append(
                    f"{plugin} manifest name is invalid; repair with {install_command(plugin)}"
                )
            installed = version_tuple(manifest.get("version"))
            minimum = version_tuple(component.get("minimum_version"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            failures.append(
                "%s cannot verify version: %s; repair with %s" %
                (plugin, exc, install_command(plugin))
            )
            continue
        if installed < minimum:
            failures.append(
                "%s version %s is below required %s" %
                (plugin, manifest.get("version"), component.get("minimum_version"))
                + "; repair with " + install_command(plugin)
            )
        invocation = "$" + str(representative)
        if not isinstance(representative, str) or invocation not in skills:
            failures.append("%s representative skill is unavailable: %s" % (
                plugin, representative,
            ))

    selected_commands = room_commands(room)
    malformed = sorted(command for command in selected_commands if not SKILL.fullmatch(command))
    if malformed:
        failures.append("room contains malformed skill invocations: %s" % ", ".join(malformed))
    missing = sorted(selected_commands - skills)
    if missing:
        failures.append("room commands are unavailable: %s" % ", ".join(missing))

    validator = (
        suite / "plugins/ai/skills/agent-room-templates/scripts/validate_rooms.py"
    )
    if not validator.is_file():
        failures.append("AgentRoom validator is unavailable")
        validator_output = ""
    else:
        try:
            result = subprocess.run(
                [sys.executable, str(validator), str(room_path), "--suite", str(suite)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=120,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            failures.append("AgentRoom validator could not run: %s" % exc)
            validator_output = ""
        else:
            validator_output = (result.stdout + result.stderr).strip()
            if result.returncode != 0:
                failures.append("AgentRoom validator rejected the selected room")
    return {
        "status": "PASS" if not failures else "FAIL",
        "room": room.get("name"),
        "components_checked": len(components),
        "commands_checked": len(selected_commands),
        "validator_output": validator_output,
        "failures": failures,
    }


def main() -> int:
    here = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("room", type=Path)
    parser.add_argument("--suite-root", type=Path, required=True)
    parser.add_argument(
        "--contract", type=Path,
        default=here / "references/component-plugins.json",
    )
    args = parser.parse_args()
    result = preflight(args.suite_root, args.room, args.contract)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
