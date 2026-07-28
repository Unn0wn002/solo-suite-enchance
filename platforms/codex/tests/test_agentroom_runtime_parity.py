"""Fail-closed parity checks between AgentRoom validation and execution."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ROOM_SKILL = ROOT / "plugins/ai/skills/agent-room-templates"
SCRIPTS = ROOM_SKILL / "scripts"
BUG_ROOM = ROOM_SKILL / "agentsrooms/bug-fix-loop.json"

sys.path.insert(0, str(SCRIPTS))
try:
    import run_room as runner
    import validate_rooms as validator
finally:
    sys.path.pop(0)


def room_fixture() -> dict:
    return json.loads(BUG_ROOM.read_text(encoding="utf-8"))


def runtime_accepts_path(value: object) -> bool:
    try:
        runner.safe_relative(value, "fixture")
    except runner.RunnerError:
        return False
    return True


class CommandInventoryParity(unittest.TestCase):
    def test_supplied_suite_without_skills_fails_closed(self):
        room = room_fixture()
        declared = sorted({
            command
            for seat in room["seats"]
            for command in seat["commands"]
        })
        with tempfile.TemporaryDirectory() as temp:
            suite = Path(temp)
            # Even an apparently valid stale conversion map is not executable
            # proof when no SKILL.md files exist in the supplied suite.
            (suite / "command-map.json").write_text(
                json.dumps({
                    "commands": [
                        {"codex_invocation": command} for command in declared
                    ]
                }),
                encoding="utf-8",
            )
            self.assertEqual(validator.known_commands(str(suite)), set())
            problems = validator.validate_files(
                [str(BUG_ROOM)], suite_root=str(suite)
            )

        self.assertTrue(
            any("does not exist in this suite" in problem for problem in problems),
            problems,
        )

    def test_no_suite_still_means_inventory_check_was_not_requested(self):
        self.assertIsNone(validator.known_commands(None))


class WorkspaceRuntimeParity(unittest.TestCase):
    def test_validator_rejects_workspace_type_the_runner_cannot_materialize(self):
        room = room_fixture()
        workspace = next(
            item for item in room["workspaces"] if item["type"] == "worktree"
        )
        workspace["type"] = "read-only"
        problems = validator.validate_room(
            room, "fixture.json", known=validator.known_commands(str(ROOT))
        )
        self.assertTrue(
            any("workspace %r has invalid type" % workspace["id"] in problem
                for problem in problems),
            problems,
        )


class PathRuntimeParity(unittest.TestCase):
    def assert_path_contract(self, value: object, expected: bool) -> None:
        self.assertEqual(
            validator.is_portable_relative_path(value), expected,
            "validator decision for %r" % (value,),
        )
        self.assertEqual(
            runtime_accepts_path(value), expected,
            "runner decision for %r" % (value,),
        )

    def test_portable_paths_are_accepted_by_validator_and_runner(self):
        for value in (
            ".solo/",
            "artifacts/runs/live-run-001/report.json",
            "worktrees/runs/live-run-001/frontend",
            "reports/user-facing summary.json",
            "reports/valid-unicode-ไทย.json",
        ):
            with self.subTest(value=value):
                self.assert_path_contract(value, True)

    def test_dangerous_paths_are_rejected_by_validator_and_runner(self):
        for value in (
            None,
            "",
            " ",
            "/absolute/path",
            "C:/absolute/path",
            "C:drive-relative",
            "../escape",
            "safe/../escape",
            "safe/./file.json",
            "safe//file.json",
            "safe\\file.json",
            "safe/\x00file.json",
            "//server/share/file.json",
            "artifacts/CON/report.json",
            "artifacts/nul.txt",
            "artifacts/report.",
            "artifacts/report ",
            "artifacts/report:stream",
            "artifacts/<report>.json",
            "artifacts/report?.json",
        ):
            with self.subTest(value=value):
                self.assert_path_contract(value, False)

    def test_room_validation_uses_the_same_path_contract(self):
        room = copy.deepcopy(room_fixture())
        workspace = next(
            item for item in room["workspaces"] if item["type"] == "worktree"
        )
        workspace["path"] = "worktrees/CON/worker"
        problems = validator.validate_room(
            room, "fixture.json", known=validator.known_commands(str(ROOT))
        )
        self.assertTrue(
            any("non-portable path" in problem for problem in problems), problems
        )


if __name__ == "__main__":
    unittest.main()
