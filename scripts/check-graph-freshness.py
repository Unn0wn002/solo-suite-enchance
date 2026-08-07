#!/usr/bin/env python3
"""Fail when the Graphify graph no longer describes the current working tree.

Why this exists
---------------
`graphify-out/GRAPH_REPORT.md` tells you to compare `git rev-parse HEAD`
against the graph's `built_at_commit`. That check is not sufficient here, and
the 2026-08-07 audit (Audit #2) proved it: both values were `cea51645`, so the
documented check reported "fresh" — while the graph was in fact missing
`.github/workflows/ci.yml`, `app/robots.ts`, `app/sitemap.ts`,
`worker-configuration.d.ts`, `tests/page-interactions.test.mjs`, and 24 skill
directories, because that entire day's work was uncommitted.

A commit-SHA comparison is blind to uncommitted work. This repository routinely
carries large uncommitted working trees, so the SHA check is exactly the wrong
instrument. This validator compares the graph manifest against the files that
are actually on disk right now — tracked *and* untracked-but-not-ignored.

See docs/audit/MASTER_AUDIT.md, finding F-01 and Improvement-001.

Scope
-----
Deliberately narrow. It checks only source roots that represent structural
capability, and only extensions Graphify is known to extract into the manifest.
Files Graphify legitimately does not index (for example `.env.example`, which
has no extractable structure and is absent from the manifest even immediately
after a refresh) must not produce a false positive — a validator that cries
wolf gets disabled, which is worse than no validator.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from agent_platform_common import ROOT

MANIFEST = ROOT / "graphify-out" / "manifest.json"

# Directories whose contents represent structural capability. A change here is
# the kind of change that should be visible in an architecture graph.
#
# `platforms/` is deliberately excluded: it holds three vendored distribution
# checkouts (1257 files) with their own release cadence, on the same reasoning
# .github/dependabot.yml uses to scope itself to the root manifest. Including
# it would make this guard fire on every distribution sync and get it disabled.
STRUCTURAL_ROOTS = (
    "app",
    "worker",
    "db",
    "tests",
    "scripts",
    "drizzle",
    ".agents",
    ".claude",
    "agent-platform",
    ".github/workflows",
)

# Extensions Graphify extracts into graphify-out/manifest.json. Measured
# against the manifest produced by `graphify update .` on 2026-08-07 rather
# than assumed: .md 904, .py 224, .yaml 201, .json 188, .ps1 15, .ts 12,
# .mjs 11, .yml 8, .tsx 2, .js 1.
#
# `.md` matters most and is easy to leave out by mistake. Skills, workflows,
# rules, and role definitions in this repository ARE markdown — they are the
# capability, not documentation about it. A first draft of this validator
# omitted .md and would therefore have missed the 24 unindexed skill
# directories that were one of finding F-01's two symptoms. Do not narrow this
# set without re-checking what F-01 looked like.
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

# Root-level files that are structural despite living outside STRUCTURAL_ROOTS.
STRUCTURAL_ROOT_FILES = (
    "next.config.ts",
    "vite.config.ts",
    "drizzle.config.ts",
    "eslint.config.mjs",
    "postcss.config.mjs",
    "worker-configuration.d.ts",
)

REFRESH_HINT = (
    "Run `graphify update .` to refresh the graph, then re-run this check.\n"
    "  If the graph is intentionally stale (for example mid-refactor), say so\n"
    "  explicitly in docs/audit/MASTER_AUDIT.md rather than silencing this."
)


def tracked_and_untracked() -> list[str]:
    """Every file on disk that git would consider part of the project.

    `--cached` gives tracked files; `--others --exclude-standard` gives
    untracked files that are not ignored. Together they are the working tree as
    a reviewer would see it — which is precisely what the graph should match.
    """
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
        help="List every structural file missing from the graph instead of the first 20.",
    )
    args = parser.parse_args()

    if not MANIFEST.is_file():
        print(f"ERROR: no graph manifest at {MANIFEST.relative_to(ROOT).as_posix()}")
        print(f"  {REFRESH_HINT}")
        return 1

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
        print("Graph freshness check passed: every structural file is represented.")
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
