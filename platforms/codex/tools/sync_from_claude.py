#!/usr/bin/env python3
"""Regenerate the Codex adapter from a canonical Solo Suite Claude checkout.

Claude commands become explicit-only Codex skills.  Shared specialist skills and
platform-neutral helpers are copied from the canonical tree.  Codex-native
AgentRoom runtime files and the Codex integrity checker are preserved as declared
adapter implementations, and the canonical room files are archived for review.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_VERSION = "1.0.27"
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".txt"}
ADAPTER_SKILLS = {
    ("ai", "agent-room-templates"),
    ("solo", "suite-integrity"),
}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def title_case(value: str) -> str:
    acronyms = {
        "a11y": "A11y", "ai": "AI", "api": "API", "authz": "AuthZ",
        "ci": "CI", "db": "DB", "e2e": "E2E", "prd": "PRD",
        "qa": "QA", "rls": "RLS", "seo": "SEO", "ui": "UI", "ux": "UX",
    }
    return " ".join(acronyms.get(word, word[:1].upper() + word[1:]) for word in value.split("-"))


def normalize_skill_frontmatter(text: str) -> str:
    """Remove Claude-only model-invocation metadata from SKILL.md."""
    match = re.match(r"^---\n(?P<header>.*?)\n---\n?(?P<body>.*)$", text, re.S)
    if not match:
        return text
    header = [
        line for line in match.group("header").splitlines()
        if not line.lower().startswith("disable-model-invocation:")
    ]
    return "---\n" + "\n".join(header) + "\n---\n" + match.group("body")


def translate_text(text: str, plugin: str, skill: str, *, command_skill: bool = False) -> str:
    text = text.replace("\r\n", "\n")
    # Installed Codex skills resolve helpers relative to their own SKILL.md.
    def skill_path(match: re.Match[str]) -> str:
        helper = match.group(1)
        if not command_skill and helper == skill:
            return "<skill-root>/"
        return f"<skill-root>/../{helper}/"

    text = re.sub(
        r"\$\{CLAUDE_PLUGIN_ROOT\}/skills/([a-z0-9-]+)/",
        skill_path,
        text,
        flags=re.I,
    )
    text = text.replace("${CLAUDE_PLUGIN_ROOT}/lib/", "<skill-root>/../../lib/")
    text = text.replace("${CLAUDE_PLUGIN_ROOT}", "<resolved-plugin-root>")
    text = re.sub(
        r"(?<![A-Za-z0-9])/(?!/)([a-z0-9-]+):([a-z0-9*-]+)",
        lambda match: f"${match.group(1).lower()}-{match.group(2).lower()}",
        text,
        flags=re.I,
    )
    text = text.replace("CLAUDE.md", "AGENTS.md")
    text = text.replace("Claude Code", "Codex")
    text = re.sub(r"slash commands", "skill invocations", text, flags=re.I)
    text = re.sub(r"slash command", "skill invocation", text, flags=re.I)
    text = text.replace("Next Recommended Command", "Next Recommended Skill")
    text = re.sub(r"\bnext command\b", "next skill", text, flags=re.I)
    text = re.sub(
        r"(?m)^/…$",
        "Choose the next validated skill for the current workflow.",
        text,
    )
    return text


def explicit_policy(yaml_text: str) -> str:
    text = yaml_text.replace("\r\n", "\n").rstrip() + "\n"
    if re.search(r"^policy:\s*$", text, re.M):
        if re.search(r"^\s+allow_implicit_invocation:\s*(?:true|false)\s*$", text, re.M):
            text = re.sub(
                r"^(\s+allow_implicit_invocation:)\s*(?:true|false)\s*$",
                r"\1 false",
                text,
                flags=re.M,
            )
        else:
            text += "  allow_implicit_invocation: false\n"
    else:
        text += "policy:\n  allow_implicit_invocation: false\n"
    return text


def generated_openai(skill: str) -> str:
    display = title_case(skill)
    short = f"Run the {display} workflow in Codex"
    if len(short) > 64:
        short = f"Run the {display} workflow"[:64].rstrip()
    return (
        "interface:\n"
        f"  display_name: {json.dumps(display)}\n"
        f"  short_description: {json.dumps(short)}\n"
        f"  default_prompt: {json.dumps(f'Use ${skill} to help with this project.')}\n"
        "policy:\n"
        "  allow_implicit_invocation: false\n"
    )


def safe_remove_skill(path: Path, target: Path) -> None:
    expected_root = (target / "plugins").resolve()
    resolved = path.resolve()
    if expected_root not in resolved.parents or path.name in {"", ".", ".."}:
        raise RuntimeError(f"refusing to remove path outside target plugins: {path}")
    if path.is_symlink():
        raise RuntimeError(f"refusing to remove symlinked skill: {path}")
    if path.exists():
        shutil.rmtree(path)


def remove_derived_skills(target: Path) -> None:
    map_path = target / "command-map.json"
    if not map_path.is_file():
        return
    for entry in load_json(map_path):
        plugin = entry.get("plugin")
        skill = entry.get("skill_name")
        if not isinstance(plugin, str) or not isinstance(skill, str):
            raise RuntimeError("invalid existing command-map entry")
        safe_remove_skill(target / "plugins" / plugin / "skills" / skill, target)


def copy_specialists(source: Path, target: Path) -> int:
    count = 0
    for source_skill_md in sorted(source.glob("plugins/*/skills/*/SKILL.md")):
        skill_root = source_skill_md.parent
        plugin = source_skill_md.parents[2].name
        skill = skill_root.name
        if (plugin, skill) in ADAPTER_SKILLS:
            continue
        target_skill = target / "plugins" / plugin / "skills" / skill
        old_openai = target_skill / "agents" / "openai.yaml"
        interface = old_openai.read_text(encoding="utf-8") if old_openai.is_file() else ""
        shutil.copytree(
            skill_root,
            target_skill,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        for path in target_skill.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            body = path.read_text(encoding="utf-8")
            body = translate_text(body, plugin, skill)
            if path.name == "SKILL.md":
                body = normalize_skill_frontmatter(body)
            path.write_bytes(body.encode("utf-8"))
        openai = target_skill / "agents" / "openai.yaml"
        openai.parent.mkdir(parents=True, exist_ok=True)
        openai.write_bytes(
            (explicit_policy(interface) if interface else generated_openai(skill))
            .encode("utf-8")
        )
        count += 1
    return count


def copy_shared_roots(source: Path, target: Path) -> None:
    for relative in (Path("plugins/gate/lib"), Path("plugins/site-doctor/lib")):
        source_root = source / relative
        target_root = target / relative
        target_root.mkdir(parents=True, exist_ok=True)
        for source_path in source_root.rglob("*"):
            if not source_path.is_file() or source_path.suffix in {".pyc", ".pyo"}:
                continue
            target_path = target_root / source_path.relative_to(source_root)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)


def run_converter(source: Path, target: Path, node: str) -> None:
    command = [
        node,
        str(target / "tools" / "convert_commands_to_skills.mjs"),
        "--source-root", str(source),
        "--package-root", str(target),
        "--skip-init",
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"command converter failed:\n{result.stdout}{result.stderr}")
    print(result.stdout.strip())

    # Apply portable helper paths that depend on the generated skill's location.
    for entry in load_json(target / "command-map.json"):
        skill_md = target / entry["target_path"]
        body = skill_md.read_text(encoding="utf-8")
        body = translate_text(body, entry["plugin"], entry["skill_name"], command_skill=True)
        skill_md.write_bytes(body.encode("utf-8"))


def normalize_output_contracts(target: Path) -> None:
    """Reapply the Codex-native terminal response contract after source sync."""
    command = [
        sys.executable,
        str(target / "tools" / "normalize_skill_contracts.py"),
        "--root",
        str(target),
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(
            f"skill output-contract normalization failed:\n{result.stdout}{result.stderr}"
        )
    print(result.stdout.strip())


def make_all_explicit(target: Path) -> None:
    for skill_md in target.glob("plugins/*/skills/*/SKILL.md"):
        skill = skill_md.parent.name
        openai = skill_md.parent / "agents" / "openai.yaml"
        openai.parent.mkdir(parents=True, exist_ok=True)
        content = openai.read_text(encoding="utf-8") if openai.is_file() else generated_openai(skill)
        openai.write_bytes(explicit_policy(content).encode("utf-8"))


def copy_parity(source: Path, target: Path) -> None:
    source_parity = source / "parity"
    target_parity = target / "parity"
    target_parity.mkdir(parents=True, exist_ok=True)
    # capabilities.json is the canonical machine contract.  Other target
    # parity files document and reproduce the Codex adapter/release overlay;
    # overwriting them with Claude-facing prose would erase that provenance.
    source_manifest = source_parity / "capabilities.json"
    if source_manifest.is_file():
        shutil.copy2(source_manifest, target_parity / source_manifest.name)
    source_rooms = source / "plugins" / "ai" / "skills" / "agent-room-templates"
    if source_rooms.is_dir():
        archive = target_parity / "claude-rooms"
        if archive.exists():
            shutil.rmtree(archive)
        shutil.copytree(
            source_rooms,
            archive,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
    parity_tool = source / "tools" / "parity.py"
    if parity_tool.is_file():
        shutil.copy2(parity_tool, target / "tools" / "parity.py")


def sync(source: Path, target: Path, node: str) -> None:
    source = source.resolve()
    target = target.resolve()
    if source == target or not (source / "plugins").is_dir() or not (target / "plugins").is_dir():
        raise RuntimeError("source and target must be distinct Solo Suite checkouts")
    source_plugins = sorted(path.name for path in (source / "plugins").iterdir() if path.is_dir())
    target_plugins = sorted(path.name for path in (target / "plugins").iterdir() if path.is_dir())
    if source_plugins != target_plugins or not source_plugins:
        raise RuntimeError(f"plugin inventory mismatch: source={source_plugins}, target={target_plugins}")

    remove_derived_skills(target)
    specialists = copy_specialists(source, target)
    copy_shared_roots(source, target)
    run_converter(source, target, node)
    normalize_output_contracts(target)
    make_all_explicit(target)
    copy_parity(source, target)
    mappings = load_json(target / "command-map.json")
    print(
        f"Synchronized {len(source_plugins)} plugins, {len(mappings)} commands, "
        f"and {specialists + len(ADAPTER_SKILLS)} specialist skills from {source}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="canonical Claude checkout")
    parser.add_argument("--target", type=Path, default=ROOT, help="Codex checkout to update")
    parser.add_argument("--node", default="node")
    args = parser.parse_args(argv)
    try:
        sync(args.source, args.target, args.node)
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
