#!/usr/bin/env python3
"""Validate every Solo Suite directory against the current Codex contract.

The structural checks are portable. With ``--official-if-available``, the
script also invokes ``codex plugin validate`` when the installed CLI exposes
that command and reports an explicit UNVERIFIED note otherwise.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
PLUGIN_KEYS = {
    "id", "name", "version", "description", "skills", "apps",
    "mcpServers", "interface", "author", "homepage", "repository",
    "license", "keywords",
}
INTERFACE_KEYS = {
    "displayName", "shortDescription", "longDescription", "developerName",
    "category", "capabilities", "websiteURL", "privacyPolicyURL",
    "termsOfServiceURL", "brandColor", "composerIcon", "logo", "logoDark",
    "screenshots", "defaultPrompt", "default_prompt",
}
SKILL_UI_KEYS = {"interface", "policy", "dependencies"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def split_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("must begin with YAML frontmatter")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError("frontmatter is not closed")
    data = yaml.safe_load(text[4:end])
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data


def validate_plugin(plugin: Path) -> list[str]:
    failures: list[str] = []
    manifest_path = plugin / ".codex-plugin/plugin.json"
    try:
        manifest = load_json(manifest_path)
    except Exception as exc:
        return [f"{manifest_path}: invalid or missing JSON ({exc})"]
    if not isinstance(manifest, dict):
        return [f"{manifest_path}: root must be an object"]
    unknown = sorted(set(manifest) - PLUGIN_KEYS)
    if unknown:
        failures.append(f"{manifest_path}: unsupported fields {unknown}")
    for field in ("name", "version", "description"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            failures.append(f"{manifest_path}: {field} must be non-empty")
    if manifest.get("name") != plugin.name:
        failures.append(f"{manifest_path}: name must match plugin folder")
    if not isinstance(manifest.get("version"), str) or not SEMVER.fullmatch(
        manifest.get("version", "")
    ):
        failures.append(f"{manifest_path}: version must be strict semver")
    author = manifest.get("author")
    if not isinstance(author, dict) or not isinstance(author.get("name"), str):
        failures.append(f"{manifest_path}: author.name is required")
    if manifest.get("skills") != "./skills/":
        failures.append(f"{manifest_path}: skills must be './skills/'")
    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        failures.append(f"{manifest_path}: interface must be an object")
    else:
        extra = sorted(set(interface) - INTERFACE_KEYS)
        if extra:
            failures.append(f"{manifest_path}: unsupported interface fields {extra}")
        for field in (
            "displayName", "shortDescription", "longDescription",
            "developerName", "category",
        ):
            if not isinstance(interface.get(field), str) or not interface[field].strip():
                failures.append(f"{manifest_path}: interface.{field} is required")
        if not isinstance(interface.get("capabilities"), list):
            failures.append(f"{manifest_path}: interface.capabilities must be an array")
        if "defaultPrompt" not in interface and "default_prompt" not in interface:
            failures.append(f"{manifest_path}: interface.defaultPrompt is required")

    skills = sorted((plugin / "skills").glob("*/SKILL.md"))
    if not skills:
        failures.append(f"{plugin}: no skills found")
    seen: set[str] = set()
    for skill in skills:
        try:
            frontmatter = split_frontmatter(skill)
        except Exception as exc:
            failures.append(f"{skill}: {exc}")
            continue
        name = frontmatter.get("name")
        if name != skill.parent.name:
            failures.append(f"{skill}: name must match skill folder")
        if name in seen:
            failures.append(f"{skill}: duplicate skill name {name!r}")
        if isinstance(name, str):
            seen.add(name)
        if not isinstance(frontmatter.get("description"), str):
            failures.append(f"{skill}: description is required")
        ui_path = skill.parent / "agents/openai.yaml"
        try:
            ui = yaml.safe_load(ui_path.read_text(encoding="utf-8"))
        except Exception as exc:
            failures.append(f"{ui_path}: invalid or missing YAML ({exc})")
            continue
        if not isinstance(ui, dict):
            failures.append(f"{ui_path}: root must be a mapping")
            continue
        extra = sorted(set(ui) - SKILL_UI_KEYS)
        if extra:
            failures.append(f"{ui_path}: unsupported fields {extra}")
        ui_interface = ui.get("interface")
        if not isinstance(ui_interface, dict):
            failures.append(f"{ui_path}: interface is required")
        else:
            for field in ("display_name", "short_description", "default_prompt"):
                if not isinstance(ui_interface.get(field), str) or not ui_interface[field].strip():
                    failures.append(f"{ui_path}: interface.{field} is required")
            if isinstance(name, str) and isinstance(ui_interface.get("default_prompt"), str):
                if f"${name}" not in ui_interface["default_prompt"]:
                    failures.append(f"{ui_path}: default_prompt must mention ${name}")
        policy = ui.get("policy", {})
        if not isinstance(policy, dict) or not isinstance(
            policy.get("allow_implicit_invocation", True), bool
        ):
            failures.append(
                f"{ui_path}: policy.allow_implicit_invocation must be boolean"
            )
    return failures


def official_validation(paths: list[Path]) -> tuple[bool, list[str], dict[str, Any]]:
    executable = shutil.which("codex")
    if executable is None:
        print("UNVERIFIED official Codex CLI plugin validation: codex is unavailable")
        return False, [], {
            "status": "unavailable",
            "cli_version": None,
            "reason": "codex executable is unavailable",
        }
    version = None
    try:
        version_result = subprocess.run(
            [executable, "--version"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=20,
        )
        version = (version_result.stdout + version_result.stderr).strip() or None
    except (OSError, subprocess.SubprocessError):
        version = None
    try:
        help_result = subprocess.run(
            [executable, "plugin", "--help"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"UNVERIFIED official Codex CLI plugin validation: {exc}")
        return False, [], {
            "status": "unavailable",
            "cli_version": version,
            "reason": f"unable to query plugin help: {exc}",
        }
    help_text = help_result.stdout + help_result.stderr
    if help_result.returncode != 0 or "validate" not in help_text.lower():
        print("UNVERIFIED official Codex CLI plugin validation: installed CLI has no validate subcommand")
        return False, [], {
            "status": "unavailable",
            "cli_version": version,
            "reason": "installed CLI has no validate subcommand",
        }
    failures = []
    for path in paths:
        result = subprocess.run(
            [executable, "plugin", "validate", str(path)], capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=60,
        )
        if result.returncode:
            failures.append(f"official validation failed for {path}: {result.stdout}{result.stderr}")
    if not failures:
        print(f"PASS official Codex CLI validated {len(paths)} plugin(s)")
    return not failures, failures, {
        "status": "pass" if not failures else "fail",
        "cli_version": version,
        "reason": None if not failures else "one or more plugins failed official validation",
    }


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # ``Path.write_text`` did not accept ``newline`` on Python 3.9, which is
    # still part of the CI matrix.  Encode explicitly so report bytes remain
    # UTF-8 with deterministic LF endings across every supported interpreter.
    path.write_bytes(
        (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        .encode("utf-8")
    )


def overall_validation_status(
    portable_status: str, official_status: str
) -> str:
    """Summarize validation without treating a missing official check as a pass."""

    if portable_status == "fail" or official_status == "fail":
        return "fail"
    if official_status == "pass":
        return "pass"
    if official_status == "unavailable":
        return "portable_pass_official_unavailable"
    return "portable_pass_official_not_requested"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--official-if-available", action="store_true")
    parser.add_argument(
        "--report", type=Path,
        help="write a deterministic portable/official validation status JSON",
    )
    args = parser.parse_args()
    paths = [path.resolve() for path in args.paths] or sorted(
        path.resolve() for path in (ROOT / "plugins").iterdir() if path.is_dir()
    )
    failures = []
    portable_failures = 0
    for path in paths:
        mine = validate_plugin(path)
        if mine:
            failures.extend(mine)
            portable_failures += len(mine)
        else:
            print(f"PASS portable plugin validation: {path.name}")
    official = {
        "status": "not_requested",
        "cli_version": None,
        "reason": "--official-if-available was not supplied",
    }
    if args.official_if_available:
        _available, official_failures, official = official_validation(paths)
        failures.extend(official_failures)
    for failure in failures:
        print(f"FAIL {failure}")
    print(f"== {len(paths)} plugin(s), {len(failures)} failure(s) ==")
    if args.report:
        portable_status = "pass" if portable_failures == 0 else "fail"
        write_report(args.report.resolve(), {
            "schema": "solo-suite/plugin-validation-report-v1",
            "plugin_count": len(paths),
            "portable": {
                "status": portable_status,
                "failure_count": portable_failures,
            },
            "official": official,
            "overall_status": overall_validation_status(
                portable_status, official["status"]
            ),
        })
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
