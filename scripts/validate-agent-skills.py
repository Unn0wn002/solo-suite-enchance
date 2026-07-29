#!/usr/bin/env python3
"""Validate canonical Agent Skills and generated Claude mirrors."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from agent_platform_common import NAME_RE, ROOT, canonical_skills, parse_frontmatter, relative


ALLOWED_FRONTMATTER = {"name", "description"}
ABSOLUTE_PATH_PATTERNS = [
    re.compile(r"[A-Za-z]:\\(?:Users|Documents and Settings)\\", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9])/(?:Users|home|root)/"),
    re.compile(r"(?<![A-Za-z0-9])~[/\\]"),
]
SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*[\"'][^\"']{8,}[\"']", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
DESTRUCTIVE_PATTERNS = [
    re.compile(r"\brm\s+-[^\n]*r[^\n]*f\b", re.IGNORECASE),
    re.compile(r"\bRemove-Item\b[^\n]*(?:-Recurse[^\n]*-Force|-Force[^\n]*-Recurse)", re.IGNORECASE),
    re.compile(r"\b(?:git\s+reset\s+--hard|git\s+clean\s+-[^\n]*f|--no-verify)\b", re.IGNORECASE),
    re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:ba|z|fi)?sh\b", re.IGNORECASE),
    re.compile(r"\b(?:irm|Invoke-RestMethod)\b[^\n|]*\|\s*(?:iex|Invoke-Expression)\b", re.IGNORECASE),
]
REFERENCE_RE = re.compile(r"(?:\]\(|`)((?:references|scripts|assets)/[^)`\s#]+)")


def validate_skill(directory: Path, names: dict[str, Path]) -> list[str]:
    errors: list[str] = []
    skill_file = directory / "SKILL.md"
    if not skill_file.is_file():
        return [f"{relative(directory)}: missing SKILL.md"]
    try:
        fields, body = parse_frontmatter(skill_file)
    except (OSError, ValueError) as exc:
        return [f"{relative(skill_file)}: {exc}"]

    unsupported = set(fields) - ALLOWED_FRONTMATTER
    if unsupported:
        errors.append(f"{relative(skill_file)}: unsupported frontmatter fields {sorted(unsupported)}")
    name = fields.get("name", "")
    description = fields.get("description", "")
    if name != directory.name:
        errors.append(f"{relative(skill_file)}: name {name!r} does not match directory {directory.name!r}")
    if not NAME_RE.fullmatch(name):
        errors.append(f"{relative(skill_file)}: name is not lowercase kebab-case")
    if name in names:
        errors.append(f"{relative(skill_file)}: duplicate canonical skill name also in {relative(names[name])}")
    else:
        names[name] = skill_file
    if not description:
        errors.append(f"{relative(skill_file)}: description is missing")
    else:
        lowered = description.lower()
        if "activate" not in lowered or "do not activate" not in lowered:
            errors.append(f"{relative(skill_file)}: description must state activate and do-not-activate boundaries")

    text = skill_file.read_text(encoding="utf-8")
    for pattern in ABSOLUTE_PATH_PATTERNS:
        if pattern.search(text):
            errors.append(f"{relative(skill_file)}: contains an absolute user path")
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append(f"{relative(skill_file)}: contains secret-like content")
    for pattern in DESTRUCTIVE_PATTERNS:
        if pattern.search(text):
            errors.append(f"{relative(skill_file)}: contains an obvious destructive or bypass command")
    for match in REFERENCE_RE.finditer(body):
        target = (directory / match.group(1)).resolve()
        try:
            target.relative_to(directory.resolve())
        except ValueError:
            errors.append(f"{relative(skill_file)}: reference escapes skill directory: {match.group(1)}")
            continue
        if not target.exists():
            errors.append(f"{relative(skill_file)}: missing referenced path {match.group(1)}")

    for support in (directory / "scripts", directory / "references", directory / "assets"):
        if support.exists() and not support.is_dir():
            errors.append(f"{relative(support)}: supporting path must be a directory")
    return errors


def main() -> int:
    errors: list[str] = []
    skills = canonical_skills()
    if not skills:
        errors.append(".agents/skills: no canonical skills found")
    names: dict[str, Path] = {}
    for directory in skills.values():
        errors.extend(validate_skill(directory, names))

    sync = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync-agent-skills.py"), "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if sync.returncode:
        detail = (sync.stdout + sync.stderr).strip()
        errors.append(f"Claude mirrors are stale: {detail}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Agent skill validation failed with {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"Agent skill validation passed: {len(skills)} canonical names, Claude mirrors current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
