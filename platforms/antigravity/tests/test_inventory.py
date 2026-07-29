"""Inventory consistency — README bold counts, marketplace metadata, CHANGELOG
top entry, and the cheatsheet docx version must all match the filesystem."""
import glob
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATOR = os.path.join(REPO, "release", "gen_release_inventory.py")
SPEC = importlib.util.spec_from_file_location("gen_release_inventory",
                                              GENERATOR)
gen_release_inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gen_release_inventory)


def real_counts():
    g = lambda p: len(glob.glob(os.path.join(REPO, p)))
    return {"plugins": g("plugins/*/.claude-plugin/plugin.json"),
            "skills": g("plugins/*/skills/*/SKILL.md"),
            "commands": g("plugins/*/commands/*.md"),
            "scripts": g("plugins/*/skills/*/scripts/*.py"),
            "agents": g("plugins/*/agents/*.md")}


class Inventory(unittest.TestCase):
    def setUp(self):
        self.real = real_counts()
        with open(os.path.join(REPO, ".claude-plugin", "marketplace.json"),
                  encoding="utf-8") as f:
            self.mk = json.load(f)

    def test_readme_counts_match_filesystem(self):
        with open(os.path.join(REPO, "README.md"), encoding="utf-8") as f:
            rd = f.read()
        m = re.search(r"\*\*(\d+) plugins\*\*.*?\*\*(\d+) skills\*\*.*?"
                      r"\*\*(\d+) slash commands\*\*.*?\*\*(\d+) stdlib"
                      r".*?\*\*(\d+) room-\* agents\*\*", rd, re.S)
        self.assertIsNotNone(m, "README counts line missing")
        claimed = dict(zip(("plugins", "skills", "commands", "scripts",
                            "agents"), map(int, m.groups())))
        self.assertEqual(claimed, self.real)

    def test_pinned_counts_cannot_drift(self):
        """Drift guard with LITERAL expectations: if a plugin, skill,
        command, script, or room agent is added or removed, this test and
        the marketplace metadata must both be updated deliberately."""
        self.assertEqual(self.real, {
            "plugins": 19, "skills": 80, "commands": 126,
            "scripts": 16, "agents": 24})

    def test_helper_script_and_agent_manifests(self):
        """The 16 helper scripts and 24 room-* agents, by exact name."""
        scripts = sorted(os.path.basename(p) for p in glob.glob(
            os.path.join(REPO, "plugins", "*", "skills", "*", "scripts",
                         "*.py")))
        self.assertEqual(len(scripts), 16, scripts)
        self.assertIn("animation_check.py", scripts)
        self.assertIn("record_evidence.py", scripts)
        self.assertIn("check_evidence.py", scripts)
        self.assertIn("schema_check.py", scripts)
        self.assertIn("sitemap_check.py", scripts)
        self.assertIn("update_run_state.py", scripts)  # v1.0.17
        agents = sorted(os.path.basename(p)[:-3] for p in glob.glob(
            os.path.join(REPO, "plugins", "*", "agents", "*.md")))
        self.assertEqual(agents, [
            "room-ai-agent-reviewer", "room-backend-developer",
            "room-browser-qa-engineer", "room-bug-fixer",
            "room-bug-reproducer", "room-code-reviewer",
            "room-database-engineer", "room-devops-engineer",
            "room-documentation-writer", "room-evidence-finalizer",
            "room-frontend-developer", "room-git-pr-manager",
            "room-growth-reviewer", "room-memory-steward",
            "room-product-manager", "room-production-gatekeeper",
            "room-qa-engineer", "room-release-manager",
            "room-repo-analyst", "room-security-engineer",
            "room-site-doctor", "room-software-architect",
            "room-ui-ux-designer", "room-worktree-integrator"], agents)
        self.assertEqual(len(agents), 24, agents)
        self.assertTrue(all(a.startswith("room-") for a in agents), agents)

    def test_marketplace_metadata_has_no_unsupported_count_fields(self):
        """v1.0.15: count fields were REMOVED from marketplace metadata
        (the CLI warns on unknown fields). Canonical counts live in the
        README line and this file's pinned literals."""
        md = self.mk["metadata"]
        for k in ("plugins", "skills", "commands", "scripts", "agents",
                  "license"):
            self.assertNotIn(k, md, k)
        self.assertEqual(len(self.mk["plugins"]), self.real["plugins"])
        for p in self.mk["plugins"]:
            src = p["source"].lstrip("./")
            self.assertTrue(os.path.isdir(os.path.join(REPO, src)), src)

    def test_changelog_top_matches_metadata_version(self):
        with open(os.path.join(REPO, "CHANGELOG.md"), encoding="utf-8") as f:
            ch = f.read()
        top = re.search(r"^## (\d+\.\d+\.\d+)", ch, re.M)
        self.assertEqual(top.group(1), self.mk["metadata"]["version"])

    def test_cheatsheet_version_matches_site_doctor(self):
        docx = glob.glob(os.path.join(REPO, "*site-doctor*.docx"))
        self.assertEqual(len(docx), 1)
        with zipfile.ZipFile(docx[0]) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        text = re.sub(r"<[^>]+>", "", xml)
        got = re.search(r"v(\d+\.\d+\.\d+)", text)
        with open(os.path.join(REPO, "plugins", "site-doctor",
                               ".claude-plugin", "plugin.json"),
                  encoding="utf-8") as f:
            sd = json.load(f)["version"]
        self.assertEqual(got.group(1), sd)


