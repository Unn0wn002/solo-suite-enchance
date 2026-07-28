#!/usr/bin/env python3
"""Append-only, digest-chained state authority for AgentRoom runs."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Any, Dict, List, Mapping, Optional, Tuple
import uuid


ENTRY_SCHEMA = "solo-suite/agentroom-state-journal-entry-v1"
HEAD_SCHEMA = "solo-suite/agentroom-state-journal-head-v1"
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ENTRY_NAME_RE = re.compile(r"^([0-9]{20})-([0-9a-f]{64})\.json$")


class JournalError(ValueError):
    """The state projection, journal, or external head is inconsistent."""


def _replace(source: Path, target: Path) -> None:
    for attempt in range(8):
        try:
            os.replace(str(source), str(target))
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.02 * (attempt + 1))


def canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def digest(payload: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JournalError("cannot read journal JSON %s: %s" % (path, exc)) from exc


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / (".tmp-%s" % uuid.uuid4().hex[:12])
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _exclusive_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise JournalError("state journal revision already exists: %s" % path.name)
    temporary = path.parent / (".tmp-%s" % uuid.uuid4().hex[:12])
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            raise JournalError("state journal revision already exists: %s" % path.name)
        _replace(temporary, path)
    except OSError as exc:
        raise JournalError("cannot append state journal entry %s: %s" % (path, exc)) from exc
    finally:
        temporary.unlink(missing_ok=True)


def journal_dir(state_path: Path) -> Path:
    lexical = state_path.absolute()
    if os.path.lexists(str(lexical)) and _is_linklike(lexical):
        raise JournalError("state projection is a link or reparse point")
    directory = lexical.parent / "state-journal"
    if os.path.lexists(str(directory)) and _is_linklike(directory):
        raise JournalError("state journal directory is a link or reparse point")
    return directory


def _is_linklike(path: Path) -> bool:
    """Detect symlinks and Windows reparse points without following them."""
    try:
        details = os.lstat(str(path))
    except OSError:
        return False
    if stat.S_ISLNK(details.st_mode):
        return True
    attributes = getattr(details, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse)


def registry_dir(project_root: Path) -> Path:
    """Return the lexical run registry only when no component is redirected."""
    project = project_root.resolve()
    current = project
    for part in ("artifacts", "runs", ".registry"):
        current = current / part
        if os.path.lexists(str(current)) and _is_linklike(current):
            raise JournalError(
                "state journal registry contains a link or reparse point: %s" %
                current
            )
        if os.path.lexists(str(current)) and not current.is_dir():
            raise JournalError(
                "state journal registry component is not a directory: %s" %
                current
            )
    try:
        current.resolve().relative_to(project)
    except ValueError as exc:
        raise JournalError("state journal registry escapes the project root") from exc
    return current


def anchor_path(project_root: Path, run_id: str) -> Path:
    if (not isinstance(run_id, str) or not run_id or
            "/" in run_id or "\\" in run_id or run_id in {".", ".."}):
        raise JournalError("state journal run id is not a safe path segment")
    path = registry_dir(project_root) / (
        run_id.casefold() + ".state-head.json"
    )
    if os.path.lexists(str(path)) and _is_linklike(path):
        raise JournalError("state journal head is a link or reparse point")
    return path


def _entry(state: Mapping[str, Any], previous: Optional[str]) -> Dict[str, Any]:
    revision = state.get("state_revision")
    if not isinstance(revision, int) or revision < 1:
        raise JournalError("journal state revision must be a positive integer")
    state_copy = copy.deepcopy(dict(state))
    return {
        "schema": ENTRY_SCHEMA,
        "revision": revision,
        "previous": previous,
        "state_digest": digest(state_copy),
        "state": state_copy,
    }


def _validate_entry(value: object) -> Tuple[Dict[str, Any], str]:
    if (not isinstance(value, dict) or
            set(value) != {"schema", "revision", "previous", "state_digest", "state"} or
            value.get("schema") != ENTRY_SCHEMA or
            not isinstance(value.get("revision"), int) or value["revision"] < 1 or
            (value.get("previous") is not None and
             (not isinstance(value["previous"], str) or
              DIGEST_RE.fullmatch(value["previous"]) is None)) or
            not isinstance(value.get("state"), dict) or
            value["state"].get("state_revision") != value["revision"] or
            value.get("state_digest") != digest(value["state"])):
        raise JournalError("state journal entry is malformed")
    return value, digest(value)


def _scan(state_path: Path) -> List[Tuple[Dict[str, Any], str, Path]]:
    directory = journal_dir(state_path)
    if not directory.is_dir():
        raise JournalError("state journal directory is missing")
    records: List[Tuple[Dict[str, Any], str, Path]] = []
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if path.name.startswith(".tmp-") and path.is_file():
            continue
        match = ENTRY_NAME_RE.fullmatch(path.name)
        if not match or not path.is_file():
            raise JournalError("state journal contains an unexpected object: %s" % path.name)
        entry, entry_digest = _validate_entry(_read_json(path))
        if int(match.group(1)) != entry["revision"] or match.group(2) != entry_digest[7:]:
            raise JournalError("state journal filename does not match its entry")
        records.append((entry, entry_digest, path))
    if not records:
        raise JournalError("state journal is empty")
    previous: Optional[str] = None
    for expected_revision, (entry, entry_digest, _) in enumerate(records, start=1):
        if entry["revision"] != expected_revision or entry["previous"] != previous:
            raise JournalError("state journal digest chain is discontinuous")
        previous = entry_digest
    return records


def _head(run_id: str, entry: Mapping[str, Any], entry_digest: str) -> Dict[str, Any]:
    return {
        "schema": HEAD_SCHEMA,
        "run_id": run_id,
        "revision": entry["revision"],
        "entry_digest": entry_digest,
        "state_digest": entry["state_digest"],
    }


def _validate_head(
    value: object, run_id: str, records: List[Tuple[Dict[str, Any], str, Path]],
) -> int:
    if (not isinstance(value, dict) or
            set(value) != {"schema", "run_id", "revision", "entry_digest", "state_digest"} or
            value.get("schema") != HEAD_SCHEMA or value.get("run_id") != run_id or
            not isinstance(value.get("revision"), int) or value["revision"] < 1 or
            not isinstance(value.get("entry_digest"), str) or
            not isinstance(value.get("state_digest"), str)):
        raise JournalError("state journal head is malformed")
    revision = value["revision"]
    if revision > len(records):
        raise JournalError("state journal head points past the journal")
    entry, entry_digest, _ = records[revision - 1]
    if (value["entry_digest"] != entry_digest or
            value["state_digest"] != entry["state_digest"]):
        raise JournalError("state journal head digest is inconsistent")
    return revision


def initialize(
    state_path: Path, head_path: Path, state: Mapping[str, Any], run_id: str,
) -> None:
    directory = journal_dir(state_path)
    if state_path.exists() or head_path.exists() or directory.exists():
        raise JournalError("state journal is already initialized")
    entry = _entry(state, None)
    entry_digest = digest(entry)
    path = directory / ("%020d-%s.json" % (entry["revision"], entry_digest[7:]))
    _exclusive_json(path, entry)
    _atomic_json(state_path, entry["state"])
    _atomic_json(head_path, _head(run_id, entry, entry_digest))


def load(
    state_path: Path, head_path: Path, run_id: str, *, recover: bool = False,
) -> Dict[str, Any]:
    records = _scan(state_path)
    latest_entry, latest_digest, _ = records[-1]
    projection = _read_json(state_path) if state_path.is_file() else None
    head_value = _read_json(head_path) if head_path.is_file() else None

    if head_value is None:
        if not recover or len(records) != 1 or projection not in (None, latest_entry["state"]):
            raise JournalError("state journal head is missing")
        _atomic_json(state_path, latest_entry["state"])
        _atomic_json(head_path, _head(run_id, latest_entry, latest_digest))
        return copy.deepcopy(latest_entry["state"])

    head_revision = _validate_head(head_value, run_id, records)
    head_entry, head_digest, _ = records[head_revision - 1]
    if head_revision == len(records):
        if projection != head_entry["state"]:
            raise JournalError("state projection differs from the authoritative journal")
        return copy.deepcopy(head_entry["state"])

    # Persistence appends exactly one entry, then replaces the projection, then
    # advances the external head.  Complete only that single recognized gap.
    if not recover or len(records) != head_revision + 1:
        raise JournalError("state journal contains an uncommitted revision gap")
    if projection not in (head_entry["state"], latest_entry["state"]):
        raise JournalError("state projection is inconsistent during recovery")
    _atomic_json(state_path, latest_entry["state"])
    _atomic_json(head_path, _head(run_id, latest_entry, latest_digest))
    return copy.deepcopy(latest_entry["state"])


def append(
    state_path: Path, head_path: Path, state: Dict[str, Any], run_id: str,
) -> None:
    current = load(state_path, head_path, run_id, recover=True)
    revision = state.get("state_revision")
    if not isinstance(revision, int) or revision != current.get("state_revision"):
        raise JournalError("state mutation is based on a stale revision")
    records = _scan(state_path)
    previous = records[-1][1]
    next_state = copy.deepcopy(state)
    next_state["state_revision"] = revision + 1
    entry = _entry(next_state, previous)
    entry_digest = digest(entry)
    path = journal_dir(state_path) / (
        "%020d-%s.json" % (entry["revision"], entry_digest[7:])
    )
    _exclusive_json(path, entry)
    _atomic_json(state_path, entry["state"])
    _atomic_json(head_path, _head(run_id, entry, entry_digest))
    # Preserve nested object identities held by an in-flight locked mutation;
    # only the revision differs between ``state`` and the persisted copy.
    state["state_revision"] = next_state["state_revision"]


def verify_candidate(
    state_path: Path, head_path: Path, candidate: Mapping[str, Any], run_id: str,
) -> None:
    authoritative = load(state_path, head_path, run_id, recover=False)
    if authoritative != candidate:
        raise JournalError("candidate state differs from the authoritative journal")
