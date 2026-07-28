"""Regression tests for the plugin-count contract inside ``ci.yml``.

Both plugin-validation blocks in the workflow used to compare their loop
counter against the literal ``18`` and drive the install/details smoke test
from a hand-typed plugin name list.  When the ``seo`` plugin was added those
literals silently became wrong: the count assertions would hard-fail the
packaged-ZIP and release-build jobs, and the smoke test would skip ``seo``
entirely -- the newest plugin would ship without ever being proven to install
from the packaged artifact.

The workflow now DERIVES both the expected count and the plugin name list from
the marketplace manifest.  These tests pin that derivation so a hardcoded count
or name list cannot creep back in, and assert the filesystem invariant the
derivation depends on (manifest entries and plugin directories agree), so the
mismatch is caught locally instead of on a GitHub-hosted runner.
"""
import glob
import json
import os
import re
import unittest


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(REPO, ".github", "workflows", "ci.yml")
MARKETPLACE = os.path.join(REPO, ".claude-plugin", "marketplace.json")

# The two workflow steps that validate every plugin directory.
PACKAGED_ZIP_STEP = "PACKAGED-ZIP validation + marketplace/install smoke test"
TAG_VALIDATION_STEP = "Re-run canonical tag validation and retain raw logs"


def read(path):
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def step_block(workflow, name_fragment):
    """Return one ``- name:`` step, up to the next step or job boundary."""
    match = re.search(
        r"(?ms)^      - name: .*?%s.*?(?=^      - name: |^  [A-Za-z0-9_-]+:\n|\Z)"
        % re.escape(name_fragment),
        workflow,
    )
    if match is None:
        raise AssertionError("workflow step is missing: %s" % name_fragment)
    return match.group(0)


class CiPluginCountContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = read(WORKFLOW)
        cls.packaged = step_block(cls.workflow, PACKAGED_ZIP_STEP)
        cls.tag_validation = step_block(cls.workflow, TAG_VALIDATION_STEP)

    # ---- the invariant the workflow's derivation relies on ----------------

    def test_marketplace_entries_match_plugin_directories(self):
        """Manifest entries and on-disk plugin dirs must agree exactly.

        Both workflow blocks derive their expected count from the manifest and
        compare it against a glob over ``plugins/*/``.  If these two ever
        disagree, CI fails -- so fail here first, with a readable diff.
        """
        with open(MARKETPLACE, encoding="utf-8") as stream:
            declared = [p["name"] for p in json.load(stream)["plugins"]]
        on_disk = sorted(
            os.path.basename(os.path.dirname(os.path.dirname(p)))
            for p in glob.glob(
                os.path.join(REPO, "plugins", "*", ".claude-plugin",
                             "plugin.json"))
        )
        self.assertEqual(sorted(declared), on_disk)
        self.assertEqual(len(declared), len(set(declared)),
                         "duplicate plugin name in marketplace.json")

    def test_every_declared_source_resolves_to_its_plugin_dir(self):
        """``source`` must point at the directory the smoke test will install."""
        with open(MARKETPLACE, encoding="utf-8") as stream:
            entries = json.load(stream)["plugins"]
        for entry in entries:
            source = entry["source"]
            self.assertIsInstance(source, str, entry["name"])
            target = os.path.join(REPO, source.lstrip("./").replace("/", os.sep))
            self.assertTrue(os.path.isdir(target),
                            "%s: source does not resolve: %s"
                            % (entry["name"], source))
            self.assertTrue(
                os.path.isfile(os.path.join(target, ".claude-plugin",
                                            "plugin.json")),
                "%s: no plugin.json under %s" % (entry["name"], source))

    # ---- the derivation must stay derived --------------------------------

    def test_packaged_zip_count_is_derived_from_the_manifest(self):
        self.assertIn(
            '[ "$n" = "$expected" ]', self.packaged,
            "packaged-ZIP plugin count must compare against the derived value")
        self.assertIn('.claude-plugin/marketplace.json', self.packaged)
        self.assertIsNone(
            re.search(r'\[\s*"\$n"\s*=\s*"\d+"\s*\]', self.packaged),
            "packaged-ZIP plugin count regressed to a hardcoded literal")

    def test_tag_validation_count_is_derived_from_the_manifest(self):
        self.assertIn('test "$count" = "$declared"', self.tag_validation)
        self.assertIn('.claude-plugin/marketplace.json', self.tag_validation)
        self.assertIsNone(
            re.search(r'test\s+"\$count"\s*=\s*"\d+"', self.tag_validation),
            "release-build plugin count regressed to a hardcoded literal")

    def test_smoke_test_plugin_names_are_derived_not_hardcoded(self):
        """The install/details loops must enumerate the manifest, not a list.

        A hand-typed list is what let ``seo`` be skipped; requiring the loops
        to read the generated file makes omission impossible.
        """
        self.assertEqual(
            2, self.packaged.count("for p in $(cat plugin-names.txt); do"),
            "both the install-verify and details loops must read the "
            "derived plugin name list")
        self.assertIn('> plugin-names.txt', self.packaged)
        self.assertIn('[ "$(wc -l < plugin-names.txt)" = "$expected" ]',
                      self.packaged,
                      "derived name list must be cross-checked against the "
                      "validated plugin count")
        for name in ("solo", "site-doctor", "full-team", "seo"):
            self.assertIsNone(
                re.search(r"for p in [a-z][a-z0-9 -]*\b%s\b" % re.escape(name),
                          self.packaged),
                "hardcoded plugin name list regressed (%s)" % name)

    def test_no_plugin_count_literal_survives_in_either_block(self):
        """Guard the exact shapes that broke, in both validation blocks.

        ``18`` legitimately appears elsewhere in the workflow as the fixed
        release-ASSET allowlist size; that contract is pinned separately by
        tests/test_release_asset_policy.py.  It must never again describe a
        number of plugins.
        """
        for label, block in (("packaged-ZIP", self.packaged),
                             ("release-build", self.tag_validation)):
            self.assertNotIn("expected 18 plugin dirs", block, label)
            self.assertIsNone(
                re.search(r'(?i)\b(all|every|the)\s+18\s+plugin', block),
                "%s: stale '18 plugins' prose" % label)
            for counter in (r"\$n", r"\$count", r"\$\{#plugins\[@\]\}"):
                self.assertIsNone(
                    re.search(r'"%s"\s*=\s*"\d+"' % counter, block),
                    "%s: plugin counter compared to a literal" % label)

    def test_validation_report_does_not_pin_a_plugin_count(self):
        """The signed validation report must not restate a stale count."""
        self.assertNotIn("18 strict plugin validations", self.workflow)
        self.assertIn("per-plugin strict validations", self.workflow)


if __name__ == "__main__":
    unittest.main()
