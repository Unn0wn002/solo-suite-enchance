#!/usr/bin/env python3
"""Durable, fail-closed state machine for prepared Solo Suite AgentRooms.

The runner does not invent an agent runtime.  It emits bounded seat tasks for
Codex collaboration (or another adapter), verifies returned artifacts against
the prepared room, validates gate evidence with the bundled validators, and
persists every transition so a run can resume safely.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import shutil
import socket
import subprocess
import sys
import time
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Set, Tuple
import uuid

from git_trust import GitTrustError, build_manifest, verify_manifest
from runtime_trust import (
    TrustError,
    install_trusted_validators,
    trusted_validator,
    verify_trusted_install,
    verify_suite_trust,
)
from state_journal import (
    JournalError,
    anchor_path as journal_anchor_path,
    append as append_state_journal,
    initialize as initialize_state_journal,
    load as load_state_journal,
    registry_dir as journal_registry_dir,
    verify_candidate as verify_journal_candidate,
)
from validate_rooms import (
    is_portable_relative_path,
    is_windows_safe_run_id,
    validate_files,
)


STATE_SCHEMA = "solo-suite/agentroom-run-state-v2"
TASK_SCHEMA = "solo-suite/agentroom-task-v1"
RESULT_SCHEMA = "solo-suite/agentroom-task-result-v1"
SHA256_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
ENVIRONMENT_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$")
SKIP_SNAPSHOT_PARTS = frozenset({
    ".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache",
    "htmlcov",
})


class RunnerError(RuntimeError):
    """A fail-closed AgentRoom runner error."""


def state_head_path(project_root: Path, run_id: str) -> Path:
    """Resolve the external journal head through the controlled registry."""
    try:
        return journal_anchor_path(project_root, run_id)
    except JournalError as exc:
        raise RunnerError("state journal registry is unsafe: %s" % exc) from exc


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerError("cannot read JSON %s: %s" % (path, exc)) from exc


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise RunnerError("cannot hash %s: %s" % (path, exc)) from exc
    return "sha256:" + digest.hexdigest()


def replace_with_retry(source: Path, target: Path) -> None:
    """Tolerate short Windows sharing races from scanners and readers."""
    for attempt in range(8):
        try:
            os.replace(str(source), str(target))
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.02 * (attempt + 1))


def atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / (".tmp-%s" % uuid.uuid4().hex[:12])
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        replace_with_retry(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_bytes(path: Path, payload: bytes) -> None:
    """Atomically install exact bytes without following the final path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / (".tmp-%s" % uuid.uuid4().hex[:12])
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        replace_with_retry(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def persist_state(path: Path, state: Dict[str, Any]) -> None:
    """Append one authoritative revision and replace the state projection."""
    try:
        head_path = state_head_path(
            Path(str(state["project_root"])), str(state["run_id"]),
        )
        if head_path.exists() and is_linklike(head_path):
            raise RunnerError("state journal head is a link or reparse point")
        append_state_journal(
            path,
            head_path,
            state,
            str(state["run_id"]),
        )
    except (JournalError, KeyError) as exc:
        raise RunnerError("state journal rejected mutation: %s" % exc) from exc


def authoritative_state(
    path: Path, project_root: Path, run_id: str,
) -> Dict[str, Any]:
    try:
        head_path = state_head_path(project_root, run_id)
        if head_path.exists() and is_linklike(head_path):
            raise RunnerError("state journal head is a link or reparse point")
        return load_state_journal(
            path, head_path, run_id,
            recover=True,
        )
    except JournalError as exc:
        raise RunnerError("state journal verification failed: %s" % exc) from exc


def next_marker() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_relative(value: object, field: str) -> str:
    if not is_portable_relative_path(value):
        raise RunnerError("%s must be a portable POSIX relative path" % field)
    assert isinstance(value, str)  # narrowed by is_portable_relative_path
    normalized = value.rstrip("/")
    pure = PurePosixPath(normalized)
    return pure.as_posix()


def project_path(project_root: Path, value: object, field: str) -> Path:
    relative = safe_relative(value, field)
    root = project_root.resolve()
    candidate = (root / Path(*PurePosixPath(relative).parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RunnerError("%s escapes the project root: %r" % (field, value)) from exc
    return candidate


def state_paths(project_root: Path, run_id: str) -> Tuple[Path, Path, Path]:
    if not is_windows_safe_run_id(run_id):
        raise RunnerError("runner state path has an unsafe run_id")
    project = project_root.resolve()
    lexical = project / "artifacts" / "runs" / run_id / "runner"
    current = project
    for part in lexical.relative_to(project).parts:
        current = current / part
        if current.exists() and is_linklike(current):
            raise RunnerError("runner control path contains a link or reparse point")
    runner_root = lexical.resolve()
    try:
        runner_root.relative_to(project)
    except ValueError as exc:
        raise RunnerError("runner control path escapes the project root") from exc
    lock_path = runner_root / ".state.lock"
    if lock_path.exists() and is_linklike(lock_path):
        raise RunnerError("runner lock is a link or reparse point")
    return runner_root, runner_root / "state.json", lock_path


def git_manifest_repositories(
    room: Mapping[str, Any], project_root: Path,
) -> Dict[str, Path]:
    repositories = {"project": project_root.resolve()}
    for workspace in room.get("workspaces", []):
        if not isinstance(workspace, dict) or workspace.get("type") != "worktree":
            continue
        relative = safe_relative(workspace.get("path"), "workspace.path")
        repositories[relative] = project_path(
            project_root, relative, "workspace.path",
        )
    return repositories


def write_git_manifests(
    room: Mapping[str, Any], project_root: Path, commit: str, runner_root: Path,
) -> Dict[str, Dict[str, str]]:
    """Pin actual filtered working-tree bytes for the project and worktrees."""
    contracts: Dict[str, Dict[str, str]] = {}
    for key, repository in sorted(
            git_manifest_repositories(room, project_root).items()):
        try:
            manifest = build_manifest(repository, commit)
        except GitTrustError as exc:
            raise RunnerError("Git trust check failed for %s: %s" % (key, exc)) from exc
        name = hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json"
        relative = "tracked-manifests/" + name
        target = runner_root.resolve() / "tracked-manifests" / name
        atomic_json(target, manifest)
        contracts[key] = {"path": relative, "digest": sha256_file(target)}
    return contracts


def verify_git_manifest_contract(
    key: str, repository: Path, state: Mapping[str, Any], runner_root: Path,
    commit: str,
) -> None:
    contracts = state.get("tracked_manifests")
    contract = contracts.get(key) if isinstance(contracts, dict) else None
    if (not isinstance(contract, dict) or
            set(contract) != {"path", "digest"} or
            not isinstance(contract.get("digest"), str)):
        raise RunnerError("tracked manifest contract is invalid for %s" % key)
    relative = safe_relative(contract.get("path"), "tracked manifest path")
    if not relative.startswith("tracked-manifests/"):
        raise RunnerError("tracked manifest path is outside its control directory")
    manifest_path = runner_root.resolve() / Path(*PurePosixPath(relative).parts)
    try:
        manifest_path.resolve().relative_to(runner_root.resolve())
    except ValueError as exc:
        raise RunnerError("tracked manifest escapes the runner root") from exc
    if (not manifest_path.is_file() or
            sha256_file(manifest_path) != contract.get("digest")):
        raise RunnerError("tracked manifest is missing or changed for %s" % key)
    manifest = read_json(manifest_path)
    try:
        verify_manifest(repository, manifest, commit)
    except GitTrustError as exc:
        raise RunnerError("Git trust check failed for %s: %s" % (key, exc)) from exc


@contextmanager
def exclusive(path: Path, timeout: float = 30.0) -> Iterator[None]:
    """Hold a crash-released operating-system lock for one state mutation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Windows byte-range locks must not share a buffered stream with
        # pre-lock sentinel writes.  Under contention, another process can
        # truncate the metadata while this handle still has a buffered byte;
        # its later flush then fails with PermissionError before the lock is
        # acquired.  msvcrt can lock byte zero even when the file is empty, so
        # acquire first and touch the file only while holding the OS lock.
        handle = path.open("a+b", buffering=0)
    except OSError as exc:
        raise RunnerError("cannot open runner lock %s: %s" % (path, exc)) from exc
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, BlockingIOError) as exc:
                if time.monotonic() >= deadline:
                    raise RunnerError(
                        "another runner process holds %s" % path
                    ) from exc
                time.sleep(0.05)
        metadata = json.dumps({
            "pid": os.getpid(), "host": socket.gethostname(),
            "acquired_at": next_marker(),
        }).encode("utf-8")
        handle.seek(0)
        handle.truncate()
        handle.write(metadata + b"\n")
        handle.flush()
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        handle.close()


def load_prepared_room(path: Path, suite_root: Path) -> Tuple[Dict[str, Any], str]:
    room_path = path.resolve()
    room = read_json(room_path)
    if not isinstance(room, dict):
        raise RunnerError("prepared room must be a JSON object")
    if room.get("prepared") is not True:
        raise RunnerError("runner accepts only prepared=true rooms")
    if room.get("profile") == "profile-selected-at-runtime":
        raise RunnerError("prepared room must bind a concrete project profile")
    try:
        verify_suite_trust(suite_root.resolve(), room.get("runtime_trust"))
    except TrustError as exc:
        raise RunnerError("suite trust mismatch: %s" % exc) from exc
    problems = validate_files([str(room_path)], suite_root=str(suite_root.resolve()))
    if problems:
        raise RunnerError("invalid prepared room: " + "; ".join(problems))
    return room, sha256_file(room_path)


def verify_claim(
    room_path: Path, room: Mapping[str, Any], room_digest: str, project_root: Path,
) -> None:
    run_id = room.get("run_id")
    try:
        registry = journal_registry_dir(project_root)
    except JournalError as exc:
        raise RunnerError("run registry is unsafe: %s" % exc) from exc
    claim_path = registry / (str(run_id).casefold() + ".lock")
    if os.path.lexists(str(claim_path)) and is_linklike(claim_path):
        raise RunnerError("run registry claim is a link or reparse point")
    claim = read_json(claim_path)
    if not isinstance(claim, dict):
        raise RunnerError("run registry claim must be a JSON object")
    expected = {
        "schema": "solo-suite/agentroom-run-claim-v1",
        "run_id": run_id,
        "profile": room.get("profile"),
        "plan_digest": room_digest,
    }
    for field, value in expected.items():
        if claim.get(field) != value:
            raise RunnerError("run registry claim has mismatched %s" % field)
    try:
        claimed_plan = Path(str(claim.get("plan"))).resolve()
    except (OSError, TypeError, ValueError) as exc:
        raise RunnerError("run registry claim has invalid plan path") from exc
    if claimed_plan != room_path.resolve():
        raise RunnerError("run registry claim points at another prepared plan")


def seat_map(room: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(seat["id"]): seat for seat in room.get("seats", [])}


def stage_map(room: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(stage["id"]): stage for stage in room.get("stages", [])}


def gate_for_stage(room: Mapping[str, Any], stage_id: str) -> Optional[Dict[str, Any]]:
    matches = [
        gate for gate in room.get("gates", [])
        if isinstance(gate, dict) and gate.get("stage") == stage_id
    ]
    if len(matches) > 1:
        raise RunnerError("stage %s declares multiple gates" % stage_id)
    return matches[0] if matches else None


def workspace_for_seat(
    room: Mapping[str, Any], seat: Mapping[str, Any], project_root: Path,
) -> Tuple[str, Path]:
    workspace_id = seat.get("workspace")
    matches = [
        workspace for workspace in room.get("workspaces", [])
        if isinstance(workspace, dict) and workspace.get("id") == workspace_id
    ]
    if len(matches) != 1:
        raise RunnerError("seat %s has no unique workspace" % seat.get("id"))
    relative = safe_relative(matches[0].get("path"), "workspace.path")
    return relative, project_path(project_root, relative, "workspace.path")


def git_command(project_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(project_root.resolve()), *arguments],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RunnerError("Git workspace command could not run: %s" % exc) from exc
    if completed.returncode != 0:
        raise RunnerError(
            "Git workspace command failed: %s" %
            (completed.stdout + completed.stderr).strip()
        )
    return completed.stdout.strip()


def materialize_workspaces(
    room: Mapping[str, Any], project_root: Path, commit_sha: str,
) -> Dict[str, str]:
    if git_command(project_root, "rev-parse", "--is-inside-work-tree") != "true":
        raise RunnerError("project root must be a Git working tree")
    git_command(project_root, "cat-file", "-e", commit_sha + "^{commit}")
    if git_command(project_root, "rev-parse", "HEAD") != commit_sha:
        raise RunnerError("initial commit must be the project root's current HEAD")
    if git_command(project_root, "status", "--porcelain", "--untracked-files=no"):
        raise RunnerError("project root has tracked changes; commit or restore them first")
    created: List[Path] = []
    heads: Dict[str, str] = {}
    try:
        for workspace in room.get("workspaces", []):
            if not isinstance(workspace, dict):
                raise RunnerError("room contains a malformed workspace")
            relative = safe_relative(workspace.get("path"), "workspace.path")
            target = project_path(project_root, relative, "workspace.path")
            workspace_type = workspace.get("type")
            if workspace_type == "shared-memory":
                target.mkdir(parents=True, exist_ok=True)
                heads[relative] = "shared-memory"
                continue
            if workspace_type != "worktree":
                raise RunnerError("workspace %s has an unsupported type" % relative)
            if target.exists():
                raise RunnerError(
                    "runner-owned worktree path already exists: %s" % relative
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            git_command(
                project_root, "worktree", "add", "--detach", str(target), commit_sha,
            )
            created.append(target)
            head = git_command(target, "rev-parse", "HEAD")
            if head != commit_sha:
                raise RunnerError("worktree %s is on the wrong commit" % relative)
            heads[relative] = head
    except Exception:
        for target in reversed(created):
            try:
                # Every target was resolved under this run's declared project
                # workspace before creation; remove only those newly created here.
                git_command(project_root, "worktree", "remove", "--force", str(target))
            except RunnerError:
                pass
        raise
    return heads


def remove_materialized_workspaces(
    room: Mapping[str, Any], project_root: Path,
) -> None:
    """Best-effort rollback of only this prepared run's Git worktrees."""
    for workspace in reversed(list(room.get("workspaces", []))):
        if not isinstance(workspace, dict) or workspace.get("type") != "worktree":
            continue
        try:
            relative = safe_relative(workspace.get("path"), "workspace.path")
            target = project_path(project_root, relative, "workspace.path")
            if target.exists():
                git_command(
                    project_root, "worktree", "remove", "--force", str(target),
                )
        except RunnerError:
            continue


def cleanup_runner_control(
    runner_root: Path, head_path: Path, lock_path: Path,
) -> None:
    """Remove only control objects created by a failed initialization."""
    head_path.unlink(missing_ok=True)
    if not runner_root.is_dir():
        return
    for child in list(runner_root.iterdir()):
        if child == lock_path:
            continue
        try:
            if child.is_dir() and not is_linklike(child):
                shutil.rmtree(str(child))
            else:
                child.unlink(missing_ok=True)
        except OSError:
            continue


def reject_untracked_project_inputs(
    project_root: Path, room_path: Path,
) -> None:
    allowed_exact: Set[str] = set()
    try:
        allowed_exact.add(room_path.resolve().relative_to(project_root.resolve()).as_posix())
    except ValueError:
        pass
    status = git_command(
        project_root, "status", "--porcelain=v1", "-z", "--untracked-files=all",
    )
    unexpected = []
    for entry in status.split("\x00"):
        if not entry.startswith("?? "):
            continue
        relative = entry[3:].replace("\\", "/")
        if relative in allowed_exact or relative.startswith((
            ".solo/", "artifacts/runs/", "worktrees/runs/",
        )):
            continue
        unexpected.append(relative)
    if unexpected:
        raise RunnerError(
            "project has untracked inputs outside runner namespaces: " +
            ", ".join(sorted(unexpected))
        )


def verify_workspace_state(
    room: Mapping[str, Any], state: Mapping[str, Any], project_root: Path,
    seat_id: Optional[str] = None, *, current_stage_only: bool = False,
) -> None:
    """Bind every mutation to the exact clean project and worktree heads."""
    project = project_root.resolve()
    expected_commit = str(state.get("commit_sha"))
    actual_commit = git_command(project, "rev-parse", "HEAD")
    if actual_commit != expected_commit:
        raise RunnerError(
            "project HEAD changed from %s to %s; integrate and rebind first" %
            (expected_commit, actual_commit)
        )
    runner_root, _, _ = state_paths(project, str(state.get("run_id")))
    verify_git_manifest_contract(
        "project", project, state, runner_root, expected_commit,
    )
    if git_command(project, "status", "--porcelain", "--untracked-files=no"):
        raise RunnerError("project repository has tracked changes; restore or commit them")
    reject_untracked_project_inputs(project, Path(str(state.get("room"))))
    verify_live_artifact_provenance(state, project)

    expected_heads = state.get("workspace_heads")
    if not isinstance(expected_heads, dict):
        raise RunnerError("runner state has no workspace head manifest")
    selected_workspaces: Optional[Set[str]] = None
    if seat_id is not None:
        seat = seat_map(room).get(seat_id)
        if seat is None:
            raise RunnerError("task lease references an unknown seat")
        selected_workspaces = {str(seat.get("workspace"))}
    elif current_stage_only:
        stage = stage_map(room).get(str(state.get("current_stage")))
        if stage is None:
            raise RunnerError("runner state references an unknown stage")
        seats = seat_map(room)
        selected_workspaces = {
            str(seats[str(member)].get("workspace"))
            for member in stage.get("seats", []) if str(member) in seats
        }
    for workspace in room.get("workspaces", []):
        if not isinstance(workspace, dict):
            raise RunnerError("room contains a malformed workspace")
        relative = safe_relative(workspace.get("path"), "workspace.path")
        target = project_path(project, relative, "workspace.path")
        expected = expected_heads.get(relative)
        if (selected_workspaces is not None and
                workspace.get("id") not in selected_workspaces):
            continue
        if workspace.get("type") == "shared-memory":
            if expected != "shared-memory" or not target.is_dir():
                raise RunnerError("shared-memory workspace changed or is missing: %s" % relative)
            continue
        if workspace.get("type") != "worktree" or not target.is_dir():
            raise RunnerError("declared worktree is missing: %s" % relative)
        if not isinstance(expected, str) or COMMIT_RE.fullmatch(expected) is None:
            raise RunnerError("workspace head manifest is invalid for %s" % relative)
        actual = git_command(target, "rev-parse", "HEAD")
        if actual != expected:
            raise RunnerError(
                "worktree HEAD changed for %s; integrate and rebind first" % relative
            )
        verify_git_manifest_contract(
            relative, target, state, runner_root, expected,
        )
        if git_command(target, "status", "--porcelain"):
            raise RunnerError("worktree has uncommitted changes: %s" % relative)
    all_declared_paths = {
        safe_relative(workspace.get("path"), "workspace.path")
        for workspace in room.get("workspaces", []) if isinstance(workspace, dict)
    }
    if set(expected_heads) != all_declared_paths:
        raise RunnerError("workspace head manifest does not match the prepared room")
    expected_manifests = {
        "project",
        *(relative for relative in all_declared_paths
          if expected_heads.get(relative) != "shared-memory"),
    }
    manifests = state.get("tracked_manifests")
    if not isinstance(manifests, dict) or set(manifests) != expected_manifests:
        raise RunnerError("tracked manifest inventory does not match the prepared room")


def validate_state(
    state: object, room: Mapping[str, Any], room_path: Path,
    project_root: Path, room_digest: str,
) -> Dict[str, Any]:
    """Strictly validate persisted state after every lock acquisition."""
    if not isinstance(state, dict):
        raise RunnerError("runner state must be a JSON object")
    required = {
        "schema", "room", "room_digest", "suite_root", "runtime_trust",
        "project_root", "run_id", "profile", "commit_sha", "environment",
        "workspace_heads", "tracked_manifests", "commit_history", "status", "current_stage",
        "stage_attempts", "loop_iterations", "results", "task_leases",
        "artifact_claims", "artifact_provenance", "completed_stages",
        "history", "blocker", "state_revision",
    }
    allowed = required | {"unexpected_changes"}
    if set(state) - allowed or required - set(state):
        raise RunnerError("runner state fields are missing or unrecognized")
    expected_scalars = {
        "schema": STATE_SCHEMA,
        "room": str(room_path.resolve()),
        "room_digest": room_digest,
        "project_root": str(project_root.resolve()),
        "run_id": room.get("run_id"),
        "profile": room.get("profile"),
        "runtime_trust": room.get("runtime_trust"),
    }
    for field, expected in expected_scalars.items():
        if state.get(field) != expected:
            raise RunnerError("runner state trust mismatch for %s" % field)
    _, projection_path, _ = state_paths(project_root, str(state["run_id"]))
    head_path = state_head_path(project_root, str(state["run_id"]))
    if projection_path.is_file() or head_path.is_file():
        if head_path.exists() and is_linklike(head_path):
            raise RunnerError("state journal head is a link or reparse point")
        try:
            verify_journal_candidate(
                projection_path, head_path, state, str(state["run_id"]),
            )
        except JournalError as exc:
            raise RunnerError("state journal candidate mismatch: %s" % exc) from exc
    suite_root = state.get("suite_root")
    if not isinstance(suite_root, str) or str(Path(suite_root).resolve()) != suite_root:
        raise RunnerError("runner state suite_root is not canonical")
    try:
        verify_suite_trust(Path(suite_root), state.get("runtime_trust"))
    except TrustError as exc:
        raise RunnerError("suite trust mismatch: %s" % exc) from exc
    runner_root, _, _ = state_paths(project_root, str(state["run_id"]))
    try:
        verify_trusted_install(runner_root, state.get("runtime_trust"))
    except TrustError as exc:
        raise RunnerError("trusted runtime mismatch: %s" % exc) from exc
    if (not isinstance(state.get("commit_sha"), str) or
            COMMIT_RE.fullmatch(str(state["commit_sha"])) is None):
        raise RunnerError("runner state commit_sha is invalid")
    if (not isinstance(state.get("environment"), str) or
            ENVIRONMENT_RE.fullmatch(str(state["environment"])) is None):
        raise RunnerError("runner state environment is invalid")
    if state.get("status") not in {"READY", "BLOCKED", "COMPLETE"}:
        raise RunnerError("runner state status is invalid")
    stages = stage_map(room)
    if state.get("current_stage") not in stages:
        raise RunnerError("runner state current_stage is invalid")
    attempts = state.get("stage_attempts")
    if (not isinstance(attempts, dict) or
            any(stage not in stages or not isinstance(value, int) or value < 1
                for stage, value in attempts.items())):
        raise RunnerError("runner state stage_attempts is invalid")
    if (not isinstance(state.get("loop_iterations"), int) or
            int(state["loop_iterations"]) < 0):
        raise RunnerError("runner state loop counter is invalid")
    if (not isinstance(state.get("state_revision"), int) or
            int(state["state_revision"]) < 0):
        raise RunnerError("runner state revision is invalid")
    for field in ("workspace_heads", "tracked_manifests", "results", "task_leases",
                  "artifact_claims", "artifact_provenance"):
        if not isinstance(state.get(field), dict):
            raise RunnerError("runner state %s must be an object" % field)
    lease_required = {
        "lease_id", "stage", "attempt", "seat", "baseline",
        "baseline_digest", "commit_sha", "output_root", "task_path",
        "task_digest", "status", "issued_at",
    }
    lease_allowed = lease_required | {
        "started_at", "recorded_at", "failed_at", "runner_pid", "runner_host",
        "runner_identity",
        "execution_snapshot", "execution_snapshot_digest", "adapter_pid",
        "adapter_identity", "adapter_started_at",
        "committing_at", "pending_result", "pending_result_digest",
    }
    seats = seat_map(room)
    for task_id, lease in state["task_leases"].items():
        if (not isinstance(task_id, str) or not isinstance(lease, dict) or
                lease_required - set(lease) or set(lease) - lease_allowed):
            raise RunnerError("runner state contains a malformed task lease")
        if (not isinstance(lease.get("lease_id"), str) or
                re.fullmatch(r"[0-9a-f]{32}", lease["lease_id"]) is None or
                lease.get("stage") not in stages or
                lease.get("seat") not in seats or
                COMMIT_RE.fullmatch(str(lease.get("commit_sha", ""))) is None or
                not isinstance(lease.get("attempt"), int) or
                int(lease["attempt"]) < 1 or
                lease.get("status") not in {
                    "issued", "running", "committing", "recorded", "failed",
                } or
                SHA256_RE.fullmatch(str(lease.get("baseline_digest"))) is None or
                SHA256_RE.fullmatch(str(lease.get("task_digest"))) is None):
            raise RunnerError("runner state task lease values are invalid")
        expected_task_id = "%s:%s:%s:%d" % (
            state["run_id"], lease["stage"], lease["seat"], lease["attempt"],
        )
        expected_baseline = "baselines/%s-%d.json" % (
            lease["stage"], lease["attempt"],
        )
        expected_output = "leases/%s/output" % lease["lease_id"]
        expected_task_path = "tasks/%s.json" % hashlib.sha256(
            task_id.encode("utf-8")
        ).hexdigest()
        if (task_id != expected_task_id or
                lease["seat"] not in stages[lease["stage"]].get("seats", []) or
                lease["attempt"] > int(attempts.get(lease["stage"], 0)) or
                lease.get("baseline") != expected_baseline or
                lease.get("output_root") != expected_output or
                lease.get("task_path") != expected_task_path):
            raise RunnerError("runner state task lease identity is invalid")
        safe_relative(lease.get("baseline"), "task lease baseline")
        runner_root, _, _ = state_paths(project_root, str(state["run_id"]))
        baseline_path = runner_root / Path(
            *PurePosixPath(str(lease["baseline"])).parts
        )
        if (not baseline_path.is_file() or
                sha256_file(baseline_path) != lease["baseline_digest"]):
            raise RunnerError("runner state task baseline is missing or changed")
        task_path = runner_root / Path(*PurePosixPath(lease["task_path"]).parts)
        if (not task_path.is_file() or
                sha256_file(task_path) != lease["task_digest"]):
            raise RunnerError("runner state task contract is missing or changed")
        if isinstance(lease.get("execution_snapshot"), str):
            snapshot_relative = safe_relative(
                lease["execution_snapshot"], "execution snapshot",
            )
            expected_snapshot = "leases/%s/execution-baseline.json" % lease["lease_id"]
            snapshot_path = runner_root / Path(
                *PurePosixPath(snapshot_relative).parts
            )
            if (snapshot_relative != expected_snapshot or
                    not snapshot_path.is_file() or
                    sha256_file(snapshot_path) != lease.get("execution_snapshot_digest")):
                raise RunnerError("runner execution snapshot is missing or changed")
        if lease["status"] == "committing" and (
                not isinstance(lease.get("committing_at"), str) or
                not isinstance(lease.get("pending_result"), str) or
                SHA256_RE.fullmatch(
                    str(lease.get("pending_result_digest", ""))
                ) is None):
            raise RunnerError("committing task lease has no pending result")
        if isinstance(lease.get("pending_result"), str):
            pending_relative = safe_relative(
                lease["pending_result"], "pending task result",
            )
            expected_pending = "leases/%s/pending-result.json" % lease["lease_id"]
            pending_path = runner_root / Path(*PurePosixPath(pending_relative).parts)
            if (pending_relative != expected_pending or not pending_path.is_file() or
                    sha256_file(pending_path) != lease.get("pending_result_digest")):
                raise RunnerError("pending task result is missing or changed")
        if lease["status"] == "running" and not isinstance(
                lease.get("started_at"), str):
            raise RunnerError("running task lease has no start marker")
        if lease["status"] == "running" and (
                not isinstance(lease.get("runner_pid"), int) or
                int(lease["runner_pid"]) < 1 or
                not isinstance(lease.get("runner_host"), str)):
            raise RunnerError("running task lease has no runner identity")
        if lease.get("runner_identity") is not None and (
                not isinstance(lease.get("runner_identity"), str) or
                not lease.get("runner_identity")):
            raise RunnerError("task lease runner creation identity is malformed")
        if lease["status"] == "running" and (
                not isinstance(lease.get("execution_snapshot"), str) or
                SHA256_RE.fullmatch(
                    str(lease.get("execution_snapshot_digest", ""))
                ) is None):
            raise RunnerError("running task lease has no execution snapshot")
        adapter_fields = (
            lease.get("adapter_pid"), lease.get("adapter_identity"),
            lease.get("adapter_started_at"),
        )
        if any(value is not None for value in adapter_fields) and not (
                isinstance(adapter_fields[0], int) and adapter_fields[0] > 0 and
                isinstance(adapter_fields[1], str) and adapter_fields[1] and
                isinstance(adapter_fields[2], str) and adapter_fields[2]):
            raise RunnerError("task lease adapter identity is malformed")
        if lease["status"] == "recorded" and not isinstance(
                lease.get("recorded_at"), str):
            raise RunnerError("recorded task lease has no completion marker")
        if lease["status"] == "failed" and not isinstance(
                lease.get("failed_at"), str):
            raise RunnerError("failed task lease has no failure marker")
    for field in ("commit_history", "completed_stages", "history"):
        if not isinstance(state.get(field), list):
            raise RunnerError("runner state %s must be a list" % field)
    if state.get("blocker") is not None and not isinstance(state.get("blocker"), str):
        raise RunnerError("runner state blocker must be text or null")
    unexpected = state.get("unexpected_changes", {})
    if not isinstance(unexpected, dict):
        raise RunnerError("runner unexpected_changes must be an object")
    for relative, change in unexpected.items():
        safe_relative(relative, "unexpected change path")
        if (not isinstance(change, dict) or set(change) != {"before", "after"} or
                any(value is not None and (
                    not isinstance(value, str) or SHA256_RE.fullmatch(value) is None
                ) for value in change.values())):
            raise RunnerError("runner unexpected change entry is malformed")
    if unexpected and state.get("status") != "BLOCKED":
        raise RunnerError("unexpected project changes require a BLOCKED run")
    validate_persisted_registries(room, state, project_root)
    return state


def _process_exists(pid: int) -> bool:
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        synchronize = 0x00100000
        wait_timeout = 0x00000102
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        wait_for_single_object = kernel32.WaitForSingleObject
        wait_for_single_object.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        wait_for_single_object.restype = wintypes.DWORD
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        handle = open_process(synchronize, False, pid)
        if not handle:
            return False
        try:
            return wait_for_single_object(handle, 0) == wait_timeout
        finally:
            close_handle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _process_identity(pid: int) -> Optional[str]:
    """Return a creation identity so PID reuse cannot target another process."""
    if pid < 1:
        return None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        query_limited = 0x1000
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        get_process_times = kernel32.GetProcessTimes
        get_process_times.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        ]
        get_process_times.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        handle = open_process(query_limited, False, pid)
        if not handle:
            return None
        try:
            creation = wintypes.FILETIME()
            exit_time = wintypes.FILETIME()
            kernel = wintypes.FILETIME()
            user = wintypes.FILETIME()
            if not get_process_times(
                    handle, ctypes.byref(creation), ctypes.byref(exit_time),
                    ctypes.byref(kernel), ctypes.byref(user)):
                return None
            value = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
            return "windows-filetime:%d" % value
        finally:
            close_handle(handle)
    stat_path = Path("/proc") / str(pid) / "stat"
    try:
        raw = stat_path.read_text(encoding="ascii")
        fields = raw[raw.rfind(")") + 2:].split()
        return "linux-startticks:%s" % fields[19]
    except (OSError, IndexError, UnicodeDecodeError):
        try:
            completed = subprocess.run(
                ["ps", "-o", "lstart=", "-p", str(pid)],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        created = completed.stdout.strip()
        return "ps-start:%s" % created if completed.returncode == 0 and created else None


def terminate_adapter_tree(pid: int, identity: str) -> bool:
    """Terminate only the process tree whose creation identity was recorded."""
    if _process_identity(pid) != identity:
        return not _process_exists(pid)
    try:
        if os.name == "nt":
            completed = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True, timeout=15,
            )
            if completed.returncode not in {0, 128}:  # 128: already exited.
                return False
        else:
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                return True
            deadline = time.monotonic() + 2
            while _process_identity(pid) == identity and time.monotonic() < deadline:
                time.sleep(0.05)
            if _process_identity(pid) == identity:
                os.killpg(pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        return False
    deadline = time.monotonic() + 2
    while _process_identity(pid) == identity and time.monotonic() < deadline:
        time.sleep(0.05)
    return _process_identity(pid) != identity


def recover_crashed_adapter_leases(
    state: Dict[str, Any], room: Mapping[str, Any], project_root: Path,
) -> bool:
    """Block safely when a local runner died while an adapter lease was active."""
    recovered = []
    local_host = socket.gethostname()
    runner_root, _, _ = state_paths(project_root, str(state.get("run_id")))
    recovered_changes: Dict[str, Dict[str, Optional[str]]] = {}
    active_orphans: List[str] = []
    for task_id, lease in state.get("task_leases", {}).items():
        if not isinstance(lease, dict) or lease.get("status") != "running":
            continue
        pid = lease.get("runner_pid")
        host = lease.get("runner_host")
        runner_identity = lease.get("runner_identity")
        if host != local_host or not isinstance(pid, int):
            continue
        if isinstance(runner_identity, str):
            if (_process_exists(pid) and
                    _process_identity(pid) == runner_identity):
                continue
        elif _process_exists(pid):
            # Legacy v2 leases did not persist a creation identity.  Preserve
            # their liveness behavior without ever terminating a reused PID.
            continue
        adapter_pid = lease.get("adapter_pid")
        adapter_identity = lease.get("adapter_identity")
        if (isinstance(adapter_pid, int) and isinstance(adapter_identity, str) and
                _process_identity(adapter_pid) == adapter_identity and
                not terminate_adapter_tree(adapter_pid, adapter_identity)):
            active_orphans.append(str(task_id))
        snapshot_relative = lease.get("execution_snapshot")
        if isinstance(snapshot_relative, str):
            snapshot_path = runner_root / Path(
                *PurePosixPath(snapshot_relative).parts
            )
            before = read_json(snapshot_path)
            if not isinstance(before, dict):
                raise RunnerError("crashed adapter execution snapshot is malformed")
            after = snapshot(project_root, runner_root, room)
            for relative in unexpected_unprovenanced_changes(before, after, state):
                recovered_changes[relative] = {
                    "before": before.get(relative), "after": after.get(relative),
                }
        lease["status"] = "failed"
        lease["failed_at"] = next_marker()
        recovered.append(str(task_id))
    if not recovered:
        return False
    state["status"] = "BLOCKED"
    blocker = "adapter runner exited before finalization: " + ", ".join(sorted(recovered))
    if active_orphans:
        blocker += "; adapter process tree is still active: " + ", ".join(
            sorted(active_orphans)
        )
    state["blocker"] = blocker
    if recovered_changes:
        state["unexpected_changes"] = recovered_changes
    state.setdefault("history", []).append({
        "event": next_marker(), "action": "recover-crashed-adapter",
        "tasks": sorted(recovered),
    })
    return True


def recover_incomplete_promotions(
    state: Dict[str, Any], room: Mapping[str, Any], project_root: Path,
) -> bool:
    """Quarantine a crash between promotion intent and recorded provenance."""
    committing = [
        (str(task_id), lease)
        for task_id, lease in state.get("task_leases", {}).items()
        if isinstance(lease, dict) and lease.get("status") == "committing"
    ]
    if not committing:
        return False
    runner_root, _, _ = state_paths(project_root, str(state["run_id"]))
    after = snapshot(project_root, runner_root, room)
    recovered_changes: Dict[str, Dict[str, Optional[str]]] = {}
    task_ids = []
    for task_id, lease in committing:
        baseline_path = runner_root / Path(
            *PurePosixPath(str(lease["baseline"])).parts
        )
        before = read_json(baseline_path)
        if not isinstance(before, dict):
            raise RunnerError("promotion recovery baseline is malformed")
        for relative in unexpected_unprovenanced_changes(before, after, state):
            recovered_changes[relative] = {
                "before": before.get(relative), "after": after.get(relative),
            }
        lease["status"] = "failed"
        lease["failed_at"] = next_marker()
        task_ids.append(task_id)
    state["status"] = "BLOCKED"
    state["blocker"] = (
        "artifact promotion did not reach recorded provenance: " +
        ", ".join(sorted(task_ids))
    )
    if recovered_changes:
        state["unexpected_changes"] = recovered_changes
    state.setdefault("history", []).append({
        "event": next_marker(), "action": "recover-incomplete-promotion",
        "tasks": sorted(task_ids),
    })
    return True


def git_is_ancestor(project_root: Path, ancestor: str, descendant: str) -> bool:
    try:
        completed = subprocess.run(
            ["git", "-C", str(project_root.resolve()), "merge-base",
             "--is-ancestor", ancestor, descendant],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RunnerError("Git ancestry check could not run: %s" % exc) from exc
    if completed.returncode not in {0, 1}:
        raise RunnerError(
            "Git ancestry check failed: %s" %
            (completed.stdout + completed.stderr).strip()
        )
    return completed.returncode == 0


def rebind_workspaces(
    room: Mapping[str, Any], project_root: Path, commit_sha: str,
) -> Dict[str, str]:
    git_command(project_root, "cat-file", "-e", commit_sha + "^{commit}")
    if git_command(project_root, "rev-parse", "HEAD") != commit_sha:
        raise RunnerError("rebind commit must be the project root's current HEAD")
    if git_command(project_root, "status", "--porcelain", "--untracked-files=no"):
        raise RunnerError("project root has tracked changes; commit or restore them first")
    worktrees: List[Tuple[str, Path, str]] = []
    heads: Dict[str, str] = {}
    for workspace in room.get("workspaces", []):
        if not isinstance(workspace, dict):
            raise RunnerError("room contains a malformed workspace")
        relative = safe_relative(workspace.get("path"), "workspace.path")
        target = project_path(project_root, relative, "workspace.path")
        if workspace.get("type") == "shared-memory":
            heads[relative] = "shared-memory"
            continue
        if workspace.get("type") != "worktree" or not target.exists():
            raise RunnerError("declared worktree is missing: %s" % relative)
        if git_command(target, "status", "--porcelain"):
            raise RunnerError("worktree has uncommitted changes: %s" % relative)
        old_head = git_command(target, "rev-parse", "HEAD")
        if not git_is_ancestor(project_root, old_head, commit_sha):
            raise RunnerError(
                "worktree commit was not integrated into the rebind commit: %s" %
                relative
            )
        worktrees.append((relative, target, old_head))

    removed: List[Tuple[str, Path, str]] = []
    added: List[Tuple[str, Path, str]] = []
    try:
        for item in worktrees:
            relative, target, old_head = item
            git_command(project_root, "worktree", "remove", "--force", str(target))
            removed.append(item)
        for item in worktrees:
            relative, target, old_head = item
            git_command(
                project_root, "worktree", "add", "--detach", str(target), commit_sha,
            )
            added.append(item)
            if git_command(target, "rev-parse", "HEAD") != commit_sha:
                raise RunnerError("rebound worktree is on the wrong commit: %s" % relative)
            heads[relative] = commit_sha
    except Exception:
        for _, target, _ in reversed(added):
            try:
                git_command(project_root, "worktree", "remove", "--force", str(target))
            except RunnerError:
                pass
        for relative, target, old_head in removed:
            if target.exists():
                continue
            try:
                git_command(
                    project_root, "worktree", "add", "--detach", str(target), old_head,
                )
            except RunnerError:
                pass
        raise
    return heads


def rebind_commit(
    room: Mapping[str, Any], state: Dict[str, Any], project_root: Path,
    commit_sha: str,
) -> None:
    if COMMIT_RE.fullmatch(commit_sha) is None:
        raise RunnerError("--commit must be a 40-character lowercase Git SHA")
    if commit_sha == state.get("commit_sha"):
        raise RunnerError("rebind commit is already active")
    if state.get("status") != "READY":
        raise RunnerError("only a READY run can rebind its commit")
    if any(
        isinstance(lease, dict) and lease.get("status") == "running"
        for lease in state.get("task_leases", {}).values()
    ):
        raise RunnerError("rebind cannot run while an adapter task is active")
    if len(pending_tasks(room, state, project_root)) != len(
            stage_map(room)[str(state["current_stage"])].get("seats", [])):
        raise RunnerError("rebind is allowed only before recording the current stage")
    reject_untracked_project_inputs(project_root, Path(str(state["room"])))
    runner_root, _, _ = state_paths(project_root, str(state["run_id"]))
    repositories = git_manifest_repositories(room, project_root)
    for key, repository in repositories.items():
        if key == "project":
            continue
        verify_git_manifest_contract(
            key, repository, state, runner_root, str(state["commit_sha"]),
        )
    try:
        # Unlike ordinary state verification, rebind intentionally observes a
        # new project HEAD.  Build its exact manifest before removing workers.
        build_manifest(project_root, commit_sha)
    except GitTrustError as exc:
        raise RunnerError("Git trust check failed for project: %s" % exc) from exc
    old_workspace_heads = {
        key: git_command(repository, "rev-parse", "HEAD")
        for key, repository in repositories.items() if key != "project"
    }
    old_manifest_bytes: Dict[Path, bytes] = {}
    for contract in state.get("tracked_manifests", {}).values():
        if not isinstance(contract, dict):
            continue
        relative = safe_relative(contract.get("path"), "tracked manifest path")
        manifest_path = runner_root / Path(*PurePosixPath(relative).parts)
        old_manifest_bytes[manifest_path] = manifest_path.read_bytes()
    workspace_heads = rebind_workspaces(room, project_root, commit_sha)
    try:
        tracked_manifests = write_git_manifests(
            room, project_root, commit_sha, runner_root,
        )
    except Exception:
        for manifest_path, payload in old_manifest_bytes.items():
            try:
                atomic_bytes(manifest_path, payload)
            except OSError:
                pass
        for key, repository in repositories.items():
            if key == "project":
                continue
            try:
                if repository.exists():
                    git_command(
                        project_root, "worktree", "remove", "--force",
                        str(repository),
                    )
                git_command(
                    project_root, "worktree", "add", "--detach",
                    str(repository), old_workspace_heads[key],
                )
            except RunnerError:
                pass
        raise
    previous = str(state["commit_sha"])
    first_stage = str(room["stages"][0]["id"])
    state["commit_sha"] = commit_sha
    state["workspace_heads"] = workspace_heads
    state["tracked_manifests"] = tracked_manifests
    state["current_stage"] = first_stage
    attempts = state.setdefault("stage_attempts", {})
    attempts[first_stage] = int(attempts.get(first_stage, 0)) + 1
    state.setdefault("commit_history", []).append({
        "event": next_marker(), "from": previous, "to": commit_sha,
        "action": "rebind-and-revalidate",
    })
    state.setdefault("history", []).append({
        "event": next_marker(), "action": "rebind",
        "from_commit": previous, "to_commit": commit_sha,
        "restart_stage": first_stage,
    })


def task_for(
    room: Mapping[str, Any], state: Mapping[str, Any], seat: Mapping[str, Any],
    project_root: Path, *, stage_id: Optional[str] = None,
    attempt: Optional[int] = None, commit_sha: Optional[str] = None,
) -> Dict[str, Any]:
    stage_id = str(stage_id if stage_id is not None else state["current_stage"])
    attempt = int(
        attempt if attempt is not None
        else state.get("stage_attempts", {}).get(stage_id, 1)
    )
    seat_id = str(seat["id"])
    workspace, workspace_root = workspace_for_seat(room, seat, project_root)
    gate = gate_for_stage(room, stage_id)
    task_id = "%s:%s:%s:%d" % (state["run_id"], stage_id, seat_id, attempt)
    lease = state.get("task_leases", {}).get(task_id, {})
    runner_root, _, _ = state_paths(project_root, str(state["run_id"]))
    output_relative = lease.get("output_root") if isinstance(lease, dict) else None
    artifact_root = project_root.resolve()
    if isinstance(output_relative, str):
        output_relative = safe_relative(output_relative, "task output root")
        artifact_root = unredirected_path(
            runner_root, output_relative, "task output root",
        )
    return {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "run_id": state["run_id"],
        "profile": state["profile"],
        "commit_sha": commit_sha if commit_sha is not None else state["commit_sha"],
        "stage": stage_id,
        "attempt": attempt,
        "seat": seat_id,
        "kind": seat.get("kind"),
        "role": seat.get("role"),
        "workspace": workspace,
        "workspace_root": str(workspace_root.resolve()),
        "artifact_root": str(artifact_root),
        "lease_id": lease.get("lease_id"),
        "baseline_digest": lease.get("baseline_digest"),
        "reads": list(seat.get("reads", [])),
        "writes": list(seat.get("writes", [])),
        "proposals": list(seat.get("proposals", [])),
        "commands": list(seat.get("commands", [])),
        "deliverable": seat.get("deliverable"),
        "gate": gate.get("id") if gate and gate.get("seat") == seat_id else None,
    }


def pending_tasks(
    room: Mapping[str, Any], state: Mapping[str, Any], project_root: Path,
) -> List[Dict[str, Any]]:
    if state.get("status") != "READY":
        return []
    stage_id = str(state["current_stage"])
    stage = stage_map(room).get(stage_id)
    if stage is None:
        raise RunnerError("state references an unknown stage")
    seats = seat_map(room)
    recorded = state.get("results", {})
    tasks = []
    for seat_id in stage.get("seats", []):
        seat = seats.get(str(seat_id))
        if seat is None:
            raise RunnerError("stage references unknown seat %s" % seat_id)
        task = task_for(room, state, seat, project_root)
        if task["task_id"] not in recorded:
            tasks.append(task)
    return tasks


def validate_digest(value: object, field: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise RunnerError("%s must be sha256:<64 lowercase hex>" % field)
    return value


def validate_result_item(item: object, index: int) -> Tuple[str, str]:
    if not isinstance(item, dict) or set(item) != {"path", "digest"}:
        raise RunnerError("artifacts[%d] must contain only path and digest" % index)
    path = safe_relative(item.get("path"), "artifacts[%d].path" % index)
    digest = validate_digest(item.get("digest"), "artifacts[%d].digest" % index)
    return path, digest


def validate_proposal_item(item: object, index: int) -> Dict[str, str]:
    if not isinstance(item, dict) or set(item) != {"path", "digest", "content"}:
        raise RunnerError(
            "proposals[%d] must contain only path, digest, and content" % index
        )
    path = safe_relative(item.get("path"), "proposals[%d].path" % index)
    content = item.get("content")
    if not isinstance(content, str):
        raise RunnerError("proposals[%d].content must be text" % index)
    digest = validate_digest(item.get("digest"), "proposals[%d].digest" % index)
    if digest != sha256_bytes(content.encode("utf-8")):
        raise RunnerError("proposals[%d] content digest does not match" % index)
    return {"path": path, "digest": digest, "content": content}


def validate_result(
    result: object, task: Mapping[str, Any], room: Mapping[str, Any],
    state: Mapping[str, Any], project_root: Path, *,
    verify_artifact_files: bool = True,
) -> Dict[str, Any]:
    if not isinstance(result, dict):
        raise RunnerError("task result must be a JSON object")
    required = {
        "schema", "task_id", "lease_id", "run_id", "commit_sha", "stage", "seat", "status",
        "commands_executed", "artifacts", "proposals",
    }
    allowed = required | {"notes"}
    missing = sorted(required - set(result))
    unknown = sorted(set(result) - allowed)
    if missing or unknown:
        raise RunnerError("task result fields invalid; missing=%r unknown=%r" % (
            missing, unknown,
        ))
    expected = {
        "schema": RESULT_SCHEMA,
        "task_id": task["task_id"],
        "lease_id": task["lease_id"],
        "run_id": state["run_id"],
        "commit_sha": task["commit_sha"],
        "stage": task["stage"],
        "seat": task["seat"],
    }
    for field, value in expected.items():
        if result.get(field) != value:
            raise RunnerError("task result has mismatched %s" % field)
    if result.get("status") not in {"PASS", "FAIL"}:
        raise RunnerError("task result status must be PASS or FAIL")
    if "notes" in result and not isinstance(result.get("notes"), str):
        raise RunnerError("task result notes must be text")

    commands = result.get("commands_executed")
    if (not isinstance(commands, list) or
            not all(isinstance(command, str) for command in commands) or
            len(commands) != len(set(commands))):
        raise RunnerError("commands_executed must be a unique string list")
    declared_commands = set(task.get("commands", []))
    if not set(commands).issubset(declared_commands):
        raise RunnerError("task result cites an undeclared command")
    if declared_commands and result.get("status") == "PASS" and not commands:
        raise RunnerError("a passing command-bearing seat must execute a command")
    if not declared_commands and commands:
        raise RunnerError("a commandless seat cannot report commands")

    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list):
        raise RunnerError("artifacts must be a list")
    normalized_artifacts = [
        validate_result_item(item, index) for index, item in enumerate(artifacts)
    ]
    artifact_paths = [path for path, _ in normalized_artifacts]
    if len(artifact_paths) != len(set(artifact_paths)):
        raise RunnerError("task result repeats an artifact")
    declared_writes = set(task.get("writes", []))
    if not set(artifact_paths).issubset(declared_writes):
        raise RunnerError("task result contains an undeclared write")
    seat = seat_map(room)[str(task["seat"])]
    if (result.get("status") == "PASS" and seat.get("kind") != "memory-steward" and
            set(artifact_paths) != declared_writes):
        raise RunnerError("a passing seat must provide every declared artifact")

    lock_owners = {
        lock.get("artifact"): lock.get("owner")
        for lock in room.get("artifact_locks", []) if isinstance(lock, dict)
    }
    for artifact, digest in normalized_artifacts:
        if lock_owners.get(artifact) != task["seat"]:
            raise RunnerError("seat does not own the artifact lock for %s" % artifact)
        if verify_artifact_files:
            artifact_root = private_output_root(task, project_root)
            absolute = unredirected_path(
                artifact_root, artifact, "artifact.path",
            )
            if not absolute.is_file():
                raise RunnerError("declared artifact does not exist: %s" % artifact)
            if sha256_file(absolute) != digest:
                raise RunnerError("declared artifact digest does not match: %s" % artifact)

    proposals = result.get("proposals")
    if not isinstance(proposals, list):
        raise RunnerError("proposals must be a list")
    normalized_proposals = [
        validate_proposal_item(item, index) for index, item in enumerate(proposals)
    ]
    proposal_paths = [item["path"] for item in normalized_proposals]
    if len(proposal_paths) != len(set(proposal_paths)):
        raise RunnerError("task result repeats a proposal target")
    if not set(proposal_paths).issubset(set(task.get("proposals", []))):
        raise RunnerError("task result contains an undeclared proposal target")

    normalized = dict(result)
    normalized["artifacts"] = [
        {"path": path, "digest": digest} for path, digest in normalized_artifacts
    ]
    normalized["proposals"] = normalized_proposals
    return normalized


def validate_persisted_registries(
    room: Mapping[str, Any], state: Mapping[str, Any], project_root: Path,
) -> None:
    """Cross-check every mutable lease, result, claim, and audit registry."""
    stages = stage_map(room)
    seats = seat_map(room)
    results = state.get("results", {})
    leases = state.get("task_leases", {})
    history = state.get("history", [])
    if not isinstance(results, dict) or not isinstance(leases, dict):
        raise RunnerError("runner result and lease registries must be objects")

    commit_history = state.get("commit_history")
    if not isinstance(commit_history, list) or not commit_history:
        raise RunnerError("runner commit history is missing")
    previous: Optional[str] = None
    known_commits: Set[str] = set()
    for index, entry in enumerate(commit_history):
        if not isinstance(entry, dict):
            raise RunnerError("runner commit history entry is malformed")
        expected_keys = (
            {"event", "from", "to", "action"} if index == 0
            else {"event", "from", "to", "action"}
        )
        if set(entry) != expected_keys or not isinstance(entry.get("event"), str):
            raise RunnerError("runner commit history entry is malformed")
        source = entry.get("from")
        target = entry.get("to")
        action = entry.get("action")
        if (not isinstance(target, str) or COMMIT_RE.fullmatch(target) is None or
                (source is not None and (
                    not isinstance(source, str) or COMMIT_RE.fullmatch(source) is None
                ))):
            raise RunnerError("runner commit history contains an invalid SHA")
        if index == 0:
            if source is not None or action != "initialize":
                raise RunnerError("runner commit history has no valid origin")
        elif source != previous or action != "rebind-and-revalidate":
            raise RunnerError("runner commit history chain is discontinuous")
        known_commits.add(target)
        if isinstance(source, str):
            known_commits.add(source)
        previous = target
    if previous != state.get("commit_sha"):
        raise RunnerError("runner commit history does not end at the active commit")

    runner_root, _, _ = state_paths(project_root, str(state["run_id"]))
    lease_tasks: Dict[str, Dict[str, Any]] = {}
    for task_id, lease in leases.items():
        if not isinstance(lease, dict) or lease.get("commit_sha") not in known_commits:
            raise RunnerError("runner task lease references an unknown commit")
        seat = seats.get(str(lease.get("seat")))
        if seat is None:
            raise RunnerError("runner task lease references an unknown seat")
        task = task_for(
            room, state, seat, project_root,
            stage_id=str(lease["stage"]), attempt=int(lease["attempt"]),
            commit_sha=str(lease["commit_sha"]),
        )
        task_path = runner_root / Path(*PurePosixPath(lease["task_path"]).parts)
        if read_json(task_path) != task:
            raise RunnerError("persisted task contract differs from its lease")
        lease_tasks[task_id] = task
        if lease.get("status") == "committing":
            pending_path = runner_root / Path(
                *PurePosixPath(str(lease["pending_result"])).parts
            )
            pending = read_json(pending_path)
            normalized_pending = validate_result(
                pending, task, room, state, project_root,
                verify_artifact_files=True,
            )
            if normalized_pending != pending:
                raise RunnerError("pending task result is not canonical")

    record_order: List[str] = []
    allowed_history_shapes = {
        "initialize": {"event", "action"},
        "record": {"event", "action", "task_id", "status"},
        "recover-crashed-adapter": {"event", "action", "tasks"},
        "recover-incomplete-promotion": {"event", "action", "tasks"},
        "rebind": {
            "event", "action", "from_commit", "to_commit", "restart_stage",
        },
        "block": {"event", "action", "stage", "reason"},
        "retry": {"event", "action", "stage"},
    }
    if not isinstance(history, list) or not history:
        raise RunnerError("runner audit history is missing")
    for entry in history:
        if not isinstance(entry, dict) or not isinstance(entry.get("event"), str):
            raise RunnerError("runner audit history entry is malformed")
        action = entry.get("action")
        if action not in allowed_history_shapes or set(entry) != allowed_history_shapes[action]:
            raise RunnerError("runner audit history action is malformed")
        if action == "record":
            task_id = entry.get("task_id")
            if (not isinstance(task_id, str) or task_id in record_order or
                    entry.get("status") not in {"PASS", "FAIL"}):
                raise RunnerError("runner record history is inconsistent")
            record_order.append(task_id)
        elif action in {"block", "retry"} and entry.get("stage") not in stages:
            raise RunnerError("runner audit history references an unknown stage")
        elif action == "rebind" and (
                entry.get("from_commit") not in known_commits or
                entry.get("to_commit") not in known_commits or
                entry.get("restart_stage") not in stages):
            raise RunnerError("runner rebind history is inconsistent")
        elif action in {
                "recover-crashed-adapter", "recover-incomplete-promotion",
        } and not (
                isinstance(entry.get("tasks"), list) and
                all(isinstance(item, str) for item in entry["tasks"])):
            raise RunnerError("runner recovery history is malformed")
    if set(record_order) != set(results) or len(record_order) != len(results):
        raise RunnerError("runner results do not match record history")

    normalized_results: Dict[str, Dict[str, Any]] = {}
    for task_id, result in results.items():
        lease = leases.get(task_id)
        if not isinstance(lease, dict) or lease.get("status") != "recorded":
            raise RunnerError("runner result has no recorded task lease")
        task = lease_tasks[task_id]
        normalized = validate_result(
            result, task, room, state, project_root,
            verify_artifact_files=(lease["commit_sha"] == state.get("commit_sha")),
        )
        if normalized != result:
            raise RunnerError("persisted task result is not canonical")
        normalized_results[task_id] = normalized
    for task_id, lease in leases.items():
        if isinstance(lease, dict) and (
                (lease.get("status") == "recorded") != (task_id in results)):
            raise RunnerError("runner lease/result completion state is inconsistent")

    expected_claims: Dict[str, str] = {}
    expected_provenance: Dict[str, Dict[str, Any]] = {}
    for task_id in record_order:
        result = normalized_results[task_id]
        for artifact in result["artifacts"]:
            path = artifact["path"]
            owner = result["seat"]
            previous_owner = expected_claims.get(path)
            if previous_owner is not None and previous_owner != owner:
                raise RunnerError("artifact result history has conflicting owners")
            expected_claims[path] = owner
            expected_provenance[path] = {
                "task_id": task_id,
                "seat": owner,
                "commands_executed": list(result["commands_executed"]),
                "commit_sha": result["commit_sha"],
                "digest": artifact["digest"],
            }
    if state.get("artifact_claims") != expected_claims:
        raise RunnerError("artifact claims do not match recorded results")
    if state.get("artifact_provenance") != expected_provenance:
        raise RunnerError("artifact provenance does not match recorded results")
    verify_live_artifact_provenance(state, project_root)

    completed = state.get("completed_stages")
    if not isinstance(completed, list):
        raise RunnerError("completed stage registry must be a list")
    seen_attempts: Set[Tuple[str, int]] = set()
    for item in completed:
        if (not isinstance(item, dict) or
                set(item) != {"event", "stage", "attempt", "gate_status", "validator"} or
                not isinstance(item.get("event"), str) or
                item.get("stage") not in stages or
                not isinstance(item.get("attempt"), int) or item["attempt"] < 1 or
                item["attempt"] > int(state["stage_attempts"].get(item["stage"], 0))):
            raise RunnerError("completed stage entry is malformed")
        identity = (str(item["stage"]), int(item["attempt"]))
        if identity in seen_attempts:
            raise RunnerError("completed stage attempt is duplicated")
        seen_attempts.add(identity)
        gate = gate_for_stage(room, str(item["stage"]))
        if gate is None:
            if item.get("gate_status") is not None or item.get("validator") is not None:
                raise RunnerError("non-gated stage has validator evidence")
        elif (not isinstance(item.get("gate_status"), str) or
              not isinstance(item.get("validator"), str)):
            raise RunnerError("gated stage has no bound validator result")
        for seat_id in stages[str(item["stage"])].get("seats", []):
            expected_task = "%s:%s:%s:%d" % (
                state["run_id"], item["stage"], seat_id, item["attempt"],
            )
            result = results.get(expected_task)
            if not isinstance(result, dict) or result.get("status") != "PASS":
                raise RunnerError("completed stage lacks passing recorded tasks")
    if state.get("status") == "COMPLETE":
        if (not completed or completed[-1].get("stage") != state.get("current_stage") or
                gate_for_stage(room, str(state["current_stage"])) is None):
            raise RunnerError("COMPLETE state has no completed exit gate")


def is_linklike(path: Path) -> bool:
    try:
        details = os.lstat(str(path))
    except OSError:
        return False
    return path.is_symlink() or bool(
        getattr(details, "st_file_attributes", 0) & 0x400
    )


def unredirected_path(root: Path, value: object, field: str) -> Path:
    relative = safe_relative(value, field)
    lexical_root = Path(root)
    if not lexical_root.is_absolute():
        raise RunnerError("%s controlled root must be absolute" % field)
    if os.path.lexists(str(lexical_root)) and is_linklike(lexical_root):
        raise RunnerError("%s root is a link or reparse point" % field)
    base = lexical_root.resolve()
    candidate = base
    for part in PurePosixPath(relative).parts:
        candidate = candidate / part
        if candidate.exists() and is_linklike(candidate):
            raise RunnerError("%s contains a link or reparse point" % field)
    try:
        candidate.resolve().relative_to(base)
    except ValueError as exc:
        raise RunnerError("%s escapes its controlled root" % field) from exc
    return candidate


def private_output_root(
    task: Mapping[str, Any], project_root: Path,
) -> Path:
    """Reconstruct one lease root instead of trusting its resolved task string."""
    lease_id = task.get("lease_id")
    run_id = task.get("run_id")
    if (not isinstance(lease_id, str) or
            re.fullmatch(r"[0-9a-f]{32}", lease_id) is None or
            not isinstance(run_id, str)):
        raise RunnerError("task has no valid private output identity")
    runner_root, _, _ = state_paths(project_root, run_id)
    expected = unredirected_path(
        runner_root, "leases/%s/output" % lease_id, "private task output root",
    )
    declared = Path(str(task.get("artifact_root")))
    if not declared.is_absolute() or declared != expected:
        raise RunnerError("task artifact root differs from its lease-private root")
    return expected


def verify_live_artifact_provenance(
    state: Mapping[str, Any], project_root: Path,
) -> None:
    """Rehash every promoted artifact for the active commit at its live path."""
    provenance = state.get("artifact_provenance", {})
    if not isinstance(provenance, dict):
        raise RunnerError("runner state has no artifact provenance registry")
    active_commit = state.get("commit_sha")
    exempt: Set[str] = set()
    if state.get("status") == "BLOCKED":
        unexpected = state.get("unexpected_changes", {})
        if isinstance(unexpected, dict):
            exempt.update(str(path) for path in unexpected)
    runner_root, _, _ = state_paths(project_root, str(state.get("run_id")))
    for lease in state.get("task_leases", {}).values():
        if not isinstance(lease, dict) or lease.get("status") != "committing":
            continue
        pending_relative = safe_relative(
            lease.get("pending_result"), "pending task result",
        )
        pending_path = unredirected_path(
            runner_root, pending_relative, "pending task result",
        )
        pending = read_json(pending_path)
        if not isinstance(pending, dict) or not isinstance(pending.get("artifacts"), list):
            raise RunnerError("pending task result is malformed")
        for artifact in pending["artifacts"]:
            if isinstance(artifact, dict):
                exempt.add(safe_relative(
                    artifact.get("path"), "pending artifact path",
                ))
    for relative, produced in sorted(provenance.items()):
        if not isinstance(relative, str) or not isinstance(produced, dict):
            raise RunnerError("artifact provenance entry is malformed")
        if produced.get("commit_sha") != active_commit or relative in exempt:
            continue
        expected = produced.get("digest")
        if not isinstance(expected, str) or SHA256_RE.fullmatch(expected) is None:
            raise RunnerError("artifact provenance digest is malformed: %s" % relative)
        live = unredirected_path(project_root, relative, "recorded artifact")
        if not live.is_file():
            raise RunnerError("recorded artifact is missing from the project: %s" % relative)
        if sha256_file(live) != expected:
            raise RunnerError("recorded artifact changed after promotion: %s" % relative)


def validate_private_output_tree(
    task: Mapping[str, Any], project_root: Path,
) -> None:
    root = private_output_root(task, project_root)
    if not root.is_dir():
        raise RunnerError("private task output root is missing or redirected")
    allowed = {safe_relative(path, "task write") for path in task.get("writes", [])}
    actual: Set[str] = set()
    for path in root.rglob("*"):
        if is_linklike(path):
            raise RunnerError("private task output contains a link or reparse point")
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:  # pragma: no cover - rglob guarantees ancestry.
            raise RunnerError("private task output escapes its lease") from exc
        actual.add(safe_relative(relative, "private task output"))
    unexpected = sorted(actual - allowed)
    if unexpected:
        raise RunnerError(
            "private task output contains undeclared artifacts: " +
            ", ".join(unexpected)
        )


def promote_result_artifacts(
    result: Mapping[str, Any], task: Mapping[str, Any], project_root: Path,
) -> None:
    """Atomically import only one lease's validated files into the project."""
    source_root = private_output_root(task, project_root)
    promoted: List[Tuple[Path, Optional[bytes]]] = []
    try:
        for artifact in result.get("artifacts", []):
            relative = safe_relative(artifact.get("path"), "artifact.path")
            source = unredirected_path(source_root, relative, "staged artifact")
            destination = unredirected_path(project_root, relative, "artifact.path")
            payload = source.read_bytes()
            if sha256_bytes(payload) != artifact.get("digest"):
                raise RunnerError("staged artifact changed before promotion: %s" % relative)
            previous = destination.read_bytes() if destination.is_file() else None
            # Register rollback state before the first byte can be replaced.
            promoted.append((destination, previous))
            atomic_bytes(destination, payload)
            if sha256_file(destination) != artifact.get("digest"):
                raise RunnerError("promoted artifact digest mismatch: %s" % relative)
    except (OSError, RunnerError) as exc:
        rollback_failures: List[str] = []
        for destination, previous in reversed(promoted):
            try:
                if previous is None:
                    destination.unlink(missing_ok=True)
                else:
                    atomic_bytes(destination, previous)
            except (OSError, RunnerError) as rollback_exc:
                rollback_failures.append("%s (%s)" % (destination, rollback_exc))
                continue
            try:
                if previous is None:
                    if os.path.lexists(str(destination)):
                        raise RunnerError("path still exists after rollback")
                elif (not destination.is_file() or is_linklike(destination) or
                      destination.read_bytes() != previous):
                    raise RunnerError("restored bytes do not match")
            except (OSError, RunnerError) as rollback_exc:
                rollback_failures.append("%s (%s)" % (destination, rollback_exc))
        if rollback_failures:
            raise RunnerError(
                "artifact promotion rollback was incomplete; quarantine required: " +
                "; ".join(rollback_failures)
            ) from exc
        if isinstance(exc, RunnerError):
            raise
        raise RunnerError("artifact promotion failed: %s" % exc) from exc


def persist_pending_promotion(
    normalized: Mapping[str, Any], lease: Dict[str, Any], state: Dict[str, Any],
    runner_root: Path, state_path: Path,
) -> None:
    relative = "leases/%s/pending-result.json" % lease["lease_id"]
    path = runner_root / Path(*PurePosixPath(relative).parts)
    if path.exists():
        raise RunnerError("pending result path was preseeded")
    atomic_json(path, normalized)
    lease["status"] = "committing"
    lease["committing_at"] = next_marker()
    lease["pending_result"] = relative
    lease["pending_result_digest"] = sha256_file(path)
    persist_state(state_path, state)


def record_result(
    result: object, room: Mapping[str, Any], state: Dict[str, Any],
    project_root: Path, *, lease_statuses: Set[str] = frozenset({"issued"}),
    before_promotion: Optional[
        Callable[[Mapping[str, Any], Dict[str, Any]], None]
    ] = None,
) -> None:
    tasks = {
        task["task_id"]: task
        for task in pending_tasks(room, state, project_root)
    }
    task_id = result.get("task_id") if isinstance(result, dict) else None
    task = tasks.get(str(task_id))
    if task is None:
        raise RunnerError("result is not for a pending task in the current stage")
    verify_task_boundary(
        task["task_id"], room, state, project_root,
        lease_statuses=lease_statuses,
    )
    validate_private_output_tree(task, project_root)
    normalized = validate_result(result, task, room, state, project_root)
    lease = state.setdefault("task_leases", {}).get(task["task_id"])
    if not isinstance(lease, dict):
        raise RunnerError("task lease disappeared before artifact promotion")
    claims = state.setdefault("artifact_claims", {})
    for artifact in normalized["artifacts"]:
        previous = claims.get(artifact["path"])
        if previous is not None and previous != task["seat"]:
            raise RunnerError("artifact was already claimed by another seat")
    if before_promotion is not None:
        before_promotion(normalized, lease)
    try:
        promote_result_artifacts(normalized, task, project_root)
    except RunnerError as exc:
        state["status"] = "BLOCKED"
        state["blocker"] = "artifact promotion quarantined: %s" % exc
        lease["status"] = "failed"
        lease["failed_at"] = next_marker()
        try:
            runner_root, _, _ = state_paths(project_root, str(state["run_id"]))
            baseline_path = unredirected_path(
                runner_root, lease["baseline"], "task baseline",
            )
            before = read_json(baseline_path)
            after = snapshot(project_root, runner_root, room)
            violations = unexpected_unprovenanced_changes(before, after, state)
            if violations:
                state["unexpected_changes"] = {
                    path: {"before": before.get(path), "after": after.get(path)}
                    for path in violations
                }
        except (KeyError, RunnerError):
            pass
        raise RunnerError(state["blocker"]) from exc
    provenance = state.setdefault("artifact_provenance", {})
    for artifact in normalized["artifacts"]:
        claims[artifact["path"]] = task["seat"]
        provenance[artifact["path"]] = {
            "task_id": task["task_id"],
            "seat": task["seat"],
            "commands_executed": list(normalized["commands_executed"]),
            "commit_sha": normalized["commit_sha"],
            "digest": artifact["digest"],
        }
    state.setdefault("results", {})[task["task_id"]] = normalized
    lease["status"] = "recorded"
    lease["recorded_at"] = next_marker()
    state.setdefault("history", []).append({
        "event": next_marker(),
        "action": "record",
        "task_id": task["task_id"],
        "status": normalized["status"],
    })
    validate_persisted_registries(room, state, project_root)


def stage_results(
    room: Mapping[str, Any], state: Mapping[str, Any], project_root: Path,
) -> List[Dict[str, Any]]:
    stage_id = str(state["current_stage"])
    stage = stage_map(room)[stage_id]
    seats = seat_map(room)
    results = state.get("results", {})
    output = []
    for seat_id in stage.get("seats", []):
        task = task_for(room, state, seats[str(seat_id)], project_root)
        result = results.get(task["task_id"])
        if not isinstance(result, dict):
            raise RunnerError("stage %s still has pending tasks" % stage_id)
        lease = state.get("task_leases", {}).get(task["task_id"])
        if not isinstance(lease, dict) or lease.get("status") != "recorded":
            raise RunnerError("stage %s has a result without a recorded lease" % stage_id)
        normalized = validate_result(result, task, room, state, project_root)
        if normalized != result:
            raise RunnerError("recorded task result is not canonical")
        output.append(normalized)
    return output


def _artifact_references(payload: object) -> Set[str]:
    """Collect transitive artifact references understood by gate validators."""
    references: Set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"evidence_artifact", "profile_artifact"}:
                if isinstance(value, str):
                    references.add(safe_relative(value, key))
            references.update(_artifact_references(value))
    elif isinstance(payload, list):
        for value in payload:
            references.update(_artifact_references(value))
    return references


def freeze_gate_bundle(
    room_path: Path, gate_artifact: str, state: Mapping[str, Any],
    project_root: Path, runner_root: Path,
) -> Tuple[Path, Path, Dict[str, Any], Dict[str, str], str]:
    """Capture one immutable, transitive gate input graph for validation/routing."""
    project = project_root.resolve()
    provenance = state.get("artifact_provenance")
    if not isinstance(provenance, dict):
        raise RunnerError("runner state has no artifact provenance registry")
    bundle_id = "%s-%s" % (
        hashlib.sha256(gate_artifact.encode("utf-8")).hexdigest()[:16],
        uuid.uuid4().hex,
    )
    bundle_root = runner_root.resolve() / "gate-bundles" / bundle_id
    try:
        bundle_root.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise RunnerError("cannot create gate input bundle: %s" % exc) from exc

    room_bytes = room_path.resolve().read_bytes()
    if sha256_bytes(room_bytes) != state.get("room_digest"):
        raise RunnerError("prepared room changed before gate validation")
    frozen_room = bundle_root / "prepared-room.json"
    atomic_bytes(frozen_room, room_bytes)

    manifest: Dict[str, str] = {"prepared-room.json": sha256_bytes(room_bytes)}
    frozen_payloads: Dict[str, Dict[str, Any]] = {}
    pending = [safe_relative(gate_artifact, "gate evidence")]
    # Production validators also load required prior-gate artifacts from the
    # prepared-room contract rather than from the final verdict.  Freeze every
    # current-commit runner artifact so those implicit inputs cannot race.
    for relative, produced in provenance.items():
        if (isinstance(relative, str) and isinstance(produced, dict) and
                produced.get("commit_sha") == state.get("commit_sha")):
            pending.append(safe_relative(relative, "artifact provenance"))
    seen: Set[str] = set()
    while pending:
        relative = pending.pop()
        if relative in seen:
            continue
        seen.add(relative)
        produced = provenance.get(relative)
        if not isinstance(produced, dict):
            raise RunnerError(
                "gate input was not recorded by this runner: %s" % relative
            )
        expected_digest = produced.get("digest")
        if not isinstance(expected_digest, str):
            raise RunnerError("gate input provenance is malformed: %s" % relative)
        live_path = project_path(project, relative, "gate input")
        try:
            payload_bytes = live_path.read_bytes()
        except OSError as exc:
            raise RunnerError("cannot read gate input %s: %s" % (relative, exc)) from exc
        digest = sha256_bytes(payload_bytes)
        if digest != expected_digest:
            raise RunnerError("gate input digest changed after recording: %s" % relative)
        frozen_path = project_path(bundle_root, relative, "frozen gate input")
        atomic_bytes(frozen_path, payload_bytes)
        manifest[relative] = digest
        try:
            parsed = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = None
        if isinstance(parsed, dict):
            frozen_payloads[relative] = parsed
            pending.extend(sorted(_artifact_references(parsed) - seen))

    gate_record = frozen_payloads.get(gate_artifact)
    if not isinstance(gate_record, dict):
        raise RunnerError("validated gate evidence must be a JSON object")
    manifest_digest = sha256_bytes(json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8"))
    atomic_json(bundle_root / "manifest.json", {
        "schema": "solo-suite/agentroom-gate-bundle-v1",
        "digest": manifest_digest,
        "files": manifest,
    })
    frozen_gate = project_path(bundle_root, gate_artifact, "frozen gate evidence")
    return bundle_root, frozen_gate, gate_record, manifest, manifest_digest


def verify_gate_bundle(
    bundle_root: Path, manifest: Mapping[str, str], room_path: Path,
    project_root: Path,
) -> None:
    """Reject any frozen-input or live-input change during validation."""
    for relative, digest in manifest.items():
        frozen = (
            bundle_root / "prepared-room.json" if relative == "prepared-room.json"
            else project_path(bundle_root, relative, "frozen gate input")
        )
        if not frozen.is_file() or sha256_file(frozen) != digest:
            raise RunnerError("frozen gate input changed during validation: %s" % relative)
        live = (
            room_path.resolve() if relative == "prepared-room.json"
            else project_path(project_root, relative, "gate input")
        )
        if not live.is_file() or sha256_file(live) != digest:
            raise RunnerError("live gate input changed during validation: %s" % relative)


def run_gate_validator(
    room_path: Path, room: Mapping[str, Any], gate: Mapping[str, Any],
    state: Mapping[str, Any], project_root: Path,
) -> Tuple[str, str]:
    evidence = gate.get("evidence")
    if not isinstance(evidence, dict):
        raise RunnerError("gate has no evidence contract")
    gate_artifact = safe_relative(evidence.get("artifact"), "gate evidence")
    evidence_path = project_path(project_root, gate_artifact, "gate evidence")
    if not evidence_path.is_file():
        raise RunnerError("gate evidence does not exist: %s" % evidence.get("artifact"))
    provenance = state.get("artifact_provenance", {})
    if not isinstance(provenance, dict):
        raise RunnerError("runner state has no artifact provenance registry")
    gate_produced = provenance.get(gate_artifact)
    if not isinstance(gate_produced, dict):
        raise RunnerError("gate evidence was not recorded by this runner")
    current_gate_digest = sha256_file(evidence_path)
    if gate_produced.get("digest") != current_gate_digest:
        raise RunnerError("gate evidence digest changed after runner recording")
    if (gate_produced.get("seat") != gate.get("seat") or
            gate.get("command") not in gate_produced.get("commands_executed", [])):
        raise RunnerError("gate evidence provenance does not match its gatekeeper")
    runner_root, _, _ = state_paths(project_root, str(state["run_id"]))
    (
        bundle_root, frozen_evidence, record, bundle_manifest,
        bundle_digest,
    ) = freeze_gate_bundle(
        room_path, gate_artifact, state, project_root, runner_root,
    )
    validator_name = (
        "production" if gate.get("command") == "$gate-production-ready"
        else "phase"
    )
    try:
        validator_path = trusted_validator(
            runner_root, state["runtime_trust"], validator_name,
        )
    except TrustError as exc:
        raise RunnerError("trusted validator mismatch: %s" % exc) from exc
    common = [
        sys.executable, "-I", str(validator_path),
        str(frozen_evidence),
        "--root", str(bundle_root.resolve()),
        "--run-id", str(state["run_id"]),
        "--gate-id", str(gate["id"]),
        "--commit", str(state["commit_sha"]),
        "--environment", str(state["environment"]),
        "--room", str((bundle_root / "prepared-room.json").resolve()),
    ]
    if gate.get("command") == "$gate-production-ready":
        common.extend(["--mode", "production"])
    try:
        completed = subprocess.run(
            common, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RunnerError("gate validator could not run: %s" % exc) from exc
    transcript = (completed.stdout + completed.stderr).strip()
    if completed.returncode != 0:
        raise RunnerError("gate validator rejected evidence: " + transcript)
    verify_gate_bundle(
        bundle_root, bundle_manifest, room_path, project_root.resolve(),
    )
    if gate.get("command") == "$gate-production-ready":
        evidence_items = [
            (
                item.get("evidence_artifact"),
                [item.get("command_executed")],
                item.get("artifact_digest"),
            )
            for item in record.get("categories", []) if isinstance(item, dict)
        ]
    else:
        evidence_items = [
            (
                item.get("evidence_artifact"),
                item.get("commands_executed"),
                item.get("artifact_digest"),
            )
            for item in record.get("checks", []) if isinstance(item, dict)
        ]
    for artifact, commands, digest in evidence_items:
        produced = provenance.get(artifact) if isinstance(artifact, str) else None
        if not isinstance(produced, dict):
            raise RunnerError(
                "gate evidence cites an artifact not produced by this runner: %r" %
                artifact
            )
        executed = produced.get("commands_executed")
        if (not isinstance(commands, list) or
                not isinstance(executed, list) or
                not set(commands).issubset(set(executed))):
            raise RunnerError(
                "gate evidence command was not executed for artifact %s" % artifact
            )
        if produced.get("digest") != digest:
            raise RunnerError(
                "gate evidence digest differs from runner provenance for %s" % artifact
            )
        if produced.get("commit_sha") != state.get("commit_sha"):
            raise RunnerError(
                "gate evidence artifact was produced for another commit: %s" % artifact
            )
    status_field = gate.get("transitions", {}).get("status_field")
    status = record.get(status_field) if isinstance(record, dict) else None
    if not isinstance(status, str):
        raise RunnerError("validated gate evidence has no configured status field")
    return status, "%s\nGATE_BUNDLE %s" % (transcript, bundle_digest)


def route_gate(
    room: Mapping[str, Any], state: Dict[str, Any], gate: Mapping[str, Any],
    status: str,
) -> None:
    transitions = gate.get("transitions", {})
    routes = [
        route for route in transitions.get("routes", [])
        if isinstance(route, dict) and status in route.get("statuses", [])
    ]
    if len(routes) != 1:
        state["status"] = "BLOCKED"
        state["blocker"] = "gate status has no single fail-closed route"
        return
    route = routes[0]
    action = route.get("action")
    next_stage = route.get("next_stage")
    if action == "complete":
        state["status"] = "COMPLETE"
        state["current_stage"] = gate.get("stage")
        return
    if action == "stop":
        state["status"] = "BLOCKED"
        state["blocker"] = "gate %s returned %s" % (gate.get("id"), status)
        return
    if not isinstance(next_stage, str) or next_stage not in stage_map(room):
        state["status"] = "BLOCKED"
        state["blocker"] = "gate route has no valid next stage"
        return
    loop = room.get("loop")
    if isinstance(loop, dict):
        current = int(state.get("loop_iterations", 0))
        maximum = int(loop.get("max_iterations", 0))
        follows_loop_edge = (
            gate.get("stage") == loop.get("from_stage") and
            next_stage == loop.get("to_stage")
        )
        enters_loop_stage = next_stage == loop.get("from_stage")
        if (follows_loop_edge or enters_loop_stage) and current >= maximum:
            state["status"] = "BLOCKED"
            state["blocker"] = str(loop.get("on_exhaustion"))
            return
        if follows_loop_edge:
            state["loop_iterations"] = current + 1
    state["current_stage"] = next_stage
    state["status"] = "READY"
    attempts = state.setdefault("stage_attempts", {})
    attempts[next_stage] = int(attempts.get(next_stage, 0)) + 1


def advance_stage(
    room_path: Path, room: Mapping[str, Any], state: Dict[str, Any],
    project_root: Path,
) -> None:
    verify_workspace_state(
        room, state, project_root, current_stage_only=True,
    )
    stage_id = str(state["current_stage"])
    results = stage_results(room, state, project_root)
    for result in results:
        verify_task_boundary(
            str(result["task_id"]), room, state, project_root,
            lease_statuses={"recorded"},
        )
    if any(result.get("status") != "PASS" for result in results):
        state["status"] = "BLOCKED"
        state["blocker"] = "stage %s contains a failed task" % stage_id
        return
    gate = gate_for_stage(room, stage_id)
    gate_status = None
    transcript = None
    if gate is not None:
        gate_status, transcript = run_gate_validator(
            room_path, room, gate, state, project_root,
        )
        route_gate(room, state, gate, gate_status)
    else:
        loop = room.get("loop")
        if isinstance(loop, dict) and stage_id == loop.get("from_stage"):
            maximum = int(loop.get("max_iterations", 0))
            current = int(state.get("loop_iterations", 0))
            if current >= maximum:
                state["status"] = "BLOCKED"
                state["blocker"] = str(loop.get("on_exhaustion"))
            else:
                state["loop_iterations"] = current + 1
                target = str(loop.get("to_stage"))
                state["current_stage"] = target
                state["status"] = "READY"
                attempts = state.setdefault("stage_attempts", {})
                attempts[target] = int(attempts.get(target, 0)) + 1
        else:
            stages = [str(stage["id"]) for stage in room.get("stages", [])]
            index = stages.index(stage_id)
            if index + 1 >= len(stages):
                state["status"] = "BLOCKED"
                state["blocker"] = "room ended without its declared exit gate"
            else:
                target = stages[index + 1]
                state["current_stage"] = target
                state["status"] = "READY"
                attempts = state.setdefault("stage_attempts", {})
                attempts[target] = int(attempts.get(target, 0)) + 1
    state.setdefault("completed_stages", []).append({
        "event": next_marker(),
        "stage": stage_id,
        "attempt": int(state.get("stage_attempts", {}).get(stage_id, 1)),
        "gate_status": gate_status,
        "validator": transcript,
    })
    validate_persisted_registries(room, state, project_root)


def snapshot(
    project_root: Path, runner_root: Path,
    room: Optional[Mapping[str, Any]] = None,
) -> Dict[str, str]:
    output = {}
    root = project_root.resolve()
    excluded_prefixes = {"artifacts/runs/.registry"}
    if room is not None:
        excluded_prefixes.update({
            safe_relative(workspace.get("path"), "workspace.path").rstrip("/")
            for workspace in room.get("workspaces", [])
            if isinstance(workspace, dict) and workspace.get("type") == "worktree"
        })
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root)
        relative = relative_path.as_posix()
        if any(
            relative == prefix or relative.startswith(prefix + "/")
            for prefix in excluded_prefixes
        ):
            continue
        if any(part in SKIP_SNAPSHOT_PARTS for part in relative_path.parts):
            continue
        try:
            path.resolve().relative_to(runner_root.resolve())
        except ValueError:
            pass
        else:
            continue
        output[relative] = sha256_file(path)
    return output


def unexpected_unprovenanced_changes(
    before: Mapping[str, str], after: Mapping[str, str],
    state: Mapping[str, Any],
) -> List[str]:
    changed = {
        path for path in set(before) | set(after) if before.get(path) != after.get(path)
    }
    provenance = state.get("artifact_provenance", {})
    results = state.get("results", {})
    leases = state.get("task_leases", {})
    approved: Set[str] = set()
    if isinstance(provenance, dict):
        for path, produced in provenance.items():
            if not isinstance(path, str) or not isinstance(produced, dict):
                continue
            task_id = produced.get("task_id")
            lease = leases.get(task_id) if isinstance(leases, dict) else None
            if (isinstance(results, dict) and task_id in results and
                    isinstance(lease, dict) and lease.get("status") == "recorded" and
                    after.get(path) == produced.get("digest")):
                approved.add(path)
    return sorted(changed - approved)


def issue_tasks(
    room: Mapping[str, Any], state: Dict[str, Any], project_root: Path,
) -> List[Dict[str, Any]]:
    """Issue pending tasks against one immutable stage baseline."""
    project = project_root.resolve()
    verify_workspace_state(room, state, project, current_stage_only=True)
    tasks = pending_tasks(room, state, project)
    if not tasks:
        return []
    runner_root, _, _ = state_paths(project, str(state["run_id"]))
    stage_id = str(state["current_stage"])
    attempt = int(state["stage_attempts"][stage_id])
    baseline_relative = "baselines/%s-%d.json" % (stage_id, attempt)
    baseline_path = runner_root / Path(*PurePosixPath(baseline_relative).parts)
    leases = state.setdefault("task_leases", {})
    stage_leases = [
        lease for lease in leases.values()
        if isinstance(lease, dict) and lease.get("stage") == stage_id and
        lease.get("attempt") == attempt
    ]
    if baseline_path.is_file():
        if not stage_leases:
            raise RunnerError("task baseline was preseeded before any lease")
        baseline_digest = sha256_file(baseline_path)
    else:
        if stage_leases:
            raise RunnerError("issued task baseline is missing")
        atomic_json(baseline_path, snapshot(project, runner_root, room))
        baseline_digest = sha256_file(baseline_path)
    created: Set[str] = set()
    for task in tasks:
        existing = leases.get(task["task_id"])
        if existing is None:
            lease_id = uuid.uuid4().hex
            output_relative = "leases/%s/output" % lease_id
            output_root = unredirected_path(
                runner_root, output_relative, "private task output root",
            )
            try:
                output_root.mkdir(parents=True, exist_ok=False)
            except OSError as exc:
                raise RunnerError("cannot create private task output root: %s" % exc) from exc
            output_root = unredirected_path(
                runner_root, output_relative, "private task output root",
            )
            task_relative = "tasks/%s.json" % hashlib.sha256(
                task["task_id"].encode("utf-8")
            ).hexdigest()
            leases[task["task_id"]] = {
                "lease_id": lease_id,
                "stage": stage_id,
                "attempt": attempt,
                "seat": task["seat"],
                "baseline": baseline_relative,
                "baseline_digest": baseline_digest,
                "commit_sha": state["commit_sha"],
                "output_root": output_relative,
                "task_path": task_relative,
                "task_digest": "",
                "status": "issued",
                "issued_at": next_marker(),
            }
            created.add(task["task_id"])
        elif (not isinstance(existing, dict) or
              existing.get("baseline_digest") != baseline_digest or
              existing.get("status") not in {"issued", "running"}):
            raise RunnerError("task lease is inconsistent for %s" % task["task_id"])
    issued = [
        task for task in pending_tasks(room, state, project)
        if state["task_leases"][task["task_id"]].get("status") == "issued"
    ]
    for task in issued:
        lease = leases[task["task_id"]]
        task_path = runner_root / Path(*PurePosixPath(lease["task_path"]).parts)
        if task["task_id"] in created:
            if task_path.exists():
                raise RunnerError("task contract path was preseeded")
            atomic_json(task_path, task)
            lease["task_digest"] = sha256_file(task_path)
        elif (not task_path.is_file() or
              sha256_file(task_path) != lease.get("task_digest") or
              read_json(task_path) != task):
            raise RunnerError("issued task contract is missing or changed")
    return issued


def verify_task_boundary(
    task_id: str, room: Mapping[str, Any], state: Mapping[str, Any],
    project_root: Path, *, lease_statuses: Set[str] = frozenset({"issued"}),
) -> None:
    """Reject drift and undeclared writes since the task was issued."""
    project = project_root.resolve()
    lease = state.get("task_leases", {}).get(task_id)
    if not isinstance(lease, dict) or lease.get("status") not in lease_statuses:
        raise RunnerError("task has no active runner-issued lease")
    verify_workspace_state(
        room, state, project, seat_id=str(lease.get("seat")),
    )
    runner_root, _, _ = state_paths(project, str(state["run_id"]))
    relative = safe_relative(lease.get("baseline"), "task lease baseline")
    baseline_path = runner_root / Path(*PurePosixPath(relative).parts)
    expected_digest = lease.get("baseline_digest")
    if (not baseline_path.is_file() or
            sha256_file(baseline_path) != expected_digest):
        raise RunnerError("task baseline is missing or changed")
    baseline = read_json(baseline_path)
    if (not isinstance(baseline, dict) or
            not all(isinstance(key, str) and isinstance(value, str)
                    for key, value in baseline.items())):
        raise RunnerError("task baseline is malformed")
    current = snapshot(project, runner_root, room)
    violations = unexpected_unprovenanced_changes(baseline, current, state)
    if violations:
        raise RunnerError(
            "undeclared project changes since task issue: " +
            ", ".join(violations)
        )


def load_context(
    room_path: Path, project_root: Path,
) -> Tuple[Dict[str, Any], Dict[str, Any], Path, Path, Path]:
    project = project_root.resolve()
    room_raw = read_json(room_path.resolve())
    if not isinstance(room_raw, dict) or not isinstance(room_raw.get("run_id"), str):
        raise RunnerError("room has no run_id")
    if not is_windows_safe_run_id(room_raw["run_id"]):
        raise RunnerError("room has an unsafe run_id")
    _, state_path, lock_path = state_paths(project, room_raw["run_id"])
    if not state_path.is_file():
        raise RunnerError("run is not initialized")
    with exclusive(lock_path):
        state = authoritative_state(state_path, project, room_raw["run_id"])
        if not isinstance(state, dict) or state.get("schema") != STATE_SCHEMA:
            raise RunnerError("runner state is invalid")
        suite_root = Path(str(state.get("suite_root")))
        room, digest = load_prepared_room(room_path, suite_root)
        if digest != state.get("room_digest") or room.get("run_id") != state.get("run_id"):
            raise RunnerError("prepared room changed after initialization")
        state = validate_state(
            state, room, room_path, project, digest,
        )
        verify_claim(room_path, room, digest, project)
    return room, state, state_path.parent, state_path, lock_path


def initialize(args: argparse.Namespace) -> Dict[str, Any]:
    project_root = args.project_root.resolve()
    suite_root = args.suite.resolve()
    room, digest = load_prepared_room(args.room, suite_root)
    verify_claim(args.room, room, digest, project_root)
    if COMMIT_RE.fullmatch(args.commit) is None:
        raise RunnerError("--commit must be a 40-character lowercase Git SHA")
    if ENVIRONMENT_RE.fullmatch(args.environment) is None:
        raise RunnerError("--environment must be a safe lowercase identifier")
    runner_root, state_path, lock_path = state_paths(project_root, str(room["run_id"]))
    head_path = state_head_path(project_root, str(room["run_id"]))
    with exclusive(lock_path):
        if state_path.exists():
            raise RunnerError("run is already initialized; use status to resume it")
        unexpected_control = [
            path.name for path in runner_root.iterdir() if path != lock_path
        ]
        if unexpected_control or head_path.exists():
            raise RunnerError(
                "runner control root was preseeded: " +
                ", ".join(sorted(unexpected_control + (
                    [head_path.name] if head_path.exists() else []
                )))
            )
        reject_untracked_project_inputs(project_root, args.room)
        workspace_heads: Optional[Dict[str, str]] = None
        try:
            workspace_heads = materialize_workspaces(
                room, project_root, args.commit,
            )
            install_trusted_validators(
                suite_root, room["runtime_trust"], runner_root,
            )
            tracked_manifests = write_git_manifests(
                room, project_root, args.commit, runner_root,
            )
            first_stage = str(room["stages"][0]["id"])
            state = {
                "schema": STATE_SCHEMA,
                "room": str(args.room.resolve()),
                "room_digest": digest,
                "suite_root": str(suite_root),
                "runtime_trust": room["runtime_trust"],
                "project_root": str(project_root),
                "run_id": room["run_id"],
                "profile": room["profile"],
                "commit_sha": args.commit,
                "environment": args.environment,
                "workspace_heads": workspace_heads,
                "tracked_manifests": tracked_manifests,
                "commit_history": [{
                    "event": next_marker(), "from": None, "to": args.commit,
                    "action": "initialize",
                }],
                "status": "READY",
                "current_stage": first_stage,
                "stage_attempts": {first_stage: 1},
                "loop_iterations": 0,
                "results": {},
                "task_leases": {},
                "artifact_claims": {},
                "artifact_provenance": {},
                "completed_stages": [],
                "history": [{"event": next_marker(), "action": "initialize"}],
                "blocker": None,
                "state_revision": 1,
            }
            validate_state(state, room, args.room, project_root, digest)
            try:
                initialize_state_journal(
                    state_path,
                    head_path,
                    state,
                    str(room["run_id"]),
                )
            except JournalError as exc:
                raise RunnerError("cannot initialize state journal: %s" % exc) from exc
        except Exception:
            if workspace_heads is not None:
                remove_materialized_workspaces(room, project_root)
            cleanup_runner_control(runner_root, head_path, lock_path)
            raise
    return state


def execute_adapter(
    args: argparse.Namespace, room: Dict[str, Any], state: Dict[str, Any],
    runner_root: Path, state_path: Path,
) -> Dict[str, Any]:
    """Execute one adapter without assuming an outer state lock."""
    execution = prepare_adapter_execution(args, room, state, runner_root)
    persist_state(state_path, state)

    def register_process(pid: int, identity: str) -> None:
        lease = state["task_leases"][execution["task"]["task_id"]]
        lease["adapter_pid"] = pid
        lease["adapter_identity"] = identity
        lease["adapter_started_at"] = next_marker()
        persist_state(state_path, state)

    completed, process_error = run_adapter_process(
        args, execution, register_process,
    )
    try:
        result = finalize_adapter_execution(
            args, room, state, runner_root, execution, completed, process_error,
        )
    except RunnerError:
        persist_state(state_path, state)
        raise
    persist_state(state_path, state)
    return result


def prepare_adapter_execution(
    args: argparse.Namespace, room: Dict[str, Any], state: Dict[str, Any],
    runner_root: Path,
) -> Dict[str, Any]:
    tasks = issue_tasks(room, state, args.project_root.resolve())
    selected = [task for task in tasks if task["seat"] == args.seat]
    if len(selected) != 1:
        raise RunnerError("--seat must identify one pending task")
    if not args.adapter:
        raise RunnerError("--adapter requires an executable and optional arguments")
    task = selected[0]
    lease = state.setdefault("task_leases", {}).get(task["task_id"])
    if not isinstance(lease, dict) or lease.get("status") != "issued":
        raise RunnerError("task is not available for adapter execution")
    runner_pid = os.getpid()
    runner_identity = _process_identity(runner_pid)
    if runner_identity is None:
        raise RunnerError("runner process identity could not be captured")
    lease["status"] = "running"
    lease["started_at"] = next_marker()
    lease["runner_pid"] = runner_pid
    lease["runner_host"] = socket.gethostname()
    lease["runner_identity"] = runner_identity
    task_path = runner_root / Path(*PurePosixPath(lease["task_path"]).parts)
    if (not task_path.is_file() or sha256_file(task_path) != lease["task_digest"] or
            read_json(task_path) != task):
        raise RunnerError("adapter task contract changed before execution")
    result_path = runner_root / "leases" / lease["lease_id"] / "result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.unlink(missing_ok=True)
    before = snapshot(args.project_root, runner_root, room)
    execution_relative = "leases/%s/execution-baseline.json" % lease["lease_id"]
    execution_path = runner_root / Path(*PurePosixPath(execution_relative).parts)
    if execution_path.exists():
        raise RunnerError("adapter execution snapshot was preseeded")
    atomic_json(execution_path, before)
    lease["execution_snapshot"] = execution_relative
    lease["execution_snapshot_digest"] = sha256_file(execution_path)
    _, workspace = workspace_for_seat(
        room, seat_map(room)[str(task["seat"])], args.project_root,
    )
    environment = os.environ.copy()
    environment.update({
        "SOLO_AGENTROOM_TASK": str(task_path),
        "SOLO_AGENTROOM_RESULT": str(result_path),
        "SOLO_AGENTROOM_RUN_ID": str(state["run_id"]),
        "SOLO_AGENTROOM_COMMIT_SHA": str(state["commit_sha"]),
        "SOLO_AGENTROOM_ARTIFACT_ROOT": str(task["artifact_root"]),
        "SOLO_AGENTROOM_WORKSPACE_ROOT": str(workspace.resolve()),
    })
    return {
        "task": task,
        "lease_id": lease["lease_id"],
        "task_path": task_path,
        "result_path": result_path,
        "before": before,
        "workspace": workspace,
        "environment": environment,
    }


def run_adapter_process(
    args: argparse.Namespace, execution: Mapping[str, Any],
    on_started: Optional[Callable[[int, str], None]] = None,
) -> Tuple[Optional[subprocess.CompletedProcess[str]], Optional[str]]:
    process: Optional[Any] = None
    identity: Optional[str] = None
    try:
        options: Dict[str, Any] = {}
        if os.name == "nt":
            options["creationflags"] = getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0,
            )
        else:
            options["start_new_session"] = True
        process = subprocess.Popen(
            args.adapter, cwd=str(execution["workspace"]),
            env=dict(execution["environment"]),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            **options,
        )
        identity = _process_identity(process.pid)
        if identity is None:
            process.terminate()
            return None, "adapter process identity could not be captured"
        if on_started is not None:
            on_started(process.pid, identity)
        try:
            stdout, stderr = process.communicate(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            terminate_adapter_tree(process.pid, identity)
            stdout, stderr = process.communicate(timeout=10)
            return None, "adapter timed out after %s seconds: %s" % (
                args.timeout, (stdout + stderr).strip(),
            )
        completed = subprocess.CompletedProcess(
            args=args.adapter, returncode=process.returncode,
            stdout=stdout, stderr=stderr,
        )
    except (OSError, subprocess.SubprocessError, RunnerError) as exc:
        if (process is not None and process.poll() is None and
                isinstance(identity, str)):
            terminate_adapter_tree(process.pid, identity)
        return None, "adapter could not complete: %s" % exc
    return completed, None


def finalize_adapter_execution(
    args: argparse.Namespace, room: Dict[str, Any], state: Dict[str, Any],
    runner_root: Path, execution: Mapping[str, Any],
    completed: Optional[subprocess.CompletedProcess[str]],
    process_error: Optional[str],
    before_promotion: Optional[
        Callable[[Mapping[str, Any], Dict[str, Any]], None]
    ] = None,
) -> Dict[str, Any]:
    task = execution["task"]
    if not isinstance(task, dict):
        raise RunnerError("adapter task context is invalid")
    lease = state.get("task_leases", {}).get(task.get("task_id"))
    if (state.get("status") != "READY" or not isinstance(lease, dict) or
            lease.get("status") != "running" or
            lease.get("lease_id") != execution.get("lease_id")):
        raise RunnerError("adapter task lease is no longer active")
    before = execution["before"]
    if not isinstance(before, dict):
        raise RunnerError("adapter snapshot context is invalid")

    def block(message: str) -> None:
        state["status"] = "BLOCKED"
        state["blocker"] = message
        lease["status"] = "failed"
        lease["failed_at"] = next_marker()

    after = snapshot(args.project_root, runner_root, room)
    violations = unexpected_unprovenanced_changes(before, after, state)
    if violations:
        block("adapter changed undeclared paths: " + ", ".join(violations))
        state["unexpected_changes"] = {
            path: {"before": before.get(path), "after": after.get(path)}
            for path in violations
        }
        raise RunnerError(state["blocker"])
    if process_error is not None:
        block(process_error)
        raise RunnerError(process_error)
    if completed is None:
        block("adapter process returned no result")
        raise RunnerError(state["blocker"])
    if completed.returncode != 0:
        block("adapter exited %d: %s" % (
            completed.returncode, (completed.stdout + completed.stderr).strip(),
        ))
        raise RunnerError(state["blocker"])
    try:
        result = read_json(Path(str(execution["result_path"])))
        record_result(
            result, room, state, args.project_root.resolve(),
            lease_statuses={"running"},
            before_promotion=before_promotion,
        )
    except RunnerError as exc:
        block("adapter result was rejected: %s" % exc)
        raise RunnerError(state["blocker"]) from exc
    return result


def execute_adapter_command(args: argparse.Namespace) -> Dict[str, Any]:
    """Lease under the state lock, execute unlocked, then commit under lock."""
    room, state, runner_root, state_path, lock_path = load_context(
        args.room, args.project_root,
    )
    room_digest = str(state["room_digest"])
    with exclusive(lock_path):
        state = validate_state(
            authoritative_state(
                state_path, args.project_root.resolve(), str(state["run_id"]),
            ), room, args.room, args.project_root.resolve(),
            room_digest,
        )
        recovered = recover_crashed_adapter_leases(
            state, room, args.project_root.resolve(),
        )
        recovered = recover_incomplete_promotions(
            state, room, args.project_root.resolve(),
        ) or recovered
        if recovered:
            persist_state(state_path, state)
        if state.get("status") != "READY":
            raise RunnerError("only a READY run can execute an adapter")
        execution = prepare_adapter_execution(args, room, state, runner_root)
        persist_state(state_path, state)

    def register_process(pid: int, identity: str) -> None:
        with exclusive(lock_path):
            registered = validate_state(
                authoritative_state(
                    state_path, args.project_root.resolve(), str(state["run_id"]),
                ), room, args.room, args.project_root.resolve(), room_digest,
            )
            task_id = execution["task"]["task_id"]
            lease = registered.get("task_leases", {}).get(task_id)
            if (not isinstance(lease, dict) or lease.get("status") != "running" or
                    lease.get("lease_id") != execution.get("lease_id")):
                raise RunnerError("adapter lease ended before process registration")
            lease["adapter_pid"] = pid
            lease["adapter_identity"] = identity
            lease["adapter_started_at"] = next_marker()
            persist_state(state_path, registered)

    completed, process_error = run_adapter_process(
        args, execution, register_process,
    )

    # Re-read the immutable room and trust contract after the unlocked process.
    room, state, runner_root, state_path, lock_path = load_context(
        args.room, args.project_root,
    )
    with exclusive(lock_path):
        state = validate_state(
            authoritative_state(
                state_path, args.project_root.resolve(), str(state["run_id"]),
            ), room, args.room, args.project_root.resolve(),
            room_digest,
        )
        try:
            result = finalize_adapter_execution(
                args, room, state, runner_root, execution,
                completed, process_error,
                before_promotion=lambda normalized, lease: persist_pending_promotion(
                    normalized, lease, state, runner_root, state_path,
                ),
            )
        except RunnerError:
            if state.get("status") == "BLOCKED":
                persist_state(state_path, state)
            raise
        persist_state(state_path, state)
        return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    subparsers = root.add_subparsers(dest="command", required=True)

    initialize_parser = subparsers.add_parser("init")
    initialize_parser.add_argument("room", type=Path)
    initialize_parser.add_argument("--project-root", type=Path, required=True)
    initialize_parser.add_argument("--suite", type=Path, required=True)
    initialize_parser.add_argument("--commit", required=True)
    initialize_parser.add_argument("--environment", required=True)

    for name in ("status", "next", "advance", "retry"):
        command = subparsers.add_parser(name)
        command.add_argument("room", type=Path)
        command.add_argument("--project-root", type=Path, required=True)

    record = subparsers.add_parser("record")
    record.add_argument("room", type=Path)
    record.add_argument("result", type=Path)
    record.add_argument("--project-root", type=Path, required=True)

    rebind = subparsers.add_parser("rebind")
    rebind.add_argument("room", type=Path)
    rebind.add_argument("--project-root", type=Path, required=True)
    rebind.add_argument("--commit", required=True)

    execute = subparsers.add_parser("execute")
    execute.add_argument("room", type=Path)
    execute.add_argument("--project-root", type=Path, required=True)
    execute.add_argument("--seat", required=True)
    execute.add_argument("--timeout", type=int, default=900)
    execute.add_argument("--adapter", nargs=argparse.REMAINDER, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "init":
            payload = initialize(args)
        elif args.command == "execute":
            payload = execute_adapter_command(args)
        else:
            room, state, runner_root, state_path, lock_path = load_context(
                args.room, args.project_root,
            )
            with exclusive(lock_path):
                # Reload after acquiring the lock so two callers cannot act on
                # the same prior state.
                refreshed = authoritative_state(
                    state_path, args.project_root.resolve(), str(state["run_id"]),
                )
                state = validate_state(
                    refreshed, room, args.room, args.project_root.resolve(),
                    str(state["room_digest"]),
                )
                recovered = recover_crashed_adapter_leases(
                    state, room, args.project_root.resolve(),
                )
                recovered = recover_incomplete_promotions(
                    state, room, args.project_root.resolve(),
                ) or recovered
                if recovered:
                    persist_state(state_path, state)
                if args.command == "status":
                    payload = state
                elif args.command == "next":
                    tasks = (
                        issue_tasks(room, state, args.project_root.resolve())
                        if state.get("status") == "READY" else []
                    )
                    if state.get("status") == "READY":
                        persist_state(state_path, state)
                    payload = {
                        "run_id": state["run_id"],
                        "status": state["status"],
                        "current_stage": state["current_stage"],
                        "tasks": tasks,
                    }
                elif args.command == "record":
                    if state.get("status") != "READY":
                        raise RunnerError("only a READY run accepts task results")
                    try:
                        record_result(
                            read_json(args.result), room, state,
                            args.project_root.resolve(),
                            before_promotion=lambda normalized, lease: persist_pending_promotion(
                                normalized, lease, state, runner_root, state_path,
                            ),
                        )
                    except RunnerError:
                        if state.get("status") == "BLOCKED":
                            persist_state(state_path, state)
                        raise
                    persist_state(state_path, state)
                    payload = state
                elif args.command == "advance":
                    if state.get("status") != "READY":
                        raise RunnerError("only a READY run can advance")
                    if pending_tasks(room, state, args.project_root.resolve()):
                        raise RunnerError(
                            "current stage still has pending or running tasks"
                        )
                    try:
                        advance_stage(
                            args.room.resolve(), room, state,
                            args.project_root.resolve(),
                        )
                    except RunnerError as exc:
                        state["status"] = "BLOCKED"
                        state["blocker"] = str(exc)
                        state.setdefault("history", []).append({
                            "event": next_marker(), "action": "block",
                            "stage": state["current_stage"], "reason": str(exc),
                        })
                        persist_state(state_path, state)
                        raise
                    persist_state(state_path, state)
                    payload = state
                elif args.command == "retry":
                    if state.get("status") != "BLOCKED":
                        raise RunnerError("retry requires a BLOCKED run")
                    if any(
                        isinstance(lease, dict) and lease.get("status") == "running"
                        for lease in state.get("task_leases", {}).values()
                    ):
                        raise RunnerError("retry cannot run while an adapter task is active")
                    active_failed = []
                    for task_id, lease in state.get("task_leases", {}).items():
                        if not isinstance(lease, dict) or lease.get("status") != "failed":
                            continue
                        pid = lease.get("adapter_pid")
                        identity = lease.get("adapter_identity")
                        if (isinstance(pid, int) and isinstance(identity, str) and
                                _process_identity(pid) == identity):
                            active_failed.append(str(task_id))
                    if active_failed:
                        raise RunnerError(
                            "retry cannot run while an orphan adapter is active: " +
                            ", ".join(sorted(active_failed))
                        )
                    unexpected = state.get("unexpected_changes", {})
                    if isinstance(unexpected, dict) and unexpected:
                        unrestored = []
                        for relative, digests in unexpected.items():
                            target = unredirected_path(
                                args.project_root.resolve(), relative,
                                "unexpected change",
                            )
                            if os.path.lexists(str(target)) and is_linklike(target):
                                unrestored.append(relative)
                                continue
                            if target.is_file():
                                current = sha256_file(target)
                            elif os.path.lexists(str(target)):
                                unrestored.append(relative)
                                continue
                            else:
                                current = None
                            before = (
                                digests.get("before")
                                if isinstance(digests, dict) else None
                            )
                            if current != before:
                                unrestored.append(relative)
                        if unrestored:
                            raise RunnerError(
                                "retry requires cleanup of unexpected paths: " +
                                ", ".join(sorted(unrestored))
                            )
                        state["unexpected_changes"] = {}
                    stage_id = str(state["current_stage"])
                    attempts = state.setdefault("stage_attempts", {})
                    attempts[stage_id] = int(attempts.get(stage_id, 0)) + 1
                    state["status"] = "READY"
                    state["blocker"] = None
                    state.setdefault("history", []).append({
                        "event": next_marker(), "action": "retry", "stage": stage_id,
                    })
                    persist_state(state_path, state)
                    payload = state
                elif args.command == "rebind":
                    rebind_commit(
                        room, state, args.project_root.resolve(), args.commit,
                    )
                    persist_state(state_path, state)
                    payload = state
                else:  # pragma: no cover - argparse makes this unreachable.
                    raise RunnerError("unknown runner command")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    except (RunnerError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print("FAIL %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
