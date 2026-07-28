"""Codex source-checkout and installed-plugin self-check regressions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SELF = ROOT / "plugins/solo/skills/suite-integrity/scripts/self_check.py"
OUTPUT_CONTRACT = (
    "## User-facing output contract\n\n"
    "Outside required machine-readable artifacts, end every response with exactly "
    "these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, "
    "**Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), "
    "**Verification**, and **Next skill** (the exact `$skill` invocation).\n"
)


def run_self_check(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SELF), str(root), "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env=dict(os.environ, PYTHONIOENCODING="utf-8"),
    )


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_fixture(root: Path) -> None:
    manifest = {
        "name": "foo",
        "version": "0.0.1",
        "description": "Fixture plugin",
        "author": {"name": "Fixture"},
        "license": "MIT",
        "skills": "./skills/",
        "interface": {
            "displayName": "Foo",
            "shortDescription": "Fixture workflows",
            "longDescription": "Fixture workflows for integrity tests.",
            "developerName": "Fixture",
            "category": "Testing",
            "capabilities": ["Read"],
            "defaultPrompt": ["Use Foo."],
        },
    }
    write(
        root / ".agents/plugins/marketplace.json",
        json.dumps({
            "name": "fixture",
            "interface": {"displayName": "Fixture"},
            "plugins": [{
                "name": "foo",
                "source": {"source": "local", "path": "./plugins/foo"},
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Testing",
            }],
        }),
    )
    write(root / "plugins/foo/.codex-plugin/plugin.json", json.dumps(manifest))
    write(
        root / "plugins/foo/skills/foo-go/SKILL.md",
        "---\nname: foo-go\ndescription: Run the fixture workflow.\n---\n\n"
        "# Go\n\nRead only.\n\n" + OUTPUT_CONTRACT,
    )
    write(
        root / "plugins/foo/skills/foo-go/agents/openai.yaml",
        "interface:\n"
        "  display_name: Foo Go\n"
        "  short_description: Run the fixture workflow safely\n"
        "  default_prompt: Use $foo-go for this fixture.\n"
        "policy:\n"
        "  allow_implicit_invocation: false\n",
    )
    mapping = [{
        "legacy_invocation": "/foo:go",
        "codex_invocation": "$foo-go",
        "target_path": "plugins/foo/skills/foo-go/SKILL.md",
    }]
    write(root / "command-map.json", json.dumps(mapping))
    write(
        root / "README.md",
        "# Fixture\n\n**1 plugins** · **1 skills** · "
        "**1 migrated commands** · **0 helper scripts**\n",
    )
    write(root / "CHANGELOG.md", "# Changelog\n\n## 0.0.1\n")
    write(
        root / "RELEASE.json",
        json.dumps({
            "version": "0.0.1",
            "previous_version": "0.0.0",
            "counts": {"plugins": 1, "skills": 1, "commands": 1, "scripts": 0},
        }),
    )


class FullRun(unittest.TestCase):
    def test_repo_passes_all_structural_checks(self):
        result = run_self_check(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MODE  source-checkout", result.stdout)
        self.assertIn("0 fail", result.stdout)
        self.assertIn("not proof of security or launch readiness", result.stdout)

    def test_path_handling_uses_portable_pathlib_logic(self):
        source = SELF.read_text(encoding="utf-8")
        self.assertIn(".as_posix()", source)
        self.assertNotIn('split("/")[1]', source)


class SourceBreakageDetection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="codex-selfcheck-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        make_fixture(self.root)

    def test_control_fixture_passes(self):
        result = run_self_check(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_readme_count_drift_fails(self):
        path = self.root / "README.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace("**1 plugins**", "**9 plugins**"),
            encoding="utf-8",
        )
        result = run_self_check(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("README counts mismatch", result.stdout)

    def test_unresolved_helper_reference_fails(self):
        skill = self.root / "plugins/foo/skills/foo-go/SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8")
            + "\nRun `<skill-root>/scripts/missing.py`.\n",
            encoding="utf-8",
        )
        result = run_self_check(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not resolve", result.stdout)

    def test_missing_output_contract_fails(self):
        skill = self.root / "plugins/foo/skills/foo-go/SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace("\n" + OUTPUT_CONTRACT, "\n"),
            encoding="utf-8",
        )
        result = run_self_check(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("seven-part user-facing output contract", result.stdout)

    def test_stale_next_command_fails(self):
        skill = self.root / "plugins/foo/skills/foo-go/SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace("Next skill", "Next command"),
            encoding="utf-8",
        )
        result = run_self_check(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("stale 'Next command' wording", result.stdout)

    def test_manifest_version_drift_fails(self):
        path = self.root / "plugins/foo/.codex-plugin/plugin.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["version"] = "0.0.2"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = run_self_check(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("plugin versions do not match release", result.stdout)

    def test_malformed_skill_yaml_fails_cleanly(self):
        path = self.root / "plugins/foo/skills/foo-go/SKILL.md"
        path.write_text(
            "---\nname: [not-closed\ndescription: broken\n---\nBody\n",
            encoding="utf-8",
        )
        result = run_self_check(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid YAML frontmatter", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)


class InstalledPluginMode(unittest.TestCase):
    def test_cached_plugin_validates_without_repo_marketplace(self):
        with tempfile.TemporaryDirectory(prefix="codex-cache-") as temp:
            root = Path(temp) / "cache" / "foo" / "0.0.1"
            make_fixture(Path(temp) / "source")
            shutil.copytree(Path(temp) / "source/plugins/foo", root)
            outside = Path(temp) / "outside"
            outside.mkdir()
            result = subprocess.run(
                [sys.executable, str(SELF), str(root), "-"],
                cwd=outside,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("MODE  installed-plugin", result.stdout)

    def test_agentrooms_plugin_defers_cross_plugin_validation(self):
        with tempfile.TemporaryDirectory(prefix="codex-cache-ai-") as temp:
            root = Path(temp) / "cache" / "ai" / "1.0.27"
            shutil.copytree(ROOT / "plugins/ai", root)
            result = subprocess.run(
                [sys.executable, str(SELF), str(root), "-"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("AgentRooms validation skipped in installed-plugin mode", result.stdout)
            self.assertIn("0 fail", result.stdout)


if __name__ == "__main__":
    unittest.main()
