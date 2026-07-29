#!/usr/bin/env python3
"""Synchronize canonical portable skills into the Claude project adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / ".agents" / "skills"
TARGET_ROOT = ROOT / ".claude" / "skills"
MARKER_NAME = ".agent-skill-generated.json"
GENERATOR = "scripts/sync-agent-skills.py"
GENERATED_COMMENT = "<!-- GENERATED from .agents/skills by scripts/sync-agent-skills.py; do not edit. -->"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized_text_bytes(data: bytes) -> bytes:
    """Use canonical LF bytes for generated text on every checkout platform."""
    if b"\0" in data:
        return data
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def mirrored_bytes(path: Path) -> bytes:
    data = normalized_text_bytes(path.read_bytes())
    if path.name != "SKILL.md":
        return data
    text = data.decode("utf-8")
    closing = text.find("\n---", 4)
    if not text.startswith("---\n") or closing < 0:
        raise ValueError(f"{path.relative_to(ROOT)} has invalid frontmatter")
    insert_at = text.find("\n", closing + 1)
    if insert_at < 0:
        raise ValueError(f"{path.relative_to(ROOT)} has incomplete frontmatter")
    mirrored = text[: insert_at + 1] + "\n" + GENERATED_COMMENT + "\n" + text[insert_at + 1 :]
    return mirrored.encode("utf-8")


def source_skills() -> dict[str, Path]:
    if not SOURCE_ROOT.is_dir():
        raise FileNotFoundError(f"missing canonical skill root: {SOURCE_ROOT}")
    result: dict[str, Path] = {}
    for directory in sorted(path for path in SOURCE_ROOT.iterdir() if path.is_dir()):
        if not (directory / "SKILL.md").is_file():
            raise ValueError(f"{directory.relative_to(ROOT)} is missing SKILL.md")
        result[directory.name] = directory
    return result


def expected_skill_files(source: Path) -> dict[Path, bytes]:
    result: dict[Path, bytes] = {}
    for path in sorted(item for item in source.rglob("*") if item.is_file()):
        relative = path.relative_to(source)
        if relative.name == MARKER_NAME:
            continue
        result[relative] = mirrored_bytes(path)
    marker = {
        "generated_by": GENERATOR,
        "source": source.relative_to(ROOT).as_posix(),
        "files": {relative.as_posix(): sha256(data) for relative, data in result.items()},
    }
    result[Path(MARKER_NAME)] = (json.dumps(marker, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return result


def has_owned_marker(directory: Path) -> bool:
    marker = directory / MARKER_NAME
    if not marker.is_file():
        return False
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return data.get("generated_by") == GENERATOR


def safe_generated_directory(path: Path) -> bool:
    try:
        resolved = path.resolve()
        resolved.relative_to(TARGET_ROOT.resolve())
    except (OSError, ValueError):
        return False
    return resolved != TARGET_ROOT.resolve() and has_owned_marker(path)


def compare_directory(directory: Path, expected: dict[Path, bytes]) -> list[str]:
    differences: list[str] = []
    actual_files = {
        path.relative_to(directory)
        for path in directory.rglob("*")
        if path.is_file()
    } if directory.is_dir() else set()
    expected_files = set(expected)
    for relative in sorted(actual_files | expected_files):
        path = directory / relative
        if relative not in expected:
            differences.append(f"extra {path.relative_to(ROOT).as_posix()}")
        elif relative not in actual_files:
            differences.append(f"missing {path.relative_to(ROOT).as_posix()}")
        elif normalized_text_bytes(path.read_bytes()) != normalized_text_bytes(expected[relative]):
            differences.append(f"changed {path.relative_to(ROOT).as_posix()}")
    return differences


def write_directory(directory: Path, expected: dict[Path, bytes]) -> None:
    if directory.exists() and not has_owned_marker(directory):
        raise PermissionError(
            f"refusing to overwrite manually maintained Claude skill: {directory.relative_to(ROOT)}"
        )
    if directory.exists():
        for path in sorted((item for item in directory.rglob("*") if item.is_file()), reverse=True):
            if path.relative_to(directory) not in expected:
                path.unlink()
        for path in sorted((item for item in directory.rglob("*") if item.is_dir()), reverse=True):
            if not any(path.iterdir()):
                path.rmdir()
    directory.mkdir(parents=True, exist_ok=True)
    for relative, data in expected.items():
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Exit non-zero when mirrors are stale.")
    mode.add_argument("--dry-run", action="store_true", help="Show changes without writing.")
    args = parser.parse_args()

    try:
        sources = source_skills()
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    changes: list[str] = []
    expected_by_name = {name: expected_skill_files(source) for name, source in sources.items()}
    for name, expected in expected_by_name.items():
        target = TARGET_ROOT / name
        if target.exists() and not has_owned_marker(target):
            print(f"ERROR: manual Claude skill conflicts with canonical name: {target.relative_to(ROOT)}", file=sys.stderr)
            return 2
        differences = compare_directory(target, expected)
        if differences:
            changes.extend(differences)
            if not args.check and not args.dry_run:
                write_directory(target, expected)
                print(f"synchronized .claude/skills/{name}")

    if TARGET_ROOT.is_dir():
        for directory in sorted(path for path in TARGET_ROOT.iterdir() if path.is_dir()):
            if directory.name in sources or not has_owned_marker(directory):
                continue
            if not safe_generated_directory(directory):
                print(f"ERROR: refused unsafe stale mirror removal: {directory}", file=sys.stderr)
                return 2
            changes.append(f"stale generated .claude/skills/{directory.name}")
            if not args.check and not args.dry_run:
                shutil.rmtree(directory)
                print(f"removed stale generated .claude/skills/{directory.name}")

    if args.check:
        if changes:
            for change in changes:
                print(change)
            print(f"{len(changes)} mirror difference(s)", file=sys.stderr)
            return 1
        print("Claude skill mirrors are current")
    elif args.dry_run:
        if changes:
            for change in changes:
                print(f"would change: {change}")
        else:
            print("Claude skill mirrors are current")
    elif not changes:
        print("Claude skill mirrors are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
