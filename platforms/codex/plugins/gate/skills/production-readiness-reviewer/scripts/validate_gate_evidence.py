#!/usr/bin/env python3
"""Validate Solo Suite production-gate evidence and reject stale artifacts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def _gate_policy_module():
    """Load the shared Gate policy from source or a trusted AgentRoom copy."""
    path = Path(__file__).resolve().parent.parents[2] / "lib/gate_policy.py"
    spec = importlib.util.spec_from_file_location("solo_suite_gate_policy", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load shared Gate policy: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gp = _gate_policy_module()
CATEGORIES = list(gp.CATEGORY_LABEL_ORDER)
STATUSES = gp.LAUNCH_STATUSES
SCORE_STATUSES = {"SCORED", "INSUFFICIENT EVIDENCE"}
DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")
SKILL_INVOCATION = re.compile(r"^\$[a-z][a-z0-9-]*$")
RUN_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,62}[a-z0-9])$")
GATE_ID = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
COMMIT = re.compile(r"^[0-9a-fA-F]{7,64}$")
WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{value}" for value in range(1, 10)),
    *(f"LPT{value}" for value in range(1, 10)),
}
PROJECT_PROFILES = gp.RECOGNIZED_PROFILES
PROFILE_NA_ALLOWED = {
    profile: frozenset(gp.CATEGORY_LABELS[category]
                       for category in gp.PROFILE_NA_ALLOWED[profile])
    for profile in gp.PROFILE_ORDER
}
MANDATORY_CATEGORIES = frozenset(
    gp.CATEGORY_LABELS[category] for category in gp.MANDATORY
)
evaluate_production_gate = gp.evaluate_production_gate

# Keep this list intentionally narrow: each entry is a real skill bundled with
# Solo Suite and is capable of producing evidence relevant to the category.
# The JSON Schema mirrors these category constraints so both schema-only and
# semantic validation reject invented or misplaced skill invocations.
CATEGORY_SKILLS = {
    "Product": frozenset({
        "$acceptance-criteria-writer", "$product-manager", "$project-prd",
        "$spec-acceptance", "$spec-feature-brief",
    }),
    "Architecture": frozenset({
        "$project-architecture", "$repo-dependency-map", "$repo-risk-map",
        "$software-architect",
    }),
    "Design": frozenset({
        "$accessibility-review", "$browser-visual-check",
        "$design-ui-review", "$design-ux-flow",
    }),
    "Frontend": frozenset({
        "$browser-console-errors", "$browser-mobile-test",
        "$browser-qa-engineer", "$browser-smoke-test", "$site-doctor-a11y",
        "$test-e2e",
    }),
    "Backend": frozenset({
        "$api-audit", "$authz-security-reviewer", "$site-doctor-audit-api",
        "$test-integration",
    }),
    "Database": frozenset({
        "$backup-recovery", "$database-audit", "$security-rls-test",
        "$site-doctor-audit-db", "$stack-audit-supabase",
    }),
    "Security": frozenset({
        "$authz-security-reviewer", "$dependency-audit", "$security-authz-matrix",
        "$security-review", "$security-reviewer", "$security-rls-test",
        "$security-threat-model", "$site-doctor-security-scan",
    }),
    "Testing": frozenset({
        "$browser-qa-engineer", "$qa-engineer", "$test-e2e",
        "$test-edge-cases", "$test-integration", "$test-unit",
    }),
    "Performance": frozenset({
        "$load-testing", "$performance-tuning", "$site-doctor-load-test",
        "$site-doctor-perf", "$website-audit",
    }),
    "SEO": frozenset({
        "$content-audit", "$seo-optimization", "$site-doctor-audit-content",
        "$site-doctor-seo", "$website-audit",
    }),
    "Analytics": frozenset({
        "$analytics-audit", "$forms-audit", "$site-doctor-audit-analytics",
        "$stack-audit-tags", "$tag-audit",
    }),
    "Deployment": frozenset({
        "$deployment-review", "$infrastructure-audit", "$release-deploy-plan",
        "$release-preflight", "$release-rollback-plan",
        "$site-doctor-review-deploy", "$stack-audit-cloudflare",
        "$stack-audit-vercel",
    }),
    "Monitoring": frozenset({
        "$incident-response", "$observability", "$site-doctor-monitoring",
        "$solo-sync-grafana",
    }),
    "Documentation": frozenset({
        "$docs-api", "$docs-runbook", "$docs-setup-guide", "$docs-update",
        "$documentation-writer", "$repo-onboarding",
    }),
}
BUNDLED_EVIDENCE_SKILLS = frozenset().union(*CATEGORY_SKILLS.values())
EVIDENCE_SOURCE_KINDS = {
    "ci-report": frozenset({"ci"}),
    "tool-report": frozenset({"local-tool"}),
    "manual-observation": frozenset({"manual-review"}),
    "narrative-assertion": frozenset({"manual-review", "repository-record"}),
    "applicability-record": frozenset({"repository-record"}),
}


def producer_coverage_failures(
    category_producer_commands: dict[str, object],
) -> list[str]:
    """Return categories whose declared producers cannot satisfy any profile."""

    failures = []
    for category in CATEGORIES:
        applicable_profiles = sorted(
            profile for profile in PROJECT_PROFILES
            if category not in PROFILE_NA_ALLOWED[profile]
        )
        commands = category_producer_commands.get(category)
        declared = (
            set(commands)
            if (isinstance(commands, (list, tuple, frozenset)) and
                all(isinstance(command, str) for command in commands))
            else set()
        )
        if applicable_profiles and not declared & CATEGORY_SKILLS[category]:
            failures.append(
                f"{category} has no declared producer command allowed by the "
                "production evidence contract for applicable profiles: "
                f"{', '.join(applicable_profiles)}"
            )
    return failures


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


def load_room_contract(path: Path, run_id: str, gate_id: str) -> dict:
    """Load the predeclared production contract from one prepared room plan."""

    room_bytes = path.read_bytes()
    room = json.loads(room_bytes.decode("utf-8"))
    if room.get("prepared") is not True:
        raise ValueError("room must be an instantiated plan with prepared=true")
    if room.get("run_id") != run_id:
        raise ValueError("room is for a different run_id")
    gates = [item for item in room.get("gates", []) if isinstance(item, dict)]
    matches = [item for item in gates if item.get("id") == gate_id]
    if len(matches) != 1:
        raise ValueError("room must declare the requested production gate exactly once")
    gate = matches[0]
    if gate.get("command") != "$gate-production-ready":
        raise ValueError("requested room gate is not a production gate")
    if gate.get("evidence", {}).get("schema") != "solo-suite/gate-evidence-v1":
        raise ValueError("production gate does not declare the production evidence schema")
    prerequisites = gate.get("prerequisites")
    if not isinstance(prerequisites, list):
        raise ValueError("production gate has no prerequisite contract")
    for prerequisite in prerequisites:
        commands = prerequisite.get("producer_commands") if isinstance(prerequisite, dict) else None
        if (not isinstance(commands, list) or not commands or
                not all(isinstance(command, str) and SKILL_INVOCATION.fullmatch(command)
                        for command in commands) or
                len(commands) != len(set(commands))):
            raise ValueError(
                "production prerequisite has malformed producer_commands"
            )
    category_prerequisites = [
        item for item in prerequisites if isinstance(item, dict)
        and item.get("category") in CATEGORIES
    ]
    category_artifacts = {
        item.get("category"): item.get("artifact")
        for item in category_prerequisites
    }
    category_producer_commands = {
        item.get("category"): tuple(item["producer_commands"])
        for item in category_prerequisites
    }
    if (len(category_prerequisites) != 14 or
            [item.get("category") for item in category_prerequisites] != CATEGORIES):
        raise ValueError("production gate must predeclare all 14 category artifacts in order")
    if len(set(category_artifacts.values())) != 14:
        raise ValueError("production gate category artifacts must be unique")
    coverage_failures = producer_coverage_failures(category_producer_commands)
    if coverage_failures:
        raise ValueError("; ".join(coverage_failures))
    profiles = [item for item in prerequisites if isinstance(item, dict)
                and item.get("category") == "Project profile"]
    if len(profiles) != 1:
        raise ValueError("production gate must predeclare one project-profile artifact")
    run_prefix = f"artifacts/runs/{run_id}/"
    for artifact in [*category_artifacts.values(), profiles[0].get("artifact")]:
        if not isinstance(artifact, str) or not artifact.startswith(run_prefix):
            raise ValueError("production prerequisite is outside the exact run namespace")
    freshness = gate.get("evidence", {}).get("freshness", {})
    max_age = freshness.get("max_age_hours")
    if not isinstance(max_age, int) or isinstance(max_age, bool) or max_age < 1:
        raise ValueError("production gate has invalid max_age_hours")
    if {key: freshness.get(key) for key in ("run_id", "commit", "environment")} != {
            "run_id": "exact", "commit": "exact", "environment": "exact"}:
        raise ValueError("production gate freshness must bind exact run, commit, and environment")

    required_results = []
    gate_by_id = {item.get("id"): item for item in gates}
    for requirement in gate.get("required_gate_results", []):
        if not isinstance(requirement, dict):
            raise ValueError("production gate has a malformed required gate result")
        required_gate = gate_by_id.get(requirement.get("gate_id"))
        if not isinstance(required_gate, dict):
            raise ValueError("production gate requires an unknown gate result")
        evidence = required_gate.get("evidence", {})
        artifact = evidence.get("artifact")
        prereqs = required_gate.get("prerequisites")
        required_max_age = evidence.get("freshness", {}).get("max_age_hours")
        if (not isinstance(artifact, str) or not artifact.startswith(run_prefix) or
                not isinstance(prereqs, list) or not prereqs or
                not isinstance(required_max_age, int) or required_max_age < 1):
            raise ValueError("required gate result has an incomplete contract")
        if (required_gate.get("command") != "$gate-before-deploy" or
                evidence.get("schema") != "solo-suite/phase-gate-evidence-v1"):
            raise ValueError("production required result must be a before-deploy phase gate")
        if requirement.get("freshness") != {
                "run_id": "exact", "commit": "exact",
                "environment": "exact", "latest": True}:
            raise ValueError("required gate result freshness is not exact and latest")
        required_results.append({
            "gate_id": requirement.get("gate_id"),
            "status": requirement.get("status"),
            "artifact": artifact,
            "prerequisites": prereqs,
            "max_age_hours": required_max_age,
        })
    if not any(item["gate_id"] == "before_deploy" and item["status"] == "GO"
               for item in required_results):
        raise ValueError("production gate must require an exact before_deploy GO")
    return {
        "room_digest": f"sha256:{hashlib.sha256(room_bytes).hexdigest()}",
        "max_age_hours": max_age,
        "category_artifacts": category_artifacts,
        "category_producer_commands": category_producer_commands,
        "profile_artifact": profiles[0]["artifact"],
        "required_gate_results": required_results,
    }


def _phase_validator_module():
    path = (
        Path(__file__).resolve().parents[2] / "quality-gatekeeper" /
        "scripts" / "validate_phase_gate_evidence.py"
    )
    spec = importlib.util.spec_from_file_location("solo_phase_gate_validator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the phase-gate validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_project_profile(
    data: dict, root: Path, run_id: str, commit: str, environment: str,
    project: object, now: datetime, max_age_hours: int, expected_artifact: str,
    failures: list[str],
) -> dict[str, dict]:
    artifact = data.get("profile_artifact")
    digest = data.get("profile_artifact_digest")
    match = DIGEST.fullmatch(digest) if isinstance(digest, str) else None
    if artifact != expected_artifact:
        failures.append("profile_artifact is not the room's declared project profile")
    if not match:
        failures.append("profile_artifact_digest is invalid")
    if not isinstance(artifact, str):
        return {}
    path = (root / artifact).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        failures.append("profile_artifact escapes the project root")
        return {}
    if not path.is_file():
        failures.append("profile_artifact is missing")
        return {}
    if match and sha256(path) != match.group(1):
        failures.append("profile_artifact_digest does not match the file")
        return {}
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        failures.append("profile_artifact must be valid UTF-8 JSON")
        return {}
    required = {
        "schema", "run_id", "project", "commit_sha", "environment",
        "profile", "timestamp", "categories",
    }
    if not isinstance(profile, dict) or not required.issubset(profile):
        failures.append("profile_artifact is missing required project-profile fields")
        return {}
    unknown_profile = sorted(set(profile) - required)
    if unknown_profile:
        failures.append(f"profile_artifact has unknown fields: {unknown_profile}")
    if profile.get("schema") != "solo-suite/project-profile-v1":
        failures.append("profile_artifact uses the wrong schema")
    for field, expected in (
        ("run_id", run_id), ("project", project), ("commit_sha", commit),
        ("environment", environment), ("profile", data.get("project_profile")),
    ):
        if profile.get(field) != expected:
            failures.append(f"profile_artifact {field} does not match gate evidence")
    profile_time = parse_time(profile.get("timestamp"), "profile_artifact.timestamp", failures)
    if profile_time is not None:
        if profile_time > now:
            failures.append("profile_artifact.timestamp is in the future")
        elif (now - profile_time).total_seconds() > max_age_hours * 3600:
            failures.append("profile_artifact exceeds the gate's max_age_hours")
    records = profile.get("categories")
    if not isinstance(records, list):
        failures.append("profile_artifact.categories must be an array")
        return {}
    names = [item.get("category") for item in records if isinstance(item, dict)]
    if names != CATEGORIES:
        failures.append("profile_artifact must cover the canonical 14 categories in order")
    result: dict[str, dict] = {}
    allowed_na = PROFILE_NA_ALLOWED.get(profile.get("profile"), frozenset())
    for index, item in enumerate(records):
        if not isinstance(item, dict):
            failures.append(f"profile_artifact.categories[{index}] must be an object")
            continue
        allowed_fields = {"category", "applicability", "reason"}
        unknown_item = sorted(set(item) - allowed_fields)
        if unknown_item:
            failures.append(
                f"profile_artifact.categories[{index}] has unknown fields: {unknown_item}"
            )
        category = item.get("category")
        applicability = item.get("applicability")
        if applicability not in {"applicable", "not-applicable"}:
            failures.append(f"profile_artifact category {category!r} has invalid applicability")
        if applicability == "not-applicable":
            if category not in allowed_na:
                failures.append(
                    f"project profile {profile.get('profile')!r} cannot mark {category} N/A"
                )
            if not isinstance(item.get("reason"), str) or not item["reason"].strip():
                failures.append(f"profile_artifact category {category!r} needs an N/A reason")
        if isinstance(category, str):
            result[category] = item
    return result


def validate_required_gate_results(
    contract: dict, root: Path, run_id: str, commit: str, environment: str,
    now: datetime, failures: list[str],
) -> None:
    requirements = contract.get("required_gate_results")
    if not isinstance(requirements, list) or not requirements:
        failures.append("production contract has no required gate results")
        return
    try:
        phase = _phase_validator_module()
    except (OSError, ImportError, RuntimeError) as exc:
        failures.append(f"cannot validate required phase-gate results: {exc}")
        return
    for requirement in requirements:
        gate_id = requirement.get("gate_id")
        artifact = requirement.get("artifact")
        prefix = f"required gate {gate_id!r}"
        if not isinstance(artifact, str):
            failures.append(f"{prefix} has no evidence artifact")
            continue
        path = (root / artifact).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            failures.append(f"{prefix} evidence escapes the project root")
            continue
        if not path.is_file():
            failures.append(f"{prefix} evidence is missing")
            continue
        try:
            evidence = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            failures.append(f"{prefix} evidence is not valid UTF-8 JSON")
            continue
        phase_failures = phase.validate(
            evidence, root, run_id, str(gate_id), commit, environment, now=now,
            expected_prerequisites=requirement.get("prerequisites"),
            expected_room_digest=contract.get("room_digest"),
            max_age_hours=requirement.get("max_age_hours", 1),
        )
        failures.extend(f"{prefix}: {message}" for message in phase_failures)
        if evidence.get("decision") != requirement.get("status"):
            failures.append(
                f"{prefix} must be {requirement.get('status')}, got {evidence.get('decision')}"
            )


def validate_warning(value: object, index: int, failures: list[str]) -> None:
    prefix = f"warnings[{index}]"
    if not isinstance(value, dict):
        failures.append(f"{prefix} must be a structured warning object")
        return
    required = {"message", "category", "owner", "remediation", "verification"}
    missing = sorted(required - set(value))
    if missing:
        failures.append(f"{prefix} is missing fields: {missing}")
    unknown = sorted(set(value) - required)
    if unknown:
        failures.append(f"{prefix} has unknown fields: {unknown}")
    for field in ("message", "owner", "remediation"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            failures.append(f"{prefix}.{field} must be a non-empty string")
    if value.get("category") not in CATEGORIES:
        failures.append(f"{prefix}.category must be one of the 14 gate categories")
    verification = value.get("verification")
    if not isinstance(verification, dict):
        failures.append(f"{prefix}.verification must be an object")
        return
    verification_fields = {"method", "success_criteria"}
    unknown_verification = sorted(set(verification) - verification_fields)
    if unknown_verification:
        failures.append(
            f"{prefix}.verification has unknown fields: {unknown_verification}"
        )
    for field in ("method", "success_criteria"):
        if not isinstance(verification.get(field), str) or not verification[field].strip():
            failures.append(
                f"{prefix}.verification.{field} must be a non-empty string"
            )


def validate_provenance(record: dict, prefix: str, record_time: datetime | None,
                        now: datetime, failures: list[str]) -> None:
    evidence_type = record.get("evidence_type")
    if evidence_type not in EVIDENCE_SOURCE_KINDS:
        failures.append(f"{prefix}.evidence_type is invalid")
    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        failures.append(f"{prefix}.provenance must be an object")
        return
    required = {"source_kind", "producer", "source_reference", "generated_at"}
    missing = sorted(required - set(provenance))
    if missing:
        failures.append(f"{prefix}.provenance is missing fields: {missing}")
    unknown = sorted(set(provenance) - required)
    if unknown:
        failures.append(f"{prefix}.provenance has unknown fields: {unknown}")
    for field in ("producer", "source_reference"):
        if not isinstance(provenance.get(field), str) or not provenance[field].strip():
            failures.append(f"{prefix}.provenance.{field} must be a non-empty string")
    source_kind = provenance.get("source_kind")
    allowed_sources = EVIDENCE_SOURCE_KINDS.get(evidence_type, frozenset())
    if source_kind not in allowed_sources:
        failures.append(
            f"{prefix}.provenance.source_kind is incompatible with evidence_type"
        )
    generated_at = parse_time(
        provenance.get("generated_at"), f"{prefix}.provenance.generated_at", failures
    )
    if generated_at is not None and generated_at > now:
        failures.append(f"{prefix}.provenance.generated_at is in the future")
    if (generated_at is not None and record_time is not None and
            generated_at > record_time):
        failures.append(
            f"{prefix}.provenance.generated_at must not be after the review timestamp"
        )


def validate(data: object, root: Path, commit: str, environment: str,
             now: datetime | None = None, *, run_id: str | None = None,
             gate_id: str | None = None, mode: str | None = None,
             contract: dict | None = None,
             max_age_hours: int = 24) -> list[str]:
    failures: list[str] = []
    now = now or datetime.now(timezone.utc)
    if not isinstance(data, dict):
        return ["evidence root must be an object"]
    if mode is None:
        mode = ("score" if data.get("schema") == "solo-suite/score-evidence-v1"
                else "production")
    if mode not in {"production", "score"}:
        return ["mode must be production or score"]
    required = {
        "schema", "run_id", "gate_id", "project", "commit_sha", "environment", "timestamp",
        "expires_at", "reviewer", "categories", "total_score",
        "normalized_score",
    }
    if mode == "production":
        required.update({
            "room_digest", "project_profile", "profile_artifact",
            "profile_artifact_digest", "launch_status", "blockers", "warnings",
        })
    else:
        required.update({"assessment_status", "risks"})
    missing = sorted(required - set(data))
    if missing:
        failures.append(f"missing top-level fields: {missing}")
    unknown_top = sorted(set(data) - required)
    if unknown_top:
        failures.append(f"unknown top-level fields: {unknown_top}")
    expected_schema = ("solo-suite/gate-evidence-v1" if mode == "production"
                       else "solo-suite/score-evidence-v1")
    if data.get("schema") != expected_schema:
        failures.append(f"schema must be {expected_schema}")
    if not isinstance(max_age_hours, int) or isinstance(max_age_hours, bool) or max_age_hours < 1:
        failures.append("max_age_hours must be a positive integer")
        max_age_hours = 1
    if mode == "production":
        if not isinstance(contract, dict):
            failures.append("production validation requires a prepared-room contract")
            contract = {}
        else:
            max_age_hours = contract.get("max_age_hours", max_age_hours)
        category_producer_commands = contract.get("category_producer_commands")
        if (not isinstance(category_producer_commands, dict) or
                list(category_producer_commands) != CATEGORIES):
            failures.append(
                "prepared-room contract must preserve producer_commands for all "
                "14 categories in canonical order"
            )
            category_producer_commands = {}
        else:
            failures.extend(
                f"prepared-room contract {failure}"
                for failure in producer_coverage_failures(category_producer_commands)
            )
        if (not isinstance(max_age_hours, int) or isinstance(max_age_hours, bool) or
                max_age_hours < 1):
            failures.append("prepared-room max_age_hours must be a positive integer")
            max_age_hours = 1
        if data.get("room_digest") != contract.get("room_digest"):
            failures.append("production evidence is bound to a different prepared room")
        if data.get("project_profile") not in PROJECT_PROFILES:
            failures.append("project_profile is invalid")
    actual_run = data.get("run_id")
    if not (isinstance(actual_run, str) and RUN_ID.fullmatch(actual_run)):
        failures.append("run_id is not a portable path segment")
    elif actual_run.split(".", 1)[0].upper() in WINDOWS_RESERVED:
        failures.append("run_id is a Windows-reserved path name")
    if run_id is not None and actual_run != run_id:
        failures.append("top-level evidence is from a different run_id")
    actual_gate = data.get("gate_id")
    if not (isinstance(actual_gate, str) and GATE_ID.fullmatch(actual_gate)):
        failures.append("gate_id is invalid")
    if gate_id is not None and actual_gate != gate_id:
        failures.append("top-level evidence is for a different gate_id")
    if data.get("commit_sha") != commit:
        failures.append("top-level evidence is from a different commit")
    if not isinstance(data.get("commit_sha"), str) or not COMMIT.fullmatch(
            data.get("commit_sha", "")):
        failures.append("top-level commit_sha is invalid")
    if data.get("environment") != environment:
        failures.append("top-level evidence is from a different environment")
    for field in ("project", "environment", "reviewer"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            failures.append(f"top-level {field} must be a non-empty string")
    expires = parse_time(data.get("expires_at"), "expires_at", failures)
    timestamp = parse_time(data.get("timestamp"), "timestamp", failures)
    if timestamp is not None and timestamp > now:
        failures.append("top-level evidence timestamp is in the future")
    max_age_seconds = max_age_hours * 60 * 60
    if timestamp is not None and (now - timestamp).total_seconds() > max_age_seconds:
        failures.append("top-level evidence exceeds the gate's max_age_hours")
    if expires is not None and expires <= now:
        failures.append("top-level evidence is expired")
    if timestamp is not None and expires is not None and expires <= timestamp:
        failures.append("top-level expires_at must be after timestamp")
    if (timestamp is not None and expires is not None and
            (expires - timestamp).total_seconds() > max_age_seconds):
        failures.append("top-level evidence validity exceeds the gate's max_age_hours")
    if mode == "production":
        blockers_value = data.get("blockers")
        if not isinstance(blockers_value, list) or not all(
            isinstance(value, str) and value.strip() for value in blockers_value
        ):
            failures.append("blockers must be an array of non-empty strings")
        warnings_value = data.get("warnings")
        if not isinstance(warnings_value, list):
            failures.append("warnings must be an array")
        else:
            for index, warning in enumerate(warnings_value):
                validate_warning(warning, index, failures)
    else:
        if "launch_status" in data or "decision" in data:
            failures.append("score evidence must not contain a launch or phase verdict")
        risks = data.get("risks")
        if not isinstance(risks, list) or not all(
            isinstance(value, str) and value.strip() for value in risks
        ):
            failures.append("risks must be an array of non-empty strings")
    root = root.resolve()
    profile_map: dict[str, dict] = {}
    if mode == "production":
        profile_map = validate_project_profile(
            data, root, str(actual_run), commit, environment, data.get("project"),
            now, max_age_hours, str(contract.get("profile_artifact", "")), failures,
        )
    records = data.get("categories")
    if not isinstance(records, list):
        failures.append("categories must be an array")
        records = []
    names = [record.get("category") for record in records if isinstance(record, dict)]
    if names != CATEGORIES:
        failures.append("categories must contain the exact 14 categories in canonical order")
    scores: dict[str, int] = {}
    not_applicable: set[str] = set()
    for index, record in enumerate(records):
        prefix = f"categories[{index}]"
        if not isinstance(record, dict):
            failures.append(f"{prefix} must be an object")
            continue
        for field in (
            "project", "run_id", "gate_id", "commit_sha", "environment", "timestamp", "expires_at",
            "category", "score", "applicability", "command_executed",
            "exit_code", "evidence_artifact", "artifact_digest", "reviewer",
            "evidence_type", "provenance",
        ):
            if field not in record:
                failures.append(f"{prefix}.{field} is required")
        allowed_record_fields = {
            "project", "run_id", "gate_id", "commit_sha", "environment",
            "timestamp", "expires_at", "category", "score", "applicability",
            "na_reason", "command_executed", "exit_code", "evidence_type",
            "provenance", "evidence_artifact", "artifact_digest", "reviewer",
        }
        unknown_record = sorted(set(record) - allowed_record_fields)
        if unknown_record:
            failures.append(f"{prefix} has unknown fields: {unknown_record}")
        if record.get("project") != data.get("project"):
            failures.append(f"{prefix} belongs to another project")
        if record.get("run_id") != actual_run:
            failures.append(f"{prefix} is from a different run_id")
        if record.get("gate_id") != actual_gate:
            failures.append(f"{prefix} is for a different gate_id")
        if record.get("commit_sha") != commit:
            failures.append(f"{prefix} is from a different commit")
        if record.get("environment") != environment:
            failures.append(f"{prefix} is from a different environment")
        record_time = parse_time(
            record.get("timestamp"), f"{prefix}.timestamp", failures
        )
        if record_time is not None and record_time > now:
            failures.append(f"{prefix}.timestamp is in the future")
        if (record_time is not None and
                (now - record_time).total_seconds() > max_age_seconds):
            failures.append(f"{prefix} exceeds the gate's max_age_hours")
        record_expiry = parse_time(record.get("expires_at"),
                                   f"{prefix}.expires_at", failures)
        if record_expiry is not None and record_expiry <= now:
            failures.append(f"{prefix} is expired")
        if (record_time is not None and record_expiry is not None and
                record_expiry <= record_time):
            failures.append(f"{prefix}.expires_at must be after timestamp")
        if (record_time is not None and record_expiry is not None and
                (record_expiry - record_time).total_seconds() > max_age_seconds):
            failures.append(f"{prefix} validity exceeds the gate's max_age_hours")
        score = record.get("score")
        if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 10:
            failures.append(f"{prefix}.score must be an integer from 0 to 10")
        elif record.get("category") in CATEGORIES:
            scores[str(record["category"])] = score
        applicability = record.get("applicability")
        if applicability not in {"applicable", "not-applicable"}:
            failures.append(f"{prefix}.applicability is invalid")
        if applicability == "not-applicable":
            category_key = gp.LABEL_CATEGORIES.get(record.get("category"))
            if category_key is not None:
                not_applicable.add(category_key)
            if not isinstance(record.get("na_reason"), str) or not record["na_reason"].strip():
                failures.append(f"{prefix}.na_reason is required for N/A")
            if score != 0:
                failures.append(
                    f"{prefix}: N/A must score 0 and leave the applicable denominator"
                )
            if record.get("evidence_type") != "applicability-record":
                failures.append(
                    f"{prefix}: N/A evidence_type must be applicability-record"
                )
            if mode == "production":
                profile_record = profile_map.get(str(record.get("category")), {})
                if profile_record.get("applicability") != "not-applicable":
                    failures.append(f"{prefix}: project profile does not approve N/A")
                elif record.get("na_reason") != profile_record.get("reason"):
                    failures.append(f"{prefix}: N/A reason differs from project profile")
                provenance = record.get("provenance")
                if (not isinstance(provenance, dict) or
                        provenance.get("source_reference") != data.get("profile_artifact")):
                    failures.append(f"{prefix}: N/A provenance must reference profile_artifact")
        elif record.get("evidence_type") == "applicability-record":
            failures.append(
                f"{prefix}: applicability-record is only valid for not-applicable controls"
            )
        elif mode == "production" and profile_map.get(
                str(record.get("category")), {}).get("applicability") != "applicable":
            failures.append(f"{prefix}: category applicability conflicts with project profile")
        command = record.get("command_executed")
        if not isinstance(command, str) or not SKILL_INVOCATION.fullmatch(command):
            failures.append(f"{prefix}.command_executed must be a Codex $skill invocation")
        elif command not in BUNDLED_EVIDENCE_SKILLS:
            failures.append(
                f"{prefix}.command_executed is not a bundled evidence skill"
            )
        elif command not in CATEGORY_SKILLS.get(record.get("category"), frozenset()):
            failures.append(
                f"{prefix}.command_executed is not allowed for {record.get('category')}"
            )
        if (mode == "production" and isinstance(command, str) and
                command not in category_producer_commands.get(
                    record.get("category"), ())):
            failures.append(
                f"{prefix}.command_executed was not declared by the room producer "
                f"for {record.get('category')}"
            )
        exit_code = record.get("exit_code")
        if not isinstance(exit_code, int) or isinstance(exit_code, bool):
            failures.append(f"{prefix}.exit_code must be an integer")
        elif exit_code != 0 and isinstance(score, int) and score > 0:
            failures.append(f"{prefix}: failed evidence command cannot support a positive score")
        if record.get("reviewer") != data.get("reviewer"):
            failures.append(f"{prefix} was attested by a different reviewer")
        validate_provenance(record, prefix, record_time, now, failures)
        artifact = record.get("evidence_artifact")
        digest = record.get("artifact_digest")
        match = DIGEST.fullmatch(digest) if isinstance(digest, str) else None
        if not match:
            failures.append(f"{prefix}.artifact_digest is invalid")
        if isinstance(artifact, str):
            expected_prefix = f"artifacts/runs/{actual_run}/"
            if not artifact.startswith(expected_prefix):
                failures.append(f"{prefix}.evidence_artifact is outside the exact run namespace")
            if mode == "production":
                expected_artifact = contract.get("category_artifacts", {}).get(
                    record.get("category"))
                if artifact != expected_artifact:
                    failures.append(
                        f"{prefix}.evidence_artifact is not the room's declared category artifact"
                    )
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
    applicable_labels = [
        category for category in CATEGORIES
        if gp.LABEL_CATEGORIES[category] not in not_applicable
    ]
    applicable_scores = [scores[category] for category in applicable_labels
                         if category in scores]
    complete_scores = len(scores) == len(CATEGORIES)
    total = sum(applicable_scores) if complete_scores else None
    normalized = None
    if total is not None:
        try:
            normalized = gp.normalized_score(total, len(applicable_labels))
        except ValueError as exc:
            failures.append(f"production scoring policy rejected evidence: {exc}")
    if total is not None and data.get("total_score") != total:
        failures.append("total_score does not equal the applicable category scores")
    if normalized is not None and data.get("normalized_score") != normalized:
        failures.append(
            "normalized_score does not equal "
            "round(total/(10*applicable_category_count)*100)"
        )
    if mode == "score":
        assessment = data.get("assessment_status")
        if assessment not in {"SCORED", "INSUFFICIENT EVIDENCE"}:
            failures.append("assessment_status is invalid")
        risks = data.get("risks") if isinstance(data.get("risks"), list) else []
        if assessment == "INSUFFICIENT EVIDENCE" and not risks:
            failures.append("INSUFFICIENT EVIDENCE requires at least one risk")
        if records and all(
                isinstance(record, dict) and
                record.get("applicability") == "not-applicable"
                for record in records) and assessment != "INSUFFICIENT EVIDENCE":
            failures.append("all-N/A scoring must be INSUFFICIENT EVIDENCE")
        return failures

    validate_required_gate_results(
        contract, root, str(actual_run), commit, environment, now, failures,
    )
    status = data.get("launch_status")
    if status not in STATUSES:
        failures.append("launch_status is invalid")
    blockers = data.get("blockers") if isinstance(data.get("blockers"), list) else []
    warnings = data.get("warnings") if isinstance(data.get("warnings"), list) else []
    if (normalized is not None and applicable_scores and
            data.get("project_profile") in PROJECT_PROFILES):
        policy_scores = {
            gp.LABEL_CATEGORIES[category]: scores[category]
            for category in CATEGORIES if category in scores
        }
        if len(policy_scores) == len(gp.CATEGORY_ORDER):
            try:
                assessment = gp.evaluate_production_gate(
                    policy_scores, data["project_profile"], not_applicable,
                    blockers, warnings,
                )
            except ValueError as exc:
                failures.append(f"production policy rejected evidence: {exc}")
            else:
                expected = assessment["launch_status"]
                if status in STATUSES and status != expected:
                    failures.append(
                        f"launch_status must be {expected} under the shared "
                        "production policy"
                    )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--gate-id", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--mode", choices=("production", "score"), required=True)
    parser.add_argument("--room", type=Path)
    parser.add_argument("--max-age-hours", type=int, default=24)
    args = parser.parse_args()
    data = json.loads(args.evidence.read_text(encoding="utf-8"))
    contract = None
    if args.mode == "production":
        if args.room is None:
            parser.error("--room is required for production validation")
        try:
            contract = load_room_contract(args.room, args.run_id, args.gate_id)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            parser.error(f"invalid prepared-room contract: {exc}")
    failures = validate(
        data, args.root, args.commit, args.environment,
        run_id=args.run_id, gate_id=args.gate_id, mode=args.mode,
        contract=contract, max_age_hours=args.max_age_hours,
    )
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        print(f"{len(failures)} gate evidence failure(s)")
        return 1
    print("PASS gate evidence is complete, current, and internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
