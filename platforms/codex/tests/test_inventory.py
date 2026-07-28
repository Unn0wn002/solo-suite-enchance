"""Codex marketplace, manifest, release, and README inventory consistency."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def actual_counts() -> dict[str, int]:
    return {
        "plugins": len(list(ROOT.glob("plugins/*/.codex-plugin/plugin.json"))),
        "skills": len(list(ROOT.glob("plugins/*/skills/*/SKILL.md"))),
        "commands": len(json.loads((ROOT / "command-map.json").read_text(encoding="utf-8"))),
        "scripts": len([
            path for path in ROOT.glob("plugins/**/*.py")
            if "__pycache__" not in path.parts
        ]),
    }


class Inventory(unittest.TestCase):
    def setUp(self):
        self.actual = actual_counts()
        self.marketplace = json.loads(
            (ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8")
        )
        self.release = json.loads((ROOT / "RELEASE.json").read_text(encoding="utf-8"))

    def test_readme_and_release_counts_match_filesystem(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        match = re.search(
            r"\*\*(\d+) plugins\*\*.*?\*\*(\d+) skills\*\*.*?"
            r"\*\*(\d+) migrated commands\*\*.*?\*\*(\d+) helper scripts\*\*",
            readme,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "README inventory line is missing")
        claimed = dict(zip(self.actual, map(int, match.groups())))
        self.assertEqual(claimed, self.actual)
        self.assertEqual(self.release["counts"], self.actual)

    def test_marketplace_matches_plugin_manifests(self):
        self.assertEqual(self.marketplace["name"], "solo-suite-codex")
        entries = self.marketplace["plugins"]
        manifests = {
            path.parents[1].name: json.loads(path.read_text(encoding="utf-8"))
            for path in ROOT.glob("plugins/*/.codex-plugin/plugin.json")
        }
        self.assertEqual({entry["name"] for entry in entries}, set(manifests))
        self.assertEqual(len(entries), self.actual["plugins"])
        for entry in entries:
            with self.subTest(plugin=entry["name"]):
                source = entry["source"]
                self.assertEqual(source["source"], "local")
                self.assertTrue((ROOT / source["path"]).is_dir())
                self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
                self.assertIn(entry["policy"]["authentication"], {"ON_INSTALL", "ON_USE"})
                self.assertEqual(manifests[entry["name"]]["name"], entry["name"])

    def test_versions_changelog_and_publisher_agree(self):
        version = self.release["version"]
        self.assertEqual(version, "1.0.27")
        self.assertEqual(self.release["previous_version"], "1.0.12")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        top = re.search(r"^##\s+(\d+\.\d+\.\d+)", changelog, re.MULTILINE)
        self.assertIsNotNone(top)
        self.assertEqual(top.group(1), version)
        for path in ROOT.glob("plugins/*/.codex-plugin/plugin.json"):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], version, path)
            self.assertEqual(manifest["author"]["name"], "Sakura Yukihira (Ayaya)")
            self.assertNotIn("$schema", manifest, "unsupported Codex manifest field")

    def test_manifest_descriptions_cover_every_migrated_workflow(self):
        mapping = json.loads((ROOT / "command-map.json").read_text(encoding="utf-8"))
        by_plugin: dict[str, set[str]] = {}
        for entry in mapping:
            by_plugin.setdefault(entry["plugin"], set()).add(entry["codex_invocation"])
        for plugin, invocations in by_plugin.items():
            manifest = json.loads(
                (ROOT / "plugins" / plugin / ".codex-plugin/plugin.json").read_text(
                    encoding="utf-8"
                )
            )
            text = manifest["description"] + " " + manifest["interface"]["longDescription"]
            missing = sorted(invocation for invocation in invocations if invocation not in text)
            self.assertEqual(missing, [], plugin)

    def test_full_team_component_contract_covers_all_other_plugins(self):
        contract = json.loads((
            ROOT / "plugins/full-team/skills/full-team-orchestrator/"
            "references/component-plugins.json"
        ).read_text(encoding="utf-8"))
        required = {item["plugin"] for item in contract["components"]}
        actual = {
            path.name for path in (ROOT / "plugins").iterdir()
            if path.is_dir() and path.name != "full-team"
        }
        self.assertEqual(required, actual)
        self.assertEqual(len(contract["components"]), 18)
        for item in contract["components"]:
            plugin = item["plugin"]
            minimum = tuple(
                int(part) for part in item["minimum_version"].split(".")
            )
            manifest = json.loads((
                ROOT / "plugins" / plugin / ".codex-plugin/plugin.json"
            ).read_text(encoding="utf-8"))
            installed = tuple(
                int(part) for part in manifest["version"].split("+", 1)[0].split(".")
            )
            self.assertGreaterEqual(installed, minimum, plugin)
            self.assertTrue((
                ROOT / "plugins" / plugin / "skills" /
                item["representative_skill"] / "SKILL.md"
            ).is_file(), plugin)


if __name__ == "__main__":
    unittest.main()
