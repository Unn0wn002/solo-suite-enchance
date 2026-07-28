"""Strict AgentRooms schema, semantic policy, and runner-adapter tests."""

from __future__ import annotations

import copy
import glob
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
ROOM_ROOT = ROOT / "plugins/ai/skills/agent-room-templates"
VPATH = ROOM_ROOT / "scripts/validate_rooms.py"
SCHEMA_PATH = ROOM_ROOT / "schema/agentroom-v1.schema.json"
BUG_ROOM = ROOM_ROOT / "agentsrooms/bug-fix-loop.json"
FULL_TEAM_ROOM = ROOM_ROOT / "agentsrooms/full-team-website.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vr = load_module("validate_rooms_v111", VPATH)


def room_fixture() -> dict:
    return json.loads(BUG_ROOM.read_text(encoding="utf-8"))


def full_team_fixture() -> dict:
    return json.loads(FULL_TEAM_ROOM.read_text(encoding="utf-8"))


class BundledTemplates(unittest.TestCase):
    def setUp(self):
        self.paths = sorted(glob.glob(str(ROOM_ROOT / "agentsrooms/*.json")))
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_all_four_templates_pass_schema_and_policy(self):
        self.assertEqual(len(self.paths), 4)
        Draft202012Validator.check_schema(self.schema)
        validator = Draft202012Validator(
            self.schema, format_checker=FormatChecker()
        )
        for path in self.paths:
            with self.subTest(path=path):
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
                self.assertEqual(errors, [])
        self.assertEqual(vr.validate_files(self.paths, suite_root=str(ROOT)), [])

    def test_prepare_run_works_from_an_external_cwd(self):
        prepare = ROOM_ROOT / "scripts/prepare_run.py"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "plans" / "run.json"
            result = subprocess.run(
                [
                    sys.executable, str(prepare), str(BUG_ROOM), str(output),
                    "--run-id", "external-run-001", "--suite", str(ROOT),
                    "--profile", "saas-application",
                ],
                cwd=temp, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn(b"\r", output.read_bytes())
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8"))["run_id"],
                "external-run-001",
            )
            prepared = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(prepared["prepared"])
            self.assertTrue(all(
                workspace["path"] == ".solo/" or
                workspace["path"].startswith(
                    "worktrees/runs/external-run-001/")
                for workspace in prepared["workspaces"]
            ))
            self.assertTrue(all(
                lock["artifact"].startswith(".solo/") or
                lock["artifact"].startswith(
                    "artifacts/runs/external-run-001/")
                for lock in prepared["artifact_locks"]
            ))
            self.assertTrue(all(
                gate["evidence"]["artifact"].startswith(
                    "artifacts/runs/external-run-001/")
                for gate in prepared["gates"]
            ))
            second = subprocess.run(
                [
                    sys.executable, str(prepare), str(BUG_ROOM), str(output),
                    "--run-id", "external-run-002", "--suite", str(ROOT),
                    "--profile", "saas-application",
                ],
                cwd=temp, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30,
            )
            self.assertEqual(second.returncode, 1)
            self.assertIn("already exists", second.stdout)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8"))["run_id"],
                "external-run-001",
            )
            duplicate_output = Path(temp) / "plans" / "duplicate.json"
            duplicate = subprocess.run(
                [
                    sys.executable, str(prepare), str(BUG_ROOM),
                    str(duplicate_output), "--run-id", "external-run-001",
                    "--profile", "saas-application", "--suite", str(ROOT),
                ],
                cwd=temp, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30,
            )
            self.assertEqual(duplicate.returncode, 1)
            self.assertIn("already registered", duplicate.stdout)
            self.assertFalse(duplicate_output.exists())

    def test_agentroom_generator_is_deterministic(self):
        generated = [
            ROOM_ROOT / "agentsrooms/full-team-website.json",
            ROOM_ROOT / "agentsrooms/production-release.json",
            ROOM_ROOT / "agentsrooms/site-doctor-audit.json",
        ]
        before = {path: path.read_bytes() for path in generated}
        builder = load_module(
            "agentroom_builder_coverage", ROOT / "tools/build_agentrooms.py"
        )
        in_process = [
            builder.full_team(),
            builder.production_release(),
            builder.site_doctor_audit(),
        ]
        self.assertEqual(
            [json.loads(before[path].decode("utf-8")) for path in generated],
            in_process,
        )
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/build_agentrooms.py")],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, {path: path.read_bytes() for path in generated})

    def test_full_team_vendor_tasks_and_generated_docs_stay_in_sync(self):
        room = full_team_fixture()
        commands = {
            command
            for seat in room["seats"]
            for command in seat["commands"]
        }
        self.assertTrue({
            "$stack-audit-vercel",
            "$stack-audit-supabase",
            "$stack-audit-cloudflare",
            "$stack-audit-tags",
            "$stack-audit-payments",
        } <= commands)
        self.assertTrue({
            "$spec-feature-brief",
            "$spec-acceptance",
            "$git-commit-plan",
            "$release-ci-setup",
            "$solo-handoff-memory",
        } <= commands)
        self.assertTrue(all(
            seat["handoff_check"] == "$ai-handoff-check"
            for seat in room["seats"]
            if seat["kind"] != "memory-steward"
        ))
        vendor_artifacts = {
            artifact["artifact"]
            for artifact in room["artifact_locks"]
            if "/vendor-audits/" in artifact["artifact"]
        }
        self.assertEqual(len(vendor_artifacts), 5)
        for gate_id in ("before_merge", "before_deploy"):
            gate = next(item for item in room["gates"] if item["id"] == gate_id)
            prerequisites = {
                item["artifact"] for item in gate["prerequisites"]
            }
            self.assertTrue(vendor_artifacts <= prerequisites, gate_id)
        docs = (
            ROOT / "plugins/full-team/skills/full-team-orchestrator/references"
        )
        seat_map = (docs / "seat-stage-map.md").read_text(encoding="utf-8")
        flow = (docs / "authoritative-flow.md").read_text(encoding="utf-8")
        for stage in room["stages"]:
            self.assertIn(f"`{stage['id']}`", seat_map)
            for seat_id in stage["seats"]:
                self.assertIn(f"`{seat_id}`", seat_map)
        for command in {
            "$stack-audit-vercel",
            "$stack-audit-supabase",
            "$stack-audit-cloudflare",
            "$stack-audit-tags",
            "$stack-audit-payments",
        }:
            self.assertIn(command, seat_map)
            self.assertIn(command, flow)
        self.assertNotIn("room-*", seat_map)
        self.assertNotIn("room-*", flow)
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/build_agentrooms.py"), "--check-docs"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_full_team_website_has_advanced_delivery_controls(self):
        room = full_team_fixture()
        stage_ids = [stage["id"] for stage in room["stages"]]
        self.assertLess(stage_ids.index("architecture"),
                        stage_ids.index("database_architecture"))
        self.assertLess(stage_ids.index("database_architecture"),
                        stage_ids.index("design"))
        self.assertLess(stage_ids.index("before_merge"),
                        stage_ids.index("release_and_docs"))
        self.assertLess(stage_ids.index("release_and_docs"),
                        stage_ids.index("release_management"))
        self.assertLess(stage_ids.index("release_management"),
                        stage_ids.index("before_deploy"))
        self.assertLess(stage_ids.index("before_deploy"),
                        stage_ids.index("repair_retest"))
        self.assertLess(stage_ids.index("repair_retest"),
                        stage_ids.index("production"))

        commands = {command for seat in room["seats"]
                    for command in seat["commands"]}
        self.assertTrue(vr.FULL_TEAM_REQUIRED_COMMANDS <= commands)
        deploy_gate = next(gate for gate in room["gates"]
                           if gate["command"] == "$gate-before-deploy")
        deploy_artifacts = {item["artifact"]
                            for item in deploy_gate["prerequisites"]}
        self.assertTrue(vr.FULL_TEAM_BEFORE_DEPLOY_ARTIFACTS <= deploy_artifacts)
        production_gate = next(gate for gate in room["gates"]
                               if gate["command"] == "$gate-production-ready")
        self.assertEqual(
            {(item["gate_id"], item["status"])
             for item in production_gate["required_gate_results"]},
            {("before_deploy", "GO")},
        )
        self.assertEqual(room["loop"]["from_stage"], "repair_retest")
        self.assertEqual(room["loop"]["to_stage"], "implementation")
        self.assertEqual(room["loop"]["max_iterations"], 3)


