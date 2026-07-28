"""Release-versioning regression (v1.0.17, blocker 1): a plugin whose
tree MATERIALLY changed since the previous release must NOT keep the
previous release's component version.

The previous release is snapshotted in
release/previous-release-inventory.json (written by
release/gen_release_inventory.py against the pristine previous tree).
This test recomputes the current tree's file digests with the SAME
shared ignore rules (generated files — __pycache__, *.pyc, coverage
output, dist, test caches — never count as changes) and fails when a
changed plugin retains its old version. A post-release development tree may
carry an explicit ``release/unreleased-remediation.json`` version plan, but
the release builder refuses to package any commit containing that plan. The
exact v1.0.16 audit finding — ai/gate/solo changed since v1.0.15 at
unchanged versions — therefore still cannot ship."""
import importlib.util
import json
import os
import re
import subprocess
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INVENTORY = os.path.join(REPO, "release",
                         "previous-release-inventory.json")
GEN = os.path.join(REPO, "release", "gen_release_inventory.py")
UNRELEASED = os.path.join(REPO, "release", "unreleased-remediation.json")

_spec = importlib.util.spec_from_file_location("gen_release_inventory",
                                               GEN)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def plugin_of(rel):
    parts = rel.split("/")
    if len(parts) >= 2 and parts[0] == "plugins":
        return parts[1]
    return None


