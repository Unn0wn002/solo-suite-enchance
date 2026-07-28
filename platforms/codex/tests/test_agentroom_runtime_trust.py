"""Content-pinned AgentRoom runtime trust regressions."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT / "plugins/ai/skills/agent-room-templates/scripts/runtime_trust.py"
)
spec = importlib.util.spec_from_file_location("agentroom_runtime_trust", SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot import AgentRoom runtime trust helper")
trust = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trust)


class RuntimeTrust(unittest.TestCase):
    def make_suite(self, root: Path) -> None:
        skill = root / "plugins/example/skills/example-skill/SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(
            "---\nname: example-skill\ndescription: Fixture.\n---\n",
            encoding="utf-8",
        )
        for name, relative in trust.VALIDATOR_PATHS.items():
            validator = root.joinpath(*relative.split("/"))
            validator.parent.mkdir(parents=True, exist_ok=True)
            validator.write_text(
                "#!/usr/bin/env python3\nprint(%r)\n" % name,
                encoding="utf-8",
            )
        for name, relative in trust.RUNTIME_PATHS.items():
            runtime = root.joinpath(*relative.split("/"))
            runtime.parent.mkdir(parents=True, exist_ok=True)
            runtime.write_text(
                "#!/usr/bin/env python3\n# %s fixture\n" % name,
                encoding="utf-8",
            )

    def test_suite_and_validator_tampering_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "suite"
            runner_root = Path(temp) / "runner"
            self.make_suite(root)
            expected = trust.suite_trust(root)
            self.assertEqual(expected["skill_count"], 1)
            self.assertEqual(trust.verify_suite_trust(root, expected), expected)
            installed = trust.install_trusted_validators(
                root, expected, runner_root,
            )
            self.assertEqual(set(installed), {"phase", "production"})
            phase = trust.trusted_validator(runner_root, expected, "phase")
            phase.write_text("print('tampered')\n", encoding="utf-8")
            with self.assertRaisesRegex(trust.TrustError, "missing or changed"):
                trust.trusted_validator(runner_root, expected, "phase")

            trust.install_trusted_validators(root, expected, runner_root)
            trusted_runtime = runner_root.joinpath(
                "trusted-suite", *trust.RUNTIME_PATHS["run_room"].split("/")
            )
            trusted_runtime.write_text("tampered runtime\n", encoding="utf-8")
            with self.assertRaisesRegex(trust.TrustError, "missing or changed"):
                trust.verify_trusted_install(runner_root, expected)

            skill = root / "plugins/example/skills/example-skill/SKILL.md"
            skill.write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(trust.TrustError, "suite trust mismatch"):
                trust.verify_suite_trust(root, expected)

            self.make_suite(root)
            expected = trust.suite_trust(root)
            runtime = root.joinpath(*trust.RUNTIME_PATHS["git_trust"].split("/"))
            runtime.write_text("changed runtime\n", encoding="utf-8")
            with self.assertRaisesRegex(trust.TrustError, "suite trust mismatch"):
                trust.verify_suite_trust(root, expected)


if __name__ == "__main__":
    unittest.main()
