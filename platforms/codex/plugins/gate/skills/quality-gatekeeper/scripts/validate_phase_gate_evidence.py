#!/usr/bin/env python3
"""Validate fail-closed Solo Suite phase-gate evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


RUN_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,62}[a-z0-9])$")
GATE_ID = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
COMMIT = re.compile(r"^[0-9a-fA-F]{7,64}$")
SKILL = re.compile(r"^\$[a-z][a-z0-9-]*$")
DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")
WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{value}" for value in range(1, 10)),
    *(f"LPT{value}" for value in range(1, 10)),
}


def parse_time(value: object, field: str, failures: list[str]) -> datetime | None:
    if not isinstance(value, str):
        failures.append(f"{field} must be an ISO-8601 string")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        failures.append(f"{field} is not valid ISO-8601")
        return None
    if parsed.tzinfo is None:
        failures.append(f"{field} must include a timezone")
        return None
    return parsed.astimezone(timezone.utc)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(data: object, root: Path, run_id: str, gate_id: str,
             commit: str, environment: str,
             now: datetime | None = None, *,
             expected_prerequisites: list[dict] | None = None,
             expected_room_digest: str | None = None,
             max_age_hours: int = 24) -> list[str]:
    failures: list[str] = []
    now = now or datetime.now(timezone.utc)
    if not isinstance(data, dict):
        return ["evidence root must be an object"]
    required = {
        "schema", "room_digest", "run_id", "gate_id", "project", "commit_sha",
        "environment", "timestamp", "expires_at", "reviewer", "decision",
        "checks", "blockers",
    }
    missing = sorted(required - set(data))
    if missing:
        failures.append(f"missing top-level fields: {missing}")
    unknown = sorted(set(data) - required)
    if unknown:
        failures.append(f"unknown top-level fields: {unknown}")
    if data.get("schema") != "solo-suite/phase-gate-evidence-v1":
        failures.append("schema must be solo-suite/phase-gate-evidence-v1")
    if not isinstance(data.get("room_digest"), str) or not DIGEST.fullmatch(
            data.get("room_digest", "")):
        failures.append("room_digest must be a sha256 digest")
    if expected_room_digest is None:
        failures.append("a prepared-room digest is required")
    elif data.get("room_digest") != expected_room_digest:
        failures.append("evidence is bound to a different prepared room")
    if not isinstance(max_age_hours, int) or isinstance(max_age_hours, bool) or max_age_hours < 1:
        failures.append("max_age_hours must be a positive integer")
        max_age_hours = 1
    actual_run = data.get("run_id")
    if not (isinstance(actual_run, str) and RUN_ID.fullmatch(actual_run)):
        failures.append("run_id is not a portable path segment")
    elif actual_run.split(".", 1)[0].upper() in WINDOWS_RESERVED:
        failures.append("run_id is a Windows-reserved path name")
    if actual_run != run_id:
        failures.append("evidence is from a different run_id")
    if not (isinstance(data.get("gate_id"), str) and
            GATE_ID.fullmatch(data["gate_id"])):
        failures.append("gate_id is invalid")
    if data.get("gate_id") != gate_id:
        failures.append("evidence is for a different gate_id")
    if data.get("commit_sha") != commit:
        failures.append("evidence is from a different commit")
    if not isinstance(data.get("commit_sha"), str) or not COMMIT.fullmatch(
            data.get("commit_sha", "")):
        failures.append("commit_sha is invalid")
    if data.get("environment") != environment:
        failures.append("evidence is from a different environment")
    for field in ("project", "environment", "reviewer"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            failures.append(f"{field} must be a non-empty string")
    timestamp = parse_time(data.get("timestamp"), "timestamp", failures)
    expires = parse_time(data.get("expires_at"), "expires_at", failures)
    if timestamp is not None and timestamp > now:
        failures.append("evidence timestamp is in the future")
    max_age_seconds = max_age_hours * 60 * 60
    if timestamp is not None and (now - timestamp).total_seconds() > max_age_seconds:
        failures.append("evidence exceeds the gate's max_age_hours")
    if expires is not None and expires <= now:
        failures.append("evidence is expired")
    if timestamp is not None and expires is not None and expires <= timestamp:
        failures.append("expires_at must be after timestamp")
    if (timestamp is not None and expires is not None and
            (expires - timestamp).total_seconds() > max_age_seconds):
        failures.append("evidence validity exceeds the gate's max_age_hours")

    blockers = data.get("blockers")
    if not isinstance(blockers, list) or not all(
            isinstance(item, str) and item.strip() for item in blockers):
        failures.append("blockers must be an array of non-empty strings")
        blockers = []
    checks = data.get("checks")
    if not isinstance(checks, list) or not checks:
        failures.append("checks must be a non-empty array")
        checks = []
    if not isinstance(expected_prerequisites, list) or not expected_prerequisites:
        failures.append("the exact gate prerequisite contract is required")
        expected_prerequisites = []
    categories: list[str] = []
    check_statuses: list[str] = []
    root = root.resolve()
    for index, check in enumerate(checks):
        prefix = f"checks[{index}]"
        if not isinstance(check, dict):
            failures.append(f"{prefix} must be an object")
            continue
        required_check = {
            "category", "run_id", "gate_id", "status", "commands_executed", "exit_code",
            "evidence_artifact", "artifact_digest",
        }
        missing_check = sorted(required_check - set(check))
        if missing_check:
            failures.append(f"{prefix} is missing fields: {missing_check}")
        unknown_check = sorted(set(check) - required_check)
        if unknown_check:
            failures.append(f"{prefix} has unknown fields: {unknown_check}")
        category = check.get("category")
        if not isinstance(category, str) or not category.strip():
            failures.append(f"{prefix}.category must be a non-empty string")
        else:
            categories.append(category)
        if check.get("run_id") != run_id:
            failures.append(f"{prefix} is from a different run_id")
        if check.get("gate_id") != gate_id:
            failures.append(f"{prefix} is for a different gate_id")
        status = check.get("status")
        if status not in {"PASS", "FAIL"}:
            failures.append(f"{prefix}.status is invalid")
        else:
            check_statuses.append(status)
        commands = check.get("commands_executed")
        if not isinstance(commands, list) or not commands:
            failures.append(f"{prefix}.commands_executed must be a non-empty array")
            commands = []
        elif len(commands) != len(set(commands)):
            failures.append(f"{prefix}.commands_executed must not contain duplicates")
        for command in commands:
            if not isinstance(command, str) or not SKILL.fullmatch(command):
                failures.append(
                    f"{prefix}.commands_executed must contain Codex $skill invocations")
        exit_code = check.get("exit_code")
        if not isinstance(exit_code, int) or isinstance(exit_code, bool):
            failures.append(f"{prefix}.exit_code must be an integer")
        elif exit_code != 0 and status == "PASS":
            failures.append(f"{prefix}: failed command cannot support PASS")
        artifact = check.get("evidence_artifact")
        digest = check.get("artifact_digest")
        match = DIGEST.fullmatch(digest) if isinstance(digest, str) else None
        if not match:
            failures.append(f"{prefix}.artifact_digest is invalid")
        if not isinstance(artifact, str) or not artifact:
            failures.append(f"{prefix}.evidence_artifact must be a path")
            continue
        path = (root / artifact).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            failures.append(f"{prefix}.evidence_artifact escapes the project root")
        else:
            if not path.is_file():
                failures.append(f"{prefix}.evidence_artifact is missing")
            elif match and sha256(path) != match.group(1):
                failures.append(f"{prefix}.artifact_digest does not match the file")
    if len(categories) != len(set(categories)):
        failures.append("checks must not repeat a category")
    if expected_prerequisites:
        expected_categories = [item.get("category") for item in expected_prerequisites]
        if categories != expected_categories:
            failures.append("checks must match every declared prerequisite in order")
        for index, expected in enumerate(expected_prerequisites):
            if index >= len(checks) or not isinstance(checks[index], dict):
                break
            check = checks[index]
            prefix = f"checks[{index}]"
            if check.get("evidence_artifact") != expected.get("artifact"):
                failures.append(f"{prefix}.evidence_artifact is not the declared prerequisite")
            allowed = expected.get("producer_commands")
            commands = check.get("commands_executed")
            if not isinstance(allowed, list) or not allowed:
                failures.append(f"prerequisite {index} has no declared producer commands")
            elif isinstance(commands, list) and not set(commands).issubset(set(allowed)):
                failures.append(f"{prefix}.commands_executed includes an undeclared producer")

    decision = data.get("decision")
    if decision not in {"GO", "NO-GO"}:
        failures.append("decision is invalid")
    if decision == "GO" and (blockers or any(
            status != "PASS" for status in check_statuses)):
        failures.append("GO requires every check to PASS and no blockers")
    if decision == "NO-GO" and not blockers:
        failures.append("NO-GO requires at least one blocker")
    if decision == "NO-GO" and checks and "FAIL" not in check_statuses:
        failures.append("NO-GO requires at least one failed check")
    return failures


def load_room_contract(path: Path, run_id: str, gate_id: str) -> tuple[list[dict], str, int]:
    room_bytes = path.read_bytes()
    room = json.loads(room_bytes.decode("utf-8"))
    if room.get("prepared") is not True:
        raise ValueError("room must be an instantiated plan with prepared=true")
    if room.get("run_id") != run_id:
        raise ValueError("room is for a different run_id")
    matches = [gate for gate in room.get("gates", [])
               if isinstance(gate, dict) and gate.get("id") == gate_id]
    if len(matches) != 1:
        raise ValueError("room must declare the requested gate exactly once")
    gate = matches[0]
    if gate.get("command") not in {
            "$gate-before-code", "$gate-before-merge", "$gate-before-deploy"}:
        raise ValueError("room gate does not use a phase-gate command")
    evidence = gate.get("evidence", {})
    if evidence.get("schema") != "solo-suite/phase-gate-evidence-v1":
        raise ValueError("room gate does not declare the phase evidence schema")
    prerequisites = gate.get("prerequisites")
    freshness = evidence.get("freshness", {})
    max_age = freshness.get("max_age_hours")
    if not isinstance(prerequisites, list) or not prerequisites:
        raise ValueError("room gate has no prerequisite contract")
    expected_prefix = f"artifacts/runs/{run_id}/"
    categories: list[str] = []
    artifacts: list[str] = []
    for prerequisite in prerequisites:
        if not isinstance(prerequisite, dict):
            raise ValueError("room gate has a malformed prerequisite")
        if not str(prerequisite.get("artifact", "")).startswith(expected_prefix):
            raise ValueError("room gate prerequisite is outside the run namespace")
        categories.append(str(prerequisite.get("category", "")))
        artifacts.append(str(prerequisite.get("artifact", "")))
        commands = prerequisite.get("producer_commands")
        if (not isinstance(commands, list) or not commands or
                len(commands) != len(set(commands)) or
                not all(isinstance(command, str) and SKILL.fullmatch(command)
                        for command in commands)):
            raise ValueError("room gate prerequisite has no producer_commands")
    if len(categories) != len(set(categories)) or len(artifacts) != len(set(artifacts)):
        raise ValueError("room gate prerequisites must use unique categories and artifacts")
    if {key: freshness.get(key) for key in ("run_id", "commit", "environment")} != {
            "run_id": "exact", "commit": "exact", "environment": "exact"}:
        raise ValueError("room gate freshness must bind exact run, commit, and environment")
    if not isinstance(max_age, int) or isinstance(max_age, bool) or max_age < 1:
        raise ValueError("room gate has invalid max_age_hours")
    return prerequisites, f"sha256:{hashlib.sha256(room_bytes).hexdigest()}", max_age


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--gate-id", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--room", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.evidence.read_text(encoding="utf-8"))
    try:
        prerequisites, room_digest, max_age = load_room_contract(
            args.room, args.run_id, args.gate_id)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL invalid prepared-room contract: {exc}")
        return 1
    failures = validate(
        data, args.root, args.run_id, args.gate_id,
        args.commit, args.environment,
        expected_prerequisites=prerequisites,
        expected_room_digest=room_digest,
        max_age_hours=max_age,
    )
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        print(f"{len(failures)} phase-gate evidence failure(s)")
        return 1
    print("PASS phase-gate evidence is current and fail-closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
