"""Fixture-driven coverage tests for self_check.py (T-017, T-022).

Two classes of blind spot are closed here.

T-017 -- the portability guards (CWD-relative helper invocations, and
${CLAUDE_PLUGIN_ROOT}/<path> targets that do not exist) used to run ONLY
inside the skills loop, so the same defect in a command or an agent passed
silently. Three command files and the whole agent tree were unguarded.

T-022 -- self_check verified only that a command declared *some* input
(argument-hint OR $ARGUMENTS). It never checked that the two agreed, so a
stale hint advertising options the body ignores passed, as did a body
consuming arguments with no hint at all. Local markdown links were never
resolved either.

Every case plants the defect in a disposable fixture suite and asserts
self_check FAILS with an actionable message, plus a control proving the same
fixture passes without the defect. Offline throughout: no link is fetched,
and http/https targets are explicitly out of scope.
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELF_CHECK = os.path.join(REPO, "plugins", "solo", "skills",
                          "suite-integrity", "scripts", "self_check.py")

MARKETPLACE = """{
  "$schema": "https://www.schemastore.org/claude-code-marketplace.json",
  "name": "fixture",
  "owner": {"name": "t", "email": "t@example.com"},
  "metadata": {"description": "fixture suite", "version": "0.0.1"},
  "plugins": [{"name": "foo", "source": "./plugins/foo",
               "description": "fixture plugin"}]
}
"""

PLUGIN_JSON = '{"name": "foo", "version": "0.0.1", "description": "fixture"}\n'

README = """# fixture

- **1 plugins** · **1 skills** · **1 slash commands** · **1 stdlib helper scripts** · **0 room-* agents**
"""

CHANGELOG = "## 0.0.1 — 2026-01-01\n\n- fixture\n"

GOOD_COMMAND = """---
description: Do the fixture thing
---
Run the fixture.

## Output

A report.
"""

GOOD_SKILL = """---
name: bar
description: Fixture skill used by the self-check coverage tests.
---

# Bar