class ReleaseVersioning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INVENTORY, encoding="utf-8") as f:
            cls.prev = json.load(f)
        cls.now_files = gen.walk_files(REPO)
        cls.now = gen.build_inventory(REPO)
        cls.unreleased = None
        if os.path.isfile(UNRELEASED):
            with open(UNRELEASED, encoding="utf-8") as f:
                cls.unreleased = json.load(f)

    @staticmethod
    def version_tuple(value):
        if not isinstance(value, str) or not re.fullmatch(
                r"[0-9]+\.[0-9]+\.[0-9]+", value):
            return None
        return tuple(int(part) for part in value.split("."))

    def changed_files(self, plugin):
        """Added/removed/modified files under plugins/<plugin>/, computed
        against the previous-release inventory with the shared ignore
        rules."""
        prev = {r: h for r, h in self.prev["files"].items()
                if plugin_of(r) == plugin}
        now = {r: h for r, h in self.now_files.items()
               if plugin_of(r) == plugin}
        changed = sorted(
            set(prev) ^ set(now)
            | {r for r in set(prev) & set(now) if prev[r] != now[r]})
        return changed

    def test_inventory_snapshot_is_wellformed(self):
        self.assertEqual(self.prev["schema"],
                         "solo-suite/release-inventory-v1")
        self.assertTrue(self.prev["files"])
        self.assertTrue(self.prev["plugin_versions"])

    def test_unreleased_remediation_plan_is_fail_closed(self):
        if self.unreleased is None:
            return
        plan = self.unreleased
        self.assertEqual(plan.get("schema"),
                         "solo-suite/unreleased-remediation-v1")
        base_release = self.version_tuple(plan.get("base_release"))
        target_release = self.version_tuple(plan.get("target_release"))
        current_release = self.version_tuple(self.now["release"])
        self.assertIsNotNone(base_release)
        self.assertIsNotNone(target_release)
        self.assertIsNotNone(current_release)
        self.assertGreater(target_release, base_release)
        # The plan is present in two valid release-cut phases: before the
        # target metadata is applied, and after it is applied but before the
        # final cut removes the plan. No third/current release is accepted.
        self.assertIn(current_release, (base_release, target_release))
        self.assertEqual(set(plan.get("tasks", [])),
                         {"T-SUITE-%03d" % n for n in range(1, 9)})
        planned = plan.get("planned_plugin_versions")
        self.assertIsInstance(planned, dict)
        self.assertTrue(planned)
        for name, planned_version in planned.items():
            self.assertIn(name, self.now["plugin_versions"])
            planned_tuple = self.version_tuple(planned_version)
            current_tuple = self.version_tuple(self.now["plugin_versions"][name])
            self.assertIsNotNone(planned_tuple)
            self.assertIsNotNone(current_tuple)
            if current_release == base_release:
                self.assertGreater(planned_tuple, current_tuple, name)
            else:
                self.assertEqual(planned_tuple, current_tuple, name)
        self.assertTrue(plan.get("release_blocked_until"))

    def test_checkout_policy_keeps_inventory_bytes_cross_platform(self):
        """Git must materialize release text as LF even on Windows.

        The inventory intentionally hashes exact bytes. Without an explicit
        repository policy, ``core.autocrlf`` can make every unchanged plugin
        look modified on a Windows runner.
        """
        attrs_path = os.path.join(REPO, ".gitattributes")
        with open(attrs_path, encoding="utf-8") as stream:
            attrs = stream.read()
        self.assertIn("* text=auto eol=lf", attrs)
        self.assertIn("*.docx binary", attrs)

        probes = [
            "plugins/ai/.claude-plugin/plugin.json",
            "plugins/site-doctor/skills/security-review/scripts/"
            "scan_secrets.py",
        ]
        for rel in probes:
            with open(os.path.join(REPO, *rel.split("/")), "rb") as stream:
                self.assertNotIn(b"\r\n", stream.read(), rel)

        # Public release archives intentionally contain no .git directory.
        # Their committed text bytes and the shipped policy are still
        # verifiable above; check Git's attribute resolution only when the
        # test is running from an actual checkout.
        if not os.path.isdir(os.path.join(REPO, ".git")):
            return

        checked = subprocess.run(
            ["git", "-C", REPO, "check-attr", "text", "eol", "--"]
            + probes,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="strict", check=False)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        lines = set(checked.stdout.splitlines())
        for rel in probes:
            self.assertIn("%s: text: auto" % rel, lines)
            self.assertIn("%s: eol: lf" % rel, lines)

        binary = subprocess.run(
            ["git", "-C", REPO, "check-attr", "text", "diff", "--",
             "site-doctor-cheatsheet.docx"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="strict", check=False)
        self.assertEqual(binary.returncode, 0, binary.stderr)
        self.assertIn("site-doctor-cheatsheet.docx: text: unset",
                      binary.stdout.splitlines())
        self.assertIn("site-doctor-cheatsheet.docx: diff: unset",
                      binary.stdout.splitlines())

    def test_materially_changed_plugins_carry_new_versions(self):
        offenders = []
        planned = ((self.unreleased or {}).get("planned_plugin_versions")
                   or {})
        for name, prev_version in sorted(
                self.prev["plugin_versions"].items()):
            now_version = self.now["plugin_versions"].get(name)
            if now_version is None:
                continue                      # plugin removed: nothing to pin
            changed = self.changed_files(name)
            if changed and now_version == prev_version:
                target = planned.get(name)
                if (self.version_tuple(target) is not None
                        and self.version_tuple(target)
                        > self.version_tuple(now_version)):
                    continue
                offenders.append(
                    "plugins/%s changed since release %s but kept version "
                    "%s — bump it. Changed files (first 10): %s"
                    % (name, self.prev["release"], prev_version,
                       ", ".join(changed[:10])))
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_checkout_policy_is_runnable_without_git_metadata(self):
        """The test suite shipped in the public ZIP must remain runnable."""
        with mock.patch.object(os.path, "isdir", return_value=False), \
                mock.patch.object(
                    subprocess, "run",
                    side_effect=AssertionError(
                        "archive validation must not invoke Git")):
            self.test_checkout_policy_keeps_inventory_bytes_cross_platform()

    def test_unchanged_plugins_keep_their_versions(self):
        """The inverse guard: an UNCHANGED plugin tree must not have been
        bumped gratuitously (version churn hides real changes)."""
        offenders = []
        for name, prev_version in sorted(
                self.prev["plugin_versions"].items()):
            now_version = self.now["plugin_versions"].get(name)
            if now_version is None:
                continue
            if not self.changed_files(name) \
                    and now_version != prev_version:
                offenders.append("plugins/%s is byte-identical to release "
                                 "%s but its version moved %s -> %s"
                                 % (name, self.prev["release"],
                                    prev_version, now_version))
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_any_tree_change_requires_a_new_release_version(self):
        prev_all = self.prev["files"]
        now_all = self.now_files
        changed = (set(prev_all) ^ set(now_all)) \
            | {r for r in set(prev_all) & set(now_all)
               if prev_all[r] != now_all[r]}
        # the snapshot file itself always differs between releases
        changed.discard("release/previous-release-inventory.json")
        if changed:
            self.assertNotEqual(
                self.now["release"], self.prev["release"],
                "the tree changed (%d files, e.g. %s) but the marketplace "
                "release version is still %s"
                % (len(changed), sorted(changed)[:5],
                   self.prev["release"]))

    def test_changelog_transition_matches_inventory_and_marketplace(self):
        changelog = os.path.join(REPO, "CHANGELOG.md")
        with open(changelog, encoding="utf-8") as stream:
            text = stream.read()
        headings = re.findall(
            r"(?m)^## ([0-9]+\.[0-9]+\.[0-9]+)\b", text)
        self.assertTrue(headings, "CHANGELOG has no release heading")
        self.assertEqual(headings[0], self.now["release"])
        current_section = text.split("\n## ", 2)[1]
        transition = "- marketplace %s -> %s" % (
            self.prev["release"], self.now["release"])
        self.assertIn(transition, current_section)

    def test_generated_files_never_count_as_changes(self):
        """The shared ignore rules exclude generated artifacts, so a
        __pycache__/ or .coverage left behind by a test run can never
        force a version bump."""
        for name in ("__pycache__", ".pytest_cache", "dist",
                     "node_modules"):
            self.assertIn(name, gen.IGNORED_DIRS, name)
        for name in (".coverage", "scan.json", "coverage.xml"):
            self.assertIn(name, gen.IGNORED_FILES, name)
        for ext in (".pyc", ".pyo"):
            self.assertIn(ext, gen.IGNORED_EXTS, ext)
        self.assertTrue(gen.ignored_file("x.pyc"))
        self.assertTrue(gen.ignored_file(".coverage.host.123"))
        self.assertTrue(gen.ignored_file("rec.json.tmp.42"))
        self.assertFalse(gen.ignored_file("gate_policy.py"))
        for rel in self.now_files:
            self.assertNotIn("__pycache__", rel)
            self.assertFalse(rel.endswith(".pyc"), rel)


if __name__ == "__main__":
    unittest.main()
