"""The shared audit output contract must not diverge again (T-018).

The "Output — evidence-based audit format" block is inlined into 44 command
files because a Claude command is a prompt: the block has to be physically
present or the model never sees the required shape. Markdown has no include
mechanism, so the anti-drift guarantee is generation plus validation rather
than de-duplication -- `tools/output_contract.py` owns the one canonical
definition and this test fails closed on any copy that differs.

One copy had already drifted before this existed: /site-doctor:animation
listed 2 of the 6 Evidence Checked lines, so that command instructed a
narrower evidence contract than its 43 siblings while looking identical at a
glance.
"""
import importlib.util
import io
import os
import sys
import unittest


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(REPO, "tools", "output_contract.py")


def load_tool():
    spec = importlib.util.spec_from_file_location("output_contract_tool", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["output_contract_tool"] = module
    spec.loader.exec_module(module)
    return module


class OutputContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool()

    def test_the_canonical_source_exists_and_is_not_shipped(self):
        """It must live in tools/, which build_release.py does not package,
        so it never becomes a cross-plugin runtime dependency."""
        self.assertTrue(os.path.isfile(TOOL))
        with io.open(os.path.join(REPO, "release", "build_release.py"),
                     encoding="utf-8") as stream:
            builder = stream.read()
        self.assertIn('ALLOW_DIRS = (".claude-plugin", ".github", "plugins", '
                      '"release", "tests")', builder,
                      "if ALLOW_DIRS changed, re-check that tools/ is still "
                      "excluded from the release artifact")

    def test_every_carrier_matches_the_canonical_block(self):
        drifted = self.tool.audit()
        self.assertEqual(
            sorted(os.path.relpath(p, REPO) for p in drifted), [],
            "run: python tools/output_contract.py --write")

    def test_the_expected_number_of_commands_carry_it(self):
        carriers = self.tool.carriers()
        self.assertEqual(len(carriers), 44, sorted(carriers))

    def test_the_canonical_block_still_contains_the_full_evidence_list(self):
        """Guard against the drift being 'fixed' by shrinking the canonical
        definition to match the one narrow copy."""
        canonical = self.tool.CANONICAL
        for line in ("- File: …", "- Config: …", "- Page: …",
                     "- Command output: …", "- Screenshot: …",
                     "- Connector data: …"):
            self.assertIn(line, canonical, line)
        for section in ("## Status", "## Evidence Checked", "## Findings",
                        "## Risk Level", "## Required Fixes",
                        "## Suggested Tasks", "## Verification Steps",
                        "## Next Recommended Command"):
            self.assertIn(section, canonical, section)

    def test_animation_command_now_carries_the_full_contract(self):
        path = os.path.join(REPO, "plugins", "site-doctor", "commands",
                            "animation.md")
        with io.open(path, encoding="utf-8", newline="") as stream:
            text = stream.read()
        span = self.tool.extract(text)
        self.assertIsNotNone(span)
        self.assertEqual(text[span[0]:span[1]], self.tool.CANONICAL)

    def test_extractor_spans_the_whole_fenced_example(self):
        """The block contains its own '## ' lines inside a fence; a
        heading-to-heading scan truncates it and hides real drift."""
        sample = ("intro\n\n" + self.tool.CANONICAL + "\n\n## After\n")
        start, end = self.tool.extract(sample)
        self.assertEqual(sample[start:end], self.tool.CANONICAL)
        self.assertIn("## Next Recommended Command", sample[start:end])

    def test_write_is_idempotent(self):
        self.assertEqual(self.tool.write(), [],
                         "a clean tree must need no rewrite")


if __name__ == "__main__":
    unittest.main()
