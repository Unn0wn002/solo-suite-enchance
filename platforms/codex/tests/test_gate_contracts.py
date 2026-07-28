"""Fail-closed phase-gate and score-only evidence contract tests."""

from __future__ import annotations

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

from tests.test_gate_evidence import build_evidence


ROOT = Path(__file__).resolve().parents[1]
PHASE_SKILL = ROOT / "plugins/gate/skills/quality-gatekeeper"
PRODUCTION_SKILL = ROOT / "plugins/gate/skills/production-readiness-reviewer"
COMMIT = "a" * 40
ENVIRONMENT = "staging"
RUN_ID = "contract-run-001"
ROOM_DIGEST = "sha256:" + "c" * 64


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


phase = load_module(
    "phase_gate_contract",
    PHASE_SKILL / "scripts/validate_phase_gate_evidence.py",
)
scored = load_module(
    "score_gate_contract",
    PRODUCTION_SKILL / "scripts/validate_gate_evidence.py",
)


def schema_errors(path: Path, data: dict):
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return list(Draft202012Validator(
        schema, format_checker=FormatChecker()).iter_errors(data))


def build_phase(root: Path, *, decision: str = "GO") -> dict:
    relative = Path("artifacts/runs") / RUN_ID / "evidence/check.txt"
    artifact = root / relative
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("verified\n", encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    failed = decision == "NO-GO"
    return {
        "schema": "solo-suite/phase-gate-evidence-v1",
        "room_digest": ROOM_DIGEST,
        "run_id": RUN_ID,
        "gate_id": "before_deploy",
        "project": "local/solo-suite-fixture",
        "commit_sha": COMMIT,
        "environment": ENVIRONMENT,
        "timestamp": "2030-01-01T00:00:00Z",
        "expires_at": "2030-01-02T00:00:00Z",
        "reviewer": "qa@example.test",
        "decision": decision,
        "checks": [{
            "category": "Environment",
            "run_id": RUN_ID,
            "gate_id": "before_deploy",
            "status": "FAIL" if failed else "PASS",
            "commands_executed": ["$release-preflight"],
            "exit_code": 1 if failed else 0,
            "evidence_artifact": relative.as_posix(),
            "artifact_digest": f"sha256:{digest}",
        }],
        "blockers": ["Environment is not ready"] if failed else [],
    }


class PhaseGateContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = datetime(2030, 1, 1, 1, tzinfo=timezone.utc)

    def validate(self, evidence: dict):
        return phase.validate(
            evidence, self.root, RUN_ID, "before_deploy",
            COMMIT, ENVIRONMENT, now=self.now,
            expected_prerequisites=[{
                "category": "Environment",
                "artifact": f"artifacts/runs/{RUN_ID}/evidence/check.txt",
                "producer_commands": ["$release-preflight"],
            }],
            expected_room_digest=ROOM_DIGEST,
            max_age_hours=24,
        )

    def test_go_and_no_go_records_pass_their_dedicated_contract(self):
        schema = PHASE_SKILL / "references/phase-gate-evidence-v1.schema.json"
        for decision in ("GO", "NO-GO"):
            with self.subTest(decision=decision):
                evidence = build_phase(self.root, decision=decision)
                self.assertEqual(schema_errors(schema, evidence), [])
                self.assertEqual(self.validate(evidence), [])

    def test_go_fails_closed_on_failed_check_or_blocker(self):
        evidence = build_phase(self.root)
        evidence["unexpected"] = True
        evidence["reviewer"] = ""
        evidence["checks"][0]["status"] = "FAIL"
        evidence["blockers"] = ["failed"]
        failures = self.validate(evidence)
        self.assertTrue(any("GO requires" in item for item in failures))
        self.assertTrue(any("unknown top-level fields" in item for item in failures))
        self.assertTrue(any("reviewer must be" in item for item in failures))

    def test_no_go_requires_failed_check_and_blocker(self):
        evidence = build_phase(self.root, decision="NO-GO")
        evidence["checks"][0]["status"] = "PASS"
        evidence["checks"][0]["exit_code"] = 0
        evidence["blockers"] = []
        failures = self.validate(evidence)
        self.assertTrue(any("requires at least one blocker" in item for item in failures))
        self.assertTrue(any("failed check" in item for item in failures))

    def test_run_gate_commit_environment_and_digest_are_bound(self):
        evidence = build_phase(self.root)
        artifact = self.root / evidence["checks"][0]["evidence_artifact"]
        artifact.write_text("changed\n", encoding="utf-8")
        failures = phase.validate(
            evidence, self.root, "other-run-001", "before_merge",
            "b" * 40, "production", now=self.now,
            expected_prerequisites=[{
                "category": "Environment",
                "artifact": f"artifacts/runs/{RUN_ID}/evidence/check.txt",
                "producer_commands": ["$release-preflight"],
            }],
            expected_room_digest=ROOM_DIGEST,
            max_age_hours=24,
        )
        for fragment in (
            "different run_id", "different gate_id", "different commit",
            "different environment", "digest does not match",
        ):
            self.assertTrue(any(fragment in item for item in failures), fragment)

    def test_prerequisite_contract_rejects_shallow_or_substituted_evidence(self):
        evidence = build_phase(self.root)
        evidence["checks"][0]["category"] = "Plausible but undeclared"
        evidence["checks"][0]["commands_executed"] = ["$invented-skill"]
        evidence["checks"][0]["evidence_artifact"] = "evidence/other.txt"
        failures = self.validate(evidence)
        for fragment in (
            "match every declared prerequisite",
            "not the declared prerequisite",
            "undeclared producer",
        ):
            self.assertTrue(any(fragment in item for item in failures), fragment)

    def test_max_age_rejects_old_or_overlong_evidence(self):
        evidence = build_phase(self.root)
        evidence["timestamp"] = "2029-12-30T00:00:00Z"
        evidence["expires_at"] = "2030-01-02T00:00:00Z"
        failures = self.validate(evidence)
        self.assertTrue(any("exceeds the gate's max_age_hours" in item
                            for item in failures))

    def test_prepared_full_team_phase_contract_loads_exact_prerequisites(self):
        template = (
            ROOT / "plugins/ai/skills/agent-room-templates/agentsrooms/"
            "full-team-website.json"
        )
        prepare = (
            ROOT / "plugins/ai/skills/agent-room-templates/scripts/prepare_run.py"
        )
        room = self.root / "prepared-room.json"
        result = subprocess.run(
            [
                sys.executable, str(prepare), str(template), str(room),
                "--run-id", RUN_ID, "--profile", "saas-application",
                "--suite", str(ROOT), "--project-root", str(self.root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        prerequisites, digest, max_age = phase.load_room_contract(
            room, RUN_ID, "before_deploy"
        )
        self.assertGreater(len(prerequisites), 10)
        self.assertEqual(digest, "sha256:" + hashlib.sha256(room.read_bytes()).hexdigest())
        self.assertEqual(max_age, 12)
        with self.assertRaisesRegex(ValueError, "requested gate exactly once"):
            phase.load_room_contract(room, RUN_ID, "missing-gate")


class ScoreOnlyContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = datetime(2030, 1, 1, 1, tzinfo=timezone.utc)
        self.evidence = build_evidence(
            self.root, run_id=RUN_ID, gate_id="score",
        )
        self.evidence.update({
            "schema": "solo-suite/score-evidence-v1",
            "run_id": RUN_ID,
            "gate_id": "score",
            "assessment_status": "SCORED",
            "risks": [],
        })
        for field in (
            "room_digest", "project_profile", "profile_artifact",
            "profile_artifact_digest", "launch_status", "blockers", "warnings",
        ):
            self.evidence.pop(field)

    def validate(self):
        return scored.validate(
            self.evidence, self.root, COMMIT, ENVIRONMENT, now=self.now,
            run_id=RUN_ID, gate_id="score", mode="score",
        )

    def test_score_record_has_no_launch_verdict_and_passes(self):
        schema = PRODUCTION_SKILL / "references/score-evidence-v1.schema.json"
        self.assertEqual(schema_errors(schema, self.evidence), [])
        self.assertEqual(self.validate(), [])

    def test_score_schema_rejects_a_launch_verdict(self):
        self.evidence["launch_status"] = "SAFE TO LAUNCH"
        schema = PRODUCTION_SKILL / "references/score-evidence-v1.schema.json"
        self.assertTrue(schema_errors(schema, self.evidence))
        self.assertTrue(any("must not contain" in item for item in self.validate()))

    def test_insufficient_evidence_requires_a_risk(self):
        self.evidence["assessment_status"] = "INSUFFICIENT EVIDENCE"
        self.assertTrue(any("requires at least one risk" in item
                            for item in self.validate()))
        self.evidence["risks"] = ["Missing browser evidence"]
        self.assertEqual(self.validate(), [])

    def test_all_na_score_cannot_masquerade_as_scored(self):
        for record in self.evidence["categories"]:
            record["applicability"] = "not-applicable"
            record["score"] = 0
            record["na_reason"] = "No evidence was collected."
            record["evidence_type"] = "applicability-record"
            record["provenance"]["source_kind"] = "repository-record"
        self.evidence["total_score"] = 0
        self.evidence["normalized_score"] = 0
        self.assertTrue(any("all-N/A" in item for item in self.validate()))


if __name__ == "__main__":
    unittest.main()
