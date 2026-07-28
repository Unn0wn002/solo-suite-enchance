"""Codex-native animation audit coverage and scanner regression checks."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SITE_DOCTOR = ROOT / "plugins" / "site-doctor"
SKILLS = SITE_DOCTOR / "skills"


class AnimationPluginTests(unittest.TestCase):
    def test_animation_skill_and_workflow_are_explicit(self) -> None:
        specialist = SKILLS / "animation-design-audit"
        workflow = SKILLS / "site-doctor-animation"
        self.assertTrue((specialist / "SKILL.md").is_file())
        self.assertTrue((specialist / "scripts" / "animation_check.py").is_file())
        self.assertTrue((workflow / "SKILL.md").is_file())

        agent = (workflow / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("$site-doctor-animation", agent)
        self.assertRegex(agent, r"allow_implicit_invocation:\s*false")

        content = (workflow / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("$animation-design-audit", content)
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", content)
        self.assertNotIn("$ARGUMENTS", content)

    def test_animation_command_is_mapped(self) -> None:
        mapping = json.loads((ROOT / "command-map.json").read_text(encoding="utf-8"))
        entries = [
            entry
            for entry in mapping
            if entry["legacy_invocation"] == "/site-doctor:animation"
        ]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["skill_invocation"], "$site-doctor-animation")
        self.assertEqual(
            entries[0]["target_path"],
            "plugins/site-doctor/skills/site-doctor-animation/SKILL.md",
        )

    def test_aggregate_audits_route_animation_when_code_is_available(self) -> None:
        audit_site = (SKILLS / "site-doctor-audit-site" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        full_checkup = (
            SKILLS / "site-doctor-full-checkup" / "SKILL.md"
        ).read_text(encoding="utf-8")
        website_audit = (SKILLS / "website-audit" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("$site-doctor-animation", audit_site)
        self.assertIn("$site-doctor-animation", full_checkup)
        self.assertIn("animation-design-audit", website_audit)
        self.assertIn("animation", full_checkup.lower())

    def test_scanner_has_the_v130_cleanup_signals(self) -> None:
        scanner = (
            SKILLS / "animation-design-audit" / "scripts" / "animation_check.py"
        ).read_text(encoding="utf-8")
        self.assertIn(r"gsap\.killTweensOf\s*\(", scanner)
        self.assertIn(r'overwrite\s*:\s*(?:true|["\']auto["\'])', scanner)
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", scanner)
        self.assertNotRegex(scanner, re.compile(r"^/site-doctor:", re.MULTILINE))


if __name__ == "__main__":
    unittest.main()
