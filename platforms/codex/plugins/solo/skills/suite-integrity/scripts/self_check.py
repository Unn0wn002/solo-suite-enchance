#!/usr/bin/env python3
"""Mechanical integrity checks for a Solo Suite checkout or installed plugin.

Usage:
    python self_check.py [suite_or_plugin_root] [project_root]

Pass ``-`` as project_root to skip the optional ``.solo`` memory check.
Exit 0 means no mechanical failures were found; it is not a production-readiness
or security verdict.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:  # Reported cleanly by the checker instead of hiding it.
    yaml = None


MEMORY_FILES = (
    "project.md", "stack.md", "prd.md", "architecture.md",
    "api-contract.md", "data-contract.md", "env-contract.md", "design.md",
    "tasks.md", "decisions.md", "risks.md", "bugs.md", "tests.md",
    "release.md", "monitoring.md", "handoff.md",
)
ALLOWED_SKILL_FRONTMATTER = {
    "name", "description", "argument-hint", "disable-model-invocation",
    "user-invocable", "allowed-tools", "model",
}
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
LEGACY_COMMAND = re.compile(r"(?<![\w/])/[a-z][a-z0-9-]*:[a-z][a-z0-9-]*")
PY_HELPER = re.compile(
    r"(?<![\w.-])(?:(<resolved-plugin-root>|<skill-root>)/)?"
    r"((?:\.\./)*[A-Za-z0-9_./-]*scripts/[A-Za-z0-9_./-]+\.py)"
)
USER_OUTPUT_CONTRACT = (
    "## User-facing output contract\n\n"
    "Outside required machine-readable artifacts, end every response with exactly "
    "these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, "
    "**Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), "
    "**Verification**, and **Next skill** (the exact `$skill` invocation)."
)
STALE_NEXT_COMMAND = re.compile(r"\bnext command\b", re.IGNORECASE)


@dataclass
class Report:
    passes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def ok(self, message: str) -> None:
        self.passes.append(message)


@dataclass(frozen=True)
class Layout:
    mode: str
    root: Path
    plugins: tuple[Path, ...]
    marketplace: Path | None


def _resolve(path: Path) -> Path:
    return path.expanduser().resolve()


def discover(start: Path) -> Layout | None:
    """Find a repo checkout first, or the nearest installed plugin root."""
    start = _resolve(start)
    if start.is_file():
        start = start.parent
    installed: Path | None = None
    for candidate in (start, *start.parents):
        market = candidate / ".agents" / "plugins" / "marketplace.json"
        if market.is_file() and (candidate / "plugins").is_dir():
            if installed is not None:
                try:
                    installed.relative_to(candidate / "plugins")
                except ValueError:
                    # A personal marketplace higher in the user profile must not
                    # capture an unrelated installed/cache plugin below it.
                    continue
            plugins = tuple(sorted(
                p.parent.parent for p in (candidate / "plugins").glob(
                    "*/.codex-plugin/plugin.json"
                )
            ))
            return Layout("source-checkout", candidate, plugins, market)
        if installed is None and (candidate / ".codex-plugin" / "plugin.json").is_file():
            installed = candidate
    if installed:
        return Layout("installed-plugin", installed, (installed,), None)
    return None


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def read_yaml(path: Path) -> Any:
    if yaml is None:
        raise RuntimeError(
            "PyYAML is required for safe YAML parsing; install requirements-dev.lock with --require-hashes"
        )
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def split_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing opening YAML frontmatter delimiter")
    end = next((i for i, line in enumerate(lines[1:], 1)
                if line.strip() == "---"), None)
    if end is None:
        raise ValueError("missing closing YAML frontmatter delimiter")
    if yaml is None:
        raise RuntimeError(
            "PyYAML is required for safe YAML parsing; install requirements-dev.lock with --require-hashes"
        )
    parsed = yaml.safe_load("".join(lines[1:end]))
    if not isinstance(parsed, dict):
        raise ValueError("frontmatter must parse to a mapping")
    return parsed, "".join(lines[end + 1:])


def relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def plugin_manifests(layout: Layout, report: Report) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    for plugin in layout.plugins:
        path = plugin / ".codex-plugin" / "plugin.json"
        label = relative(path, layout.root)
        try:
            data = read_json(path)
        except Exception as exc:
            report.fail(f"{label}: invalid plugin JSON: {exc}")
            continue
        required = ("name", "version", "description", "author", "interface")
        missing = [key for key in required if key not in data]
        if missing:
            report.fail(f"{label}: missing required fields {missing}")
            continue
        if layout.mode == "source-checkout" and data["name"] != plugin.name:
            report.fail(
                f"{label}: manifest name {data['name']!r} != folder {plugin.name!r}"
            )
        if not isinstance(data["version"], str) or not SEMVER.fullmatch(data["version"]):
            report.fail(f"{label}: version is not strict semver")
        if not isinstance(data["description"], str) or not data["description"].strip():
            report.fail(f"{label}: description must be non-empty")
        if not isinstance(data["author"], dict) or not data["author"].get("name"):
            report.fail(f"{label}: author.name is required")
        interface = data.get("interface")
        required_ui = ("displayName", "shortDescription", "longDescription",
                       "developerName", "category", "capabilities", "defaultPrompt")
        if not isinstance(interface, dict):
            report.fail(f"{label}: interface must be an object")
        else:
            absent = [key for key in required_ui if key not in interface]
            if absent:
                report.fail(f"{label}: interface missing {absent}")
        if data.get("skills") != "./skills/":
            report.fail(f"{label}: skills must be './skills/'")
        if "commands" in data:
            report.fail(f"{label}: unsupported Claude commands field is present")
        manifests.append(data)
    if manifests:
        report.ok(f"validated {len(manifests)} Codex plugin manifests")
    return manifests


def skill_paths(layout: Layout) -> list[Path]:
    return sorted(
        skill
        for plugin in layout.plugins
        for skill in (plugin / "skills").glob("*/SKILL.md")
    )


def validate_skills(layout: Layout, report: Report) -> list[Path]:
    skills = skill_paths(layout)
    names: dict[str, Path] = {}
    for path in skills:
        label = relative(path, layout.root)
        try:
            frontmatter, body = split_frontmatter(path)
        except Exception as exc:
            report.fail(f"{label}: invalid YAML frontmatter: {exc}")
            continue
        extra = set(frontmatter) - ALLOWED_SKILL_FRONTMATTER
        if extra:
            report.fail(f"{label}: unsupported frontmatter fields {sorted(extra)}")
        name = frontmatter.get("name")
        description = frontmatter.get("description")
        if name != path.parent.name:
            report.fail(f"{label}: name must match skill folder")
        if not isinstance(description, str) or not description.strip():
            report.fail(f"{label}: description must be non-empty")
        key = str(name)
        if key in names:
            report.fail(
                f"duplicate globally-invoked skill {key!r} in {label} and "
                f"{relative(names[key], layout.root)}"
            )
        names[key] = path
        ui = path.parent / "agents" / "openai.yaml"
        if not ui.is_file():
            report.fail(f"{relative(ui, layout.root)}: missing skill UI metadata")
        else:
            try:
                ui_data = read_yaml(ui)
                interface = ui_data.get("interface") if isinstance(ui_data, dict) else None
                if not isinstance(interface, dict):
                    raise ValueError("interface mapping is required")
                for key_name in ("display_name", "short_description", "default_prompt"):
                    if not isinstance(interface.get(key_name), str) or not interface[key_name].strip():
                        raise ValueError(f"interface.{key_name} is required")
                if f"${name}" not in interface["default_prompt"]:
                    raise ValueError("default_prompt must explicitly mention the skill")
                policy = ui_data.get("policy", {})
                implicit = policy.get("allow_implicit_invocation", True)
                if not isinstance(implicit, bool):
                    raise ValueError("policy.allow_implicit_invocation must be boolean")
            except Exception as exc:
                report.fail(f"{relative(ui, layout.root)}: invalid metadata: {exc}")

        if "${CLAUDE_PLUGIN_ROOT}" in body or "${CLAUDE_PLUGIN_DATA}" in body:
            report.fail(f"{label}: contains a Claude-only plugin-root variable")
        if STALE_NEXT_COMMAND.search(body):
            report.fail(f"{label}: contains stale 'Next command' wording")
        if not body.rstrip().endswith(USER_OUTPUT_CONTRACT):
            report.fail(
                f"{label}: must end with the canonical seven-part user-facing output contract"
            )
        if re.search(r"\b(?:python3|python|py\s+-3)\s+scripts[/\\]", body):
            report.fail(f"{label}: runs a helper relative to the current directory")
        for root_marker, helper in PY_HELPER.findall(body):
            if root_marker == "<resolved-plugin-root>":
                helper_path = path.parents[2] / Path(helper)
            else:
                helper_path = path.parent / Path(helper)
            helper_path = helper_path.resolve()
            if not helper_path.is_file():
                report.fail(
                    f"{label}: helper reference {helper!r} does not resolve in the skill"
                )
        legacy = sorted(set(LEGACY_COMMAND.findall(body)))
        if legacy:
            report.fail(f"{label}: legacy Claude command references remain: {legacy}")
    if skills:
        report.ok(f"validated {len(skills)} Codex skills and UI metadata files")
    return skills


def load_command_map(root: Path, report: Report) -> list[dict[str, Any]]:
    path = root / "command-map.json"
    if not path.is_file():
        report.fail("command-map.json is missing")
        return []
    try:
        raw = read_json(path)
    except Exception as exc:
        report.fail(f"command-map.json is invalid: {exc}")
        return []
    if isinstance(raw, dict):
        raw = raw.get("commands", raw.get("mappings", []))
    if not isinstance(raw, list):
        report.fail("command-map.json must contain a commands array")
        return []
    invocations: set[str] = set()
    targets: set[str] = set()
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            report.fail(f"command-map.json entry {index} is not an object")
            continue
        legacy = entry.get("legacy") or entry.get("legacy_invocation")
        codex = entry.get("codex") or entry.get("codex_invocation")
        target = entry.get("target") or entry.get("target_path")
        if not isinstance(legacy, str) or not LEGACY_COMMAND.fullmatch(legacy):
            report.fail(f"command-map.json entry {index} has invalid legacy invocation")
        if not isinstance(codex, str) or not re.fullmatch(r"\$[a-z][a-z0-9-]*", codex):
            report.fail(f"command-map.json entry {index} has invalid Codex invocation")
        elif codex in invocations:
            report.fail(f"duplicate Codex command mapping: {codex}")
        else:
            invocations.add(codex)
        if not isinstance(target, str):
            report.fail(f"command-map.json entry {index} has no target path")
        else:
            normalized = target.replace("\\", "/")
            if normalized in targets:
                report.fail(f"duplicate command target: {normalized}")
            targets.add(normalized)
            if not (root / normalized).is_file():
                report.fail(f"mapped command target is missing: {normalized}")
    if raw:
        report.ok(f"validated {len(raw)} one-to-one command-to-skill mappings")
    return raw


def validate_marketplace(layout: Layout, manifests: list[dict[str, Any]],
                         report: Report) -> None:
    if layout.marketplace is None:
        return
    try:
        market = read_json(layout.marketplace)
    except Exception as exc:
        report.fail(f"marketplace JSON is invalid: {exc}")
        return
    entries = market.get("plugins") if isinstance(market, dict) else None
    if not isinstance(entries, list):
        report.fail("marketplace plugins must be an array")
        return
    expected = {item.get("name") for item in manifests}
    actual: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            report.fail("marketplace plugin entry must be an object")
            continue
        name = entry.get("name")
        if name in actual:
            report.fail(f"marketplace contains duplicate plugin {name!r}")
        actual.add(name)
        source = entry.get("source")
        source_path = source.get("path") if isinstance(source, dict) else source
        if not isinstance(source_path, str) or not source_path.startswith("./"):
            report.fail(f"marketplace {name}: local source path must start with './'")
        elif not (layout.root / source_path[2:]).is_dir():
            report.fail(f"marketplace {name}: source path does not exist")
        policy = entry.get("policy")
        if not isinstance(policy, dict) or not {
            "installation", "authentication"
        }.issubset(policy):
            report.fail(f"marketplace {name}: complete policy is required")
        if not isinstance(entry.get("category"), str):
            report.fail(f"marketplace {name}: category is required")
    if actual != expected:
        report.fail(
            f"marketplace/manifest plugin mismatch: missing={sorted(expected-actual)}, "
            f"extra={sorted(actual-expected)}"
        )
    else:
        report.ok(f"marketplace exposes all {len(entries)} plugins")


def validate_release(layout: Layout, manifests: list[dict[str, Any]], skills: list[Path],
                     mappings: list[dict[str, Any]], report: Report) -> None:
    if layout.mode != "source-checkout":
        return
    release_path = layout.root / "RELEASE.json"
    if not release_path.is_file():
        report.fail("RELEASE.json is missing")
        return
    try:
        release = read_json(release_path)
    except Exception as exc:
        report.fail(f"RELEASE.json is invalid: {exc}")
        return
    version = release.get("version")
    previous = release.get("previous_version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        report.fail("RELEASE.json version is not strict semver")
    if version == previous:
        report.fail("release version was not changed from previous_version")
    divergent = sorted(
        item.get("name") for item in manifests if item.get("version") != version
    )
    if divergent:
        report.fail(f"plugin versions do not match release {version}: {divergent}")
    changelog = layout.root / "CHANGELOG.md"
    if not changelog.is_file():
        report.fail("CHANGELOG.md is missing")
    else:
        match = re.search(r"^##\s+\[?(\d+\.\d+\.\d+)\]?", changelog.read_text(
            encoding="utf-8"), re.MULTILINE)
        if not match or match.group(1) != version:
            report.fail("CHANGELOG top version does not match RELEASE.json")
    script_count = sum(
        1 for plugin in layout.plugins
        for path in plugin.rglob("*.py")
        if "__pycache__" not in path.parts
    )
    actual = {
        "plugins": len(manifests),
        "skills": len(skills),
        "commands": len(mappings),
        "scripts": script_count,
    }
    declared = release.get("counts")
    if declared != actual:
        report.fail(f"RELEASE.json counts mismatch: declared={declared}, actual={actual}")
    readme = layout.root / "README.md"
    if not readme.is_file():
        report.fail("README.md is missing")
    else:
        text = readme.read_text(encoding="utf-8")
        match = re.search(
            r"\*\*(\d+) plugins\*\*.*?\*\*(\d+) skills\*\*.*?"
            r"\*\*(\d+) migrated commands\*\*.*?\*\*(\d+) helper scripts\*\*",
            text, re.DOTALL,
        )
        if not match:
            report.fail("README inventory line is missing")
        else:
            claimed = dict(zip(actual, map(int, match.groups())))
            if claimed != actual:
                report.fail(f"README counts mismatch: claimed={claimed}, actual={actual}")
        prohibited = (
            r"any skill folder can be copied standalone",
            r"every skill (?:is|remains) standalone",
        )
        for pattern in prohibited:
            if re.search(pattern, text, re.IGNORECASE):
                report.fail("README makes an unsupported standalone-skill claim")
                break
    if not divergent and declared == actual:
        report.ok(f"release metadata and inventory agree at v{version}: {actual}")


def validate_agentrooms(layout: Layout, report: Report) -> None:
    candidates = [
        plugin / "skills" / "agent-room-templates" / "scripts" / "validate_rooms.py"
        for plugin in layout.plugins
    ]
    validator = next((path for path in candidates if path.is_file()), None)
    if validator is None:
        return
    if layout.mode == "installed-plugin":
        # AgentRooms is a suite-level runtime.  The ai plugin intentionally
        # carries its templates and validator, while the shared gate policy and
        # sibling gate validators remain in the separately installable gate
        # plugin.  Installed-plugin mode must not assume those siblings exist;
        # the source-checkout path below remains strict.
        report.warn(
            "AgentRooms validation skipped in installed-plugin mode: "
            "templates require the full suite root and sibling gate plugin"
        )
        return
    rooms = sorted(validator.parent.parent.glob("agentsrooms/*.json"))
    if not rooms:
        report.fail("AgentRooms validator is present but no templates were found")
        return
    try:
        spec = importlib.util.spec_from_file_location("solo_validate_rooms", validator)
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load validator module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        problems = module.validate_files([str(path) for path in rooms],
                                         suite_root=str(layout.root))
    except Exception as exc:
        report.fail(f"AgentRooms validation could not run: {exc}")
        return
    for problem in problems:
        report.fail(f"AgentRooms: {problem}")
    if not problems:
        report.ok(f"validated {len(rooms)} AgentRooms templates")


def validate_memory(project: str, report: Report) -> None:
    if project == "-":
        return
    solo = _resolve(Path(project)) / ".solo"
    if not solo.is_dir():
        report.warn(f"{solo}: project memory is not initialized")
        return
    missing = [name for name in MEMORY_FILES if not (solo / name).is_file()]
    if missing:
        report.warn(f"{solo}: missing memory files: {', '.join(missing)}")
    else:
        report.ok(f"project memory contains all {len(MEMORY_FILES)} standard files")


def print_report(layout: Layout | None, report: Report) -> int:
    print("== Solo Suite Codex mechanical self-check ==")
    if layout:
        print(f"MODE  {layout.mode}")
        print(f"ROOT  {layout.root}")
    for message in report.passes:
        print(f"PASS  {message}")
    for message in report.warnings:
        print(f"WARN  {message}")
    for message in report.failures:
        print(f"FAIL  {message}")
    print(
        f"== {len(report.passes)} pass, {len(report.warnings)} warn, "
        f"{len(report.failures)} fail =="
    )
    print("NOTE  This is a structural check, not proof of security or launch readiness.")
    return 1 if report.failures else 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=None)
    parser.add_argument("project_root", nargs="?", default=".")
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = Report()
    starts = [Path(args.root)] if args.root else [Path.cwd(), Path(__file__)]
    layout = next((found for start in starts if (found := discover(start))), None)
    if layout is None:
        report.fail("no Codex checkout or installed plugin root could be found")
        return print_report(None, report)
    manifests = plugin_manifests(layout, report)
    skills = validate_skills(layout, report)
    mappings = load_command_map(layout.root, report) if layout.mode == "source-checkout" else []
    validate_marketplace(layout, manifests, report)
    validate_agentrooms(layout, report)
    validate_release(layout, manifests, skills, mappings, report)
    validate_memory(args.project_root, report)
    return print_report(layout, report)


if __name__ == "__main__":
    raise SystemExit(main())