class SemanticRules(unittest.TestCase):
    def check(self, room: dict, fragment: str, *, known=None) -> None:
        problems = vr.validate_room(room, "fixture.json", known=known)
        self.assertTrue(
            any(fragment in problem for problem in problems),
            f"expected {fragment!r} in {problems!r}",
        )

    def test_valid_strict_fixture(self):
        self.assertEqual(
            vr.validate_room(room_fixture(), "fixture.json", vr.known_commands(str(ROOT))),
            [],
        )

    def test_wrong_field_type(self):
        room = room_fixture()
        room["rules"] = "not-a-list"
        self.check(room, "rules")

    def test_disconnected_stage(self):
        room = room_fixture()
        next(seat for seat in room["seats"] if seat["id"] == "reproducer")[
            "handoff_to"
        ] = None
        self.check(room, "disconnected stage")

    def test_invalid_loop_target_and_bound(self):
        room = room_fixture()
        room["loop"]["to_stage"] = "not_a_stage"
        room["loop"]["max_iterations"] = 0
        self.check(room, "invalid loop target")
        self.check(room, "bound the loop")

    def test_loop_uses_gate_statuses_and_fail_closed_exhaustion(self):
        room = room_fixture()
        room["gates"][0]["transitions"]["routes"][1] = {
            "statuses": ["NO-GO"], "action": "stop",
        }
        room["loop"]["on_exhaustion_action"] = "complete"
        self.check(room, "must route to 'diagnose_and_fix'")
        self.check(room, "on_exhaustion_action must be stop")

    def test_implicit_write_must_be_declared(self):
        room = room_fixture()
        fixer = next(seat for seat in room["seats"] if seat["id"] == "fixer")
        fixer["proposals"].remove(".solo/bugs.md")
        self.check(room, "undeclared implicit write '.solo/bugs.md'")

    def test_simultaneous_writers_are_rejected(self):
        room = room_fixture()
        reproduce = next(stage for stage in room["stages"] if stage["id"] == "reproduce")
        diagnose = next(
            stage for stage in room["stages"] if stage["id"] == "diagnose_and_fix"
        )
        reproduce["seats"].append("fixer")
        diagnose["seats"].remove("fixer")
        fixer = next(seat for seat in room["seats"] if seat["id"] == "fixer")
        fixer["writes"].append("artifacts/bug-fix-loop/reproduction.md")
        self.check(room, "unsafe simultaneous writers")

    def test_missing_gate_evidence(self):
        room = room_fixture()
        del room["gates"][0]["evidence"]
        self.check(room, "missing gate evidence")

    def test_insufficient_gatekeeper_reads(self):
        room = room_fixture()
        gatekeeper = next(
            seat for seat in room["seats"] if seat["id"] == "gatekeeper"
        )
        gatekeeper["reads"].remove("artifacts/bug-fix-loop/rollback.md")
        self.check(room, "insufficient gatekeeper reads")

    def test_duplicate_task_ids(self):
        room = room_fixture()
        duplicate = {
            "id": "T1", "owner": "fixer", "allocated_by": "memory_steward"
        }
        room["tasks"] = [duplicate, copy.deepcopy(duplicate)]
        self.check(room, "duplicate task ID")

    def test_unknown_skill_is_rejected_with_suite_inventory(self):
        room = room_fixture()
        fixer = next(seat for seat in room["seats"] if seat["id"] == "fixer")
        fixer["commands"].append("$not-a-real-solo-skill")
        self.check(room, "does not exist", known=vr.known_commands(str(ROOT)))

    def test_gate_invocation_requires_a_declaration(self):
        room = room_fixture()
        room["gates"] = []
        self.check(room, "has no prerequisites or gate evidence declaration")

    def test_full_team_requires_mandatory_web_commands(self):
        room = full_team_fixture()
        doctor = next(seat for seat in room["seats"] if seat["id"] == "site_doctor")
        doctor["commands"].remove("$site-doctor-a11y")
        self.check(room, "missing mandatory command")

    def test_full_team_requires_complete_before_deploy_evidence(self):
        room = full_team_fixture()
        gate = next(gate for gate in room["gates"]
                    if gate["command"] == "$gate-before-deploy")
        gate["prerequisites"] = [
            item for item in gate["prerequisites"]
            if item["artifact"] != "artifacts/full-team/environment-readiness.json"
        ]
        self.check(room, "gate is missing mandatory prerequisite")

    def test_full_team_repair_loop_is_tightly_bounded(self):
        room = full_team_fixture()
        room["loop"]["max_iterations"] = 4
        self.check(room, "bounded to 1-3 iterations")

    def test_gatekeeper_cannot_bypass_conditional_transitions(self):
        room = full_team_fixture()
        gatekeeper = next(
            seat for seat in room["seats"]
            if seat["id"] == "before_code_gatekeeper"
        )
        gatekeeper["handoff_to"] = ["frontend_developer", "backend_developer"]
        self.check(room, "must not declare an unconditional handoff")

    def test_phase_gate_must_use_phase_contract_and_fail_closed_routes(self):
        room = full_team_fixture()
        gate = next(gate for gate in room["gates"]
                    if gate["command"] == "$gate-before-code")
        gate["evidence"]["schema"] = "solo-suite/gate-evidence-v1"
        self.check(room, "requires evidence schema solo-suite/phase-gate-evidence-v1")
        room = full_team_fixture()
        next(item for item in room["gates"]
             if item["command"] == "$gate-before-code")["transitions"][
                 "default_action"] = "complete"
        self.check(room, "default_action must be stop")

    def test_no_go_cannot_route_to_production(self):
        room = full_team_fixture()
        gate = next(gate for gate in room["gates"]
                    if gate["command"] == "$gate-before-deploy")
        route = next(route for route in gate["transitions"]["routes"]
                     if "NO-GO" in route["statuses"])
        route.pop("next_stage", None)
        route["next_stage"] = "production"
        self.check(room, "NO-GO route cannot enter production")

    def test_production_requires_exact_current_before_deploy_go(self):
        room = full_team_fixture()
        gate = next(gate for gate in room["gates"]
                    if gate["command"] == "$gate-production-ready")
        gate.pop("required_gate_results")
        self.check(room, "requires an exact-current GO result")

    def test_same_or_later_stage_producer_read_is_rejected(self):
        room = full_team_fixture()
        architecture = next(stage for stage in room["stages"]
                            if stage["id"] == "architecture")
        database = next(stage for stage in room["stages"]
                        if stage["id"] == "database_architecture")
        architecture["seats"].append("database_engineer")
        database["seats"].remove("database_engineer")
        self.check(room, "same-stage producer")

    def test_windows_reserved_run_id_is_rejected(self):
        room = room_fixture()
        room["run_id"] = "CON"
        self.check(room, "Windows-safe")

    def test_prepared_room_requires_exact_case_stable_run_namespaces(self):
        room = full_team_fixture()
        room["prepared"] = True
        room["run_id"] = "live-run-001"
        self.check(room, "exact run namespace")

        room["run_id"] = "Live-Run-001"
        self.check(room, "Windows-safe")

    def test_prepared_room_must_bind_a_concrete_profile(self):
        room = full_team_fixture()
        room["prepared"] = True
        room["run_id"] = "live-run-001"
        self.check(room, "bind a concrete project profile")

    def test_prepared_room_rejects_malformed_runtime_trust(self):
        digest = "sha256:" + "0" * 64
        valid = {
            "schema": "solo-suite/agentroom-runtime-trust-v2",
            "suite_digest": digest,
            "skill_count": 1,
            "validators": {
                "phase": {
                    "path": (
                        "plugins/gate/skills/quality-gatekeeper/scripts/"
                        "validate_phase_gate_evidence.py"
                    ),
                    "digest": digest,
                },
                "production": {
                    "path": (
                        "plugins/gate/skills/production-readiness-reviewer/"
                        "scripts/validate_gate_evidence.py"
                    ),
                    "digest": digest,
                },
            },
            "runtime": {
                name: {
                    "path": (
                        "plugins/ai/skills/agent-room-templates/scripts/" +
                        name + ".py"
                    ),
                    "digest": digest,
                }
                for name in (
                    "git_trust", "prepare_run", "run_room", "runtime_trust",
                    "state_journal", "validate_rooms",
                )
            },
        }
        malformed = []

        extra_key = copy.deepcopy(valid)
        extra_key["unexpected"] = True
        malformed.append(("extra key", extra_key))

        zero_skills = copy.deepcopy(valid)
        zero_skills["skill_count"] = 0
        malformed.append(("empty skill inventory", zero_skills))

        bad_suite_digest = copy.deepcopy(valid)
        bad_suite_digest["suite_digest"] = "sha256:not-a-digest"
        malformed.append(("bad suite digest", bad_suite_digest))

        missing_validator = copy.deepcopy(valid)
        del missing_validator["validators"]["phase"]
        malformed.append(("missing validator", missing_validator))

        wrong_validator_path = copy.deepcopy(valid)
        wrong_validator_path["validators"]["phase"]["path"] = (
            "plugins/attacker/validate.py"
        )
        malformed.append(("substituted validator path", wrong_validator_path))

        bad_validator_digest = copy.deepcopy(valid)
        bad_validator_digest["validators"]["production"]["digest"] = "bad"
        malformed.append(("bad validator digest", bad_validator_digest))

        wrong_runtime_path = copy.deepcopy(valid)
        wrong_runtime_path["runtime"]["run_room"]["path"] = (
            "plugins/attacker/run_room.py"
        )
        malformed.append(("substituted runtime path", wrong_runtime_path))

        for label, trust in malformed:
            with self.subTest(case=label):
                room = full_team_fixture()
                room["prepared"] = True
                room["run_id"] = "live-run-001"
                room["profile"] = "saas-application"
                room["runtime_trust"] = trust
                self.check(room, "runtime_trust is malformed")

    def test_unprepared_room_rejects_runtime_trust(self):
        room = full_team_fixture()
        room["runtime_trust"] = {}
        self.check(room, "unprepared rooms must not bind runtime_trust")

    def test_gate_prerequisite_commands_are_bound_to_the_real_producer(self):
        room = full_team_fixture()
        room["gates"][0]["prerequisites"][0]["producer_commands"] = [
            "$invented-skill"
        ]
        self.check(room, "producer_commands do not match")

    def test_production_category_requires_an_allowed_producer_command(self):
        room = full_team_fixture()
        frontend = next(
            seat for seat in room["seats"]
            if seat["id"] == "frontend_developer"
        )
        frontend["commands"] = ["$dev-implement-feature"]
        production = next(
            gate for gate in room["gates"]
            if gate["command"] == "$gate-production-ready"
        )
        prerequisite = next(
            item for item in production["prerequisites"]
            if item["category"] == "Frontend"
        )
        prerequisite["producer_commands"] = ["$dev-implement-feature"]
        self.check(room, "no producer command allowed")

    def test_gate_cannot_reuse_one_artifact_for_multiple_prerequisites(self):
        room = full_team_fixture()
        room["gates"][0]["prerequisites"][1]["artifact"] = (
            room["gates"][0]["prerequisites"][0]["artifact"]
        )
        self.check(room, "reuses prerequisite artifact")

    def test_nonterminal_gate_cannot_complete_the_room(self):
        room = full_team_fixture()
        room["gates"][0]["transitions"]["routes"][0] = {
            "statuses": ["GO"], "action": "complete",
        }
        self.check(room, "cannot complete from nonterminal stage")


if __name__ == "__main__":
    unittest.main()
