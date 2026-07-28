"""Codex-native SEO plugin coverage and migration checks."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "seo"


class SeoPluginTests(unittest.TestCase):
    def test_plugin_is_manifested_and_listed_in_marketplace(self) -> None:
        manifest = json.loads(
            (PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], "seo")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["interface"]["displayName"], "Solo SEO")

        marketplace = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        entries = {entry["name"]: entry for entry in marketplace["plugins"]}
        self.assertIn("seo", entries)
        self.assertEqual(entries["seo"]["source"]["path"], "./plugins/seo")
        self.assertEqual(entries["seo"]["policy"]["installation"], "AVAILABLE")

    def test_all_specialists_and_audit_entrypoint_are_present(self) -> None:
        skill_roots = {
            path.parent.name for path in (PLUGIN / "skills").glob("*/SKILL.md")
        }
        expected = {
            "seo",
            "seo-audit",
            "seo-backlinks",
            "seo-cluster",
            "seo-competitor-pages",
            "seo-content",
            "seo-content-brief",
            "seo-drift",
            "seo-ecommerce",
            "seo-flow",
            "seo-geo",
            "seo-google",
            "seo-hreflang",
            "seo-images",
            "seo-local",
            "seo-maps",
            "seo-page",
            "seo-plan",
            "seo-programmatic",
            "seo-schema",
            "seo-sitemap",
            "seo-sxo",
            "seo-technical",
        }
        self.assertEqual(skill_roots, expected)
        for skill in expected:
            agent = (PLUGIN / "skills" / skill / "agents" / "openai.yaml").read_text(
                encoding="utf-8"
            )
            self.assertIn(f"${skill}", agent)
            self.assertRegex(agent, r"allow_implicit_invocation:\s*false")

    def test_legacy_commands_map_to_native_skills_without_losing_specialists(self) -> None:
        mapping = json.loads((ROOT / "command-map.json").read_text(encoding="utf-8"))
        seo_mapping = [entry for entry in mapping if entry["plugin"] == "seo"]
        self.assertEqual(len(seo_mapping), 22)
        self.assertEqual(
            {entry["legacy_invocation"] for entry in seo_mapping},
            {
                "/seo:audit",
                "/seo:backlinks",
                "/seo:cluster",
                "/seo:competitor-pages",
                "/seo:content",
                "/seo:content-brief",
                "/seo:drift",
                "/seo:ecommerce",
                "/seo:flow",
                "/seo:geo",
                "/seo:google",
                "/seo:hreflang",
                "/seo:images",
                "/seo:local",
                "/seo:maps",
                "/seo:page",
                "/seo:plan",
                "/seo:programmatic",
                "/seo:schema",
                "/seo:sitemap",
                "/seo:sxo",
                "/seo:technical",
            },
        )

        technical = (
            PLUGIN / "skills" / "seo-technical" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("# Technical SEO Audit", technical)
        self.assertIn("## Explicit workflow behavior", technical)

        audit = (PLUGIN / "skills" / "seo-audit" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Use $seo ", audit)

    def test_claude_runtime_tokens_are_removed(self) -> None:
        legacy_invocation = re.compile(r"/[a-z0-9-]+:[a-z0-9*-]+", re.I)
        for path in (PLUGIN / "skills").glob("*/SKILL.md"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", content, path)
            self.assertNotIn("$ARGUMENTS", content, path)
            self.assertNotIn("Next Recommended Command", content, path)
            self.assertNotRegex(content, legacy_invocation, path)

    def test_helpers_and_attribution_are_packaged(self) -> None:
        self.assertTrue((PLUGIN / "lib" / "url_guard.py").is_file())
        self.assertTrue(
            (PLUGIN / "skills" / "seo-schema" / "scripts" / "schema_check.py").is_file()
        )
        self.assertTrue(
            (
                PLUGIN
                / "skills"
                / "seo-sitemap"
                / "scripts"
                / "sitemap_check.py"
            ).is_file()
        )
        self.assertTrue((PLUGIN / "THIRD-PARTY-NOTICES.md").is_file())
        self.assertFalse((PLUGIN / "commands").exists())


if __name__ == "__main__":
    unittest.main()
