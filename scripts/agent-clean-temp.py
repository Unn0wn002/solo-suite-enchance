#!/usr/bin/env python3
"""Safely remove only the isolated agent extension audit directory."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
from pathlib import Path

from agent_platform_common import ROOT, is_within


TARGET = ROOT / ".tmp" / "agent-extension-audit"


def remove_readonly(func, path: str, exc_info) -> None:
    """Retry removal of read-only Git files, but only inside the audited temp root."""
    candidate = Path(path).resolve()
    if not is_within(candidate, TARGET.resolve()):
        raise RuntimeError(f"refused cleanup retry outside audit directory: {candidate}") from exc_info
    if not isinstance(exc_info, PermissionError):
        raise exc_info
    os.chmod(candidate, stat.S_IWRITE)
    func(candidate)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target = TARGET.resolve()
    workspace = ROOT.resolve()
    expected_parent = (ROOT / ".tmp").resolve()
    if (
        not is_within(target, workspace)
        or target.parent != expected_parent
        or target.name != "agent-extension-audit"
        or target == workspace
    ):
        print(f"ERROR: refused unsafe cleanup target: {target}", file=sys.stderr)
        return 2
    if not TARGET.exists():
        print("isolated audit directory is already absent")
        return 0
    if TARGET.is_symlink():
        print("ERROR: refused to recurse into a symbolic-link audit directory", file=sys.stderr)
        return 2
    count = sum(1 for _ in TARGET.rglob("*"))
    if args.dry_run:
        print(f"would remove {target} ({count} entries)")
        return 0
    shutil.rmtree(TARGET, onexc=remove_readonly)
    print(f"removed {target} ({count} entries); this generated audit cache is not recoverable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
