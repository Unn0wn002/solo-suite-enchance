#!/usr/bin/env python3
"""Validate Solo Suite AgentRoom templates.

The bundled JSON Schema is the portable interchange contract. When the
``jsonschema`` package is available this script applies it first; the
stdlib-only semantic pass always checks constraints JSON Schema cannot express
(unique ids by property, graph reachability, command side effects,
single-writer memory ownership, gate evidence/read coverage, and bounded
loops). It treats every Codex ``$skill`` invocation as a declarative operation;
it does not execute skills or start agents.

Usage:
  python validate_rooms.py [room.json ...] [--suite ROOT]

With no room paths, all templates in ../agentsrooms are checked.  Exit status
is 0 only when every template passes.
"""
from __future__ import print_function

import argparse
import glob
import importlib.util
import json
import os
import re
import sys

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # Semantic validation remains available in minimal installs.
    Draft202012Validator = None
    FormatChecker = None


SCHEMA_NAME = "solo-suite/agentroom-v1"
CMD_RE = re.compile(r"^\$[a-z][a-z0-9-]*$")
ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
RUN_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,62}[a-z0-9])$")
TASK_ID_RE = re.compile(r"^T[0-9]+$")
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *("COM%d" % value for value in range(1, 10)),
    *("LPT%d" % value for value in range(1, 10)),
}
WINDOWS_FORBIDDEN_PATH_CHARS = frozenset('<>:"|?*')

SHARED_PREFIX = ".solo/"
UNIVERSAL_MEMORY_EFFECTS = {
    ".solo/tasks.md",
    ".solo/decisions.md",
    ".solo/handoff.md",
}


