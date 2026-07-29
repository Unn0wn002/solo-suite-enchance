"""Ownership tests for the Claude<->Codex parity contract (T-007).

`parity/capabilities.json` is a GENERATED artifact -- `tools/parity.py generate`
owns it -- and `tools/parity.py`'s EXPECTED_* constants are literal drift guards
in the style of tests/test_inventory.py. Both went a full release stale when the
`seo` plugin landed: the constants still said 18/102/56 while the filesystem had
19/126/80, and 66 of the recorded source_sha256 values no longer matched disk.
Nothing caught it because nothing ran the tool.

These tests make the contract self-policing: the constants must equal the
filesystem, the committed manifest must equal what the generator produces right
now, and every recorded hash must match the bytes on disk.

Scope note: they verify the SOURCE side only. `tools/parity.py --check` also
compares a Codex adapter checkout, which is a separate downstream distribution
not present in this repository, so it is intentionally not exercised here.
"""
import glob
import hashlib
import importlib.util
import json
import os
import sys
import unittest


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARITY_TOOL = os.path.join(REPO, "tools", "parity.py")
MANIFEST = os.path.join(REPO, "parity", "capabilities.json")


def load_parity():
    spec = importlib.util.spec_from_file_location("parity_under_test",
                                                  PARITY_TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["parity_under_test"] = module
    spec.loader.exec_module(module)
    return module


def real_counts():
    g = lambda p: len(glob.glob(os.path.join(REPO, p)))
    return {
        "plugins": g("plugins/*/.claude-plugin/plugin.json"),
        "commands": g("plugins/*/commands/*.md"),
        "specialists": g("plugins/*/skills/*/SKILL.md"),
    }


class ParityConstants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parity = load_parity()
        cls.real = real_counts()

    def test_source_constants_match_the_filesystem(self):
        self.assertEqual(self.parity.EXPECTED_PLUGIN_COUNT,
                         self.real["plugins"])
        self.assertEqual(self.parity.EXPECTED_COMMAND_COUNT,
                         self.real["commands"])
        self.assertEqual(self.parity.EXPECTED_SPECIALIST_COUNT,
                         self.real["specialists"])

    def test_target_skill_count_is_declared(self):
        """The Codex-side count is not derivable here, but must be positive
        and at least as large as the specialist inventory."""
        self.assertGreaterEqual(self.parity.EXPECTED_TARGET_SKILL_COUNT,
                                self.real["specialists"])

    def test_no_stale_count_literals_in_error_messages(self):
        with open(PARITY_TOOL, encoding="utf-8") as stream:
            body = stream.read()
        for stale in ("102-command map", "canonical 158 skills",
                      "expected 18 source plugins"):
            self.assertNotIn(stale, body,
                             "stale hardcoded count in parity.py: %s" % stale)


class ParityManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parity = load_parity()
        with open(MANIFEST, encoding="utf-8") as stream:
            cls.manifest = json.load(stream)

    def test_counts_block_matches_the_constants(self):
        counts = self.manifest["counts"]
        self.assertEqual(counts["plugins"], self.parity.EXPECTED_PLUGIN_COUNT)
        self.assertEqual(counts["source_commands"],
                         self.parity.EXPECTED_COMMAND_COUNT)
        self.assertEqual(counts["source_specialist_skills"],
                         self.parity.EXPECTED_SPECIALIST_COUNT)
        self.assertEqual(counts["target_skills"],
                         self.parity.EXPECTED_TARGET_SKILL_COUNT)

    def test_every_declared_plugin_exists_and_seo_is_present(self):
        ids = sorted(item["id"] for item in self.manifest["plugins"])
        on_disk = sorted(
            os.path.basename(os.path.dirname(os.path.dirname(p)))
            for p in glob.glob(os.path.join(REPO, "plugins", "*",
                                            ".claude-plugin", "plugin.json")))
        self.assertEqual(ids, on_disk)
        self.assertIn("seo", ids)

    def test_recorded_hashes_match_the_bytes_on_disk(self):
        stale = []
        entries = (self.manifest["plugins"] + self.manifest["commands"]
                   + self.manifest["specialist_skills"])
        for item in entries:
            path = os.path.join(REPO, item["source_path"])
            if not os.path.isfile(path):
                stale.append("MISSING " + item["source_path"])
                continue
            with open(path, "rb") as stream:
                digest = hashlib.sha256(stream.read()).hexdigest()
            if digest != item["source_sha256"]:
                stale.append("STALE " + item["source_path"])
        self.assertEqual(
            stale, [],
            "regenerate with: python tools/parity.py generate --source .")

    def test_committed_manifest_equals_a_fresh_generation(self):
        """The generator owns this file -- it must not be hand-edited."""
        from pathlib import Path
        fresh = self.parity.build_manifest(Path(REPO))
        self.assertEqual(
            fresh, self.manifest,
            "parity/capabilities.json is out of date or hand-edited; "
            "run: python tools/parity.py generate --source .")


if __name__ == "__main__":
    unittest.main()
