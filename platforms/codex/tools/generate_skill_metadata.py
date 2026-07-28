#!/usr/bin/env python3
"""Normalize Codex skill frontmatter and create missing UI metadata."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = (
    Path.home() / ".codex" / "skills" / ".system" / "skill-creator" /
    "scripts" / "generate_openai_yaml.py"
)
EXPLICIT_ONLY = {
    "agent-room-templates",
    "authz-security-reviewer",
    "backup-recovery",
    "browser-qa-engineer",
    "connector-auditor",
    "cost-optimization",
    "data-migration",
    "database-debug",
    "database-fix",
    "deployment-review",
    "devops-engineer",
    "fullstack-developer",
    "git-workflow-manager",
    "incident-response",
    "load-testing",
    "memory-sync",
    "payments-audit",
    "performance-tuning",
    "production-readiness-reviewer",
    "quality-gatekeeper",
    "security-review",
    "security-reviewer",
    "website-fix",
}


def parse_skill(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: missing frontmatter")
    end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    data = yaml.safe_load("".join(lines[1:end]))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: frontmatter is not a mapping")
    return data, "".join(lines[end + 1:]).lstrip("\r\n")


def quote_yaml(value: str) -> str:
    return json_quote(value)


def json_quote(value: str) -> str:
    import json
    return json.dumps(value, ensure_ascii=False)


def main() -> None:
    normalized = generated = protected = 0
    for skill_file in sorted((ROOT / "plugins").glob("*/skills/*/SKILL.md")):
        data, body = parse_skill(skill_file)
        name = data.get("name")
        description = data.get("description")
        if not isinstance(name, str) or not isinstance(description, str):
            raise ValueError(f"{skill_file}: name and description are required")
        canonical = (
            "---\n"
            f"name: {name}\n"
            f"description: {json_quote(description)}\n"
            "---\n\n"
            f"{body}"
        )
        if skill_file.read_text(encoding="utf-8") != canonical:
            with skill_file.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(canonical)
            normalized += 1

        metadata = skill_file.parent / "agents" / "openai.yaml"
        if not metadata.is_file():
            display = name.replace("-", " ").title()
            short = f"Run the {display} workflow in Codex"
            prompt = f"Use ${name} to help with this project."
            subprocess.run(
                [
                    sys.executable, str(GENERATOR), str(skill_file.parent),
                    "--interface", f"display_name={display}",
                    "--interface", f"short_description={short}",
                    "--interface", f"default_prompt={prompt}",
                ],
                check=True,
            )
            generated += 1

        if name in EXPLICIT_ONLY:
            text = metadata.read_text(encoding="utf-8")
            if "allow_implicit_invocation:" not in text:
                if not text.endswith("\n"):
                    text += "\n"
                text += "policy:\n  allow_implicit_invocation: false\n"
                with metadata.open("w", encoding="utf-8", newline="\n") as handle:
                    handle.write(text)
                protected += 1
    print(
        f"Normalized {normalized} skills; generated {generated} metadata files; "
        f"protected {protected} sensitive skills"
    )


if __name__ == "__main__":
    main()
