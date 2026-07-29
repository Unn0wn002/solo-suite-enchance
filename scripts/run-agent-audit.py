#!/usr/bin/env python3
"""Run the deterministic, read-only agent audit verification pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> int:
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=ROOT, check=False)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the external source inspection plan and generated artifact plan without writing.",
    )
    args = parser.parse_args()
    python = sys.executable
    if args.dry_run:
        commands = [
            [python, "scripts/reconstruct-agent-extension-catalog.py", "--from-evidence", "--dry-run"],
            [python, "scripts/audit-agent-sources.py", "--dry-run"],
            [python, "scripts/build-agent-audit.py", "--dry-run"],
        ]
    else:
        commands = [
            [python, "scripts/reconstruct-agent-extension-catalog.py", "--check"],
            [python, "scripts/audit-agent-sources.py", "--check"],
            [python, "scripts/build-agent-audit.py", "--check"],
        ]
    failures = 0
    for command in commands:
        failures += run(command) != 0
    if failures:
        print(f"Agent audit verification failed: {failures} command(s)", file=sys.stderr)
        return 1
    print("Agent audit verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
