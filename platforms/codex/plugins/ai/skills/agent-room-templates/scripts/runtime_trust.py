#!/usr/bin/env python3
"""Build and verify the immutable runtime identity for a prepared AgentRoom."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Mapping
import uuid
import time


TRUST_SCHEMA = "solo-suite/agentroom-runtime-trust-v2"
VALIDATOR_PATHS = {
    "phase": (
        "plugins/gate/skills/quality-gatekeeper/scripts/"
        "validate_phase_gate_evidence.py"
    ),
    "production": (
        "plugins/gate/skills/production-readiness-reviewer/scripts/"
        "validate_gate_evidence.py"
    ),
}
RUNTIME_PATHS = {
    name: "plugins/ai/skills/agent-room-templates/scripts/%s.py" % name
    for name in (
        "git_trust", "prepare_run", "run_room", "runtime_trust",
        "state_journal", "validate_rooms",
    )
}
# The production validator and room semantic validator both import this exact
# policy file.  Pin and install it with the runtime so ``python -I`` validation
# cannot fall back to a mutable or absent suite-level copy.
RUNTIME_PATHS["gate_policy"] = "plugins/gate/lib/gate_policy.py"


class TrustError(ValueError):
    """The selected suite does not match a prepared room's trust contract."""


def _replace(source: Path, target: Path) -> None:
    for attempt in range(8):
        try:
            os.replace(str(source), str(target))
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.02 * (attempt + 1))


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise TrustError("cannot hash trusted file %s: %s" % (path, exc)) from exc
    return "sha256:" + digest.hexdigest()


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def suite_trust(suite_root: Path) -> Dict[str, Any]:
    """Return a content identity for executable skills and gate validators."""
    root = suite_root.resolve()
    skills = []
    for path in sorted(root.glob("plugins/*/skills/*/SKILL.md")):
        relative = path.resolve().relative_to(root).as_posix()
        skills.append({"path": relative, "digest": file_digest(path)})
    if not skills:
        raise TrustError("suite trust requires at least one discoverable SKILL.md")

    validators: Dict[str, Dict[str, str]] = {}
    for name, relative in VALIDATOR_PATHS.items():
        path = root.joinpath(*PurePosixPath(relative).parts)
        if not path.is_file():
            raise TrustError("suite trust validator is missing: %s" % relative)
        validators[name] = {"path": relative, "digest": file_digest(path)}

    runtime: Dict[str, Dict[str, str]] = {}
    for name, relative in RUNTIME_PATHS.items():
        path = root.joinpath(*PurePosixPath(relative).parts)
        if not path.is_file():
            raise TrustError("suite trust runtime is missing: %s" % relative)
        runtime[name] = {"path": relative, "digest": file_digest(path)}

    inventory = {"skills": skills, "validators": validators, "runtime": runtime}
    return {
        "schema": TRUST_SCHEMA,
        "suite_digest": _canonical_digest(inventory),
        "skill_count": len(skills),
        "validators": validators,
        "runtime": runtime,
    }


def verify_suite_trust(suite_root: Path, expected: object) -> Dict[str, Any]:
    """Fail closed unless the selected suite exactly matches ``expected``."""
    if not isinstance(expected, dict):
        raise TrustError("prepared room has no runtime trust object")
    required = {"schema", "suite_digest", "skill_count", "validators", "runtime"}
    if set(expected) != required or expected.get("schema") != TRUST_SCHEMA:
        raise TrustError("prepared room runtime trust shape is invalid")
    actual = suite_trust(suite_root)
    if actual != expected:
        raise TrustError("suite trust mismatch; skills or validators changed")
    return actual


def install_trusted_validators(
    suite_root: Path, expected: Mapping[str, Any], runner_root: Path,
) -> Dict[str, str]:
    """Copy verified validator bytes into the run-owned immutable layout."""
    verify_suite_trust(suite_root, expected)
    trusted_root = runner_root.resolve() / "trusted-suite"
    paths: Dict[str, str] = {}
    validators = expected["validators"]
    runtime = expected["runtime"]
    contracts = [
        (name, contract, VALIDATOR_PATHS, True)
        for name, contract in validators.items()
    ] + [
        (name, contract, RUNTIME_PATHS, False)
        for name, contract in runtime.items()
    ]
    for name, contract, expected_paths, is_validator in contracts:
        if not isinstance(name, str) or not isinstance(contract, dict):
            raise TrustError("runtime trust validator entry is malformed")
        relative = contract.get("path")
        digest = contract.get("digest")
        if (expected_paths.get(name) != relative or
                not isinstance(digest, str)):
            raise TrustError("runtime trust validator entry is inconsistent")
        source = suite_root.resolve().joinpath(*PurePosixPath(relative).parts)
        if file_digest(source) != digest:
            raise TrustError("validator changed before trust installation: %s" % name)
        target = trusted_root.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.parent / (".tmp-%s" % uuid.uuid4().hex[:12])
        try:
            with source.open("rb") as reader, temporary.open("xb") as writer:
                for block in iter(lambda: reader.read(1024 * 1024), b""):
                    writer.write(block)
            if file_digest(temporary) != digest:
                raise TrustError("trusted validator copy digest mismatch: %s" % name)
            _replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        if is_validator:
            paths[name] = str(target)
    return paths


def trusted_validator(
    runner_root: Path, expected: Mapping[str, Any], name: str,
) -> Path:
    """Resolve and re-hash one run-owned validator immediately before use."""
    contract = expected.get("validators", {}).get(name)
    if not isinstance(contract, dict):
        raise TrustError("runtime trust has no %s validator" % name)
    relative = contract.get("path")
    digest = contract.get("digest")
    if VALIDATOR_PATHS.get(name) != relative or not isinstance(digest, str):
        raise TrustError("runtime trust %s validator entry is invalid" % name)
    root = runner_root.resolve() / "trusted-suite"
    path = root.joinpath(*PurePosixPath(relative).parts).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise TrustError("trusted validator escapes the run directory") from exc
    if not path.is_file() or file_digest(path) != digest:
        raise TrustError("trusted %s validator is missing or changed" % name)
    return path


def verify_trusted_install(
    runner_root: Path, expected: Mapping[str, Any],
) -> None:
    """Re-hash every run-owned validator and runtime dependency."""
    root = runner_root.resolve() / "trusted-suite"
    groups = (
        (expected.get("validators"), VALIDATOR_PATHS),
        (expected.get("runtime"), RUNTIME_PATHS),
    )
    for contracts, expected_paths in groups:
        if not isinstance(contracts, dict) or set(contracts) != set(expected_paths):
            raise TrustError("trusted install contract is malformed")
        for name, relative in expected_paths.items():
            contract = contracts.get(name)
            if (not isinstance(contract, dict) or contract.get("path") != relative or
                    not isinstance(contract.get("digest"), str)):
                raise TrustError("trusted install entry is malformed: %s" % name)
            path = root.joinpath(*PurePosixPath(relative).parts).resolve()
            try:
                path.relative_to(root)
            except ValueError as exc:
                raise TrustError("trusted install escapes the run directory") from exc
            if not path.is_file() or file_digest(path) != contract["digest"]:
                raise TrustError("trusted runtime file is missing or changed: %s" % name)
