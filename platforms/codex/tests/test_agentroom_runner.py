"""Executable AgentRoom runner integration and fail-closed regression tests."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.request import Request, urlopen

from tests.fixtures.golden_web.app import GoldenWebApp


ROOT = Path(__file__).resolve().parents[1]
ROOM_SKILL = ROOT / "plugins/ai/skills/agent-room-templates"
PREPARE = ROOM_SKILL / "scripts/prepare_run.py"
FULL_TEAM = ROOM_SKILL / "agentsrooms/full-team-website.json"
BUG_ROOM = ROOM_SKILL / "agentsrooms/bug-fix-loop.json"
ENVIRONMENT = "staging"
PROJECT = "local/golden-advanced-web"
REVIEWER = "runner-e2e@example.test"

sys.path.insert(0, str(ROOM_SKILL / "scripts"))
try:
    import run_room as runner
    import validate_rooms as room_validator
finally:
    sys.path.pop(0)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


class RoomHarness:
    def __init__(self, root: Path, template: Path, run_id: str):
        self.root = root
        self.template = template
        self.run_id = run_id
        subprocess.run(["git", "init", "--quiet", str(root)], check=True)
        subprocess.run(
            ["git", "-C", str(root), "config", "user.name", "Runner Test"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(root), "config", "user.email",
             "runner@example.invalid"],
            check=True,
        )
        (root / ".gitignore").write_text(
            "artifacts/\nplans/\nworktrees/\n.solo/\n", encoding="utf-8",
        )
        (root / "app.txt").write_text(
            "golden advanced web fixture\n", encoding="utf-8",
        )
        subprocess.run(
            ["git", "-C", str(root), "add", ".gitignore", "app.txt"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(root), "commit", "--quiet", "-m", "fixture"],
            check=True,
        )
        self.commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True,
        ).strip()
        self.room_path = root / "plans" / (run_id + ".json")
        self.room_path.parent.mkdir(parents=True, exist_ok=True)
        prepared = subprocess.run(
            [
                sys.executable, str(PREPARE), str(template), str(self.room_path),
                "--run-id", run_id,
                "--profile", "saas-application",
                "--suite", str(ROOT),
                "--project-root", str(root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        if prepared.returncode:
            raise AssertionError(prepared.stdout + prepared.stderr)
        self.room = json.loads(self.room_path.read_text(encoding="utf-8"))
        self.state = runner.initialize(argparse.Namespace(
            room=self.room_path,
            project_root=root,
            suite=ROOT,
            commit=self.commit,
            environment=ENVIRONMENT,
        ))
        runner.issue_tasks(self.room, self.state, self.root)

    def write_profile(self, target: Path) -> None:
        now = datetime.now(timezone.utc) - timedelta(minutes=1)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({
            "schema": "solo-suite/project-profile-v1",
            "run_id": self.run_id,
            "project": PROJECT,
            "commit_sha": self.commit,
            "environment": ENVIRONMENT,
            "profile": "saas-application",
            "timestamp": iso(now),
            "categories": [
                {"category": category, "applicability": "applicable"}
                for category in room_validator.PRODUCTION_CATEGORIES
            ],
        }, indent=2) + "\n", encoding="utf-8")

    def write_plain_artifact(self, relative: str, task: dict) -> None:
        target = runner.project_path(
            Path(task["artifact_root"]), relative, "test artifact",
        )
        if relative.endswith("/project-profile.json"):
            self.write_profile(target)
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({
            "verified": True,
            "run_id": self.run_id,
            "stage": task["stage"],
            "seat": task["seat"],
            "commands": task["commands"],
        }, sort_keys=True) + "\n", encoding="utf-8")

    def write_phase_evidence(
        self, gate: dict, decision: str, task=None,
    ) -> None:
        timestamp = datetime.now(timezone.utc) - timedelta(minutes=1)
        expiry = timestamp + timedelta(hours=1)
        checks = []
        for index, prerequisite in enumerate(gate["prerequisites"]):
            relative = prerequisite["artifact"]
            target = runner.project_path(self.root, relative, "prerequisite")
            if not target.is_file():
                raise AssertionError("missing prerequisite " + relative)
            failed = decision == "NO-GO" and index == 0
            checks.append({
                "category": prerequisite["category"],
                "run_id": self.run_id,
                "gate_id": gate["id"],
                "status": "FAIL" if failed else "PASS",
                "commands_executed": [prerequisite["producer_commands"][0]],
                "exit_code": 1 if failed else 0,
                "evidence_artifact": relative,
                "artifact_digest": sha256(target),
            })
        output = runner.project_path(
            (Path(task["artifact_root"]) if task is not None else self.root),
            gate["evidence"]["artifact"],
            "gate evidence",
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            "schema": "solo-suite/phase-gate-evidence-v1",
            "room_digest": runner.sha256_file(self.room_path),
            "run_id": self.run_id,
            "gate_id": gate["id"],
            "project": PROJECT,
            "commit_sha": self.commit,
            "environment": ENVIRONMENT,
            "timestamp": iso(timestamp),
            "expires_at": iso(expiry),
            "reviewer": REVIEWER,
            "decision": decision,
            "checks": checks,
            "blockers": (["Injected runner repair-loop failure"]
                         if decision == "NO-GO" else []),
        }, indent=2) + "\n", encoding="utf-8")

    def write_production_evidence(self, gate: dict, task: dict) -> None:
        timestamp = datetime.now(timezone.utc) - timedelta(minutes=1)
        expiry = timestamp + timedelta(hours=1)
        prerequisites = {
            item["category"]: item for item in gate["prerequisites"]
        }
        records = []
        for category in room_validator.PRODUCTION_CATEGORIES:
            prerequisite = prerequisites[category]
            relative = prerequisite["artifact"]
            target = runner.project_path(self.root, relative, "category artifact")
            allowed = (
                set(prerequisite["producer_commands"]) &
                room_validator.PRODUCTION_CATEGORY_SKILLS[category]
            )
            if not allowed:
                raise AssertionError("unsatisfied category " + category)
            command = sorted(allowed)[0]
            records.append({
                "project": PROJECT,
                "run_id": self.run_id,
                "gate_id": gate["id"],
                "commit_sha": self.commit,
                "environment": ENVIRONMENT,
                "timestamp": iso(timestamp),
                "expires_at": iso(expiry),
                "category": category,
                "score": 10,
                "applicability": "applicable",
                "command_executed": command,
                "exit_code": 0,
                "evidence_type": "tool-report",
                "provenance": {
                    "source_kind": "local-tool",
                    "producer": command,
                    "source_reference": relative,
                    "generated_at": iso(timestamp),
                },
                "evidence_artifact": relative,
                "artifact_digest": sha256(target),
                "reviewer": REVIEWER,
            })
        profile_relative = prerequisites["Project profile"]["artifact"]
        profile = runner.project_path(self.root, profile_relative, "profile artifact")
        output = runner.project_path(
            Path(task["artifact_root"]), gate["evidence"]["artifact"],
            "production evidence",
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            "schema": "solo-suite/gate-evidence-v1",
            "room_digest": runner.sha256_file(self.room_path),
            "run_id": self.run_id,
            "gate_id": gate["id"],
            "project_profile": "saas-application",
            "profile_artifact": profile_relative,
            "profile_artifact_digest": sha256(profile),
            "project": PROJECT,
            "commit_sha": self.commit,
            "environment": ENVIRONMENT,
            "timestamp": iso(timestamp),
            "expires_at": iso(expiry),
            "reviewer": REVIEWER,
            "categories": records,
            "total_score": 140,
            "normalized_score": 100,
            "launch_status": "SAFE TO LAUNCH",
            "blockers": [],
            "warnings": [],
        }, indent=2) + "\n", encoding="utf-8")

    def result_for(self, task: dict, gate_decision: str = "GO") -> dict:
        gate = next(
            (item for item in self.room["gates"] if item["id"] == task["gate"]),
            None,
        )
        if gate is not None:
            if gate["command"] == "$gate-production-ready":
                self.write_production_evidence(gate, task)
            else:
                self.write_phase_evidence(gate, gate_decision, task)
        elif task["kind"] != "memory-steward":
            for relative in task["writes"]:
                self.write_plain_artifact(relative, task)
        artifacts = []
        if task["kind"] != "memory-steward":
            for relative in task["writes"]:
                artifacts.append({
                    "path": relative,
                    "digest": sha256(runner.project_path(
                        Path(task["artifact_root"]), relative, "result artifact",
                    )),
                })
        return {
            "schema": runner.RESULT_SCHEMA,
            "task_id": task["task_id"],
            "lease_id": task["lease_id"],
            "run_id": self.run_id,
            "commit_sha": self.commit,
            "stage": task["stage"],
            "seat": task["seat"],
            "status": "PASS",
            "commands_executed": list(task["commands"]),
            "artifacts": artifacts,
            "proposals": [],
            "notes": "Synthetic local fixture result for runner contract testing.",
        }

    def complete_stage(self, gate_decision: str = "GO") -> None:
        tasks = runner.issue_tasks(self.room, self.state, self.root)
        if not tasks:
            raise AssertionError("stage emitted no tasks")
        for task in tasks:
            runner.record_result(
                self.result_for(task, gate_decision),
                self.room, self.state, self.root,
            )
        runner.advance_stage(self.room_path, self.room, self.state, self.root)


class AgentRoomRunner(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_prepare_requires_an_explicit_profile(self):
        output = self.root / "room.json"
        result = subprocess.run(
            [
                sys.executable, str(PREPARE), str(BUG_ROOM), str(output),
                "--run-id", "missing-profile-001", "--suite", str(ROOT),
                "--project-root", str(self.root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--profile", result.stderr)
        self.assertFalse(output.exists())

    def test_initialization_emits_profile_bound_resumable_tasks(self):
        harness = RoomHarness(self.root, BUG_ROOM, "runner-init-001")
        tasks = runner.pending_tasks(harness.room, harness.state, self.root)
        self.assertEqual({task["seat"] for task in tasks}, {
            "memory_steward", "reproducer",
        })
        self.assertTrue(all(task["profile"] == "saas-application" for task in tasks))
        for workspace in harness.room["workspaces"]:
            if workspace["type"] != "worktree":
                continue
            target = runner.project_path(
                self.root, workspace["path"], "fixture worktree",
            )
            self.assertTrue((target / ".git").exists(), workspace["id"])
            self.assertEqual(
                subprocess.check_output(
                    ["git", "-C", str(target), "rev-parse", "HEAD"], text=True,
                ).strip(),
                harness.commit,
            )
        _, state_path, _ = runner.state_paths(self.root, harness.run_id)
        runner.persist_state(state_path, harness.state)
        room, resumed, _, _, _ = runner.load_context(harness.room_path, self.root)
        self.assertEqual(room["run_id"], harness.run_id)
        self.assertEqual(resumed["current_stage"], "reproduce")
        claim = json.loads((
            self.root / "artifacts/runs/.registry/runner-init-001.lock"
        ).read_text(encoding="utf-8"))
        self.assertEqual(claim["plan_digest"], runner.sha256_file(harness.room_path))

    def test_rebind_requires_an_integrated_commit_and_restarts_validation(self):
        harness = RoomHarness(self.root, BUG_ROOM, "runner-rebind-001")
        harness.complete_stage("GO")
        self.assertEqual(harness.state["current_stage"], "diagnose_and_fix")
        previous = harness.commit
        (self.root / "app.txt").write_text(
            "integrated worker change\n", encoding="utf-8",
        )
        subprocess.run(
            ["git", "-C", str(self.root), "add", "app.txt"], check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "--quiet", "-m", "integrate"],
            check=True,
        )
        current = subprocess.check_output(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True,
        ).strip()
        runner.rebind_commit(harness.room, harness.state, self.root, current)
        self.assertEqual(harness.state["commit_sha"], current)
        self.assertEqual(harness.state["current_stage"], "reproduce")
        self.assertEqual(harness.state["loop_iterations"], 0)
        self.assertEqual(harness.state["commit_history"][-1]["from"], previous)
        self.assertTrue(all(
            head in {current, "shared-memory"}
            for head in harness.state["workspace_heads"].values()
        ))
        tasks = runner.pending_tasks(harness.room, harness.state, self.root)
        self.assertTrue(tasks)
        self.assertTrue(all(task["commit_sha"] == current for task in tasks))

    def test_result_rejects_undeclared_writes_and_changed_digests(self):
        harness = RoomHarness(self.root, BUG_ROOM, "runner-result-001")
        with self.assertRaisesRegex(runner.RunnerError, "portable POSIX relative path"):
            runner.safe_relative("C:/outside.txt", "fixture")
        task = next(
            task for task in runner.pending_tasks(harness.room, harness.state, self.root)
            if task["seat"] == "reproducer"
        )
        result = harness.result_for(task)
        changed = dict(result)
        changed["artifacts"] = list(result["artifacts"]) + [{
            "path": "README.md", "digest": "sha256:" + "0" * 64,
        }]
        with self.assertRaisesRegex(runner.RunnerError, "undeclared write"):
            runner.validate_result(
                changed, task, harness.room, harness.state, self.root,
            )
        result["artifacts"][0]["digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(runner.RunnerError, "digest does not match"):
            runner.validate_result(
                result, task, harness.room, harness.state, self.root,
            )

    def test_gate_rejects_evidence_not_backed_by_recorded_command_execution(self):
        harness = RoomHarness(self.root, BUG_ROOM, "runner-provenance-001")
        while harness.state["current_stage"] != "merge_gate":
            harness.complete_stage("GO")
        for task in runner.issue_tasks(harness.room, harness.state, self.root):
            runner.record_result(
                harness.result_for(task, "GO"),
                harness.room, harness.state, self.root,
            )
        review = next(
            item for item in harness.room["gates"][0]["prerequisites"]
            if item["category"] == "Review"
        )
        harness.state["artifact_provenance"][review["artifact"]][
            "commands_executed"
        ] = []
        with self.assertRaisesRegex(
            runner.RunnerError, "was not executed for artifact"
        ):
            runner.advance_stage(
                harness.room_path, harness.room, harness.state, self.root,
            )

    def test_adapter_undeclared_project_write_blocks_the_run(self):
        harness = RoomHarness(self.root, BUG_ROOM, "runner-adapter-001")
        runner_root, state_path, _ = runner.state_paths(self.root, harness.run_id)
        adapter = runner_root / "rogue_adapter.py"
        adapter.parent.mkdir(parents=True, exist_ok=True)
        adapter.write_text(
            "import os\n"
            "from pathlib import Path\n"
            "task = Path(os.environ['SOLO_AGENTROOM_TASK'])\n"
            "(task.parents[5] / 'rogue.txt').write_text('unexpected\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(runner.RunnerError, "undeclared paths"):
            runner.execute_adapter(
                argparse.Namespace(
                    project_root=self.root,
                    seat="reproducer",
                    adapter=[sys.executable, str(adapter)],
                    timeout=30,
                ),
                harness.room, harness.state, runner_root, state_path,
            )
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["status"], "BLOCKED")
        self.assertIn("rogue.txt", persisted["blocker"])
        retry = subprocess.run(
            [
                sys.executable, str(ROOM_SKILL / "scripts/run_room.py"),
                "retry", str(harness.room_path),
                "--project-root", str(self.root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        self.assertEqual(retry.returncode, 1)
        self.assertIn("requires cleanup", retry.stderr)
        (self.root / "rogue.txt").unlink()
        retry = subprocess.run(
            [
                sys.executable, str(ROOM_SKILL / "scripts/run_room.py"),
                "retry", str(harness.room_path),
                "--project-root", str(self.root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
        self.assertEqual(json.loads(retry.stdout)["status"], "READY")

    def test_full_team_happy_path_runs_every_validator_and_completes(self):
        harness = RoomHarness(self.root, FULL_TEAM, "full-team-e2e-001")
        with tempfile.TemporaryDirectory() as web_temp:
            with GoldenWebApp(Path(web_temp)) as app:
                with urlopen(app.base_url + "/api/health", timeout=5) as response:
                    self.assertEqual(json.loads(response.read()), {"status": "ok"})
                signup = Request(
                    app.base_url + "/api/signup",
                    data=json.dumps({"email": "runner@example.test"}).encode("utf-8"),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(signup, timeout=5) as response:
                    self.assertEqual(response.status, 201)
                self.assertEqual(app.count_users(), 1)
        safety = 0
        while harness.state["status"] == "READY":
            harness.complete_stage("GO")
            safety += 1
            self.assertLess(safety, 20)
        self.assertEqual(harness.state["status"], "COMPLETE")
        self.assertEqual(harness.state["current_stage"], "production")
        self.assertEqual(harness.state["loop_iterations"], 0)
        completed = [item["stage"] for item in harness.state["completed_stages"]]
        self.assertNotIn("repair_retest", completed)
        self.assertEqual(completed[-1], "production")
        gate_records = [
            item for item in harness.state["completed_stages"]
            if item["validator"] is not None
        ]
        self.assertEqual(len(gate_records), 4)
        self.assertTrue(all("PASS" in item["validator"] for item in gate_records))
        executed_seats = {
            seat_id
            for stage in harness.room["stages"] if stage["id"] in completed
            for seat_id in stage["seats"] if seat_id != "memory_steward"
        }
        expected_artifacts = {
            artifact
            for seat in harness.room["seats"] if seat["id"] in executed_seats
            for artifact in seat["writes"]
        }
        self.assertEqual(
            set(harness.state["artifact_provenance"]), expected_artifacts,
        )

    def test_bug_room_no_go_repair_loop_exhausts_after_three_reentries(self):
        harness = RoomHarness(self.root, BUG_ROOM, "repair-loop-e2e-001")
        safety = 0
        while harness.state["status"] == "READY":
            decision = "NO-GO" if harness.state["current_stage"] == "merge_gate" else "GO"
            harness.complete_stage(decision)
            safety += 1
            self.assertLess(safety, 30)
        self.assertEqual(harness.state["status"], "BLOCKED")
        self.assertEqual(harness.state["loop_iterations"], 3)
        self.assertIn("Stop, preserve all evidence", harness.state["blocker"])


if __name__ == "__main__":
    unittest.main()
