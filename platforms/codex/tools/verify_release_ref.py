#!/usr/bin/env python3
"""Bind a release tag to one exact protected default-branch commit."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from typing import Callable
from urllib.parse import quote


COMMIT_PATTERN = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
MAX_TAG_DEPTH = 8


class ReleaseRefError(RuntimeError):
    """The remote release reference is missing, malformed, or not bound."""


def gh_json(endpoint: str) -> dict:
    """Read one GitHub API object through the authenticated GitHub CLI."""

    result = subprocess.run(
        ["gh", "api", endpoint],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if result.returncode:
        detail = (result.stdout + result.stderr).strip()
        raise ReleaseRefError(f"GitHub API request failed for {endpoint}: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ReleaseRefError(
            f"GitHub API returned invalid JSON for {endpoint}"
        ) from exc
    if not isinstance(payload, dict):
        raise ReleaseRefError(f"GitHub API returned a non-object for {endpoint}")
    return payload


def object_identity(payload: dict, label: str) -> tuple[str, str]:
    value = payload.get("object")
    if not isinstance(value, dict):
        raise ReleaseRefError(f"{label} has no object identity")
    object_type = value.get("type")
    sha = value.get("sha")
    if object_type not in {"commit", "tag"} or not isinstance(sha, str):
        raise ReleaseRefError(f"{label} has an unsupported object identity")
    sha = sha.lower()
    if COMMIT_PATTERN.fullmatch(sha) is None:
        raise ReleaseRefError(f"{label} has an invalid object SHA")
    return object_type, sha


def peel_tag(
    repository: str,
    tag: str,
    fetch: Callable[[str], dict] = gh_json,
) -> str:
    """Resolve lightweight or annotated tags to their final commit SHA."""

    endpoint = f"repos/{repository}/git/ref/tags/{quote(tag, safe='')}"
    object_type, sha = object_identity(fetch(endpoint), f"tag {tag!r}")
    seen: set[str] = set()
    for _ in range(MAX_TAG_DEPTH):
        if object_type == "commit":
            return sha
        if sha in seen:
            raise ReleaseRefError(f"tag {tag!r} contains an object cycle")
        seen.add(sha)
        endpoint = f"repos/{repository}/git/tags/{sha}"
        object_type, sha = object_identity(
            fetch(endpoint), f"annotated tag object {sha}"
        )
    raise ReleaseRefError(f"tag {tag!r} exceeds the maximum annotation depth")


def default_branch_head(
    repository: str,
    branch: str,
    fetch: Callable[[str], dict] = gh_json,
) -> str:
    endpoint = f"repos/{repository}/commits/{quote(branch, safe='')}"
    sha = fetch(endpoint).get("sha")
    if not isinstance(sha, str) or COMMIT_PATTERN.fullmatch(sha.lower()) is None:
        raise ReleaseRefError(f"default branch {branch!r} has an invalid commit SHA")
    return sha.lower()


def local_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if result.returncode:
        raise ReleaseRefError(f"unable to resolve local HEAD: {result.stderr.strip()}")
    sha = result.stdout.strip().lower()
    if COMMIT_PATTERN.fullmatch(sha) is None:
        raise ReleaseRefError("local HEAD is not a full commit SHA")
    return sha


def verify_release_ref(
    repository: str,
    tag: str,
    expected_commit: str,
    default_branch: str,
    *,
    check_local_head: bool = False,
    fetch: Callable[[str], dict] = gh_json,
    read_local_head: Callable[[], str] = local_head,
) -> None:
    expected = expected_commit.lower()
    if COMMIT_PATTERN.fullmatch(expected) is None:
        raise ReleaseRefError("expected release commit is not a full commit SHA")
    tag_commit = peel_tag(repository, tag, fetch)
    branch_commit = default_branch_head(repository, default_branch, fetch)
    if tag_commit != expected:
        raise ReleaseRefError(
            f"remote tag {tag!r} resolves to {tag_commit}, expected {expected}"
        )
    if branch_commit != expected:
        raise ReleaseRefError(
            f"default branch {default_branch!r} is {branch_commit}, expected {expected}"
        )
    if check_local_head:
        checked_out = read_local_head().lower()
        if checked_out != expected:
            raise ReleaseRefError(
                f"checked-out HEAD is {checked_out}, expected {expected}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--default-branch", required=True)
    parser.add_argument("--check-local-head", action="store_true")
    args = parser.parse_args()
    try:
        verify_release_ref(
            args.repo,
            args.tag,
            args.expected_commit,
            args.default_branch,
            check_local_head=args.check_local_head,
        )
    except ReleaseRefError as exc:
        raise SystemExit(f"release reference verification failed: {exc}") from exc
    print(
        f"PASS {args.tag} and {args.default_branch} are bound to "
        f"{args.expected_commit.lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
