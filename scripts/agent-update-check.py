#!/usr/bin/env python3
"""Compare pinned source commits with each upstream default branch, read-only."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

from agent_platform_common import ROOT


LOCK = ROOT / "agent-platform" / "agent-extensions.lock.json"


def resolve_head(git: str, url: str) -> tuple[str | None, str | None, str]:
    try:
        result = subprocess.run(
            [git, "ls-remote", "--symref", url, "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, None, "timeout"
    if result.returncode:
        return None, None, (result.stderr or result.stdout).strip()[:300]
    branch = None
    commit = None
    for line in result.stdout.splitlines():
        if line.startswith("ref:"):
            ref = line.split()[1]
            branch = ref.removeprefix("refs/heads/")
        elif line.endswith("\tHEAD"):
            commit = line.split()[0]
    return branch, commit, "ok"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not LOCK.is_file():
        print("ERROR: agent extension lock file is missing", file=sys.stderr)
        return 2
    git = shutil.which("git")
    if not git:
        print("ERROR: Git is not installed", file=sys.stderr)
        return 2
    data = json.loads(LOCK.read_text(encoding="utf-8"))
    rows = []
    failures = 0
    for source in data.get("sources", []):
        url = source.get("source")
        pinned = source.get("commit_sha")
        branch, head, detail = resolve_head(git, url)
        if head is None:
            status = "NOT_EXECUTED"
            failures += 1
        elif head == pinned:
            status = "CURRENT"
        else:
            status = "UPDATE_AVAILABLE"
        rows.append({
            "source": url,
            "default_branch": branch,
            "pinned_commit": pinned,
            "upstream_commit": head,
            "status": status,
            "detail": detail,
        })
    if args.json:
        print(json.dumps({"sources": rows}, indent=2))
    else:
        for row in rows:
            print(f"{row['status']:16} {row['source']} pinned={row['pinned_commit']} upstream={row['upstream_commit']}")
        print("Read-only check complete. Re-audit changed sources before refreshing pins.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
