#!/usr/bin/env python3
"""Verify that a draft release still contains the exact uploaded asset bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import quote


MAX_ASSET_BYTES = 100 * 1024 * 1024


class ReleaseAssetError(RuntimeError):
    """The remote draft release does not match the validated local assets."""


def gh_json(endpoint: str) -> dict:
    """Read one authenticated GitHub API object through the GitHub CLI."""

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
        raise ReleaseAssetError(f"GitHub API request failed for {endpoint}: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ReleaseAssetError(
            f"GitHub API returned invalid JSON for {endpoint}"
        ) from exc
    if not isinstance(payload, dict):
        raise ReleaseAssetError(f"GitHub API returned a non-object for {endpoint}")
    return payload


def gh_asset_bytes(repository: str, asset_id: int) -> bytes:
    """Download one release asset through the authenticated GitHub CLI."""

    result = subprocess.run(
        [
            "gh",
            "api",
            "--header",
            "Accept: application/octet-stream",
            f"repos/{repository}/releases/assets/{asset_id}",
        ],
        capture_output=True,
        timeout=120,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReleaseAssetError(
            f"GitHub asset download failed for {asset_id}: {detail}"
        )
    if len(result.stdout) > MAX_ASSET_BYTES:
        raise ReleaseAssetError(f"release asset {asset_id} exceeds the size cap")
    return result.stdout


def local_digest(path: Path) -> tuple[int, str]:
    if not path.is_file() or path.is_symlink():
        raise ReleaseAssetError(f"asset path is not a regular file: {path}")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_ASSET_BYTES:
                raise ReleaseAssetError(f"local asset exceeds the size cap: {path}")
            digest.update(chunk)
    return size, digest.hexdigest()


def verify_release_assets(
    repository: str,
    tag: str,
    paths: Iterable[Path],
    *,
    fetch_release: Callable[[str], dict] = gh_json,
    fetch_asset: Callable[[str, int], bytes] = gh_asset_bytes,
) -> list[tuple[str, int, str]]:
    """Verify exact draft-release membership, sizes, and SHA-256 bytes."""

    local: dict[str, tuple[Path, int, str]] = {}
    for raw_path in paths:
        path = Path(raw_path)
        name = path.name
        if not name or name in local:
            raise ReleaseAssetError(f"duplicate release asset name: {name!r}")
        size, digest = local_digest(path)
        local[name] = (path, size, digest)
    if not local:
        raise ReleaseAssetError("no release assets were supplied")

    release = fetch_release(
        f"repos/{repository}/releases/tags/{quote(tag, safe='')}"
    )
    if release.get("tag_name") != tag:
        raise ReleaseAssetError(
            f"release tag mismatch: expected {tag!r}, got {release.get('tag_name')!r}"
        )
    if release.get("draft") is not True:
        raise ReleaseAssetError("release must still be a draft before publication")
    remote_assets = release.get("assets")
    if not isinstance(remote_assets, list):
        raise ReleaseAssetError("release response has no asset list")

    by_name: dict[str, dict] = {}
    for asset in remote_assets:
        if not isinstance(asset, dict) or not isinstance(asset.get("name"), str):
            raise ReleaseAssetError("release contains a malformed asset record")
        name = asset["name"]
        if name in by_name:
            raise ReleaseAssetError(f"release contains duplicate asset {name!r}")
        by_name[name] = asset

    expected_names = set(local)
    actual_names = set(by_name)
    missing = sorted(expected_names - actual_names)
    unexpected = sorted(actual_names - expected_names)
    if missing or unexpected:
        details = []
        if missing:
            details.append(f"missing={missing}")
        if unexpected:
            details.append(f"unexpected={unexpected}")
        raise ReleaseAssetError("release asset set mismatch: " + "; ".join(details))

    verified: list[tuple[str, int, str]] = []
    for name in sorted(local):
        _path, expected_size, expected_digest = local[name]
        asset = by_name[name]
        if asset.get("state") not in {None, "uploaded"}:
            raise ReleaseAssetError(f"asset {name!r} is not uploaded")
        remote_size = asset.get("size")
        if not isinstance(remote_size, int) or remote_size != expected_size:
            raise ReleaseAssetError(
                f"asset {name!r} size mismatch: expected {expected_size}, got {remote_size}"
            )
        asset_id = asset.get("id")
        if not isinstance(asset_id, int):
            raise ReleaseAssetError(f"asset {name!r} has no numeric id")
        remote_bytes = fetch_asset(repository, asset_id)
        if len(remote_bytes) != expected_size:
            raise ReleaseAssetError(
                f"asset {name!r} downloaded size mismatch: expected {expected_size}, "
                f"got {len(remote_bytes)}"
            )
        remote_digest = hashlib.sha256(remote_bytes).hexdigest()
        if remote_digest != expected_digest:
            raise ReleaseAssetError(
                f"asset {name!r} digest mismatch: expected {expected_digest}, "
                f"got {remote_digest}"
            )
        advertised = asset.get("digest")
        if not isinstance(advertised, str) or not advertised.startswith("sha256:"):
            raise ReleaseAssetError(
                f"asset {name!r} is missing a sha256 advertised digest"
            )
        if advertised[7:].lower() != expected_digest:
            raise ReleaseAssetError(
                f"asset {name!r} advertised digest mismatch: {advertised}"
            )
        verified.append((name, expected_size, expected_digest))
    return verified


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--asset", action="append", required=True, metavar="PATH")
    args = parser.parse_args()
    try:
        verified = verify_release_assets(
            args.repo,
            args.tag,
            [Path(path) for path in args.asset],
        )
    except ReleaseAssetError as exc:
        raise SystemExit(f"release asset verification failed: {exc}") from exc
    print(f"PASS draft release {args.tag}: {len(verified)} exact asset bytes verified")
    for name, size, digest in verified:
        print(f"PASS {name} size={size} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
