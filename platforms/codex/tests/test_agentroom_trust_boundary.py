"""Adversarial regression tests for the AgentRoom runner trust boundary."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock

from tests.test_agentroom_runner import (
    BUG_ROOM,
    FULL_TEAM,
    ROOT,
    ROOM_SKILL,
    RoomHarness,
    runner,
)


RUNNER = ROOM_SKILL / "scripts/run_room.py"


class AgentRoomTrustBoundary(unittest.TestCase):
    """Exercise attacks that must fail before state or evidence is trusted."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def harness(self, suffix: str) -> RoomHarness:
        return RoomHarness(self.root, BUG_ROOM, "trust-" + suffix)

    @staticmethod
    def worker_task(harness: RoomHarness) -> dict:
        return next(
            task
            for task in runner.pending_tasks(
                harness.room, harness.state, harness.root,
            )
            if task["seat"] == "reproducer"
        )

    @staticmethod
    def record_current_stage(harness: RoomHarness) -> list[dict]:
        results = []
        for task in runner.issue_tasks(
            harness.room, harness.state, harness.root,
        ):
            result = harness.result_for(task)
            runner.record_result(
                result, harness.room, harness.state, harness.root,
            )
            results.append(result)
        return results

    @staticmethod
    def create_directory_link(link: Path, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        try:
            link.symlink_to(target, target_is_directory=True)
            return
        except OSError:
            if os.name != "nt":
                raise
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if completed.returncode:
            raise AssertionError(completed.stdout + completed.stderr)

    @staticmethod
    def stop_process(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)

    @staticmethod
    def commit_change(repository: Path, contents: str) -> str:
        (repository / "app.txt").write_text(contents, encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repository), "add", "app.txt"], check=True,
        )
        subprocess.run(
            ["git", "-C", str(repository), "commit", "--quiet", "-m",
             "trust boundary drift"],
            check=True,
        )
        return subprocess.check_output(
            ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True,
        ).strip()

    @staticmethod
    def forged_recorded_stage(harness: RoomHarness) -> dict:
        """Forge a plausible recorded stage without using record_result."""
        forged = copy.deepcopy(harness.state)
        marker = "2026-01-01T00:00:00Z"
        tasks = runner.pending_tasks(harness.room, forged, harness.root)
        if not tasks:
            raise AssertionError("fixture stage has no tasks to forge")
        for task in tasks:
            result = harness.result_for(task)
            forged["results"][task["task_id"]] = copy.deepcopy(result)
            lease = forged["task_leases"][task["task_id"]]
            lease["status"] = "recorded"
            lease["recorded_at"] = marker
            for artifact in result["artifacts"]:
                relative = artifact["path"]
                forged["artifact_claims"][relative] = task["seat"]
                forged["artifact_provenance"][relative] = {
                    "task_id": task["task_id"],
                    "seat": task["seat"],
                    "commands_executed": list(result["commands_executed"]),
                    "commit_sha": result["commit_sha"],
                    "digest": artifact["digest"],
                }
            forged["history"].append({
                "event": marker,
                "action": "record",
                "task_id": task["task_id"],
                "status": result["status"],
            })
        return forged

    @staticmethod
    def conceal_tracked_change(
        repository: Path, index_flag: str, contents: str,
    ) -> None:
        subprocess.run(
            ["git", "-C", str(repository), "update-index", index_flag,
             "app.txt"],
            check=True,
        )
        (repository / "app.txt").write_text(contents, encoding="utf-8")
        porcelain = subprocess.check_output(
            ["git", "-C", str(repository), "status", "--porcelain"],
            text=True,
        )
        if porcelain:
            raise AssertionError(
                "%s did not conceal the fixture edit: %r" %
                (index_flag, porcelain)
            )

    def test_tampered_state_cannot_substitute_gate_validator(self) -> None:
        harness = self.harness("suite-root-001")
        while harness.state["current_stage"] != "merge_gate":
            harness.complete_stage("GO")
        for task in runner.issue_tasks(
            harness.room, harness.state, harness.root,
        ):
            runner.record_result(
                harness.result_for(task, "GO"), harness.room, harness.state,
                harness.root,
            )

        attacker_suite = self.root / "attacker-suite"
        attacker_suite.mkdir()
        shutil.copy2(ROOT / "command-map.json", attacker_suite / "command-map.json")
        # Keep the substituted suite structurally valid so rejection proves the
        # pinned trust root stopped execution, rather than command discovery
        # merely failing before the malicious validator was reached.
        commands = {
            command
            for seat in harness.room["seats"]
            for command in seat.get("commands", [])
        }
        for command in commands:
            skill = (
                attacker_suite / "plugins/fixture/skills" /
                command.removeprefix("$") / "SKILL.md"
            )
            skill.parent.mkdir(parents=True, exist_ok=True)
            skill.write_text("# Attacker fixture\n", encoding="utf-8")
        validator = (
            attacker_suite /
            "plugins/gate/skills/quality-gatekeeper/scripts/"
            "validate_phase_gate_evidence.py"
        )
        validator.parent.mkdir(parents=True)
        marker = self.root / "substituted-validator-ran.txt"
        validator.write_text(
            "from pathlib import Path\n"
            "Path(%r).write_text('executed\\n', encoding='utf-8')\n" %
            str(marker),
            encoding="utf-8",
        )

        _, state_path, _ = runner.state_paths(harness.root, harness.run_id)
        tampered = dict(harness.state)
        tampered["suite_root"] = str(attacker_suite)
        runner.atomic_json(state_path, tampered)
        result = subprocess.run(
            [
                sys.executable, str(RUNNER), "advance", str(harness.room_path),
                "--project-root", str(harness.root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(
            result.stderr,
            r"(?i)(suite|validator|journal|projection|authoritative).*(tamper|trust|mismatch|digest|changed|differs|rejected|failed)",
        )
        self.assertFalse(marker.exists(), "an untrusted validator was executed")

    def test_validate_state_rejects_forged_recorded_stage(self) -> None:
        harness = self.harness("forged-state-validate-001")
        forged = self.forged_recorded_stage(harness)

        with self.assertRaises(runner.RunnerError):
            runner.validate_state(
                forged, harness.room, harness.room_path, harness.root,
                runner.sha256_file(harness.room_path),
            )

    def test_persisted_forged_stage_cannot_advance(self) -> None:
        harness = self.harness("forged-state-advance-001")
        forged = self.forged_recorded_stage(harness)
        original_stage = forged["current_stage"]
        _, state_path, _ = runner.state_paths(harness.root, harness.run_id)
        runner.atomic_json(state_path, forged)

        completed = subprocess.run(
            [
                sys.executable, str(RUNNER), "advance", str(harness.room_path),
                "--project-root", str(harness.root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )

        self.assertNotEqual(
            completed.returncode, 0, completed.stdout + completed.stderr,
        )
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["current_stage"], original_stage)

    def test_project_head_drift_is_rejected_before_record(self) -> None:
        harness = self.harness("project-record-001")
        task = self.worker_task(harness)
        result = harness.result_for(task)
        drifted = self.commit_change(harness.root, "new project head\n")
        self.assertNotEqual(drifted, harness.commit)

        with self.assertRaisesRegex(
            runner.RunnerError,
            r"(?i)(project|repository).*(HEAD|commit|drift|changed)",
        ):
            runner.record_result(
                result, harness.room, harness.state, harness.root,
            )

    def test_project_head_drift_is_rejected_before_advance(self) -> None:
        harness = self.harness("project-advance-001")
        for task in runner.issue_tasks(
            harness.room, harness.state, harness.root,
        ):
            runner.record_result(
                harness.result_for(task), harness.room, harness.state,
                harness.root,
            )
        drifted = self.commit_change(harness.root, "advance on wrong head\n")
        self.assertNotEqual(drifted, harness.commit)

        with self.assertRaisesRegex(
            runner.RunnerError,
            r"(?i)(project|repository).*(HEAD|commit|drift|changed)",
        ):
            runner.advance_stage(
                harness.room_path, harness.room, harness.state, harness.root,
            )

    def test_untracked_project_drift_is_rejected_before_advance(self) -> None:
        harness = self.harness("project-untracked-advance-001")
        self.record_current_stage(harness)
        original_stage = harness.state["current_stage"]
        (harness.root / "rogue-untracked.py").write_text(
            "print('unprovenanced')\n", encoding="utf-8",
        )

        with self.assertRaisesRegex(
            runner.RunnerError, r"(?i)untracked inputs.*rogue-untracked",
        ):
            runner.advance_stage(
                harness.room_path, harness.room, harness.state, harness.root,
            )
        self.assertEqual(harness.state["current_stage"], original_stage)

    def test_unprovenanced_runner_namespace_drift_blocks_advance(self) -> None:
        harness = self.harness("namespace-drift-advance-001")
        self.record_current_stage(harness)
        original_stage = harness.state["current_stage"]
        rogue = harness.root / ".solo" / "rogue-unprovenanced.txt"
        rogue.parent.mkdir(parents=True, exist_ok=True)
        rogue.write_text("unprovenanced\n", encoding="utf-8")

        with self.assertRaisesRegex(
            runner.RunnerError, r"(?i)undeclared project changes.*rogue-unprovenanced",
        ):
            runner.advance_stage(
                harness.room_path, harness.room, harness.state, harness.root,
            )
        self.assertEqual(harness.state["current_stage"], original_stage)

    def test_deleted_promoted_artifact_blocks_status(self) -> None:
        harness = self.harness("deleted-live-status-001")
        results = self.record_current_stage(harness)
        promoted = next(
            artifact["path"]
            for result in results for artifact in result["artifacts"]
        )
        _, state_path, _ = runner.state_paths(harness.root, harness.run_id)
        runner.persist_state(state_path, harness.state)
        runner.unredirected_path(
            harness.root, promoted, "promoted fixture",
        ).unlink()

        completed = subprocess.run(
            [
                sys.executable, str(RUNNER), "status", str(harness.room_path),
                "--project-root", str(harness.root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertRegex(
            completed.stderr, r"(?i)recorded artifact.*missing",
        )

    def test_deleted_promoted_artifact_blocks_advance_before_mutation(self) -> None:
        harness = self.harness("deleted-live-advance-001")
        results = self.record_current_stage(harness)
        promoted = next(
            artifact["path"]
            for result in results for artifact in result["artifacts"]
        )
        original_stage = harness.state["current_stage"]
        runner.unredirected_path(
            harness.root, promoted, "promoted fixture",
        ).unlink()

        with self.assertRaisesRegex(
            runner.RunnerError, r"(?i)recorded artifact.*missing",
        ):
            runner.advance_stage(
                harness.room_path, harness.room, harness.state, harness.root,
            )
        self.assertEqual(harness.state["current_stage"], original_stage)

    def test_dirty_worker_worktree_is_rejected_before_record(self) -> None:
        harness = self.harness("worker-dirty-001")
        task = self.worker_task(harness)
        result = harness.result_for(task)
        worktree = runner.project_path(
            harness.root, task["workspace"], "test workspace",
        )
        (worktree / "app.txt").write_text("uncommitted worker edit\n", encoding="utf-8")

        with self.assertRaisesRegex(
            runner.RunnerError,
            r"(?i)(worktree|workspace).*(dirty|uncommitted|change)",
        ):
            runner.record_result(
                result, harness.room, harness.state, harness.root,
            )

    def test_worker_worktree_head_drift_is_rejected_before_record(self) -> None:
        harness = self.harness("worker-head-001")
        task = self.worker_task(harness)
        result = harness.result_for(task)
        worktree = runner.project_path(
            harness.root, task["workspace"], "test workspace",
        )
        drifted = self.commit_change(worktree, "committed worker edit\n")
        self.assertNotEqual(drifted, harness.commit)

        with self.assertRaisesRegex(
            runner.RunnerError,
            r"(?i)(worktree|workspace).*(HEAD|commit|drift|changed)",
        ):
            runner.record_result(
                result, harness.room, harness.state, harness.root,
            )

    def test_index_concealed_worker_edit_is_rejected_before_record(self) -> None:
        cases = (
            ("--assume-unchanged", "assume"),
            ("--skip-worktree", "skip"),
        )
        for index_flag, label in cases:
            with self.subTest(index_flag=index_flag):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    harness = RoomHarness(
                        root, BUG_ROOM, "trust-index-record-%s-001" % label,
                    )
                    task = self.worker_task(harness)
                    result = harness.result_for(task)
                    worktree = runner.project_path(
                        root, task["workspace"], "test workspace",
                    )
                    self.conceal_tracked_change(
                        worktree, index_flag,
                        "index-concealed worker edit\n",
                    )

                    with self.assertRaises(runner.RunnerError):
                        runner.record_result(
                            result, harness.room, harness.state, root,
                        )

    def test_index_concealed_project_edit_is_rejected_before_advance(self) -> None:
        cases = (
            ("--assume-unchanged", "assume"),
            ("--skip-worktree", "skip"),
        )
        for index_flag, label in cases:
            with self.subTest(index_flag=index_flag):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    harness = RoomHarness(
                        root, BUG_ROOM, "trust-index-advance-%s-001" % label,
                    )
                    for task in runner.issue_tasks(
                        harness.room, harness.state, root,
                    ):
                        runner.record_result(
                            harness.result_for(task), harness.room,
                            harness.state, root,
                        )
                    self.conceal_tracked_change(
                        root, index_flag,
                        "index-concealed project edit\n",
                    )

                    with self.assertRaises(runner.RunnerError):
                        runner.advance_stage(
                            harness.room_path, harness.room, harness.state, root,
                        )

    def test_gate_verdict_cannot_be_swapped_after_result_recording(self) -> None:
        harness = self.harness("verdict-swap-001")
        while harness.state["current_stage"] != "merge_gate":
            harness.complete_stage("GO")
        for task in runner.issue_tasks(
            harness.room, harness.state, harness.root,
        ):
            runner.record_result(
                harness.result_for(task, "NO-GO"), harness.room,
                harness.state, harness.root,
            )
        gate = harness.room["gates"][0]
        evidence = runner.project_path(
            harness.root, gate["evidence"]["artifact"], "gate evidence",
        )
        recorded_digest = harness.state["artifact_provenance"][
            gate["evidence"]["artifact"]
        ]["digest"]
        harness.write_phase_evidence(gate, "GO")
        self.assertNotEqual(runner.sha256_file(evidence), recorded_digest)

        with self.assertRaisesRegex(
            runner.RunnerError,
            r"(?i)(gate evidence|recorded artifact).*(digest|changed|recorded|provenance|promotion)",
        ):
            runner.advance_stage(
                harness.room_path, harness.room, harness.state, harness.root,
            )
        self.assertEqual(harness.state["current_stage"], "merge_gate")

    def test_gate_verdict_swap_during_validation_never_routes_go(self) -> None:
        harness = self.harness("verdict-race-001")
        while harness.state["current_stage"] != "merge_gate":
            harness.complete_stage("GO")
        for task in runner.issue_tasks(
            harness.room, harness.state, harness.root,
        ):
            runner.record_result(
                harness.result_for(task, "NO-GO"), harness.room,
                harness.state, harness.root,
            )
        gate = runner.gate_for_stage(harness.room, "merge_gate")
        self.assertIsNotNone(gate)
        assert gate is not None

        original_run = subprocess.run
        swapped = False

        def swap_after_validator(command, *args, **kwargs):
            nonlocal swapped
            completed = original_run(command, *args, **kwargs)
            if (
                not swapped and isinstance(command, (list, tuple)) and
                any("validate_phase_gate_evidence.py" in str(part)
                    for part in command)
            ):
                # The validator just accepted the recorded NO-GO bytes. Replace
                # the mutable pathname before the runner derives its route.
                harness.write_phase_evidence(gate, "GO")
                swapped = True
            return completed

        with mock.patch.object(
            runner.subprocess, "run", side_effect=swap_after_validator,
        ):
            try:
                runner.advance_stage(
                    harness.room_path, harness.room, harness.state, harness.root,
                )
            except runner.RunnerError:
                # Detecting the race and failing closed is an acceptable result.
                pass

        self.assertTrue(swapped, "the validator-time swap was not exercised")
        merge_statuses = [
            entry.get("gate_status")
            for entry in harness.state["completed_stages"]
            if entry.get("stage") == "merge_gate"
        ]
        self.assertNotIn("GO", merge_statuses)
        self.assertNotEqual(harness.state["status"], "COMPLETE")

    def test_adapter_writes_declared_artifacts_via_controlled_root(self) -> None:
        harness = self.harness("artifact-root-001")
        runner_root, state_path, _ = runner.state_paths(
            harness.root, harness.run_id,
        )
        adapter = runner_root / "artifact_root_adapter.py"
        adapter.parent.mkdir(parents=True, exist_ok=True)
        adapter.write_text(textwrap.dedent("""
            import hashlib
            import json
            import os
            from pathlib import Path

            task = json.loads(Path(os.environ["SOLO_AGENTROOM_TASK"]).read_text(
                encoding="utf-8"
            ))
            artifact_root = Path(
                os.environ["SOLO_AGENTROOM_ARTIFACT_ROOT"]
            ).resolve()
            artifacts = []
            for relative in task["writes"]:
                target = artifact_root.joinpath(*relative.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("adapter evidence\\n", encoding="utf-8")
                digest = "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest()
                artifacts.append({"path": relative, "digest": digest})
            result = {
                "schema": "solo-suite/agentroom-task-result-v1",
                "task_id": task["task_id"],
                "lease_id": task["lease_id"],
                "run_id": task["run_id"],
                "commit_sha": task["commit_sha"],
                "stage": task["stage"],
                "seat": task["seat"],
                "status": "PASS",
                "commands_executed": task["commands"],
                "artifacts": artifacts,
                "proposals": [],
            }
            Path(os.environ["SOLO_AGENTROOM_RESULT"]).write_text(
                json.dumps(result) + "\\n", encoding="utf-8"
            )
        """), encoding="utf-8")

        result = runner.execute_adapter(
            argparse.Namespace(
                project_root=harness.root,
                seat="reproducer",
                adapter=[sys.executable, str(adapter)],
                timeout=30,
            ),
            harness.room, harness.state, runner_root, state_path,
        )

        self.assertEqual(result["status"], "PASS")
        relative = result["artifacts"][0]["path"]
        artifact = runner.project_path(harness.root, relative, "adapter artifact")
        self.assertTrue(artifact.is_file())
        _, worktree = runner.workspace_for_seat(
            harness.room,
            next(seat for seat in harness.room["seats"]
                 if seat["id"] == "reproducer"),
            harness.root,
        )
        worktree_copy = worktree.joinpath(*relative.split("/"))
        self.assertFalse(worktree_copy.exists())

    def test_one_seat_cannot_stage_another_seats_artifact(self) -> None:
        harness = RoomHarness(self.root, FULL_TEAM, "seat-stage-isolation-001")
        tasks = {
            task["seat"]: task
            for task in runner.pending_tasks(harness.room, harness.state, harness.root)
        }
        owner = tasks["repo_analyst"]
        other = tasks["product_manager"]
        result = harness.result_for(owner)
        foreign = runner.unredirected_path(
            Path(owner["artifact_root"]), other["writes"][0], "foreign output",
        )
        foreign.parent.mkdir(parents=True, exist_ok=True)
        foreign.write_text("cross-seat output\n", encoding="utf-8")

        with self.assertRaisesRegex(
            runner.RunnerError, r"(?i)private task output.*undeclared",
        ):
            runner.record_result(
                result, harness.room, harness.state, harness.root,
            )
        self.assertNotIn(owner["task_id"], harness.state["results"])

    def test_redirected_lease_output_root_is_rejected(self) -> None:
        harness = self.harness("lease-output-redirect-001")
        task = self.worker_task(harness)
        output_root = Path(task["artifact_root"])
        output_root.rmdir()
        foreign = self.root / "foreign-lease-output"
        self.create_directory_link(output_root, foreign)
        result = harness.result_for(task)

        with self.assertRaisesRegex(
            runner.RunnerError, r"(?i)(private task output|artifact).*link|reparse",
        ):
            runner.record_result(
                result, harness.room, harness.state, harness.root,
            )
        self.assertNotIn(task["task_id"], harness.state["results"])

    def test_promotion_post_write_failure_restores_previous_bytes(self) -> None:
        harness = self.harness("promotion-rollback-bytes-001")
        task = self.worker_task(harness)
        result = harness.result_for(task)
        relative = result["artifacts"][0]["path"]
        destination = runner.unredirected_path(
            harness.root, relative, "promotion destination",
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"previous-live-bytes\n")

        with mock.patch.object(
            runner, "sha256_file", return_value="sha256:" + "0" * 64,
        ):
            with self.assertRaisesRegex(
                runner.RunnerError, r"(?i)promoted artifact digest mismatch",
            ):
                runner.promote_result_artifacts(
                    result, task, harness.root,
                )
        self.assertEqual(destination.read_bytes(), b"previous-live-bytes\n")

    def test_promotion_rollback_failure_requires_quarantine(self) -> None:
        harness = self.harness("promotion-rollback-quarantine-001")
        task = self.worker_task(harness)
        result = harness.result_for(task)
        relative = result["artifacts"][0]["path"]
        destination = runner.unredirected_path(
            harness.root, relative, "promotion destination",
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        previous = b"previous-live-bytes\n"
        destination.write_bytes(previous)
        real_atomic = runner.atomic_bytes

        def fail_restore(path: Path, payload: bytes) -> None:
            if path == destination and payload == previous:
                raise OSError("injected rollback failure")
            real_atomic(path, payload)

        with mock.patch.object(
            runner, "sha256_file", return_value="sha256:" + "0" * 64,
        ), mock.patch.object(runner, "atomic_bytes", side_effect=fail_restore):
            with self.assertRaisesRegex(
                runner.RunnerError, r"(?i)rollback.*incomplete.*quarantine",
            ):
                runner.promote_result_artifacts(
                    result, task, harness.root,
                )

    def test_one_seat_cannot_write_another_seats_live_artifact(self) -> None:
        harness = RoomHarness(self.root, FULL_TEAM, "seat-live-isolation-001")
        tasks = {
            task["seat"]: task
            for task in runner.pending_tasks(harness.room, harness.state, harness.root)
        }
        owner = tasks["repo_analyst"]
        other = tasks["product_manager"]
        result = harness.result_for(owner)
        foreign = runner.unredirected_path(
            harness.root, other["writes"][0], "foreign live output",
        )
        foreign.parent.mkdir(parents=True, exist_ok=True)
        foreign.write_text("unprovenanced cross-seat output\n", encoding="utf-8")

        with self.assertRaisesRegex(
            runner.RunnerError, r"(?i)undeclared project changes",
        ):
            runner.record_result(
                result, harness.room, harness.state, harness.root,
            )
        self.assertNotIn(owner["task_id"], harness.state["results"])

    def test_manual_record_rejects_undeclared_project_write(self) -> None:
        harness = self.harness("manual-write-001")
        task = self.worker_task(harness)
        result = harness.result_for(task)
        (harness.root / "rogue.txt").write_text(
            "undeclared manual-record side effect\n", encoding="utf-8",
        )

        with self.assertRaisesRegex(
            runner.RunnerError,
            r"(?i)(undeclared|unexpected|untracked).*(path|write|change|input|rogue)",
        ):
            runner.record_result(
                result, harness.room, harness.state, harness.root,
            )

    def test_record_rejects_a_changed_task_baseline(self) -> None:
        harness = self.harness("baseline-tamper-001")
        task = self.worker_task(harness)
        result = harness.result_for(task)
        runner_root, _, _ = runner.state_paths(harness.root, harness.run_id)
        lease = harness.state["task_leases"][task["task_id"]]
        baseline = runner_root / Path(*lease["baseline"].split("/"))
        baseline.write_bytes(baseline.read_bytes() + b" ")
        self.assertNotEqual(runner.sha256_file(baseline), lease["baseline_digest"])

        with self.assertRaisesRegex(
            runner.RunnerError, r"(?i)task baseline.*(missing|changed)",
        ):
            runner.record_result(
                result, harness.room, harness.state, harness.root,
            )
        self.assertNotIn(task["task_id"], harness.state["results"])
        self.assertEqual(lease["status"], "issued")

    def test_next_rejects_a_preseeded_stage_baseline(self) -> None:
        harness = self.harness("baseline-preseed-001")
        harness.complete_stage("GO")
        runner_root, _, _ = runner.state_paths(harness.root, harness.run_id)
        stage = harness.state["current_stage"]
        attempt = harness.state["stage_attempts"][stage]
        baseline = runner_root / "baselines" / ("%s-%d.json" % (stage, attempt))
        runner.atomic_json(baseline, {"forged": "sha256:" + "0" * 64})

        with self.assertRaisesRegex(
            runner.RunnerError, r"(?i)baseline.*preseeded",
        ):
            runner.issue_tasks(harness.room, harness.state, harness.root)

    def test_manual_record_cannot_steal_a_running_adapter_lease(self) -> None:
        harness = self.harness("running-lease-001")
        task = self.worker_task(harness)
        result = harness.result_for(task)
        lease = harness.state["task_leases"][task["task_id"]]
        lease.update({
            "status": "running",
            "started_at": runner.next_marker(),
            "runner_pid": os.getpid(),
            "runner_host": socket.gethostname(),
        })

        with self.assertRaisesRegex(
            runner.RunnerError, r"(?i)no active runner-issued lease",
        ):
            runner.record_result(
                result, harness.room, harness.state, harness.root,
            )
        self.assertNotIn(task["task_id"], harness.state["results"])
        self.assertEqual(lease["status"], "running")

    def test_premature_advance_leaves_the_persisted_run_ready(self) -> None:
        harness = self.harness("premature-advance-001")
        _, state_path, _ = runner.state_paths(harness.root, harness.run_id)
        runner.persist_state(state_path, harness.state)
        before = json.loads(state_path.read_text(encoding="utf-8"))

        advanced = subprocess.run(
            [
                sys.executable, str(RUNNER), "advance", str(harness.room_path),
                "--project-root", str(harness.root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )

        self.assertNotEqual(advanced.returncode, 0, advanced.stdout + advanced.stderr)
        self.assertIn("pending or running tasks", advanced.stderr)
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["status"], "READY")
        self.assertIsNone(persisted["blocker"])
        self.assertEqual(persisted["current_stage"], before["current_stage"])
        self.assertEqual(persisted["state_revision"], before["state_revision"])
        self.assertFalse(any(
            item.get("action") == "block" for item in persisted["history"]
        ))

    def test_state_lock_is_released_when_the_holder_crashes(self) -> None:
        lock = self.root / "crash-recovery.lock"
        marker = self.root / "lock-acquired.txt"
        script = textwrap.dedent("""
            from pathlib import Path
            import sys
            import time
            sys.path.insert(0, %r)
            import run_room
            with run_room.exclusive(Path(%r), timeout=2):
                Path(%r).write_text("locked\\n", encoding="utf-8")
                time.sleep(30)
        """) % (str(ROOM_SKILL / "scripts"), str(lock), str(marker))
        holder = subprocess.Popen(
            [sys.executable, "-c", script], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        )
        try:
            deadline = time.monotonic() + 8
            while not marker.is_file() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(marker.is_file(), "child never acquired the test lock")
            holder.terminate()
            stdout, stderr = holder.communicate(timeout=10)
            self.assertIsNotNone(holder.returncode, stdout + stderr)
            self.assertTrue(lock.is_file(), "lock metadata should remain for diagnosis")
            with runner.exclusive(lock, timeout=2):
                pass
        finally:
            self.stop_process(holder)

    def test_windows_lock_does_not_write_before_byte_lock(self) -> None:
        operations = []

        class FakeHandle:
            def fileno(self) -> int:
                return 42

            def seek(self, offset: int) -> None:
                operations.append(("seek", offset))

            def read(self, size: int) -> bytes:
                operations.append(("read", size))
                return b""

            def truncate(self) -> None:
                operations.append(("truncate",))

            def write(self, value: bytes) -> int:
                operations.append(("write", value))
                return len(value)

            def flush(self) -> None:
                operations.append(("flush",))

            def close(self) -> None:
                operations.append(("close",))

        fake_handle = FakeHandle()
        fake_open = mock.Mock(return_value=fake_handle)
        fake_msvcrt = mock.Mock()
        fake_msvcrt.LK_NBLCK = 1
        fake_msvcrt.LK_UNLCK = 2
        fake_msvcrt.locking.side_effect = lambda _fd, mode, size: operations.append(
            ("locking", mode, size)
        )
        lock = self.root / "windows-contention.lock"

        with (
            mock.patch.object(Path, "open", fake_open),
            mock.patch.object(runner.os, "name", "nt"),
            mock.patch.dict(sys.modules, {"msvcrt": fake_msvcrt}),
        ):
            with runner.exclusive(lock, timeout=0.1):
                operations.append(("critical",))

        fake_open.assert_called_once_with("a+b", buffering=0)
        acquired = operations.index(("locking", fake_msvcrt.LK_NBLCK, 1))
        file_mutations = [
            index for index, operation in enumerate(operations)
            if operation[0] in {"truncate", "write", "flush"}
        ]
        critical = operations.index(("critical",))
        unlocked = operations.index(("locking", fake_msvcrt.LK_UNLCK, 1))
        closed = operations.index(("close",))
        self.assertLess(acquired, min(file_mutations))
        self.assertLess(max(file_mutations), critical)
        self.assertLess(critical, unlocked)
        self.assertLess(unlocked, closed)
        self.assertFalse(any(operation[0] == "read" for operation in operations))

    def test_status_recovers_a_crashed_adapter_lease_fail_closed(self) -> None:
        harness = self.harness("crashed-adapter-001")
        task = self.worker_task(harness)
        lease = harness.state["task_leases"][task["task_id"]]
        runner_root, state_path, _ = runner.state_paths(
            harness.root, harness.run_id,
        )
        snapshot_relative = "leases/%s/execution-baseline.json" % lease["lease_id"]
        snapshot_path = runner_root / Path(*snapshot_relative.split("/"))
        runner.atomic_json(
            snapshot_path, runner.snapshot(harness.root, runner_root, harness.room),
        )
        lease.update({
            "status": "running",
            "started_at": runner.next_marker(),
            "runner_pid": 99_999_999,
            "runner_host": socket.gethostname(),
            "runner_identity": "fixture-dead-runner",
            "execution_snapshot": snapshot_relative,
            "execution_snapshot_digest": runner.sha256_file(snapshot_path),
        })
        runner.persist_state(state_path, harness.state)
        status = subprocess.run(
            [
                sys.executable, str(RUNNER), "status", str(harness.room_path),
                "--project-root", str(harness.root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
        recovered = json.loads(status.stdout)
        self.assertEqual(recovered["status"], "BLOCKED")
        self.assertIn("exited before finalization", recovered["blocker"])
        self.assertEqual(
            recovered["task_leases"][task["task_id"]]["status"], "failed",
        )

    def test_runner_pid_reuse_does_not_suppress_crash_recovery(self) -> None:
        harness = self.harness("runner-pid-reuse-001")
        task = self.worker_task(harness)
        lease = harness.state["task_leases"][task["task_id"]]
        runner_root, _, _ = runner.state_paths(harness.root, harness.run_id)
        snapshot_relative = "leases/%s/execution-baseline.json" % lease["lease_id"]
        snapshot_path = runner.unredirected_path(
            runner_root, snapshot_relative, "execution snapshot",
        )
        runner.atomic_json(
            snapshot_path, runner.snapshot(harness.root, runner_root, harness.room),
        )
        lease.update({
            "status": "running",
            "started_at": runner.next_marker(),
            "runner_pid": 4242,
            "runner_host": socket.gethostname(),
            "runner_identity": "original-process-identity",
            "execution_snapshot": snapshot_relative,
            "execution_snapshot_digest": runner.sha256_file(snapshot_path),
        })

        with mock.patch.object(
            runner, "_process_identity", return_value="reused-process-identity",
        ):
            recovered = runner.recover_crashed_adapter_leases(
                harness.state, harness.room, harness.root,
            )
        self.assertTrue(recovered)
        self.assertEqual(lease["status"], "failed")
        self.assertEqual(harness.state["status"], "BLOCKED")

    def test_crashed_runner_terminates_its_recorded_adapter_tree(self) -> None:
        harness = self.harness("orphan-adapter-001")
        runner_root, state_path, _ = runner.state_paths(
            harness.root, harness.run_id,
        )
        runner.persist_state(state_path, harness.state)
        heartbeat = harness.root / "orphan-heartbeat.txt"
        adapter = runner_root / "orphan_adapter.py"
        adapter.write_text(textwrap.dedent("""
            import os
            from pathlib import Path
            import time

            task = Path(os.environ["SOLO_AGENTROOM_TASK"])
            heartbeat = task.parents[5] / "orphan-heartbeat.txt"
            counter = 0
            while True:
                counter += 1
                heartbeat.write_text(str(counter) + "\\n", encoding="utf-8")
                time.sleep(0.05)
        """), encoding="utf-8")
        process = subprocess.Popen(
            [
                sys.executable, str(RUNNER), "execute", str(harness.room_path),
                "--project-root", str(harness.root), "--seat", "reproducer",
                "--adapter", sys.executable, str(adapter),
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace",
        )
        task_id = "%s:reproduce:reproducer:1" % harness.run_id
        adapter_pid = None
        adapter_identity = None
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                try:
                    projected = json.loads(state_path.read_text(encoding="utf-8"))
                    lease = projected["task_leases"][task_id]
                    adapter_pid = lease.get("adapter_pid")
                    adapter_identity = lease.get("adapter_identity")
                except (OSError, KeyError, json.JSONDecodeError):
                    pass
                if (isinstance(adapter_pid, int) and adapter_identity and
                        heartbeat.is_file()):
                    break
                time.sleep(0.05)
            self.assertIsInstance(adapter_pid, int)
            self.assertIsInstance(adapter_identity, str)
            process.terminate()
            process.communicate(timeout=10)

            status = subprocess.run(
                [
                    sys.executable, str(RUNNER), "status", str(harness.room_path),
                    "--project-root", str(harness.root),
                ],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30,
            )
            self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
            recovered = json.loads(status.stdout)
            self.assertEqual(recovered["status"], "BLOCKED")
            self.assertEqual(recovered["task_leases"][task_id]["status"], "failed")
            self.assertIsNone(runner._process_identity(adapter_pid))
            self.assertIn("orphan-heartbeat.txt", recovered["unexpected_changes"])
        finally:
            self.stop_process(process)
            if (isinstance(adapter_pid, int) and
                    isinstance(adapter_identity, str) and
                    runner._process_identity(adapter_pid) == adapter_identity):
                runner.terminate_adapter_tree(adapter_pid, adapter_identity)

    def test_incomplete_artifact_promotion_is_quarantined(self) -> None:
        harness = self.harness("promotion-crash-001")
        task = self.worker_task(harness)
        result = harness.result_for(task)
        runner_root, state_path, _ = runner.state_paths(
            harness.root, harness.run_id,
        )
        runner.persist_state(state_path, harness.state)
        lease = harness.state["task_leases"][task["task_id"]]
        runner.persist_pending_promotion(
            result, lease, harness.state, runner_root, state_path,
        )
        runner.promote_result_artifacts(result, task, harness.root)

        status = subprocess.run(
            [
                sys.executable, str(RUNNER), "status", str(harness.room_path),
                "--project-root", str(harness.root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
        recovered = json.loads(status.stdout)
        self.assertEqual(recovered["status"], "BLOCKED")
        self.assertEqual(
            recovered["task_leases"][task["task_id"]]["status"], "failed",
        )
        promoted = result["artifacts"][0]["path"]
        self.assertIn(promoted, recovered["unexpected_changes"])

    def test_initialization_rolls_back_worktrees_after_trust_failure(self) -> None:
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "config", "user.name", "Runner Test"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.root), "config", "user.email",
             "runner@example.invalid"], check=True,
        )
        (self.root / ".gitignore").write_text(
            "artifacts/\nplans/\nworktrees/\n.solo/\n", encoding="utf-8",
        )
        (self.root / "app.txt").write_text("fixture\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.root), "add", ".gitignore", "app.txt"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "--quiet", "-m", "fixture"],
            check=True,
        )
        commit = subprocess.check_output(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True,
        ).strip()
        room_path = self.root / "plans/trust-init-rollback-001.json"
        room_path.parent.mkdir(parents=True)
        prepared = subprocess.run(
            [
                sys.executable, str(ROOM_SKILL / "scripts/prepare_run.py"),
                str(BUG_ROOM), str(room_path), "--run-id",
                "trust-init-rollback-001", "--profile", "saas-application",
                "--suite", str(ROOT), "--project-root", str(self.root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
        room = json.loads(room_path.read_text(encoding="utf-8"))
        with mock.patch.object(
            runner, "install_trusted_validators",
            side_effect=runner.TrustError("injected trust-copy failure"),
        ):
            with self.assertRaisesRegex(runner.TrustError, "injected"):
                runner.initialize(argparse.Namespace(
                    room=room_path, project_root=self.root, suite=ROOT,
                    commit=commit, environment="staging",
                ))
        _, state_path, _ = runner.state_paths(self.root, room["run_id"])
        self.assertFalse(state_path.exists())
        for workspace in room["workspaces"]:
            if workspace["type"] == "worktree":
                self.assertFalse(runner.project_path(
                    self.root, workspace["path"], "rolled-back worktree",
                ).exists())

    def test_initialization_rejects_a_preseeded_control_root(self) -> None:
        harness = self.harness("control-root-base-001")
        room_path = self.root / "plans/control-root-preseed-001.json"
        prepared = subprocess.run(
            [
                sys.executable,
                str(ROOM_SKILL / "scripts/prepare_run.py"),
                str(BUG_ROOM), str(room_path),
                "--run-id", "control-root-preseed-001",
                "--profile", "saas-application",
                "--suite", str(ROOT),
                "--project-root", str(self.root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
        room = json.loads(room_path.read_text(encoding="utf-8"))
        runner_root, state_path, _ = runner.state_paths(
            self.root, "control-root-preseed-001",
        )
        runner_root.mkdir(parents=True, exist_ok=True)
        marker = runner_root / "attacker-preseed.txt"
        marker.write_text("do not overwrite\n", encoding="utf-8")

        with self.assertRaisesRegex(
            runner.RunnerError, r"(?i)control root.*preseeded",
        ):
            runner.initialize(argparse.Namespace(
                room=room_path, project_root=self.root, suite=ROOT,
                commit=harness.commit, environment="staging",
            ))
        self.assertTrue(marker.is_file())
        self.assertFalse(state_path.exists())
        for workspace in room["workspaces"]:
            if workspace["type"] == "worktree":
                self.assertFalse(runner.project_path(
                    self.root, workspace["path"], "preseeded worktree",
                ).exists())

    def test_prepare_rejects_redirected_run_registry(self) -> None:
        external_temp = tempfile.TemporaryDirectory()
        self.addCleanup(external_temp.cleanup)
        external = Path(external_temp.name)
        self.create_directory_link(self.root / "artifacts", external)
        output = self.root / "plans" / "redirected-registry-001.json"

        completed = subprocess.run(
            [
                sys.executable,
                str(ROOM_SKILL / "scripts" / "prepare_run.py"),
                str(BUG_ROOM), str(output),
                "--run-id", "redirected-registry-001",
                "--profile", "saas-application",
                "--suite", str(ROOT),
                "--project-root", str(self.root),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )

        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertRegex(completed.stdout, r"(?i)registry.*(link|reparse|controlled)")
        self.assertFalse(output.exists())
        self.assertFalse((external / "runs" / ".registry").exists())

    def test_distinct_same_stage_adapters_execute_concurrently(self) -> None:
        harness = self.harness("parallel-001")
        runner_root, state_path, _ = runner.state_paths(
            harness.root, harness.run_id,
        )
        runner.persist_state(state_path, harness.state)
        adapter = runner_root / "parallel_adapter.py"
        adapter.write_text(textwrap.dedent("""
            import hashlib
            import json
            import os
            from pathlib import Path
            import time

            task_path = Path(os.environ["SOLO_AGENTROOM_TASK"])
            task = json.loads(task_path.read_text(encoding="utf-8"))
            trace = task_path.parents[1] / "parallel-trace"
            trace.mkdir(parents=True, exist_ok=True)
            (trace / (task["seat"] + ".ready")).write_text(
                "ready\\n", encoding="utf-8"
            )
            deadline = time.monotonic() + 20
            while len(list(trace.glob("*.ready"))) < 2:
                if time.monotonic() >= deadline:
                    raise SystemExit("other same-stage adapter never overlapped")
                time.sleep(0.05)

            artifact_root = Path(os.environ["SOLO_AGENTROOM_ARTIFACT_ROOT"])
            artifacts = []
            for relative in task["writes"]:
                target = artifact_root.joinpath(*relative.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(task["seat"] + "\\n", encoding="utf-8")
                artifacts.append({
                    "path": relative,
                    "digest": "sha256:" + hashlib.sha256(
                        target.read_bytes()
                    ).hexdigest(),
                })
            result = {
                "schema": "solo-suite/agentroom-task-result-v1",
                "task_id": task["task_id"],
                "lease_id": task["lease_id"],
                "run_id": task["run_id"],
                "commit_sha": task["commit_sha"],
                "stage": task["stage"],
                "seat": task["seat"],
                "status": "PASS",
                "commands_executed": task["commands"],
                "artifacts": artifacts,
                "proposals": [],
            }
            Path(os.environ["SOLO_AGENTROOM_RESULT"]).write_text(
                json.dumps(result) + "\\n", encoding="utf-8"
            )
        """), encoding="utf-8")
        base = [
            sys.executable, str(RUNNER), "execute", str(harness.room_path),
            "--project-root", str(harness.root),
        ]
        processes = [
            subprocess.Popen(
                base + ["--seat", seat, "--adapter", sys.executable, str(adapter)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace",
            )
            for seat in ("memory_steward", "reproducer")
        ]
        try:
            outputs = [process.communicate(timeout=30) for process in processes]
            for process, (stdout, stderr) in zip(processes, outputs):
                self.assertEqual(process.returncode, 0, stdout + stderr)
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            stage_results = [
                result for result in persisted["results"].values()
                if result["stage"] == "reproduce"
            ]
            self.assertEqual({result["seat"] for result in stage_results}, {
                "memory_steward", "reproducer",
            })
        finally:
            for process in processes:
                self.stop_process(process)

    def test_same_seat_cannot_be_executed_twice_concurrently(self) -> None:
        harness = self.harness("same-seat-001")
        runner_root, state_path, _ = runner.state_paths(
            harness.root, harness.run_id,
        )
        runner.persist_state(state_path, harness.state)
        started = runner_root / "same-seat.started"
        release = runner_root / "same-seat.release"
        adapter = runner_root / "same_seat_adapter.py"
        adapter.write_text(textwrap.dedent("""
            import hashlib
            import json
            import os
            from pathlib import Path
            import time

            task_path = Path(os.environ["SOLO_AGENTROOM_TASK"])
            task = json.loads(task_path.read_text(encoding="utf-8"))
            runner_root = task_path.parents[1]
            (runner_root / "same-seat.started").write_text(
                "started\\n", encoding="utf-8"
            )
            deadline = time.monotonic() + 15
            while not (runner_root / "same-seat.release").is_file():
                if time.monotonic() >= deadline:
                    raise SystemExit("test never released the adapter")
                time.sleep(0.05)

            artifact_root = Path(os.environ["SOLO_AGENTROOM_ARTIFACT_ROOT"])
            artifacts = []
            for relative in task["writes"]:
                target = artifact_root.joinpath(*relative.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("same-seat evidence\\n", encoding="utf-8")
                artifacts.append({
                    "path": relative,
                    "digest": "sha256:" + hashlib.sha256(
                        target.read_bytes()
                    ).hexdigest(),
                })
            result = {
                "schema": "solo-suite/agentroom-task-result-v1",
                "task_id": task["task_id"],
                "lease_id": task["lease_id"],
                "run_id": task["run_id"],
                "commit_sha": task["commit_sha"],
                "stage": task["stage"],
                "seat": task["seat"],
                "status": "PASS",
                "commands_executed": task["commands"],
                "artifacts": artifacts,
                "proposals": [],
            }
            Path(os.environ["SOLO_AGENTROOM_RESULT"]).write_text(
                json.dumps(result) + "\\n", encoding="utf-8"
            )
        """), encoding="utf-8")
        command = [
            sys.executable, str(RUNNER), "execute", str(harness.room_path),
            "--project-root", str(harness.root), "--seat", "reproducer",
            "--adapter", sys.executable, str(adapter),
        ]
        first = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace",
        )
        second = None
        first_output = ("", "")
        try:
            deadline = time.monotonic() + 10
            while not started.is_file() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(started.is_file(), "first adapter never started")
            second = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30,
            )
        finally:
            release.write_text("release\n", encoding="utf-8")
            try:
                first_output = first.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                first.kill()
                first_output = first.communicate(timeout=10)

        self.assertIsNotNone(second)
        assert second is not None
        self.assertNotEqual(
            second.returncode, 0, second.stdout + second.stderr,
        )
        self.assertIn("pending task", second.stderr)
        self.assertEqual(
            first.returncode, 0, first_output[0] + first_output[1],
        )
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        task_id = "%s:reproduce:reproducer:1" % harness.run_id
        self.assertEqual(persisted["task_leases"][task_id]["status"], "recorded")
        self.assertIn(task_id, persisted["results"])


if __name__ == "__main__":
    unittest.main()