class InventoryFilesystemSafety(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="release-inventory-safe-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.write(".claude-plugin/marketplace.json", json.dumps({
            "metadata": {"version": "1.2.3"}
        }))
        self.write("plugins/demo/.claude-plugin/plugin.json", json.dumps({
            "version": "4.5.6"
        }))
        self.write("plugins/demo/content.txt", "committed-like content\n")

    def write(self, relative, value):
        path = os.path.join(self.root, *relative.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
        return path

    def make_symlink_or_skip(self, target, link):
        try:
            os.symlink(target, link,
                       target_is_directory=os.path.isdir(target))
        except (OSError, NotImplementedError) as exc:
            if os.name == "nt" and os.path.isdir(target):
                junction = subprocess.run(
                    ["cmd", "/d", "/c", "mklink", "/J", link, target],
                    capture_output=True, text=True, timeout=30)
                if junction.returncode == 0:
                    self.addCleanup(
                        lambda: os.rmdir(link) if os.path.lexists(link)
                        else None)
                    return
            self.skipTest("filesystem symlink creation unavailable: %s" % exc)

    def test_regular_inventory_is_deterministic(self):
        first = gen_release_inventory.build_inventory(self.root)
        second = gen_release_inventory.build_inventory(self.root)
        self.assertEqual(first, second)
        self.assertEqual(first["plugin_versions"], {"demo": "4.5.6"})
        self.assertIn("plugins/demo/content.txt", first["files"])

    def test_file_symlink_is_rejected_not_hashed(self):
        outside_dir = tempfile.mkdtemp(prefix="release-inventory-outside-")
        self.addCleanup(shutil.rmtree, outside_dir, ignore_errors=True)
        target = os.path.join(outside_dir, "secret.txt")
        with open(target, "w", encoding="utf-8") as stream:
            stream.write("outside\n")
        link = os.path.join(self.root, "plugins", "demo", "escape.txt")
        self.make_symlink_or_skip(target, link)
        with self.assertRaisesRegex(gen_release_inventory.InventoryError,
                                    "link-like entry"):
            gen_release_inventory.walk_files(self.root)

    def test_ignored_directory_symlink_still_fails_closed(self):
        outside_dir = tempfile.mkdtemp(prefix="release-inventory-outside-")
        self.addCleanup(shutil.rmtree, outside_dir, ignore_errors=True)
        self.write("outside-placeholder.txt", "inside root\n")
        link = os.path.join(self.root, ".git")
        self.make_symlink_or_skip(outside_dir, link)
        with self.assertRaisesRegex(gen_release_inventory.InventoryError,
                                    "link-like entry"):
            gen_release_inventory.walk_files(self.root)


if __name__ == "__main__":
    unittest.main()
