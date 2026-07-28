#!/usr/bin/env python3
"""Translate synchronized Claude command references to Codex skills."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".json", ".py", ".yaml", ".yml", ".txt"}


def main() -> None:
    map_path = ROOT / "command-map.json"
    mappings = json.loads(map_path.read_text(encoding="utf-8"))
    source_prefix = "../solo-suite-v1.0.27-work/"
    map_changed = False
    for entry in mappings:
        source_path = entry.get("source_path")
        if isinstance(source_path, str) and source_path.startswith(source_prefix):
            entry["source_path"] = source_path[len(source_prefix):]
            map_changed = True
    if map_changed:
        with map_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(mappings, indent=2, ensure_ascii=False) + "\n")
    replacements = {
        entry["legacy_invocation"]: entry["codex_invocation"] for entry in mappings
    }
    changed = 0
    for path in sorted((ROOT / "plugins").rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        original = path.read_text(encoding="utf-8")
        text = original
        for legacy, codex in replacements.items():
            text = text.replace(legacy, codex)
        text = re.sub(
            r"(?<![\w])/(?:([a-z][a-z0-9-]*)):([a-z][a-z0-9-]*)-\*",
            lambda match: f"${match.group(1)}-{match.group(2)}-*",
            text,
        )
        text = re.sub(
            r"(?<![\w])/(?:([a-z][a-z0-9-]*)):\*",
            lambda match: f"${match.group(1)}-*",
            text,
        )
        text = text.replace("Claude Code", "Codex")
        text = text.replace("`CLAUDE.md`", "`AGENTS.md`")
        text = text.replace("project's `CLAUDE.md`", "project's `AGENTS.md`")
        text = text.replace("~/.claude/skills/", "~/.codex/skills/")
        text = text.replace(".claude/skills/", ".codex/skills/")
        if text != original:
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            changed += 1
    print(
        f"Translated references in {changed} plugin files; "
        f"normalized command map: {map_changed}"
    )


if __name__ == "__main__":
    main()
