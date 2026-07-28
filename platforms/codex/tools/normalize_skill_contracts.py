#!/usr/bin/env python3
"""Normalize every Codex skill to one terminal user-facing output contract."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_HEADING = "## User-facing output contract"
CONTRACT_TEXT = (
    "Outside required machine-readable artifacts, end every response with exactly "
    "these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, "
    "**Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), "
    "**Verification**, and **Next skill** (the exact `$skill` invocation)."
)
CONTRACT = f"{CONTRACT_HEADING}\n\n{CONTRACT_TEXT}"
LEGACY_CONTRACT = re.compile(
    r"(?m)^End with the 7-part contract:.*(?:\n|\Z)"
)
STALE_NEXT = re.compile(r"\bnext command\b", re.IGNORECASE)


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = LEGACY_CONTRACT.sub("", text)
    marker = f"\n{CONTRACT_HEADING}\n"
    if marker in text:
        prefix, _, remainder = text.partition(marker)
        if remainder.strip() != CONTRACT_TEXT:
            raise ValueError(
                "existing user-facing output contract is not the canonical terminal block"
            )
        text = prefix

    def replace_next(match: re.Match[str]) -> str:
        return "Next skill" if match.group(0)[0].isupper() else "next skill"

    text = STALE_NEXT.sub(replace_next, text)
    return f"{text.rstrip()}\n\n{CONTRACT}\n"


def skill_paths(root: Path) -> list[Path]:
    return sorted(root.glob("plugins/*/skills/*/SKILL.md"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    paths = skill_paths(root)
    changed: list[Path] = []
    for path in paths:
        original = path.read_text(encoding="utf-8")
        normalized = normalize(original)
        if normalized == original:
            continue
        changed.append(path)
        if not args.check:
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(normalized)
    if args.check and changed:
        for path in changed:
            print(f"STALE {path.relative_to(root).as_posix()}")
        return 1
    verb = "verified" if args.check else "normalized"
    print(f"PASS {verb} {len(paths)} skill output contracts; changed={len(changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
