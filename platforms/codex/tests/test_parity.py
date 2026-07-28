"""Regression tests for canonical Claude-to-Codex body parity."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("suite_parity", ROOT / "tools/parity.py")
assert SPEC is not None and SPEC.loader is not None
PARITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PARITY)


class CommandBodyParityTests(unittest.TestCase):
    def test_manifest_pins_all_125_command_derived_skill_bodies(self) -> None:
        manifest = json.loads(
            (ROOT / "parity/capabilities.json").read_text(encoding="utf-8")
        )
        commands = manifest["commands"]
        self.assertEqual(len(commands), 125)
        for item in commands:
            with self.subTest(skill=item["skill_name"]):
                if f"{item['plugin']}:{item['skill_name']}" in PARITY.BODY_ADAPTER_WAIVERS:
                    continue
                expected = item.get("normalized_sha256")
                self.assertRegex(expected or "", r"^[0-9a-f]{64}$")
                target = ROOT / item["target_path"]
                actual = hashlib.sha256(
                    PARITY.normalized_command_target(
                        target.read_text(encoding="utf-8")
                    ).encode("utf-8")
                ).hexdigest()
                self.assertEqual(actual, expected)

    def test_body_mutation_with_unchanged_frontmatter_names_the_skill(self) -> None:
        source_fixture = (
            ROOT
            / "parity/canonical-source-overrides/plugins/browser/commands/form-submit-test.md"
        )
        target_fixture = (
            ROOT / "plugins/browser/skills/browser-form-submit-test/SKILL.md"
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            target = root / "target"
            source_path = source / "plugins/browser/commands/form-submit-test.md"
            target_path = (
                target / "plugins/browser/skills/browser-form-submit-test/SKILL.md"
            )
            source_path.parent.mkdir(parents=True)
            target_path.parent.mkdir(parents=True)
            shutil.copy2(source_fixture, source_path)
            shutil.copy2(target_fixture, target_path)

            source_text = source_path.read_text(encoding="utf-8")
            expected = PARITY.normalized_command_skill(
                source_text,
                "browser",
                "form-submit-test",
                ["browser-qa-engineer"],
            )
            item = {
                "plugin": "browser",
                "command": "form-submit-test",
                "skill_name": "browser-form-submit-test",
                "source_path": "plugins/browser/commands/form-submit-test.md",
                "target_path": (
                    "plugins/browser/skills/browser-form-submit-test/SKILL.md"
                ),
                "source_sha256": PARITY.sha256(source_path),
                "normalized_sha256": hashlib.sha256(
                    expected.encode("utf-8")
                ).hexdigest(),
            }

            baseline_errors: list[str] = []
            PARITY._check_command_skills(
                source,
                target,
                [item],
                ["browser-qa-engineer"],
                set(),
                baseline_errors,
            )
            self.assertEqual(baseline_errors, [])

            original_name = PARITY._target_frontmatter_name(target_path)
            changed = target_path.read_text(encoding="utf-8").replace(
                "Drive a real browser/automation tool",
                "Drive an unverified browser/automation tool",
                1,
            )
            target_path.write_bytes(changed.encode("utf-8"))
            self.assertEqual(
                PARITY._target_frontmatter_name(target_path), original_name
            )

            errors: list[str] = []
            PARITY._check_command_skills(
                source,
                target,
                [item],
                ["browser-qa-engineer"],
                set(),
                errors,
            )
            self.assertEqual(
                errors,
                [
                    "normalized command-derived skill body mismatch: "
                    "browser:browser-form-submit-test ($browser-form-submit-test)"
                ],
            )


if __name__ == "__main__":
    unittest.main()
