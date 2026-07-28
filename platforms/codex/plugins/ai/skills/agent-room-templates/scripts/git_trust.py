#!/usr/bin/env python3
"""Content-level Git working-tree identity for the AgentRoom runner."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Mapping, Tuple


MANIFEST_SCHEMA = "solo-suite/agentroom-git-manifest-v1"


class GitTrustError(ValueError):
    """A repository does not exactly match its bound Git commit."""


def _run(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        completed = subprocess.run(
            ["git", "-C", str(root.resolve()), *arguments],
            capture_output=True, timeout=120, env=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitTrustError("Git content check could not run: %s" % exc) from exc
    if check and completed.returncode != 0:
        message = (completed.stdout + completed.stderr).decode(
            "utf-8", errors="replace",
        ).strip()
        raise GitTrustError("Git content check failed: %s" % message)
    return completed


def _decode_path(value: bytes) -> str:
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GitTrustError("tracked paths must be valid UTF-8") from exc


def _index_entries(root: Path) -> Dict[str, Tuple[str, str]]:
    entries: Dict[str, Tuple[str, str]] = {}
    for raw in _run(root, "ls-files", "--stage", "-z").stdout.split(b"\0"):
        if not raw:
            continue
        try:
            metadata, raw_path = raw.split(b"\t", 1)
            mode, object_id, stage = metadata.decode("ascii").split(" ")
        except (ValueError, UnicodeDecodeError) as exc:
            raise GitTrustError("Git returned a malformed index entry") from exc
        if stage != "0":
            raise GitTrustError("unmerged index entries are not allowed")
        path = _decode_path(raw_path)
        if mode == "160000":
            raise GitTrustError(
                "tracked submodules/gitlinks are not allowed: %s" % path
            )
        if path in entries:
            raise GitTrustError("Git index repeats tracked path %r" % path)
        entries[path] = (mode, object_id)
    return entries


def _reject_concealment_flags(root: Path) -> None:
    flagged: List[str] = []
    for option, description in (
        ("-v", "assume-unchanged/skip-worktree"),
        ("-f", "fsmonitor-valid"),
    ):
        for raw in _run(root, "ls-files", option, "-z").stdout.split(b"\0"):
            if not raw:
                continue
            if len(raw) < 3 or raw[1:2] != b" ":
                raise GitTrustError("Git returned malformed tracked-file flags")
            tag = chr(raw[0])
            # -v and -f lowercase their normal status tag when the respective
            # optimization bit is set.  S/s is the skip-worktree tag.
            if tag.islower() or tag.upper() == "S":
                flagged.append("%s:%s" % (description, _decode_path(raw[2:])))
    if flagged:
        raise GitTrustError(
            "tracked-file concealment flags are forbidden: " +
            ", ".join(sorted(set(flagged)))
        )


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _working_bytes(root: Path, relative: str, mode: str) -> Tuple[str, bytes]:
    path = root.resolve() / Path(relative)
    if mode == "160000":
        if not path.is_dir():
            raise GitTrustError("tracked submodule is missing: %s" % relative)
        head = _run(path, "rev-parse", "HEAD").stdout.strip()
        return "gitlink", head
    if path.is_symlink():
        try:
            return "symlink", os.fsencode(os.readlink(str(path)))
        except OSError as exc:
            raise GitTrustError("cannot read tracked symlink %s" % relative) from exc
    if not path.is_file():
        raise GitTrustError("tracked file is missing or not regular: %s" % relative)
    try:
        return "file", path.read_bytes()
    except OSError as exc:
        raise GitTrustError("cannot read tracked file %s" % relative) from exc


def build_manifest(root: Path, commit: str) -> Dict[str, Any]:
    """Build expected working-tree bytes from an exact clean commit."""
    repository = root.resolve()
    actual_head = _run(repository, "rev-parse", "HEAD").stdout.decode("ascii").strip()
    if actual_head != commit:
        raise GitTrustError("repository HEAD does not match the bound commit")
    _reject_concealment_flags(repository)
    staged = _run(
        repository, "-c", "core.fsmonitor=false", "diff-index", "--quiet",
        "--cached", commit, "--", check=False,
    )
    if staged.returncode not in {0, 1}:
        raise GitTrustError("Git could not compare the index to the bound commit")
    if staged.returncode == 1:
        raise GitTrustError("Git index differs from the bound commit")

    files: Dict[str, Dict[str, str]] = {}
    for relative, (mode, object_id) in sorted(_index_entries(repository).items()):
        kind, actual = _working_bytes(repository, relative, mode)
        if mode == "160000":
            expected = object_id.encode("ascii")
        else:
            expected = _run(
                repository, "cat-file", "--filters", "--path=" + relative,
                object_id,
            ).stdout
        if actual != expected:
            raise GitTrustError("tracked content differs from HEAD: %s" % relative)
        files[relative] = {
            "mode": mode,
            "object_id": object_id,
            "kind": kind,
            "digest": _sha256(actual),
        }
    return {"schema": MANIFEST_SCHEMA, "commit": commit, "files": files}


def verify_manifest(root: Path, manifest: Mapping[str, Any], commit: str) -> None:
    """Re-hash every tracked working-tree byte against a prepared manifest."""
    if (not isinstance(manifest, dict) or
            set(manifest) != {"schema", "commit", "files"} or
            manifest.get("schema") != MANIFEST_SCHEMA or
            manifest.get("commit") != commit or
            not isinstance(manifest.get("files"), dict)):
        raise GitTrustError("tracked-content manifest is malformed")
    repository = root.resolve()
    actual_head = _run(repository, "rev-parse", "HEAD").stdout.decode("ascii").strip()
    if actual_head != commit:
        raise GitTrustError("repository HEAD does not match the tracked manifest")
    _reject_concealment_flags(repository)
    current = _index_entries(repository)
    expected_files = manifest["files"]
    if set(current) != set(expected_files):
        raise GitTrustError("tracked path inventory differs from the manifest")
    for relative, entry in expected_files.items():
        if (not isinstance(entry, dict) or
                set(entry) != {"mode", "object_id", "kind", "digest"}):
            raise GitTrustError("tracked manifest entry is malformed: %s" % relative)
        mode, object_id = current[relative]
        if mode != entry.get("mode") or object_id != entry.get("object_id"):
            raise GitTrustError("tracked index identity changed: %s" % relative)
        kind, actual = _working_bytes(repository, relative, mode)
        if kind != entry.get("kind") or _sha256(actual) != entry.get("digest"):
            raise GitTrustError("tracked working-tree content changed: %s" % relative)