Body.
"""


class SelfCheckFixture(unittest.TestCase):
    """Builds a minimal but VALID suite, then mutates one thing at a time."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="self-check-fixture-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.plug = os.path.join(self.root, "plugins", "foo")
        for sub in (("commands",), ("skills", "bar"), ("agents",),
                    ("scripts",), (".claude-plugin",)):
            os.makedirs(os.path.join(self.plug, *sub), exist_ok=True)
        os.makedirs(os.path.join(self.root, ".claude-plugin"), exist_ok=True)
        self.write(".claude-plugin/marketplace.json", MARKETPLACE)
        self.write("plugins/foo/.claude-plugin/plugin.json", PLUGIN_JSON)
        self.write("README.md", README)
        self.write("CHANGELOG.md", CHANGELOG)
        self.write("plugins/foo/commands/do.md", GOOD_COMMAND)
        self.write("plugins/foo/skills/bar/SKILL.md", GOOD_SKILL)
        # Two copies on purpose: the plugin-root one is what
        # ${CLAUDE_PLUGIN_ROOT}/scripts/helper.py resolves to, while the
        # skill-scoped one is what the prose-reference check and the README
        # "stdlib helper scripts" count (plugins/*/skills/*/scripts/*.py) see.
        self.write("plugins/foo/scripts/helper.py", "print('ok')\n")
        self.write("plugins/foo/skills/bar/scripts/helper.py", "print('ok')\n")

    def write(self, rel, text):
        path = os.path.join(self.root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)

    def run_check(self):
        return subprocess.run(
            [sys.executable, SELF_CHECK, self.root, "-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)

    def assertFixtureFails(self, needle):
        r = self.run_check()
        out = (r.stdout + r.stderr).decode("utf-8", "replace")
        self.assertEqual(r.returncode, 1, "expected a FAIL, got:\n" + out)
        self.assertIn(needle, out, out)
        return out

    def assertFixturePasses(self):
        r = self.run_check()
        out = (r.stdout + r.stderr).decode("utf-8", "replace")
        self.assertEqual(r.returncode, 0, out)
        return out

    # ---- control ---------------------------------------------------------

    def test_control_fixture_passes(self):
        self.assertFixturePasses()

    def test_a_command_with_no_arguments_at_all_is_valid(self):
        """Regression: the old rule demanded argument-hint OR $ARGUMENTS, so a
        genuinely argument-free command could not be expressed honestly."""
        out = self.assertFixturePasses()
        self.assertNotIn("no inputs", out)

    # ---- T-022: argument-hint consistency --------------------------------

    def test_hint_without_consumption_fails(self):
        self.write("plugins/foo/commands/do.md",
                   GOOD_COMMAND.replace("---\ndescription:",
                                        "---\nargument-hint: [url]\ndescription:", 1))
        out = self.assertFixtureFails("declares argument-hint")
        self.assertIn("never consumes", out)

    def test_consumption_without_hint_fails(self):
        self.write("plugins/foo/commands/do.md",
                   GOOD_COMMAND.replace("Run the fixture.",
                                        "Run the fixture on $ARGUMENTS.", 1))
        self.assertFixtureFails("no argument-hint")

    def test_matching_hint_and_consumption_passes(self):
        self.write("plugins/foo/commands/do.md",
                   GOOD_COMMAND
                   .replace("---\ndescription:",
                            "---\nargument-hint: [url]\ndescription:", 1)
                   .replace("Run the fixture.", "Run the fixture on $ARGUMENTS.", 1))
        self.assertFixturePasses()

    def test_positional_dollar_one_counts_as_consumption(self):
        self.write("plugins/foo/commands/do.md",
                   GOOD_COMMAND
                   .replace("---\ndescription:",
                            "---\nargument-hint: [url]\ndescription:", 1)
                   .replace("Run the fixture.", "Run the fixture on $1.", 1))
        self.assertFixturePasses()

    # ---- T-022: markdown links -------------------------------------------

    def test_broken_link_in_a_command_fails(self):
        self.write("plugins/foo/commands/do.md",
                   GOOD_COMMAND.replace(
                       "Run the fixture.",
                       "See [notes](references/missing.md).", 1))
        self.assertFixtureFails("does not exist")

    def test_broken_link_in_a_skill_fails(self):
        self.write("plugins/foo/skills/bar/SKILL.md",
                   GOOD_SKILL.replace("Body.", "See [x](refs/nope.md)."))
        self.assertFixtureFails("does not exist")

    def test_link_resolves_relative_to_the_containing_file(self):
        """A link is resolved from ITS OWN directory, not the repo root."""
        self.write("plugins/foo/skills/bar/references/notes.md", "# Notes\n")
        self.write("plugins/foo/skills/bar/SKILL.md",
                   GOOD_SKILL.replace("Body.",
                                      "See [n](references/notes.md)."))
        self.assertFixturePasses()

    def test_same_named_file_at_repo_root_does_not_satisfy_a_nested_link(self):
        self.write("notes.md", "# Notes\n")   # decoy at the root
        self.write("plugins/foo/skills/bar/SKILL.md",
                   GOOD_SKILL.replace("Body.", "See [n](notes.md)."))
        self.assertFixtureFails("does not exist")

    def test_external_links_are_not_checked(self):
        self.write("plugins/foo/skills/bar/SKILL.md",
                   GOOD_SKILL.replace(
                       "Body.",
                       "See [x](https://example.invalid/nope) and "
                       "[m](mailto:a@example.com)."))
        self.assertFixturePasses()

    def test_missing_anchor_in_a_local_markdown_target_fails(self):
        self.write("plugins/foo/skills/bar/references/notes.md",
                   "# Real Heading\n")
        self.write("plugins/foo/skills/bar/SKILL.md",
                   GOOD_SKILL.replace(
                       "Body.",
                       "See [n](references/notes.md#no-such-heading)."))
        self.assertFixtureFails("no matching heading")

    def test_present_anchor_passes(self):
        self.write("plugins/foo/skills/bar/references/notes.md",
                   "# Real Heading\n")
        self.write("plugins/foo/skills/bar/SKILL.md",
                   GOOD_SKILL.replace(
                       "Body.", "See [n](references/notes.md#real-heading)."))
        self.assertFixturePasses()

    # ---- T-017: portability guards on every component type ---------------

    def test_cwd_relative_helper_in_a_command_fails(self):
        self.write("plugins/foo/commands/do.md",
                   GOOD_COMMAND.replace(
                       "Run the fixture.",
                       "Run `python3 scripts/helper.py` now.", 1))
        self.assertFixtureFails("CWD-relative helper invocation")

    def test_cwd_relative_helper_in_a_skill_still_fails(self):
        self.write("plugins/foo/skills/bar/SKILL.md",
                   GOOD_SKILL.replace("Body.",
                                      "Run `python3 scripts/helper.py`."))
        self.assertFixtureFails("CWD-relative helper invocation")

    def test_dangling_plugin_root_ref_in_a_command_fails(self):
        self.write("plugins/foo/commands/do.md",
                   GOOD_COMMAND.replace(
                       "Run the fixture.",
                       "Run `${CLAUDE_PLUGIN_ROOT}/scripts/gone.py`.", 1))
        self.assertFixtureFails("does not exist in plugin")

    def test_valid_plugin_root_ref_passes_everywhere(self):
        body = "Run `${CLAUDE_PLUGIN_ROOT}/scripts/helper.py`."
        self.write("plugins/foo/commands/do.md",
                   GOOD_COMMAND.replace("Run the fixture.", body, 1))
        self.write("plugins/foo/skills/bar/SKILL.md",
                   GOOD_SKILL.replace("Body.", body))
        self.assertFixturePasses()

    def test_dangling_plugin_root_ref_in_an_agent_fails(self):
        self.write("plugins/foo/agents/an-agent.md",
                   "---\nname: an-agent\ndescription: fixture agent\n---\n\n"
                   "Run `${CLAUDE_PLUGIN_ROOT}/scripts/gone.py`.\n")
        self.write("README.md", README.replace("**0 room-* agents**",
                                               "**1 room-* agents**"))
        self.assertFixtureFails("does not exist in plugin")


class RealSuiteStaysClean(unittest.TestCase):
    def test_repo_passes_the_strengthened_checks(self):
        r = subprocess.run([sys.executable, SELF_CHECK, REPO, "-"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=180)
        out = (r.stdout + r.stderr).decode("utf-8", "replace")
        self.assertEqual(r.returncode, 0, out)
        self.assertRegex(out, r"== \d+ pass, \d+ warn, 0 fail ==")


if __name__ == "__main__":
    unittest.main()
