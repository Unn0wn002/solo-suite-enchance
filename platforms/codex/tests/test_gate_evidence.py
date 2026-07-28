"""Production-gate schema, scoring, digest, and freshness regression tests."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/gate/skills/production-readiness-reviewer"
VALIDATOR_PATH = SKILL / "scripts/validate_gate_evidence.py"
SCHEMA_PATH = SKILL / "references/gate-evidence-v1.schema.json"
PROFILE_SCHEMA_PATH = SKILL / "references/project-profile-v1.schema.json"
ROOM_VALIDATOR_PATH = (
    ROOT / "plugins/ai/skills/agent-room-templates/scripts/validate_rooms.py"
)
COMMIT = "a" * 40
ENVIRONMENT = "staging"
RUN_ID = "gate-test-001"
GATE_ID = "production"
ROOM_DIGEST = "sha256:" + "c" * 64
PROJECT = "local/solo-suite-fixture"
CANONICAL_COMMANDS = {
    "Product": "$spec-acceptance",
    "Architecture": "$project-architecture",
    "Design": "$design-ui-review",
    "Frontend": "$browser-smoke-test",
    "Backend": "$api-audit",
    "Database": "$database-audit",
    "Security": "$security-review",
    "Testing": "$test-unit",
    "Performance": "$site-doctor-perf",
    "SEO": "$site-doctor-seo",
    "Analytics": "$analytics-audit",
    "Deployment": "$release-preflight",
    "Monitoring": "$observability",
    "Documentation": "$docs-update",
}


def load_module():
    spec = importlib.util.spec_from_file_location("gate_evidence_v111", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load_module()


def load_room_validator():
    spec = importlib.util.spec_from_file_location(
        "room_validator_gate_contract_v111", ROOM_VALIDATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {ROOM_VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


room_validator = load_room_validator()


def build_evidence(
    root: Path, *, run_id: str = RUN_ID, gate_id: str = GATE_ID,
) -> dict:
    timestamp = "2030-01-01T00:00:00Z"
    expires = "2030-01-02T00:00:00Z"
    records = []
    for index, category in enumerate(gate.CATEGORIES):
        artifact = (
            Path("artifacts/runs") / run_id / "categories" /
            f"{index + 1:02d}-{category.lower()}.txt"
        )
        absolute = root / artifact
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_text(f"verified {category}\n", encoding="utf-8")
        digest = hashlib.sha256(absolute.read_bytes()).hexdigest()
        records.append({
            "project": PROJECT,
            "run_id": run_id,
            "gate_id": gate_id,
            "commit_sha": COMMIT,
            "environment": ENVIRONMENT,
            "timestamp": timestamp,
            "expires_at": expires,
            "category": category,
            "score": 10,
            "applicability": "applicable",
            "command_executed": CANONICAL_COMMANDS[category],
            "exit_code": 0,
            "evidence_type": "tool-report",
            "provenance": {
                "source_kind": "local-tool",
                "producer": CANONICAL_COMMANDS[category],
                "source_reference": artifact.as_posix(),
                "generated_at": timestamp,
            },
            "evidence_artifact": artifact.as_posix(),
            "artifact_digest": f"sha256:{digest}",
            "reviewer": "qa@example.test",
        })
    profile_artifact = (
        Path("artifacts/runs") / run_id / "profile" / "project-profile.json"
    )
    profile_path = root / profile_artifact
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps({
        "schema": "solo-suite/project-profile-v1",
        "run_id": run_id,
        "project": PROJECT,
        "commit_sha": COMMIT,
        "environment": ENVIRONMENT,
        "profile": "saas-application",
        "timestamp": timestamp,
        "categories": [
            {"category": category, "applicability": "applicable"}
            for category in gate.CATEGORIES
        ],
    }, indent=2) + "\n", encoding="utf-8")
    profile_digest = hashlib.sha256(profile_path.read_bytes()).hexdigest()

    phase_artifact = (
        Path("artifacts/runs") / run_id / "prerequisites" / "environment.txt"
    )
    phase_path = root / phase_artifact
    phase_path.parent.mkdir(parents=True, exist_ok=True)
    phase_path.write_text("environment ready\n", encoding="utf-8")
    phase_digest = hashlib.sha256(phase_path.read_bytes()).hexdigest()
    before_deploy_artifact = (
        Path("artifacts/runs") / run_id / "gates" / "before-deploy.json"
    )
    before_deploy_path = root / before_deploy_artifact
    before_deploy_path.parent.mkdir(parents=True, exist_ok=True)
    before_deploy_path.write_text(json.dumps({
        "schema": "solo-suite/phase-gate-evidence-v1",
        "room_digest": ROOM_DIGEST,
        "run_id": run_id,
        "gate_id": "before_deploy",
        "project": PROJECT,
        "commit_sha": COMMIT,
        "environment": ENVIRONMENT,
        "timestamp": timestamp,
        "expires_at": expires,
        "reviewer": "qa@example.test",
        "decision": "GO",
        "checks": [{
            "category": "Environment",
            "run_id": run_id,
            "gate_id": "before_deploy",
            "status": "PASS",
            "commands_executed": ["$release-preflight"],
            "exit_code": 0,
            "evidence_artifact": phase_artifact.as_posix(),
            "artifact_digest": f"sha256:{phase_digest}",
        }],
        "blockers": [],
    }, indent=2) + "\n", encoding="utf-8")
    return {
        "schema": "solo-suite/gate-evidence-v1",
        "room_digest": ROOM_DIGEST,
        "run_id": run_id,
        "gate_id": gate_id,
        "project_profile": "saas-application",
        "profile_artifact": profile_artifact.as_posix(),
        "profile_artifact_digest": f"sha256:{profile_digest}",
        "project": PROJECT,
        "commit_sha": COMMIT,
        "environment": ENVIRONMENT,
        "timestamp": timestamp,
        "expires_at": expires,
        "reviewer": "qa@example.test",
        "categories": records,
        "total_score": 140,
        "normalized_score": 100,
        "launch_status": "SAFE TO LAUNCH",
        "blockers": [],
        "warnings": [],
    }


def build_contract(
    *, run_id: str = RUN_ID, gate_id: str = GATE_ID,
) -> dict:
    category_artifacts = {
        category: (
            Path("artifacts/runs") / run_id / "categories" /
            f"{index + 1:02d}-{category.lower()}.txt"
        ).as_posix()
        for index, category in enumerate(gate.CATEGORIES)
    }
    profile_artifact = (
        Path("artifacts/runs") / run_id / "profile" / "project-profile.json"
    ).as_posix()
    phase_artifact = (
        Path("artifacts/runs") / run_id / "prerequisites" / "environment.txt"
    ).as_posix()
    return {
        "room_digest": ROOM_DIGEST,
        "max_age_hours": 24,
        "category_artifacts": category_artifacts,
        "category_producer_commands": {
            category: (CANONICAL_COMMANDS[category],)
            for category in gate.CATEGORIES
        },
        "profile_artifact": profile_artifact,
        "required_gate_results": [{
            "gate_id": "before_deploy",
            "status": "GO",
            "artifact": (
                Path("artifacts/runs") / run_id / "gates" / "before-deploy.json"
            ).as_posix(),
            "prerequisites": [{
                "category": "Environment",
                "artifact": phase_artifact,
                "producer_commands": ["$release-preflight"],
            }],
            "max_age_hours": 24,
        }],
    }


class GateEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.evidence = build_evidence(self.root)
        self.contract = build_contract()
        self.now = datetime(2030, 1, 1, 1, tzinfo=timezone.utc)

    def validate(self, data=None, *, commit=COMMIT, environment=ENVIRONMENT):
        return gate.validate(
            data if data is not None else self.evidence,
            self.root,
            commit,
            environment,
            now=self.now,
            run_id=RUN_ID,
            gate_id=GATE_ID,
            contract=self.contract,
        )

    def schema_errors(self, data=None):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        return list(
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).iter_errors(data if data is not None else self.evidence)
        )

    def test_complete_evidence_passes_schema_and_semantics(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        errors = self.schema_errors()
        self.assertEqual(errors, [])
        profile_schema = json.loads(PROFILE_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(profile_schema)
        profile = json.loads(
            (self.root / self.evidence["profile_artifact"]).read_text(encoding="utf-8")
        )
        self.assertEqual(list(Draft202012Validator(
            profile_schema, format_checker=FormatChecker()
        ).iter_errors(profile)), [])
        self.assertEqual(self.validate(), [])

    def test_prepared_full_team_room_loads_as_the_production_contract(self):
        template = (
            ROOT / "plugins/ai/skills/agent-room-templates/agentsrooms/"
            "full-team-website.json"
        )
        prepare = (
            ROOT / "plugins/ai/skills/agent-room-templates/scripts/prepare_run.py"
        )
        output = self.root / "room.json"
        result = subprocess.run(
            [
                sys.executable, str(prepare), str(template), str(output),
                "--run-id", RUN_ID, "--suite", str(ROOT),
                "--profile", "saas-application",
                "--project-root", str(self.root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        contract = gate.load_room_contract(output, RUN_ID, GATE_ID)
        self.assertEqual(list(contract["category_artifacts"]), gate.CATEGORIES)
        self.assertEqual(
            list(contract["category_producer_commands"]), gate.CATEGORIES
        )
        self.assertEqual(
            gate.producer_coverage_failures(
                contract["category_producer_commands"]
            ),
            [],
        )
        for profile in sorted(gate.PROJECT_PROFILES):
            for category in gate.CATEGORIES:
                if category in gate.PROFILE_NA_ALLOWED[profile]:
                    continue
                with self.subTest(profile=profile, category=category):
                    self.assertTrue(
                        set(contract["category_producer_commands"][category]) &
                        gate.CATEGORY_SKILLS[category]
                    )
        self.assertTrue(contract["profile_artifact"].startswith(
            f"artifacts/runs/{RUN_ID}/"))
        self.assertTrue(any(
            item["gate_id"] == "before_deploy" and item["status"] == "GO"
            for item in contract["required_gate_results"]
        ))

    def test_room_contract_rejects_an_unsatisfiable_category_producer(self):
        template = (
            ROOT / "plugins/ai/skills/agent-room-templates/agentsrooms/"
            "full-team-website.json"
        )
        prepare = (
            ROOT / "plugins/ai/skills/agent-room-templates/scripts/prepare_run.py"
        )
        output = self.root / "room.json"
        result = subprocess.run(
            [
                sys.executable, str(prepare), str(template), str(output),
                "--run-id", RUN_ID, "--suite", str(ROOT),
                "--profile", "saas-application",
                "--project-root", str(self.root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        room = json.loads(output.read_text(encoding="utf-8"))
        production = next(
            item for item in room["gates"] if item["id"] == GATE_ID
        )
        analytics = next(
            item for item in production["prerequisites"]
            if item["category"] == "Analytics"
        )
        analytics["producer_commands"] = ["$growth-conversion-audit"]
        output.write_text(json.dumps(room), encoding="utf-8")
        with self.assertRaisesRegex(
            ValueError, "Analytics has no declared producer command allowed"
        ):
            gate.load_room_contract(output, RUN_ID, GATE_ID)

    def test_allowlist_only_names_real_bundled_skills(self):
        bundled = {
            path.parent.name
            for path in ROOT.glob("plugins/*/skills/*/SKILL.md")
        }
        for category, commands in gate.CATEGORY_SKILLS.items():
            with self.subTest(category=category):
                self.assertTrue(commands)
                self.assertEqual(
                    {command.removeprefix("$") for command in commands} - bundled,
                    set(),
                )

    def test_schema_and_semantic_allowlists_match(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        rules = schema["$defs"]["categoryEvidence"]["allOf"]
        schema_commands = {}
        for rule in rules:
            category = (
                rule.get("if", {})
                .get("properties", {})
                .get("category", {})
                .get("const")
            )
            if category:
                schema_commands[category] = frozenset(
                    rule["then"]["properties"]["command_executed"]["enum"]
                )
        self.assertEqual(schema_commands, gate.CATEGORY_SKILLS)
        self.assertEqual(
            room_validator.PRODUCTION_CATEGORY_SKILLS,
            gate.CATEGORY_SKILLS,
        )

    def test_category_allowed_command_must_also_be_declared_by_room_producer(self):
        frontend = self.evidence["categories"][3]
        frontend["command_executed"] = "$test-e2e"
        frontend["provenance"]["producer"] = "$test-e2e"
        self.assertEqual(self.schema_errors(), [])
        failures = self.validate()
        self.assertFalse(any("not allowed for Frontend" in item for item in failures))
        self.assertTrue(any(
            "not declared by the room producer for Frontend" in item
            for item in failures
        ))

    def test_nonexistent_and_cross_category_skills_are_rejected(self):
        record = self.evidence["categories"][0]
        record["command_executed"] = "$definitely-not-bundled"
        self.assertTrue(self.schema_errors())
        self.assertTrue(
            any("not a bundled evidence skill" in item for item in self.validate())
        )

        record["command_executed"] = "$observability"
        self.assertTrue(self.schema_errors())
        self.assertTrue(
            any("not allowed for Product" in item for item in self.validate())
        )

    def test_different_commit_and_environment_are_rejected(self):
        failures = self.validate(commit="b" * 40, environment="production")
        self.assertTrue(any("different commit" in item for item in failures))
        self.assertTrue(any("different environment" in item for item in failures))

    def test_different_run_and_gate_are_rejected(self):
        failures = gate.validate(
            self.evidence, self.root, COMMIT, ENVIRONMENT, now=self.now,
            run_id="other-run-001", gate_id="other_gate",
            contract=self.contract,
        )
        self.assertTrue(any("different run_id" in item for item in failures))
        self.assertTrue(any("different gate_id" in item for item in failures))

    def test_expired_evidence_is_rejected(self):
        self.evidence["expires_at"] = "2029-12-31T23:00:00Z"
        self.evidence["categories"][0]["expires_at"] = "2029-12-31T23:00:00Z"
        failures = self.validate()
        self.assertTrue(any("top-level evidence is expired" in item for item in failures))
        self.assertTrue(any("categories[0] is expired" in item for item in failures))

    def test_changed_artifact_is_rejected(self):
        artifact = self.root / self.evidence["categories"][0]["evidence_artifact"]
        artifact.write_text("changed after review\n", encoding="utf-8")
        self.assertTrue(
            any("digest does not match" in item for item in self.validate())
        )

    def test_applicable_denominator_formula_is_enforced(self):
        self.evidence["categories"][0]["score"] = 7
        failures = self.validate()
        self.assertIn(
            "total_score does not equal the applicable category scores", failures
        )
        self.assertIn(
            "normalized_score does not equal "
            "round(total/(10*applicable_category_count)*100)", failures
        )

    def test_na_requires_reason_and_zero_score(self):
        record = self.evidence["categories"][0]
        record["applicability"] = "not-applicable"
        failures = self.validate()
        self.assertTrue(any("na_reason is required" in item for item in failures))
        self.assertTrue(any("N/A must score 0" in item for item in failures))

    def test_verified_na_uses_an_applicability_record(self):
        record = self.evidence["categories"][9]
        reason = "The API-service profile has no public search-indexed surface."
        self.evidence["project_profile"] = "api-service"
        profile_path = self.root / self.evidence["profile_artifact"]
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["profile"] = "api-service"
        profile["categories"][9] = {
            "category": "SEO",
            "applicability": "not-applicable",
            "reason": reason,
        }
        profile_path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
        self.evidence["profile_artifact_digest"] = (
            "sha256:" + hashlib.sha256(profile_path.read_bytes()).hexdigest()
        )
        record["applicability"] = "not-applicable"
        record["score"] = 0
        record["na_reason"] = reason
        record["evidence_type"] = "applicability-record"
        record["provenance"]["source_kind"] = "repository-record"
        record["provenance"]["producer"] = "project-profile-v1"
        record["provenance"]["source_reference"] = self.evidence["profile_artifact"]
        self.evidence["total_score"] = 130
        self.evidence["normalized_score"] = 100
        self.assertEqual(self.schema_errors(), [])
        self.assertEqual(self.validate(), [])

    def test_agentroom_profile_cells_match_the_canonical_matrix(self):
        cases = (
            ("saas-application", "SEO", False),
            ("api-service", "Database", False),
            ("library-package", "Monitoring", False),
            ("library-package", "Performance", True),
        )
        for profile_name, category, allowed in cases:
            evidence = build_evidence(self.root)
            evidence["project_profile"] = profile_name
            profile_path = self.root / evidence["profile_artifact"]
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["profile"] = profile_name
            index = gate.CATEGORIES.index(category)
            reason = f"The {profile_name} fixture has no applicable {category} surface."
            profile["categories"][index] = {
                "category": category,
                "applicability": "not-applicable",
                "reason": reason,
            }
            profile_path.write_text(
                json.dumps(profile, indent=2) + "\n", encoding="utf-8"
            )
            evidence["profile_artifact_digest"] = (
                "sha256:" + hashlib.sha256(profile_path.read_bytes()).hexdigest()
            )
            record = evidence["categories"][index]
            record.update({
                "score": 0,
                "applicability": "not-applicable",
                "na_reason": reason,
                "evidence_type": "applicability-record",
            })
            record["provenance"].update({
                "source_kind": "repository-record",
                "producer": "project-profile-v1",
                "source_reference": evidence["profile_artifact"],
            })
            evidence["total_score"] = 130
            evidence["normalized_score"] = 100
            failures = gate.validate(
                evidence, self.root, COMMIT, ENVIRONMENT, now=self.now,
                run_id=RUN_ID, gate_id=GATE_ID, contract=self.contract,
            )
            with self.subTest(
                profile=profile_name, category=category, allowed=allowed
            ):
                if allowed:
                    self.assertEqual(failures, [])
                else:
                    self.assertTrue(any(
                        "cannot mark" in item or "does not permit N/A" in item
                        for item in failures
                    ), failures)

    def test_all_na_or_profile_forbidden_na_cannot_launch(self):
        for record in self.evidence["categories"]:
            record["applicability"] = "not-applicable"
            record["na_reason"] = "Claimed structurally inapplicable."
            record["evidence_type"] = "applicability-record"
            record["provenance"]["source_kind"] = "repository-record"
            record["provenance"]["source_reference"] = self.evidence["profile_artifact"]
        failures = self.validate()
        self.assertTrue(any("does not approve N/A" in item or "cannot mark" in item
                            for item in failures))

    def test_profile_and_nested_run_gate_binding_are_enforced(self):
        self.evidence["categories"][0]["run_id"] = "other-run-001"
        self.evidence["categories"][1]["gate_id"] = "score"
        profile_path = self.root / self.evidence["profile_artifact"]
        profile_path.write_text("{}\n", encoding="utf-8")
        failures = self.validate()
        for fragment in ("different run_id", "different gate_id", "profile_artifact_digest"):
            self.assertTrue(any(fragment in item for item in failures), fragment)

    def test_max_age_and_required_before_deploy_go_are_enforced(self):
        self.evidence["timestamp"] = "2029-12-30T00:00:00Z"
        phase_path = self.root / self.contract["required_gate_results"][0]["artifact"]
        phase = json.loads(phase_path.read_text(encoding="utf-8"))
        phase["decision"] = "NO-GO"
        phase["checks"][0]["status"] = "FAIL"
        phase["checks"][0]["exit_code"] = 1
        phase["blockers"] = ["Environment is blocked"]
        phase_path.write_text(json.dumps(phase, indent=2) + "\n", encoding="utf-8")
        failures = self.validate()
        self.assertTrue(any("max_age_hours" in item for item in failures))
        self.assertTrue(any("must be GO" in item for item in failures))

    def test_only_three_production_statuses_are_accepted(self):
        self.evidence["launch_status"] = "GO"
        self.assertIn("launch_status is invalid", self.validate())

    def test_failed_command_cannot_support_a_positive_score(self):
        self.evidence["categories"][0]["exit_code"] = 1
        self.assertTrue(
            any("failed evidence command" in item for item in self.validate())
        )

    def test_evidence_type_and_provenance_are_required(self):
        record = self.evidence["categories"][0]
        self.evidence["unexpected"] = True
        record["unexpected"] = True
        del record["evidence_type"]
        del record["provenance"]
        self.assertTrue(self.schema_errors())
        failures = self.validate()
        self.assertTrue(any("evidence_type is required" in item for item in failures))
        self.assertTrue(any("provenance is required" in item for item in failures))
        self.assertTrue(any("unknown top-level fields" in item for item in failures))
        self.assertTrue(any("unknown fields" in item for item in failures))

    def test_evidence_type_must_match_provenance_source(self):
        record = self.evidence["categories"][0]
        record["evidence_type"] = "narrative-assertion"
        record["provenance"]["source_kind"] = "local-tool"
        self.assertTrue(self.schema_errors())
        self.assertTrue(
            any("incompatible with evidence_type" in item for item in self.validate())
        )

    def test_provenance_cannot_postdate_the_review(self):
        self.evidence["categories"][0]["provenance"]["generated_at"] = (
            "2030-01-01T00:30:00Z"
        )
        self.assertTrue(
            any("must not be after the review timestamp" in item
                for item in self.validate())
        )

    def test_warnings_are_structured_and_actionable(self):
        self.evidence["launch_status"] = "SAFE WITH WARNINGS"
        self.evidence["warnings"] = ["low product evidence"]
        self.assertTrue(self.schema_errors())
        self.assertTrue(
            any("structured warning object" in item for item in self.validate())
        )

        self.evidence["warnings"] = [{
            "message": "The synthetic monitor covers only the primary region.",
            "category": "Monitoring",
            "owner": "platform-team",
            "remediation": "Add a second-region synthetic monitor before expansion.",
            "verification": {
                "method": "$site-doctor-monitoring",
                "success_criteria": "Both regional probes report healthy for 24 hours.",
            },
        }]
        self.assertEqual(self.schema_errors(), [])
        self.assertEqual(self.validate(), [])

    def test_safe_to_launch_must_match_scores_and_warnings(self):
        self.evidence["categories"][0]["score"] = 6
        self.evidence["total_score"] = 136
        self.evidence["normalized_score"] = round(136 / 140 * 100)
        self.evidence["warnings"] = [{
            "message": "Product evidence is below the launch target.",
            "category": "Product",
            "owner": "product-owner",
            "remediation": "Capture the missing acceptance evidence.",
            "verification": {
                "method": "$spec-acceptance",
                "success_criteria": "All launch acceptance criteria have linked evidence.",
            },
        }]
        failures = self.validate()
        self.assertTrue(any(
            "launch_status must be SAFE WITH WARNINGS under the shared"
            in item for item in failures
        ))


if __name__ == "__main__":
    unittest.main()