def _gate_policy_module():
    """Load the suite's one production category and scoring policy."""
    path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "..", "gate", "lib",
        "gate_policy.py",
    ))
    spec = importlib.util.spec_from_file_location(
        "solo_suite_agentroom_gate_policy", path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load shared Gate policy: %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GATE_POLICY = _gate_policy_module()

# These are effects documented by the target skills in addition to the suite's
# universal task/decision/handoff lifecycle.  A propose-only seat must declare
# each effect in `proposals`; the memory steward is the only direct writer.
COMMAND_MEMORY_EFFECTS = {
    "$repo-dependency-map": {".solo/risks.md"},
    "$stack-intake": {".solo/stack.md"},
    "$stack-connector-check": {".solo/stack.md"},
    "$project-prd": {".solo/prd.md"},
    "$project-task-breakdown": {".solo/tasks.md"},
    "$project-architecture": {".solo/architecture.md"},
    "$spec-feature-brief": {".solo/prd.md"},
    "$spec-acceptance": {".solo/prd.md"},
    "$spec-api-contract": {".solo/api-contract.md"},
    "$spec-data-contract": {".solo/data-contract.md"},
    "$spec-env-contract": {".solo/env-contract.md"},
    "$design-ux-flow": {".solo/design.md"},
    "$design-component-system": {".solo/design.md"},
    "$design-ui-review": {".solo/design.md"},
    "$dev-implement-feature": {".solo/tasks.md", ".solo/decisions.md"},
    "$dev-fix-bug": {".solo/bugs.md", ".solo/tasks.md", ".solo/decisions.md"},
    "$dev-code-review": {".solo/tasks.md", ".solo/risks.md"},
    "$test-unit": {".solo/tests.md"},
    "$test-integration": {".solo/tests.md"},
    "$test-e2e": {".solo/tests.md"},
    "$test-edge-cases": {".solo/tests.md"},
    "$browser-smoke-test": {".solo/bugs.md", ".solo/tests.md"},
    "$browser-console-errors": {".solo/bugs.md", ".solo/tests.md"},
    "$browser-mobile-test": {".solo/bugs.md", ".solo/tests.md"},
    "$browser-visual-check": {".solo/bugs.md", ".solo/tests.md"},
    "$security-threat-model": {".solo/risks.md"},
    "$security-authz-matrix": {".solo/risks.md"},
    "$security-rls-test": {".solo/risks.md", ".solo/tests.md"},
    "$site-doctor-full-checkup": {".solo/bugs.md", ".solo/risks.md"},
    "$site-doctor-a11y": {".solo/bugs.md", ".solo/risks.md", ".solo/tests.md"},
    "$site-doctor-audit-db": {".solo/risks.md"},
    "$site-doctor-audit-deps": {".solo/risks.md"},
    "$site-doctor-audit-forms": {".solo/bugs.md", ".solo/risks.md"},
    "$site-doctor-compliance": {".solo/risks.md"},
    "$site-doctor-load-test": {".solo/risks.md", ".solo/tests.md"},
    "$site-doctor-monitoring": {".solo/monitoring.md"},
    "$site-doctor-audit-analytics": {".solo/risks.md"},
    "$site-doctor-perf": {".solo/risks.md"},
    "$site-doctor-seo": {".solo/risks.md"},
    "$stack-audit-vercel": {".solo/risks.md"},
    "$stack-audit-supabase": {".solo/risks.md"},
    "$stack-audit-cloudflare": {".solo/risks.md"},
    "$stack-audit-tags": {".solo/risks.md"},
    "$stack-audit-payments": {".solo/risks.md"},
    "$growth-conversion-audit": {".solo/tasks.md", ".solo/risks.md"},
    "$release-preflight": {".solo/release.md", ".solo/risks.md"},
    "$release-deploy-plan": {".solo/release.md"},
    "$release-rollback-plan": {".solo/release.md", ".solo/risks.md"},
    "$gate-before-code": {".solo/risks.md"},
    "$gate-before-merge": {".solo/risks.md"},
    "$gate-before-deploy": {".solo/risks.md"},
    "$gate-production-ready": {".solo/risks.md"},
    "$gate-score-project": {".solo/risks.md"},
    "$solo-handoff-memory": {
        ".solo/handoff.md", ".solo/tasks.md", ".solo/decisions.md"
    },
}

PRODUCTION_CATEGORIES = GATE_POLICY.CATEGORY_LABEL_ORDER
PRODUCTION_PROFILE_NA_ALLOWED = {
    profile: frozenset(GATE_POLICY.CATEGORY_LABELS[category]
                       for category in GATE_POLICY.PROFILE_NA_ALLOWED[profile])
    for profile in GATE_POLICY.PROFILE_ORDER
}
PRODUCTION_MANDATORY_CATEGORIES = frozenset(
    GATE_POLICY.CATEGORY_LABELS[category]
    for category in GATE_POLICY.MANDATORY
)

# This mirrors the production-evidence validator's category allowlist.  Room
# validation applies it to the declared producer command set so an AgentRoom
# cannot pass structural validation while its production contract is
# impossible to satisfy.  tests/test_gate_evidence.py guards the two copies
# against drift alongside the JSON Schema allowlist.
PRODUCTION_CATEGORY_SKILLS = {
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

ENFORCED_GATE_COMMANDS = {
    "$gate-before-code",
    "$gate-before-merge",
    "$gate-before-deploy",
    "$gate-production-ready",
}

PHASE_GATE_EVIDENCE_FIELDS = {
    "schema", "room_digest", "run_id", "gate_id", "project", "commit_sha",
    "environment", "timestamp", "expires_at", "reviewer", "decision",
    "checks", "blockers",
}
SCORE_EVIDENCE_FIELDS = {
    "schema", "run_id", "gate_id", "project", "commit_sha",
    "environment", "timestamp", "expires_at", "reviewer", "categories",
    "total_score", "normalized_score", "assessment_status", "risks",
}
PRODUCTION_GATE_EVIDENCE_FIELDS = {
    "schema", "room_digest", "run_id", "gate_id", "project_profile",
    "profile_artifact", "profile_artifact_digest", "project", "commit_sha",
    "environment", "timestamp", "expires_at", "reviewer", "categories",
    "total_score", "normalized_score", "launch_status", "blockers",
    "warnings",
}

EVIDENCE_CONTRACTS = {
    "solo-suite/phase-gate-evidence-v1": {
        "status_field": "decision",
        "statuses": frozenset({"GO", "NO-GO"}),
        "required_fields": PHASE_GATE_EVIDENCE_FIELDS,
    },
    "solo-suite/score-evidence-v1": {
        "status_field": "assessment_status",
        "statuses": frozenset({"SCORED", "INSUFFICIENT EVIDENCE"}),
        "required_fields": SCORE_EVIDENCE_FIELDS,
    },
    "solo-suite/gate-evidence-v1": {
        "status_field": "launch_status",
        "statuses": GATE_POLICY.LAUNCH_STATUSES,
        "required_fields": PRODUCTION_GATE_EVIDENCE_FIELDS,
    },
}

COMMAND_EVIDENCE_SCHEMA = {
    "$gate-before-code": "solo-suite/phase-gate-evidence-v1",
    "$gate-before-merge": "solo-suite/phase-gate-evidence-v1",
    "$gate-before-deploy": "solo-suite/phase-gate-evidence-v1",
    "$gate-score-project": "solo-suite/score-evidence-v1",
    "$gate-production-ready": "solo-suite/gate-evidence-v1",
}

FULL_TEAM_REQUIRED_COMMANDS = {
    "$stack-intake",
    "$stack-connector-check",
    "$spec-feature-brief",
    "$spec-acceptance",
    "$browser-smoke-test",
    "$browser-mobile-test",
    "$browser-visual-check",
    "$site-doctor-a11y",
    "$site-doctor-audit-forms",
    "$site-doctor-compliance",
    "$site-doctor-audit-deps",
    "$site-doctor-perf",
    "$site-doctor-load-test",
    "$stack-audit-vercel",
    "$stack-audit-supabase",
    "$stack-audit-cloudflare",
    "$stack-audit-tags",
    "$stack-audit-payments",
    "$git-commit-plan",
    "$release-ci-setup",
    "$solo-handoff-memory",
    "$gate-before-deploy",
}

FULL_TEAM_BEFORE_MERGE_ARTIFACTS = {
    "artifacts/full-team/accessibility.json",
    "artifacts/full-team/browser-qa.json",
    "artifacts/full-team/contract-verification.json",
    "artifacts/full-team/dependency-sbom.json",
    "artifacts/full-team/forms-privacy.json",
    "artifacts/full-team/lint-types.json",
    "artifacts/full-team/migration-verification.json",
    "artifacts/full-team/performance-load.json",
    "artifacts/full-team/visual-cross-browser.json",
    "artifacts/full-team/vendor-audits/analytics-tag.json",
    "artifacts/full-team/vendor-audits/cloudflare.json",
    "artifacts/full-team/vendor-audits/payments.json",
    "artifacts/full-team/vendor-audits/supabase.json",
    "artifacts/full-team/vendor-audits/vercel.json",
}

FULL_TEAM_BEFORE_DEPLOY_ARTIFACTS = FULL_TEAM_BEFORE_MERGE_ARTIFACTS | {
    "artifacts/gates/full-team-before-merge.json",
    "artifacts/full-team/environment-readiness.json",
    "artifacts/full-team/handoff-finalization.json",
    "artifacts/full-team/release-management.json",
}

LEGACY_SEAT_KEYS = (
    "id", "role", "reads", "writes", "commands", "deliverable",
    "handoff_check",
)

STRICT_ROOT_KEYS = {
    "$schema", "schema", "name", "version", "prepared", "run_id", "description",
    "based_on_room", "profile", "runtime_trust", "memory_dir", "rules", "memory_steward",
    "tasks", "workspaces", "artifact_locks", "stages", "seats", "gates",
    "exit_gate", "exit_gate_note", "exit_criteria", "loop",
}

STRICT_SEAT_KEYS = {
    "id", "kind", "persistent", "role", "model_hint", "workspace",
    "memory_access", "reads", "writes", "proposals", "commands",
    "deliverable", "handoff_to", "handoff_check", "task_ids",
}


def find_suite(start):
    """Find a Codex-native suite root."""
    directory = os.path.abspath(start)
    while True:
        codex_market = os.path.join(
            directory, ".agents", "plugins", "marketplace.json")
        if os.path.isfile(codex_market):
            return directory
        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent


def known_commands(suite_root):
    """Return every Codex skill invocation available in the suite."""
    if not suite_root:
        return None
    commands = set()
    skills = set()

    # Codex conversion map is authoritative when present.
    map_path = os.path.join(suite_root, "command-map.json")
    if os.path.isfile(map_path):
        try:
            with open(map_path, encoding="utf-8") as handle:
                mapping = json.load(handle)
            if isinstance(mapping, list):
                entries = mapping
            elif isinstance(mapping, dict):
                entries = mapping.get("commands", [])
            else:
                entries = []
            if not isinstance(entries, list):
                entries = []
            for entry in entries:
                if isinstance(entry, dict):
                    invocation = (entry.get("codex_invocation") or
                                  entry.get("skill_invocation"))
                    if isinstance(invocation, str) and CMD_RE.match(invocation):
                        commands.add(invocation)
        except (OSError, ValueError, TypeError):
            # The suite self-check reports malformed maps.  Room validation still
            # checks aliases discoverable from actual skill folders.
            pass

    # A skill is invoked by its folder/frontmatter name.  Older converted
    # commands happen to use <plugin>-<command>, while newer specialist skills
    # (for example analytics-audit) intentionally do not.  Discover both
    # shapes so runtime capability checks cover the whole installed suite.
    skill_pattern = os.path.join(
        suite_root, "plugins", "*", "skills", "*", "SKILL.md")
    for skill_file in glob.glob(skill_pattern):
        skill_dir = os.path.dirname(skill_file)
        skill_name = os.path.basename(skill_dir)
        invocation = "$" + skill_name
        if CMD_RE.match(invocation):
            skills.add(invocation)

    # A supplied suite is a trust boundary.  A stale command-map.json cannot
    # prove that a command can actually be invoked when the suite contains no
    # skill definitions.  Return an empty inventory (rather than None, which
    # means "skip existence checks") so validation fails closed.
    if not skills:
        return set()
    commands.update(skills)
    return commands


def implicit_writes(command):
    """Return shared-memory writes a command contract can perform."""
    if not isinstance(command, str) or not CMD_RE.match(command):
        return set()
    return set(UNIVERSAL_MEMORY_EFFECTS) | set(
        COMMAND_MEMORY_EFFECTS.get(command, set()))


def _is_nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def is_windows_safe_run_id(value):
    """Return whether value is safe as one path segment on every platform."""
    if not (_is_nonempty_string(value) and RUN_ID_RE.fullmatch(value)):
        return False
    return value.split(".", 1)[0].upper() not in WINDOWS_RESERVED_NAMES


def _is_windows_safe_path_segment(value):
    """Return whether one relative-path segment is portable to Windows."""
    if (not value or value in {".", ".."} or value.endswith((" ", ".")) or
            any(ord(char) < 32 or char in WINDOWS_FORBIDDEN_PATH_CHARS
                for char in value)):
        return False
    return value.split(".", 1)[0].upper() not in WINDOWS_RESERVED_NAMES


def is_portable_relative_path(value):
    """Match the runner's fail-closed POSIX relative-path contract."""
    if not _is_nonempty_string(value) or "\\" in value or "\x00" in value:
        return False
    normalized = value.rstrip("/")
    if (not normalized or normalized.startswith("/") or
            re.match(r"^[A-Za-z]:", normalized)):
        return False
    parts = normalized.split("/")
    return all(_is_windows_safe_path_segment(part) for part in parts)


def _is_artifact(value):
    return is_portable_relative_path(value)


def _duplicates(values):
    seen = set()
    duplicate = set()
    for value in values:
        try:
            if value in seen:
                duplicate.add(value)
            else:
                seen.add(value)
        except TypeError:
            continue
    return duplicate


def _command_refs(seat):
    refs = []
    commands = seat.get("commands", []) if isinstance(seat, dict) else []
    if isinstance(commands, list):
        refs.extend(commands)
    handoff_check = seat.get("handoff_check") if isinstance(seat, dict) else None
    if handoff_check is not None:
        refs.append(handoff_check)
    return refs


def _stage_records(stages, strict, bad):
    """Normalize stages to [{id, seats}] while retaining legacy test support."""
    records = []
    if not isinstance(stages, list) or not stages:
        bad("'stages' must be a non-empty list")
        return records
    for index, raw in enumerate(stages):
        if isinstance(raw, dict):
            unknown = set(raw) - {"id", "seats"}
            if strict and unknown:
                bad("stage %d has unknown field(s): %s" %
                    (index + 1, ", ".join(sorted(unknown))))
            stage_id = raw.get("id")
            members = raw.get("seats")
            if not (_is_nonempty_string(stage_id) and ID_RE.match(stage_id)):
                bad("stage %d 'id' must be a unique identifier string" % (index + 1))
            if not (isinstance(members, list) and members):
                bad("stage %d 'seats' must be a non-empty list" % (index + 1))
                members = []
            records.append({"id": stage_id, "seats": members})
        elif isinstance(raw, list) and raw and not strict:
            records.append({"id": "stage_%d" % (index + 1), "seats": raw})
        else:
            expected = "objects with unique id and non-empty seats" if strict else "non-empty seat-id lists"
            bad("stage %d must be %s" % (index + 1, expected))
            records.append({"id": None, "seats": []})
    return records


def validate_room(data, label, known=None):
    """Return human-readable policy violations for one decoded room object."""
    problems = []

    def bad(message):
        problems.append("%s: %s" % (label, message))

    if not isinstance(data, dict):
        bad("room root must be a JSON object")
        return problems

    # Old in-memory unit fixtures predate the v1 schema file.  Files declaring a
    # version or $schema use the strict contract; compatibility is deliberately
    # limited to validate_room() callers rather than bundled templates.
    strict = "version" in data or "$schema" in data or "run_id" in data

    if data.get("schema") != SCHEMA_NAME:
        bad("schema must be %r (got %r)" % (SCHEMA_NAME, data.get("schema")))
    if not _is_nonempty_string(data.get("name")):
        bad("missing non-empty 'name'")

    if strict:
        required_root = STRICT_ROOT_KEYS - {
            "based_on_room", "exit_gate_note", "loop", "runtime_trust"
        }
        for key in sorted(required_root):
            if key not in data:
                bad("missing required root field %r" % key)
        unknown = set(data) - STRICT_ROOT_KEYS
        if unknown:
            bad("unknown root field(s): %s" % ", ".join(sorted(unknown)))
        if not _is_nonempty_string(data.get("$schema")):
            bad("'$schema' must point to agentroom-v1.schema.json")
        if not _is_int(data.get("version")) or data.get("version", 0) < 1:
            bad("'version' must be an integer >= 1")
        if not isinstance(data.get("prepared"), bool):
            bad("'prepared' must be boolean")
        if not is_windows_safe_run_id(data.get("run_id")):
            bad("'run_id' must be a Windows-safe 3-64 character path segment")
        elif data.get("prepared") is True and data["run_id"].startswith("template-"):
            bad("prepared rooms must replace the template run_id")
        elif data.get("prepared") is False and not data["run_id"].startswith("template-"):
            bad("unprepared rooms must use a template-* run_id")
        if not _is_nonempty_string(data.get("description")):
            bad("'description' must be a non-empty string")
        if data.get("memory_dir") != ".solo/":
            bad("'memory_dir' must be '.solo/'")
        if not _is_nonempty_string(data.get("profile")):
            bad("'profile' must be a non-empty project profile")
        elif (data.get("prepared") is True and
              data.get("profile") == "profile-selected-at-runtime"):
            bad("prepared rooms must bind a concrete project profile")
        if data.get("prepared") is True:
            trust = data.get("runtime_trust")
            if not isinstance(trust, dict):
                bad("prepared rooms must bind runtime_trust")
            else:
                validators = trust.get("validators")
                expected_validators = {
                    "phase": (
                        "plugins/gate/skills/quality-gatekeeper/scripts/"
                        "validate_phase_gate_evidence.py"
                    ),
                    "production": (
                        "plugins/gate/skills/production-readiness-reviewer/scripts/"
                        "validate_gate_evidence.py"
                    ),
                }
                expected_runtime = {
                    name: (
                        "plugins/ai/skills/agent-room-templates/scripts/" +
                        name + ".py"
                    )
                    for name in (
                        "git_trust", "prepare_run", "run_room", "runtime_trust",
                        "state_journal", "validate_rooms",
                    )
                }
                expected_runtime["gate_policy"] = (
                    "plugins/gate/lib/gate_policy.py"
                )
                runtime = trust.get("runtime")
                malformed = (
                    set(trust) != {"schema", "suite_digest", "skill_count",
                                   "validators", "runtime"} or
                    trust.get("schema") !=
                    "solo-suite/agentroom-runtime-trust-v2" or
                    not isinstance(trust.get("skill_count"), int) or
                    trust.get("skill_count", 0) < 1 or
                    not re.fullmatch(r"sha256:[0-9a-f]{64}",
                                     str(trust.get("suite_digest", ""))) or
                    not isinstance(validators, dict) or
                    set(validators or {}) != set(expected_validators) or
                    not isinstance(runtime, dict) or
                    set(runtime or {}) != set(expected_runtime)
                )
                if not malformed:
                    for name, expected_path in expected_validators.items():
                        contract = validators.get(name)
                        if (not isinstance(contract, dict) or
                                set(contract) != {"path", "digest"} or
                                contract.get("path") != expected_path or
                                not re.fullmatch(
                                    r"sha256:[0-9a-f]{64}",
                                    str(contract.get("digest", "")),
                                )):
                            malformed = True
                            break
                if not malformed:
                    for name, expected_path in expected_runtime.items():
                        contract = runtime.get(name)
                        if (not isinstance(contract, dict) or
                                set(contract) != {"path", "digest"} or
                                contract.get("path") != expected_path or
                                not re.fullmatch(
                                    r"sha256:[0-9a-f]{64}",
                                    str(contract.get("digest", "")),
                                )):
                            malformed = True
                            break
                if malformed:
                    bad("prepared room runtime_trust is malformed")
        elif "runtime_trust" in data:
            bad("unprepared rooms must not bind runtime_trust")
        rules = data.get("rules")
        if not (isinstance(rules, list) and rules and
                all(_is_nonempty_string(rule) for rule in rules)):
            bad("'rules' must be a non-empty list of strings")

    stage_records = _stage_records(data.get("stages"), strict, bad)
    seats_raw = data.get("seats")
    if not (isinstance(seats_raw, list) and seats_raw):
        bad("'seats' must be a non-empty list")
        return problems

    seats = []
    for index, seat in enumerate(seats_raw):
        if not isinstance(seat, dict):
            bad("seat %d must be an object" % (index + 1))
            continue
        seats.append(seat)
        sid = seat.get("id", "?")
        required = STRICT_SEAT_KEYS if strict else set(LEGACY_SEAT_KEYS)
        for key in sorted(required):
            if key not in seat:
                bad("seat %r missing key %r" % (sid, key))
        if strict:
            unknown = set(seat) - STRICT_SEAT_KEYS
            if unknown:
                bad("seat %r has unknown field(s): %s" %
                    (sid, ", ".join(sorted(unknown))))
        if not (_is_nonempty_string(sid) and ID_RE.match(sid)):
            bad("seat %d 'id' must be an identifier string" % (index + 1))
        for field in ("reads", "writes", "commands"):
            value = seat.get(field)
            if not (isinstance(value, list) and
                    all(_is_nonempty_string(item) for item in value)):
                bad("seat %r field %r must be a list of strings" % (sid, field))
        if strict:
            for field in ("proposals", "task_ids"):
                value = seat.get(field)
                if not (isinstance(value, list) and
                        all(_is_nonempty_string(item) for item in value)):
                    bad("seat %r field %r must be a list of strings" % (sid, field))
            if not isinstance(seat.get("persistent"), bool):
                bad("seat %r 'persistent' must be boolean" % sid)
            if seat.get("kind") not in {"worker", "gatekeeper", "memory-steward"}:
                bad("seat %r has invalid 'kind'" % sid)
            if seat.get("memory_access") not in {"direct", "propose-only", "read-only"}:
                bad("seat %r has invalid 'memory_access'" % sid)
        for field in ("reads", "writes", "proposals"):
            value = seat.get(field, [])
            if isinstance(value, list):
                for artifact in value:
                    if not _is_artifact(artifact):
                        bad("seat %r has non-portable artifact path %r in %s" %
                            (sid, artifact, field))
                for duplicate in sorted(_duplicates(value)):
                    bad("seat %r repeats artifact %r in %s" %
                        (sid, duplicate, field))

    ids = [seat.get("id") for seat in seats if _is_nonempty_string(seat.get("id"))]
    for duplicate in sorted(_duplicates(ids)):
        bad("duplicate seat id %r" % duplicate)
    idset = set(ids)
    seat_by_id = {seat.get("id"): seat for seat in seats if seat.get("id") in idset}

    stage_ids = [stage.get("id") for stage in stage_records
                 if _is_nonempty_string(stage.get("id"))]
    for duplicate in sorted(_duplicates(stage_ids)):
        bad("duplicate stage id %r" % duplicate)
    stage_index = {stage.get("id"): i for i, stage in enumerate(stage_records)
                   if _is_nonempty_string(stage.get("id"))}

    placements = {sid: [] for sid in idset}
    for index, stage in enumerate(stage_records):
        members = stage.get("seats", [])
        if not isinstance(members, list):
            continue
        for duplicate in sorted(_duplicates(members)):
            bad("stage %r repeats seat %r" % (stage.get("id"), duplicate))
        for sid in members:
            if not _is_nonempty_string(sid):
                bad("stage %d contains a non-string seat id" % (index + 1))
                continue
            if sid not in idset:
                bad("stage %d lists unknown seat %r" % (index + 1, sid))
                continue
            placements[sid].append(index)

    for sid, where in sorted(placements.items()):
        seat = seat_by_id.get(sid, {})
        persistent_steward = (strict and seat.get("kind") == "memory-steward" and
                              seat.get("persistent") is True)
        if not where:
            bad("seat %r is not placed in any stage" % sid)
        elif len(where) > 1 and not persistent_steward:
            bad("seat %r appears in more than one stage; a non-persistent seat "
                "belongs to exactly one stage" % sid)

    # A stage is a parallel barrier. A consumer cannot read an artifact whose
    # producer runs in the same stage or any later stage; doing so creates a
    # race even when handoff declarations happen to make the graph reachable.
    artifact_producers = {}
    for producer in seats:
        producer_id = producer.get("id")
        producer_places = placements.get(producer_id, [])
        if len(producer_places) != 1:
            continue
        for artifact in producer.get("writes", []) or []:
            if isinstance(artifact, str) and not artifact.startswith(SHARED_PREFIX):
                artifact_producers.setdefault(artifact, []).append(
                    (producer_id, producer_places[0]))
    for consumer in seats:
        consumer_id = consumer.get("id")
        consumer_places = placements.get(consumer_id, [])
        if len(consumer_places) != 1:
            continue
        consumer_stage = consumer_places[0]
        for artifact in consumer.get("reads", []) or []:
            for producer_id, producer_stage in artifact_producers.get(artifact, []):
                if producer_stage >= consumer_stage:
                    relation = "same" if producer_stage == consumer_stage else "later"
                    bad("seat %r reads artifact %r from %s-stage producer %r; "
                        "split the producer into an earlier stage" %
                        (consumer_id, artifact, relation, producer_id))

    # Handoffs establish the stage graph.  Persistent steward placement does not
    # make a stage reachable by itself.
    stage_edges = {i: set() for i in range(len(stage_records))}
    for seat in seats:
        sid = seat.get("id", "?")
        targets = seat.get("handoff_to")
        if targets is None:
            target_list = []
        elif isinstance(targets, str):
            target_list = [targets]
        elif isinstance(targets, list) and targets:
            target_list = targets
            if len(_duplicates(targets)):
                bad("seat %r repeats a handoff target" % sid)
        else:
            bad("seat %r 'handoff_to' must be null, a seat id, or a non-empty list" % sid)
            target_list = []

        source_places = placements.get(sid, [])
        if len(source_places) != 1 and seat.get("kind") == "memory-steward":
            # The persistent steward has no point-in-time handoff; proposals are
            # merged at every stage by the adapter.
            if target_list:
                bad("persistent memory steward %r cannot declare handoff targets" % sid)
            continue
        source = source_places[0] if len(source_places) == 1 else None
        for target in target_list:
            if target not in idset:
                bad("seat %r hands off to unknown seat %r" % (sid, target))
                continue
            target_places = placements.get(target, [])
            if len(target_places) != 1:
                bad("seat %r hands off to %r without one unambiguous stage" %
                    (sid, target))
                continue
            target_stage = target_places[0]
            if source is None:
                continue
            if target_stage == source:
                bad("seat %r hands off to %r in the SAME stage; parallel seats "
                    "must hand off to a later stage" % (sid, target))
            elif target_stage < source:
                bad("seat %r hands off BACKWARD to %r; loops must use the "
                    "explicit bounded 'loop' block" % (sid, target))
            else:
                stage_edges[source].add(target_stage)

    # Gate routes, rather than a gatekeeper's unconditional handoff, establish
    # conditional reachability. Unknown routes are reported in the gate pass.
    if strict and isinstance(data.get("gates"), list):
        for gate in data.get("gates", []):
            if not isinstance(gate, dict):
                continue
            source = stage_index.get(gate.get("stage"))
            transitions = gate.get("transitions")
            routes = transitions.get("routes", []) if isinstance(transitions, dict) else []
            if source is None or not isinstance(routes, list):
                continue
            for route in routes:
                if not isinstance(route, dict):
                    continue
                target = stage_index.get(route.get("next_stage"))
                if target is not None and target > source:
                    stage_edges[source].add(target)

    if stage_records:
        reachable = {0}
        pending = [0]
        while pending:
            current = pending.pop()
            for target in stage_edges.get(current, set()):
                if target not in reachable:
                    reachable.add(target)
                    pending.append(target)
        for index, stage in enumerate(stage_records):
            if index not in reachable:
                bad("disconnected stage %r is not reachable from the first stage "
                    "through handoffs" % stage.get("id"))

    # Legacy one-writer check remains available for old in-memory fixtures.
    if not strict:
        for index, stage in enumerate(stage_records):
            writers = {}
            for sid in stage.get("seats", []):
                seat = seat_by_id.get(sid, {})
                for artifact in seat.get("writes", []) or []:
                    writers.setdefault(artifact, []).append(sid)
            for artifact, owners in sorted(writers.items()):
                if len(owners) > 1:
                    bad("stage %d: artifact %r written by %s; one writer per artifact" %
                        (index + 1, artifact, " and ".join(owners)))

    # Strict memory/workspace ownership.
    steward_id = None
    lock_owner = {}
    workspace_by_id = {}
    if strict:
        steward_config = data.get("memory_steward")
        if not isinstance(steward_config, dict):
            bad("'memory_steward' must be an object")
            steward_config = {}
        steward_id = steward_config.get("seat_id")
        steward_seats = [seat for seat in seats
                         if seat.get("kind") == "memory-steward"]
        if len(steward_seats) != 1:
            bad("exactly one memory-steward seat is required (found %d)" %
                len(steward_seats))
        elif steward_seats[0].get("id") != steward_id:
            bad("memory_steward.seat_id must reference the one memory-steward seat")
        if steward_id not in idset:
            bad("memory_steward.seat_id references unknown seat %r" % steward_id)
        else:
            steward = seat_by_id[steward_id]
            if steward.get("persistent") is not True:
                bad("memory-steward seat must be persistent")
            if steward.get("memory_access") != "direct":
                bad("memory-steward seat must have direct memory access")
        for field in ("task_id_pattern", "proposal_merge_policy", "conflict_policy"):
            if not _is_nonempty_string(steward_config.get(field)):
                bad("memory_steward.%s must be a non-empty string" % field)
        try:
            re.compile(steward_config.get("task_id_pattern", ""))
        except re.error:
            bad("memory_steward.task_id_pattern must be a valid regular expression")

        workspaces = data.get("workspaces")
        if not isinstance(workspaces, list) or not workspaces:
            bad("'workspaces' must be a non-empty list")
            workspaces = []
        workspace_ids = []
        worktree_paths = []
        for index, workspace in enumerate(workspaces):
            if not isinstance(workspace, dict):
                bad("workspace %d must be an object" % (index + 1))
                continue
            wid = workspace.get("id")
            workspace_ids.append(wid)
            if not (_is_nonempty_string(wid) and ID_RE.match(wid)):
                bad("workspace %d has invalid id" % (index + 1))
                continue
            workspace_by_id[wid] = workspace
            # Keep this exactly aligned with run_room.materialize_workspaces.
            # Seat memory_access may be read-only, but a workspace is either
            # runner-managed shared memory or a detached Git worktree.
            if workspace.get("type") not in {"shared-memory", "worktree"}:
                bad("workspace %r has invalid type" % wid)
            if not _is_artifact(workspace.get("path")):
                bad("workspace %r has non-portable path %r" %
                    (wid, workspace.get("path")))
            if workspace.get("owner") not in idset:
                bad("workspace %r has unknown owner %r" %
                    (wid, workspace.get("owner")))
            if workspace.get("type") == "worktree":
                worktree_paths.append(workspace.get("path"))
            if workspace.get("type") == "shared-memory" and workspace.get("owner") != steward_id:
                bad("shared-memory workspace %r must be owned by the memory steward" % wid)
        for duplicate in sorted(_duplicates(workspace_ids)):
            bad("duplicate workspace id %r" % duplicate)
        for duplicate in sorted(_duplicates(worktree_paths)):
            bad("worktree path %r has unsafe simultaneous owners" % duplicate)

        for seat in seats:
            sid = seat.get("id")
            wid = seat.get("workspace")
            if wid not in workspace_by_id:
                bad("seat %r references unknown workspace %r" % (sid, wid))
                continue
            workspace = workspace_by_id[wid]
            if sid == steward_id:
                if workspace.get("type") != "shared-memory":
                    bad("memory steward must own a shared-memory workspace")
            elif workspace.get("type") == "shared-memory":
                bad("seat %r cannot own the shared-memory workspace" % sid)
            elif workspace.get("owner") != sid:
                bad("seat %r workspace %r is owned by %r" %
                    (sid, wid, workspace.get("owner")))

        locks = data.get("artifact_locks")
        if not isinstance(locks, list) or not locks:
            bad("'artifact_locks' must be a non-empty list")
            locks = []
        lock_artifacts = []
        for index, lock in enumerate(locks):
            if not isinstance(lock, dict):
                bad("artifact lock %d must be an object" % (index + 1))
                continue
            artifact, owner = lock.get("artifact"), lock.get("owner")
            if not _is_artifact(artifact):
                bad("artifact lock %d has non-portable artifact %r" %
                    (index + 1, artifact))
                continue
            lock_artifacts.append(artifact)
            if owner not in idset:
                bad("artifact lock %r has unknown owner %r" % (artifact, owner))
            lock_owner[artifact] = owner
            if artifact.startswith(SHARED_PREFIX) and owner != steward_id:
                bad("shared-memory artifact %r must be locked by the memory steward" % artifact)
        for duplicate in sorted(_duplicates(lock_artifacts)):
            bad("duplicate artifact lock for %r" % duplicate)

        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            bad("'tasks' must be a list")
            tasks = []
        task_ids = []
        for index, task in enumerate(tasks):
            if not isinstance(task, dict):
                bad("task %d must be an object" % (index + 1))
                continue
            task_id = task.get("id")
            task_ids.append(task_id)
            if not (_is_nonempty_string(task_id) and TASK_ID_RE.match(task_id)):
                bad("task %d has invalid task ID %r" % (index + 1, task_id))
            if task.get("owner") not in idset:
                bad("task %r has unknown owner %r" % (task_id, task.get("owner")))
            if task.get("allocated_by") != steward_id:
                bad("task %r was not allocated by the memory steward" % task_id)
        for duplicate in sorted(_duplicates(task_ids)):
            bad("duplicate task ID %r" % duplicate)
        declared_task_ids = set(task_id for task_id in task_ids
                                if isinstance(task_id, str))
        claimed = {}
        for seat in seats:
            sid = seat.get("id")
            for task_id in seat.get("task_ids", []) if isinstance(seat.get("task_ids"), list) else []:
                if task_id not in declared_task_ids:
                    bad("seat %r claims unallocated task ID %r" % (sid, task_id))
                if task_id in claimed and claimed[task_id] != sid:
                    bad("duplicate task ID %r claimed by seats %r and %r" %
                        (task_id, claimed[task_id], sid))
                claimed[task_id] = sid

        # Infer effects from commands and the handoff checker.  Merely omitting a
        # .solo path from `writes` cannot hide a command's documented side effect.
        actual_by_stage = {i: {} for i in range(len(stage_records))}
        for seat in seats:
            sid = seat.get("id")
            reads = set(seat.get("reads", [])) if isinstance(seat.get("reads"), list) else set()
            writes = set(seat.get("writes", [])) if isinstance(seat.get("writes"), list) else set()
            proposals = set(seat.get("proposals", [])) if isinstance(seat.get("proposals"), list) else set()
            access = seat.get("memory_access")
            effects = set()
            for command in _command_refs(seat):
                effects.update(implicit_writes(command))
            expected_declaration = writes if access == "direct" else proposals
            for artifact in sorted(effects - expected_declaration):
                bad("seat %r has undeclared implicit write %r from its command/skill "
                    "contract; declare it as %s" %
                    (sid, artifact, "writes" if access == "direct" else "a proposal"))
            if access == "read-only" and (writes or proposals or effects):
                bad("read-only seat %r cannot write or propose artifacts" % sid)
            if access == "propose-only":
                for artifact in sorted(writes):
                    if artifact.startswith(SHARED_PREFIX):
                        bad("propose-only seat %r declares direct shared-memory write %r" %
                            (sid, artifact))
            if sid != steward_id:
                for artifact in sorted(writes | (effects if access == "direct" else set())):
                    if artifact.startswith(SHARED_PREFIX):
                        bad("seat %r directly writes shared memory %r; only the one "
                            "memory steward may write .solo/" % (sid, artifact))
            for artifact in sorted(writes | proposals | effects):
                if artifact not in lock_owner:
                    bad("artifact %r used by seat %r has no artifact lock" %
                        (artifact, sid))
                elif artifact.startswith(SHARED_PREFIX) and lock_owner[artifact] != steward_id:
                    bad("shared artifact %r is not locked by the memory steward" % artifact)
            for artifact in sorted(writes):
                expected_owner = steward_id if artifact.startswith(SHARED_PREFIX) else sid
                if lock_owner.get(artifact) not in {None, expected_owner}:
                    bad("seat %r writes %r but its artifact lock belongs to %r" %
                        (sid, artifact, lock_owner.get(artifact)))

            actual = set(writes)
            if access == "direct":
                actual.update(effects)
            for stage_no in placements.get(sid, []):
                for artifact in actual:
                    actual_by_stage[stage_no].setdefault(artifact, []).append(sid)

        for stage_no, artifact_map in actual_by_stage.items():
            for artifact, owners in sorted(artifact_map.items()):
                unique_owners = sorted(set(owners))
                if len(unique_owners) > 1:
                    bad("stage %r has unsafe simultaneous writers %s for %r; one "
                        "writer per artifact is required" %
                        (stage_records[stage_no].get("id"),
                         " and ".join(unique_owners), artifact))

        if data.get("prepared") is True and is_windows_safe_run_id(data.get("run_id")):
            run_id = data["run_id"]
            artifact_prefix = "artifacts/runs/%s/" % run_id
            worktree_prefix = "worktrees/runs/%s/" % run_id
            for workspace in workspaces:
                if not isinstance(workspace, dict):
                    continue
                path = workspace.get("path")
                if (workspace.get("type") == "worktree" and
                        (not isinstance(path, str) or
                         not path.startswith(worktree_prefix))):
                    bad("prepared worktree %r is outside the exact run namespace" % path)
            artifacts_to_check = []
            artifacts_to_check.extend(lock_artifacts)
            for seat in seats:
                for field in ("reads", "writes"):
                    values = seat.get(field)
                    if isinstance(values, list):
                        artifacts_to_check.extend(values)
            for gate in data.get("gates", []):
                if not isinstance(gate, dict):
                    continue
                for prereq in gate.get("prerequisites", []):
                    if isinstance(prereq, dict):
                        artifacts_to_check.append(prereq.get("artifact"))
                evidence = gate.get("evidence")
                if isinstance(evidence, dict):
                    artifacts_to_check.append(evidence.get("artifact"))
            for artifact in artifacts_to_check:
                if (isinstance(artifact, str) and artifact.startswith("artifacts/") and
                        not artifact.startswith(artifact_prefix)):
                    bad("prepared artifact %r is outside the exact run namespace" %
                        artifact)

    if not (_is_nonempty_string(data.get("exit_criteria"))):
        bad("missing non-empty 'exit_criteria'")
    gate_ref = data.get("exit_gate", "__MISSING__")
    if gate_ref == "__MISSING__":
        bad("missing 'exit_gate' key (use null plus 'exit_gate_note' for a "
            "deliberately gateless room)")
    elif gate_ref is None:
        if not _is_nonempty_string(data.get("exit_gate_note")):
            bad("'exit_gate' is null with no 'exit_gate_note' documenting why")
    elif not (isinstance(gate_ref, str) and CMD_RE.match(gate_ref)):
        bad("'exit_gate' %r is not a Codex $skill reference" % gate_ref)

    refs = []
    for seat in seats:
        refs.extend((seat.get("id", "?"), command)
                    for command in _command_refs(seat))
    if isinstance(gate_ref, str) and gate_ref != "__MISSING__":
        refs.append(("exit_gate", gate_ref))
    for owner, command in refs:
        if not (isinstance(command, str) and CMD_RE.match(command)):
            bad("%s: %r is not a Codex $skill reference" % (owner, command))
        elif known is not None and command not in known:
            bad("%s: command %s does not exist in this suite" % (owner, command))

    if strict:
        gates = data.get("gates")
        if not isinstance(gates, list) or not gates:
            bad("'gates' must be a non-empty list with gate evidence declarations")
            gates = []
        gate_ids = []
        gate_commands = []
        gate_by_id = {}
        production_stage_ids = {
            candidate.get("stage") for candidate in gates
            if isinstance(candidate, dict) and
            candidate.get("command") == "$gate-production-ready"
        }
        for index, gate in enumerate(gates):
            if not isinstance(gate, dict):
                bad("gate %d must be an object" % (index + 1))
                continue
            gate_id = gate.get("id")
            command = gate.get("command")
            gate_ids.append(gate_id)
            gate_commands.append(command)
            if _is_nonempty_string(gate_id):
                gate_by_id[gate_id] = gate
            if not (_is_nonempty_string(gate_id) and ID_RE.match(gate_id)):
                bad("gate %d has invalid id" % (index + 1))
            if not (isinstance(command, str) and CMD_RE.match(command)):
                bad("gate %r has invalid command %r" % (gate_id, command))
            stage_id = gate.get("stage")
            if stage_id not in stage_index:
                bad("gate %r references unknown stage %r" % (gate_id, stage_id))
            seat_id = gate.get("seat")
            gate_seat = seat_by_id.get(seat_id)
            if gate_seat is None:
                bad("gate %r references unknown seat %r" % (gate_id, seat_id))
            else:
                if gate_seat.get("kind") != "gatekeeper":
                    bad("gate %r seat %r is not a gatekeeper" % (gate_id, seat_id))
                if command not in gate_seat.get("commands", []):
                    bad("gatekeeper %r does not execute gate command %r" %
                        (seat_id, command))
                if stage_id in stage_index and seat_id not in stage_records[stage_index[stage_id]].get("seats", []):
                    bad("gatekeeper %r is not placed in gate stage %r" %
                        (seat_id, stage_id))
                if gate_seat.get("handoff_to") is not None:
                    bad("gatekeeper %r must not declare an unconditional handoff; "
                        "use gate.transitions" % seat_id)

            prerequisites = gate.get("prerequisites")
            if not isinstance(prerequisites, list) or not prerequisites:
                bad("gate %r must declare non-empty prerequisites" % gate_id)
                prerequisites = []
            categories = []
            prerequisite_artifacts = []
            for prereq in prerequisites:
                if not isinstance(prereq, dict):
                    bad("gate %r has a non-object prerequisite" % gate_id)
                    continue
                category, artifact = prereq.get("category"), prereq.get("artifact")
                if not _is_nonempty_string(category):
                    bad("gate %r prerequisite category must be a string" % gate_id)
                else:
                    categories.append(category)
                if not _is_artifact(artifact):
                    bad("gate %r prerequisite has invalid artifact %r" %
                        (gate_id, artifact))
                else:
                    prerequisite_artifacts.append(artifact)
                producer_commands = prereq.get("producer_commands")
                if not (isinstance(producer_commands, list) and producer_commands and
                        len(producer_commands) == len(set(producer_commands)) and
                        all(isinstance(item, str) and CMD_RE.fullmatch(item)
                            for item in producer_commands)):
                    bad("gate %r prerequisite %r must declare unique producer_commands" %
                        (gate_id, artifact))
                producers = artifact_producers.get(artifact, [])
                if len(producers) != 1:
                    bad("gate %r prerequisite %r must have exactly one earlier producer" %
                        (gate_id, artifact))
                elif isinstance(producer_commands, list):
                    producer_id = producers[0][0]
                    actual_commands = sorted(set(
                        seat_by_id.get(producer_id, {}).get("commands", [])))
                    if sorted(producer_commands) != actual_commands:
                        bad("gate %r prerequisite %r producer_commands do not match "
                            "producer %r" % (gate_id, artifact, producer_id))
                if (command == "$gate-production-ready" and
                        category in PRODUCTION_CATEGORY_SKILLS and
                        isinstance(producer_commands, list) and
                        not (set(producer_commands) &
                             PRODUCTION_CATEGORY_SKILLS[category])):
                    bad("production gate %r category %r has no producer command "
                        "allowed by the production evidence contract" %
                        (gate_id, category))
            for duplicate in sorted(_duplicates(categories)):
                bad("gate %r repeats prerequisite category %r" % (gate_id, duplicate))
            for duplicate in sorted(_duplicates(prerequisite_artifacts)):
                bad("gate %r reuses prerequisite artifact %r" % (gate_id, duplicate))
            if gate_seat is not None:
                readable = set(gate_seat.get("reads", []))
                missing_reads = sorted(set(prerequisite_artifacts) - readable)
                for artifact in missing_reads:
                    bad("insufficient gatekeeper reads: seat %r cannot read required "
                        "artifact %r for gate %r" % (seat_id, artifact, gate_id))
            if command == "$gate-production-ready":
                readiness_categories = [
                    category for category in categories
                    if category != "Project profile"
                ]
                missing_categories = [category for category in PRODUCTION_CATEGORIES
                                      if category not in readiness_categories]
                extra_categories = [category for category in readiness_categories
                                    if category not in PRODUCTION_CATEGORIES]
                duplicate_categories = sorted(_duplicates(readiness_categories))
                profile_count = categories.count("Project profile")
                if (missing_categories or extra_categories or duplicate_categories or
                        profile_count != 1):
                    bad("production gate %r must cover exactly the 14 readiness "
                        "categories plus one project profile; missing=%r extra=%r "
                        "duplicate=%r profile_count=%r" %
                        (gate_id, missing_categories, extra_categories,
                         duplicate_categories, profile_count))

            evidence = gate.get("evidence")
            if not isinstance(evidence, dict):
                bad("gate %r is missing gate evidence configuration" % gate_id)
                evidence = {}
            evidence_artifact = evidence.get("artifact")
            if not _is_artifact(evidence_artifact):
                bad("gate %r is missing gate evidence artifact" % gate_id)
            elif gate_seat is not None and evidence_artifact not in gate_seat.get("writes", []):
                bad("gatekeeper %r must write gate evidence artifact %r" %
                    (seat_id, evidence_artifact))
            evidence_schema = evidence.get("schema")
            expected_schema = COMMAND_EVIDENCE_SCHEMA.get(command)
            if expected_schema is None:
                bad("gate %r command %r has no supported evidence contract" %
                    (gate_id, command))
            elif evidence_schema != expected_schema:
                bad("gate %r command %r requires evidence schema %s (got %r)" %
                    (gate_id, command, expected_schema, evidence_schema))
            contract = EVIDENCE_CONTRACTS.get(evidence_schema)
            required_fields = evidence.get("required_fields")
            if not isinstance(required_fields, list):
                bad("gate %r gate evidence required_fields must be a list" % gate_id)
            elif contract is not None:
                missing = sorted(contract["required_fields"] - set(required_fields))
                if missing:
                    bad("gate %r gate evidence is missing required field(s): %s" %
                        (gate_id, ", ".join(missing)))
            freshness = evidence.get("freshness")
            if not isinstance(freshness, dict):
                bad("gate %r is missing gate evidence freshness rules" % gate_id)
            else:
                if freshness.get("run_id") != "exact":
                    bad("gate %r must reject evidence from a different run_id" % gate_id)
                if freshness.get("commit") != "exact":
                    bad("gate %r must reject evidence from a different commit" % gate_id)
                if freshness.get("environment") != "exact":
                    bad("gate %r must reject evidence from a different environment" % gate_id)
                max_age = freshness.get("max_age_hours")
                if not _is_int(max_age) or max_age < 1:
                    bad("gate %r max_age_hours must be a positive integer" % gate_id)

            transitions = gate.get("transitions")
            if not isinstance(transitions, dict):
                bad("gate %r is missing fail-closed transitions" % gate_id)
                transitions = {}
            if transitions.get("default_action") != "stop":
                bad("gate %r transitions.default_action must be stop" % gate_id)
            expected_status_field = contract.get("status_field") if contract else None
            if transitions.get("status_field") != expected_status_field:
                bad("gate %r transitions.status_field must be %r" %
                    (gate_id, expected_status_field))
            routes = transitions.get("routes")
            if not isinstance(routes, list) or not routes:
                bad("gate %r transitions.routes must be a non-empty list" % gate_id)
                routes = []
            routed_statuses = []
            for route_index, route in enumerate(routes):
                if not isinstance(route, dict):
                    bad("gate %r transition %d must be an object" %
                        (gate_id, route_index + 1))
                    continue
                statuses = route.get("statuses")
                if not (isinstance(statuses, list) and statuses and
                        all(_is_nonempty_string(status) for status in statuses)):
                    bad("gate %r transition %d statuses must be a non-empty list" %
                        (gate_id, route_index + 1))
                    statuses = []
                routed_statuses.extend(statuses)
                has_next = "next_stage" in route
                has_action = "action" in route
                if has_next == has_action:
                    bad("gate %r transition %d must declare exactly one of "
                        "next_stage or action" % (gate_id, route_index + 1))
                    continue
                if has_next:
                    target = route.get("next_stage")
                    if target not in stage_index:
                        bad("gate %r transition references unknown stage %r" %
                            (gate_id, target))
                    elif stage_id in stage_index and stage_index[target] <= stage_index[stage_id]:
                        loop_config = data.get("loop")
                        trigger = (loop_config.get("trigger", {})
                                   if isinstance(loop_config, dict) else {})
                        loop_route = (
                            isinstance(loop_config, dict) and
                            loop_config.get("from_stage") == stage_id and
                            loop_config.get("to_stage") == target and
                            gate_id in trigger.get("gate_ids", []) and
                            set(statuses).issubset(set(trigger.get("statuses", [])))
                        )
                        if not loop_route:
                            bad("gate %r transition target %r must be a later stage "
                                "or its declared bounded-loop target" %
                                (gate_id, target))
                elif route.get("action") not in {"stop", "complete"}:
                    bad("gate %r transition has invalid action %r" %
                        (gate_id, route.get("action")))
                elif (route.get("action") == "complete" and stage_id in stage_index and
                      stage_index[stage_id] != len(stage_records) - 1):
                    bad("gate %r cannot complete from nonterminal stage %r" %
                        (gate_id, stage_id))
            if contract is not None:
                missing_statuses = sorted(contract["statuses"] - set(routed_statuses))
                unknown_statuses = sorted(set(routed_statuses) - contract["statuses"])
                duplicate_statuses = sorted(_duplicates(routed_statuses))
                if missing_statuses or unknown_statuses or duplicate_statuses:
                    bad("gate %r transitions must cover each contract status exactly "
                        "once; missing=%r unknown=%r duplicate=%r" %
                        (gate_id, missing_statuses, unknown_statuses,
                         duplicate_statuses))

            route_by_status = {
                status: route for route in routes if isinstance(route, dict)
                for status in route.get("statuses", [])
                if isinstance(status, str)
            }
            if evidence_schema == "solo-suite/phase-gate-evidence-v1":
                go_route = route_by_status.get("GO", {})
                no_go_route = route_by_status.get("NO-GO", {})
                if go_route.get("action") == "stop":
                    bad("gate %r GO route cannot stop" % gate_id)
                if no_go_route.get("action") == "complete":
                    bad("gate %r NO-GO route cannot complete" % gate_id)
                no_go_target = no_go_route.get("next_stage")
                if no_go_target in production_stage_ids:
                    bad("gate %r NO-GO route cannot enter production" % gate_id)
            elif evidence_schema == "solo-suite/score-evidence-v1":
                if route_by_status.get("SCORED", {}).get("action") != "complete":
                    bad("score gate %r must complete only for SCORED" % gate_id)
                if route_by_status.get("INSUFFICIENT EVIDENCE", {}).get("action") != "stop":
                    bad("score gate %r must stop for INSUFFICIENT EVIDENCE" % gate_id)
            elif evidence_schema == "solo-suite/gate-evidence-v1":
                if route_by_status.get("SAFE TO LAUNCH", {}).get("action") != "complete":
                    bad("production gate %r must complete only for SAFE TO LAUNCH" % gate_id)
                for status in ("BLOCKED", "SAFE WITH WARNINGS"):
                    if route_by_status.get(status, {}).get("action") != "stop":
                        bad("production gate %r must stop for %s" %
                            (gate_id, status))

            requirements = gate.get("required_gate_results", [])
            if not isinstance(requirements, list):
                bad("gate %r required_gate_results must be a list" % gate_id)
                requirements = []
            for requirement in requirements:
                if not isinstance(requirement, dict):
                    bad("gate %r has a non-object gate-result requirement" % gate_id)
                    continue
                required_id = requirement.get("gate_id")
                required_gate = gate_by_id.get(required_id)
                if required_gate is None:
                    bad("gate %r requires unknown or later-declared gate %r" %
                        (gate_id, required_id))
                    continue
                required_stage = required_gate.get("stage")
                if (stage_id in stage_index and required_stage in stage_index and
                        stage_index[required_stage] >= stage_index[stage_id]):
                    bad("gate %r requires result from non-earlier gate %r" %
                        (gate_id, required_id))
                required_contract = EVIDENCE_CONTRACTS.get(
                    required_gate.get("evidence", {}).get("schema"), {})
                if requirement.get("status") not in required_contract.get("statuses", set()):
                    bad("gate %r requires invalid status %r from gate %r" %
                        (gate_id, requirement.get("status"), required_id))
                requirement_freshness = requirement.get("freshness")
                expected_freshness = {
                    "run_id": "exact", "commit": "exact",
                    "environment": "exact", "latest": True,
                }
                if requirement_freshness != expected_freshness:
                    bad("gate %r requirement %r must demand exact run, commit, "
                        "environment, and latest evidence" % (gate_id, required_id))
                required_artifact = required_gate.get("evidence", {}).get("artifact")
                if (gate_seat is not None and _is_artifact(required_artifact) and
                        required_artifact not in gate_seat.get("reads", [])):
                    bad("gatekeeper %r cannot read required gate result %r" %
                        (seat_id, required_artifact))

            if command == "$gate-production-ready":
                before_deploy_ids = {
                    candidate.get("id") for candidate in gates
                    if isinstance(candidate, dict) and
                    candidate.get("command") == "$gate-before-deploy"
                }
                required_go = {
                    item.get("gate_id") for item in requirements
                    if isinstance(item, dict) and item.get("status") == "GO"
                }
                if not before_deploy_ids or not (before_deploy_ids & required_go):
                    bad("production gate %r requires an exact-current GO result "
                        "from a declared before-deploy gate" % gate_id)

        for duplicate in sorted(_duplicates(gate_ids)):
            bad("duplicate gate id %r" % duplicate)
        invoked_gates = {command for seat in seats
                         for command in seat.get("commands", [])
                         if command in ENFORCED_GATE_COMMANDS}
        for command in sorted(invoked_gates - set(gate_commands)):
            bad("gate command %r has no prerequisites or gate evidence declaration" %
                command)
        if isinstance(gate_ref, str) and gate_ref not in gate_commands:
            bad("exit gate %r has no gate declaration" % gate_ref)

    # The advanced website room is a reference delivery contract, not a loose
    # example. Keep its high-risk controls explicit so a future generator edit
    # cannot silently collapse detailed web evidence into a generic test result.
    if strict and data.get("name") == "full-team-website":
        prepared_prefix = "artifacts/runs/%s/" % data.get("run_id")

        def logical_artifact(artifact):
            if (data.get("prepared") is True and isinstance(artifact, str) and
                    artifact.startswith(prepared_prefix)):
                return "artifacts/" + artifact[len(prepared_prefix):]
            return artifact

        required_stage_order = (
            "discovery", "architecture", "database_architecture", "design", "before_code",
            "implementation", "post_implementation_review", "qa",
            "hardening", "before_merge", "release_and_docs",
            "release_management", "before_deploy", "repair_retest", "production",
        )
        missing_stages = [stage for stage in required_stage_order
                          if stage not in stage_index]
        if missing_stages:
            bad("full-team website room is missing required stage(s): %s" %
                ", ".join(missing_stages))
        elif [stage_index[stage] for stage in required_stage_order] != sorted(
                stage_index[stage] for stage in required_stage_order):
            bad("full-team website stages are not in the required delivery order")

        invoked = {command for seat in seats
                   for command in seat.get("commands", [])
                   if isinstance(command, str)}
        missing_commands = sorted(FULL_TEAM_REQUIRED_COMMANDS - invoked)
        if missing_commands:
            bad("full-team website room is missing mandatory command(s): %s" %
                ", ".join(missing_commands))

        declared_gates = {
            gate.get("command"): gate
            for gate in data.get("gates", [])
            if isinstance(gate, dict) and isinstance(gate.get("command"), str)
        }
        required_by_gate = {
            "$gate-before-merge": FULL_TEAM_BEFORE_MERGE_ARTIFACTS,
            "$gate-before-deploy": FULL_TEAM_BEFORE_DEPLOY_ARTIFACTS,
        }
        for command, required_artifacts in required_by_gate.items():
            gate_spec = declared_gates.get(command)
            if gate_spec is None:
                bad("full-team website room is missing required gate declaration %s" %
                    command)
                continue
            prerequisites = gate_spec.get("prerequisites", [])
            declared_artifacts = {
                logical_artifact(item.get("artifact")) for item in prerequisites
                if isinstance(item, dict) and isinstance(item.get("artifact"), str)
            }
            missing_artifacts = sorted(required_artifacts - declared_artifacts)
            if missing_artifacts:
                bad("full-team website %s gate is missing mandatory prerequisite(s): %s" %
                    (command, ", ".join(missing_artifacts)))

        written_artifacts = {
            logical_artifact(artifact) for seat in seats
            for artifact in seat.get("writes", [])
            if isinstance(artifact, str)
        }
        missing_outputs = sorted(
            FULL_TEAM_BEFORE_DEPLOY_ARTIFACTS - written_artifacts)
        if missing_outputs:
            bad("full-team website room has no declared producer for mandatory "
                "evidence artifact(s): %s" % ", ".join(missing_outputs))

        full_team_loop = data.get("loop")
        if not isinstance(full_team_loop, dict):
            bad("full-team website room requires a bounded repair/retest loop")
        else:
            if (full_team_loop.get("from_stage") != "repair_retest" or
                    full_team_loop.get("to_stage") != "implementation"):
                bad("full-team website repair/retest loop must route from "
                    "repair_retest back to implementation")
            iterations = full_team_loop.get("max_iterations")
            if not _is_int(iterations) or not 1 <= iterations <= 3:
                bad("full-team website repair/retest loop must be bounded to 1-3 iterations")
            exhaustion = full_team_loop.get("on_exhaustion", "")
            if not (isinstance(exhaustion, str) and
                    "BLOCKED" in exhaustion and "do not deploy" in exhaustion):
                bad("full-team website repair/retest exhaustion must set BLOCKED "
                    "and prohibit deployment")

    loop = data.get("loop")
    if loop is not None:
        if not isinstance(loop, dict):
            bad("'loop' must be an object")
        elif strict:
            from_stage, to_stage = loop.get("from_stage"), loop.get("to_stage")
            if from_stage not in stage_index:
                bad("loop.from_stage references unknown stage %r" % from_stage)
            if to_stage not in stage_index:
                bad("invalid loop target: loop.to_stage references unknown stage %r" %
                    to_stage)
            if from_stage in stage_index and to_stage in stage_index:
                if stage_index[to_stage] > stage_index[from_stage]:
                    bad("invalid loop target %r must not be after from_stage %r" %
                        (to_stage, from_stage))
            bound = loop.get("max_iterations")
            if not _is_int(bound) or not 1 <= bound <= 10:
                bad("loop.max_iterations must bound the loop between 1 and 10")
            if not _is_nonempty_string(loop.get("until")):
                bad("loop.until must state the loop exit condition")
            if not _is_nonempty_string(loop.get("on_exhaustion")):
                bad("loop.on_exhaustion must state the bounded-loop escape action")
            if loop.get("on_exhaustion_action") != "stop":
                bad("loop.on_exhaustion_action must be stop")
            signals = {}
            for signal_name in ("trigger", "exit"):
                signal = loop.get(signal_name)
                signals[signal_name] = signal if isinstance(signal, dict) else {}
                if not isinstance(signal, dict):
                    bad("loop.%s must be a machine-readable gate signal" % signal_name)
                    continue
                gate_ids = signal.get("gate_ids")
                statuses = signal.get("statuses")
                if not (isinstance(gate_ids, list) and gate_ids and
                        len(gate_ids) == len(set(gate_ids))):
                    bad("loop.%s.gate_ids must be a unique non-empty list" % signal_name)
                    gate_ids = []
                if not (isinstance(statuses, list) and statuses and
                        len(statuses) == len(set(statuses)) and
                        all(_is_nonempty_string(status) for status in statuses)):
                    bad("loop.%s.statuses must be a unique non-empty list" % signal_name)
                    statuses = []
                if signal.get("match") not in {"any", "all"}:
                    bad("loop.%s.match must be any or all" % signal_name)
                for loop_gate_id in gate_ids:
                    gate_spec = gate_by_id.get(loop_gate_id)
                    if gate_spec is None:
                        bad("loop.%s references unknown gate %r" %
                            (signal_name, loop_gate_id))
                        continue
                    gate_contract = EVIDENCE_CONTRACTS.get(
                        gate_spec.get("evidence", {}).get("schema"), {})
                    unknown = sorted(set(statuses) - gate_contract.get("statuses", set()))
                    if unknown:
                        bad("loop.%s uses invalid status(es) %r for gate %r" %
                            (signal_name, unknown, loop_gate_id))

            trigger = signals.get("trigger", {})
            for loop_gate_id in trigger.get("gate_ids", []):
                gate_spec = gate_by_id.get(loop_gate_id, {})
                routes = gate_spec.get("transitions", {}).get("routes", [])
                route_by_status = {
                    status: route for route in routes if isinstance(route, dict)
                    for status in route.get("statuses", [])
                }
                expected_target = (
                    loop.get("to_stage")
                    if gate_spec.get("stage") == loop.get("from_stage")
                    else loop.get("from_stage")
                )
                for status in trigger.get("statuses", []):
                    if route_by_status.get(status, {}).get("next_stage") != expected_target:
                        bad("loop trigger %r/%s must route to %r" %
                            (loop_gate_id, status, expected_target))

            exit_signal = signals.get("exit", {})
            for loop_gate_id in exit_signal.get("gate_ids", []):
                gate_spec = gate_by_id.get(loop_gate_id, {})
                routes = gate_spec.get("transitions", {}).get("routes", [])
                route_by_status = {
                    status: route for route in routes if isinstance(route, dict)
                    for status in route.get("statuses", [])
                }
                for status in exit_signal.get("statuses", []):
                    route = route_by_status.get(status, {})
                    if (route.get("next_stage") in {
                            loop.get("from_stage"), loop.get("to_stage")
                        } or not route):
                        bad("loop exit %r/%s must leave the bounded loop" %
                            (loop_gate_id, status))
        else:
            repeated = loop.get("repeat_stages")
            if not (isinstance(repeated, list) and repeated and
                    all(isinstance(group, list) and group for group in repeated)):
                bad("'loop.repeat_stages' must be a non-empty list of seat-id lists")
            else:
                for group in repeated:
                    for sid in group:
                        if sid not in idset:
                            bad("loop repeats unknown seat %r" % sid)
            if not _is_nonempty_string(loop.get("until")):
                bad("'loop.until' must state the loop exit condition")

    return problems


def validate_files(paths, suite_root=None):
    """Decode and validate room files, including run-id uniqueness."""
    known = known_commands(suite_root)
    problems = []
    run_ids = {}
    schema_validator = None
    if Draft202012Validator is not None:
        schema_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "schema",
            "agentroom-v1.schema.json",
        )
        try:
            with open(schema_path, encoding="utf-8") as handle:
                schema = json.load(handle)
            Draft202012Validator.check_schema(schema)
            schema_validator = Draft202012Validator(
                schema, format_checker=FormatChecker()
            )
        except Exception as error:  # jsonschema raises its own SchemaError type
            problems.append("agentroom-v1.schema.json: invalid schema (%s)" % error)
    for path in paths:
        label = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError, TypeError) as error:
            problems.append("%s: invalid JSON (%s)" % (label, error))
            continue
        if schema_validator is not None:
            schema_errors = sorted(
                schema_validator.iter_errors(data),
                key=lambda error: [str(part) for part in error.absolute_path],
            )
            for error in schema_errors:
                location = ".".join(str(part) for part in error.absolute_path)
                prefix = (location + ": ") if location else ""
                problems.append("%s: schema %s%s" % (label, prefix, error.message))
        problems.extend(validate_room(data, label, known))
        run_id = data.get("run_id") if isinstance(data, dict) else None
        if isinstance(run_id, str):
            if run_id in run_ids:
                problems.append(
                    "%s: duplicate run_id %r also used by %s" %
                    (label, run_id, run_ids[run_id]))
            else:
                run_ids[run_id] = label
    return problems


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "rooms", nargs="*",
        help="room JSON files (default: bundled agentsrooms/*.json)")
    parser.add_argument(
        "--suite", default=None,
        help="suite root for command-existence checks (default: auto-detect)")
    args = parser.parse_args(argv)
    rooms = args.rooms or sorted(glob.glob(
        os.path.join(here, "..", "agentsrooms", "*.json")))
    if not rooms:
        print("no room templates found")
        return 1
    suite = args.suite or find_suite(here)
    if not suite:
        print("note: suite root not found; command existence not checked")
    if Draft202012Validator is None:
        print("note: jsonschema is unavailable; semantic validation ran without the portable schema engine")
    problems = validate_files(rooms, suite_root=suite)
    print("== agentroom validation ==")
    for path in rooms:
        name = os.path.basename(path)
        mine = [problem for problem in problems
                if problem.startswith(name + ":")]
        if not mine:
            print("PASS  %s" % name)
    for problem in problems:
        print("FAIL  %s" % problem)
    print("== %d template(s), %d problem(s) ==" %
          (len(rooms), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
