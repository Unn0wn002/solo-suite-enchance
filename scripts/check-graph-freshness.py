#!/usr/bin/env python3
"""Validate a committed Graphify snapshot when one exists.

Solo Suite is distributed as AI tooling, not as a pre-indexed application.
`graphify-out/` is therefore an optional, local derived artifact. If a user
explicitly generates and commits a snapshot, this check fails closed when that
snapshot no longer represents the current structural AI-tooling surface.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from agent_platform_common import ROOT

MANIFEST = ROOT / "graphify-out" / "manifest.json"

STRUCTURAL_ROOTS = (
    "tests",
    "scripts",
    ".agents",
    ".claude",
    "agent-platform",
    ".github/workflows",
)

STRUCTURAL_SUFFIXES = {
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".py",
    ".yml",
    ".yaml",
    ".json",
    ".ps1",
    ".md",
}

STRUCTURAL_ROOT_FILES: tuple[str, ...] = ()

REFRESH_HINT = (
    "Run the reviewed project-local Graphify workflow to refresh the snapshot, "
    "or remove graphify-out/ if no persisted graph is intended."
)


def tracked_and_untracked() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git ls-files failed: {result.stderr.strip()}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_structural(path: str) -> bool:
    if Path(path).suffix not in STRUCTURAL_SUFFIXES:
        return False
    if path in STRUCTURAL_ROOT_FILES:
        return True
    return any(path == root or path.startswith(f"{root}/") for root in STRUCTURAL_ROOTS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list",
        action="store_true",
        help="List every structural file missing from an existing graph snapshot.",
    )
    args = parser.parse_args()

    if not MANIFEST.is_file():
        print("Graphify snapshot: NOT_INITIALIZED (allowed; graphify-out/ is optional derived data).")
        return 0

    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"ERROR: graph manifest is not valid JSON: {error}")
        return 1

    indexed = set(manifest)
    structural = sorted(path for path in tracked_and_untracked() if is_structural(path))
    missing = [path for path in structural if path not in indexed]

    print(
        f"graph manifest: {len(indexed)} indexed file(s); "
        f"working tree: {len(structural)} structural file(s)"
    )

    if not missing:
        print("Graph snapshot consistency passed: every structural file is represented.")
        return 0

    shown = missing if args.list else missing[:20]
    print(f"ERROR: {len(missing)} structural file(s) absent from the graph:")
    for path in shown:
        print(f"  - {path}")
    if len(shown) < len(missing):
        print(f"  ... and {len(missing) - len(shown)} more (pass --list to see all)")
    print(f"  {REFRESH_HINT}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
