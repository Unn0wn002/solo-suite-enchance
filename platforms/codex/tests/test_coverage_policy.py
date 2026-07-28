"""Coverage-scope policy must remain explicit and narrowly bounded."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CoveragePolicy(unittest.TestCase):
    def test_only_authoring_helpers_are_omitted_from_the_gated_scope(self):
        policy = json.loads((ROOT / "coverage-policy.json").read_text(encoding="utf-8"))
        omitted = policy["gated_runtime"]["omitted_authoring_helpers"]
        expected = {
            "tools/build_codex_metadata.py",
            "tools/generate_skill_metadata.py",
            "tools/normalize_skill_contracts.py",
            "tools/sync_from_claude.py",
            "tools/translate_references.py",
            "tools/update_cheatsheet.py",
        }
        self.assertEqual(set(omitted), expected)
        self.assertEqual(policy["gated_runtime"]["floor_percent"], 68)
        for relative in omitted:
            self.assertTrue((ROOT / relative).is_file(), relative)
        for forbidden in (
            "plugins/gate/lib/gate_policy.py",
            "plugins/gate/skills/production-readiness-reviewer/scripts/check_evidence.py",
            "plugins/ai/skills/agent-room-templates/scripts/run_room.py",
            "plugins/site-doctor/skills/security-review/scripts/scan_secrets.py",
            "tools/parity.py",
            "tools/package_release.py",
        ):
            self.assertNotIn(forbidden, omitted)

    def test_workflows_keep_full_report_and_same_omit_scope(self):
        policy = json.loads((ROOT / "coverage-policy.json").read_text(encoding="utf-8"))
        omit = policy["gated_runtime"]["omitted_authoring_helpers"]
        for workflow in (".github/workflows/ci.yml", ".github/workflows/publish-release.yml"):
            text = (ROOT / workflow).read_text(encoding="utf-8")
            self.assertIn("coverage report --show-missing > dist/coverage-full.txt", text)
            self.assertIn("coverage json -o dist/coverage-full.json", text)
            for relative in omit:
                self.assertIn(relative, text)

    def test_child_process_bootstrap_is_valid_without_coverage_installed(self):
        bootstrap = ROOT / ".github/coverage-bootstrap/sitecustomize.py"
        compile(bootstrap.read_text(encoding="utf-8"), str(bootstrap), "exec")
        self.assertIn("except ImportError", bootstrap.read_text(encoding="utf-8"))
        self.assertIn("    pass", bootstrap.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
