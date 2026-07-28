"""self_check.py regression tests — POSIX/Windows separator handling, a full
run against this repo, and breakage detection against a synthetic mini-suite.
On windows-latest CI the full-run test exercises real backslash glob results;
on POSIX the separator logic is regression-tested directly."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELF = os.path.join(REPO, "plugins", "solo", "skills", "suite-integrity",
                    "scripts", "self_check.py")
VALIDATOR = os.path.join(REPO, "plugins", "ai", "skills",
                         "agent-room-templates", "scripts", "validate_rooms.py")


def run_self_check(root):
    return subprocess.run(
        [sys.executable, SELF, root, "-"], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
        env=dict(os.environ, PYTHONIOENCODING="utf-8"))


class SeparatorRegression(unittest.TestCase):
    def test_normalization_fix_present(self):
        with open(SELF, encoding="utf-8") as f:
            src = f.read()
        self.assertIn('p.replace(os.sep, "/") for p in '
                      'glob.glob("plugins/*/commands/*.md")', src,
                      "W1 Windows fix (v1.0.9) must stay in place")

    def test_windows_separator_logic(self):
        # glob on Windows returns os.sep-joined paths; the fixed expression
        # must still derive plugin names, the raw split must not.
        paths = ["plugins\\solo\\commands\\x.md", "plugins\\ai\\commands\\y.md"]
        fixed = sorted(p.replace("\\", "/") for p in paths)
        self.assertEqual([p.split("/")[1] for p in fixed], ["ai", "solo"])
        with self.assertRaises(IndexError):
            [p.split("/")[1] for p in paths]


class FullRun(unittest.TestCase):
    def test_repo_passes_all_checks(self):
        r = run_self_check(REPO)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 fail", r.stdout)
        self.assertIn("NOT proof of runtime health", r.stdout)
        # at least the core check families must have passed
        import re as _re
        m = _re.search(r"== (\d+) pass", r.stdout)
        self.assertGreaterEqual(int(m.group(1)), 8, r.stdout)


class BreakageDetection(unittest.TestCase):
    def _mini_suite(self, root):
        def w(rel, content):
            p = os.path.join(root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(content)
        w(".claude-plugin/marketplace.json", json.dumps({
            "name": "t", "owner": {"name": "t"},
            "metadata": {"description": "d", "version": "0.0.1"},
            "plugins": [
                {"name": "foo", "source": "./plugins/foo", "description": "foo"},
                {"name": "ai", "source": "./plugins/ai", "description": "rooms"},
            ]}))
        w("README.md", "- **2 plugins** · **2 skills** · "
                       "**1 slash commands** · **1 stdlib helper scripts** · "
                       "**0 room-* agents**\n")
        w("CHANGELOG.md", "# Changelog\n\n## 0.0.1 — test\n")
        w("plugins/foo/.claude-plugin/plugin.json", json.dumps(
            {"name": "foo", "version": "0.0.1", "description": "d"}))
        # The body must actually consume the argument the hint advertises:
        # self_check enforces hint<->body agreement in both directions, so a
        # hint with no $ARGUMENTS is now a failure, not a valid control.
        w("plugins/foo/commands/go.md",
          "---\ndescription: run\nargument-hint: [x]\n---\nBody $ARGUMENTS\n"
          "\n## Output\nDone\n")
        w("plugins/foo/skills/s1/SKILL.md",
          "---\nname: s1\ndescription: d\n---\nBody\n")
        w("plugins/ai/.claude-plugin/plugin.json", json.dumps(
            {"name": "ai", "version": "0.0.1", "description": "d"}))
        w("plugins/ai/skills/agent-room-templates/SKILL.md",
          "---\nname: agent-room-templates\ndescription: d\n---\nBody\n")
        os.makedirs(os.path.join(root, "plugins/ai/skills/agent-room-templates/scripts"),
                    exist_ok=True)
        shutil.copy(VALIDATOR, os.path.join(
            root, "plugins/ai/skills/agent-room-templates/scripts/validate_rooms.py"))

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="selfcheck-fixture-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self._mini_suite(self.tmp)

    def test_control_fixture_passes(self):
        r = run_self_check(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 fail", r.stdout)

    def test_readme_count_drift_fails(self):
        p = os.path.join(self.tmp, "README.md")
        with open(p, encoding="utf-8") as f:
            s = f.read().replace("**2 plugins**", "**9 plugins**")
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(s)
        r = run_self_check(self.tmp)
        self.assertEqual(r.returncode, 1)
        self.assertIn("README counts mismatch", r.stdout)

    def test_description_count_drift_fails(self):
        """v1.0.17 (blocker 2): a count-bearing claim in ANY marketplace
        entry or plugin.json description that the filesystem does not
        back must fail the self-check — not only the root metadata."""
        p = os.path.join(self.tmp, ".claude-plugin", "marketplace.json")
        with open(p, encoding="utf-8") as f:
            mk = json.load(f)
        ai = next(e for e in mk["plugins"] if e["name"] == "ai")
        ai["description"] = "Ships 99 room-* agent definitions in agents/."
        with open(p, "w", encoding="utf-8", newline="") as f:
            json.dump(mk, f)
        r = run_self_check(self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("claims 99", r.stdout)
        # and the same drift inside a plugin.json fails too
        with open(p, "w", encoding="utf-8", newline="") as f:
            json.dump(mk, f)
        pj = os.path.join(self.tmp, "plugins", "ai", ".claude-plugin",
                          "plugin.json")
        with open(pj, encoding="utf-8") as f:
            d = json.load(f)
        d["description"] = "5 skills and 7 commands ship here."
        with open(pj, "w", encoding="utf-8", newline="") as f:
            json.dump(d, f)
        r = run_self_check(self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("claims 5", r.stdout)

    def test_bad_agentroom_fails_via_validator(self):
        room = {
            "schema": "solo-suite/agentroom-v1", "name": "bad",
            "stages": [["a", "b"]],
            "seats": [
                {"id": "a", "role": "r", "reads": [], "writes": ["w.md"],
                 "commands": [], "deliverable": "d",
                 "handoff_to": "b", "handoff_check": "/ai:handoff-check"},
                {"id": "b", "role": "r", "reads": [], "writes": ["v.md"],
                 "commands": [], "deliverable": "d",
                 "handoff_to": None, "handoff_check": "/ai:handoff-check"},
            ],
            "exit_gate": None, "exit_criteria": "done",
        }
        p = os.path.join(self.tmp,
                         "plugins/ai/skills/agent-room-templates/agentsrooms/bad.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(room, f)
        r = run_self_check(self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("SAME stage", r.stdout)
        self.assertIn("exit_gate_note", r.stdout)



def load_self_check():
    import importlib.util
    spec = importlib.util.spec_from_file_location("self_check_mod", SELF)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FrontmatterAnchoring(unittest.TestCase):
    """The closing --- must be a STANDALONE line: `value---` is invalid and
    equals what the official loader silently drops at runtime."""

    @classmethod
    def setUpClass(cls):
        cls.sc = load_self_check()

    def test_glued_closing_delimiter_is_invalid(self):
        text = '---\ndescription: d\nargument-hint: "[a | b]"---\nBody\n'
        fm, err, _ = self.sc.parse_frontmatter(text)
        self.assertIsNone(fm)
        self.assertIn("standalone", err)

    def test_glued_boolean_delimiter_is_invalid(self):
        text = "---\ndescription: d\ndisable-model-invocation: true---\nBody\n"
        fm, err, _ = self.sc.parse_frontmatter(text)
        self.assertIsNone(fm)
        self.assertIn("standalone", err)

    def test_standalone_closing_delimiter_parses(self):
        text = '---\ndescription: d\nargument-hint: "[a | b]"\n---\nBody\n'
        fm, err, body = self.sc.parse_frontmatter(text)
        self.assertIsNone(err)
        self.assertEqual(fm["description"], "d")
        self.assertEqual(body.strip(), "Body")

    def test_closing_delimiter_with_trailing_spaces_ok(self):
        fm, err, _ = self.sc.parse_frontmatter("---\na: b\n---   \nBody\n")
        self.assertIsNone(err)
        self.assertEqual(fm["a"], "b")

    def test_crlf_delimiters_ok(self):
        fm, err, _ = self.sc.parse_frontmatter("---\r\na: b\r\n---\r\nBody\r\n")
        self.assertIsNone(err)
        self.assertEqual(fm["a"], "b")

    def test_opening_must_be_first_line(self):
        fm, err, _ = self.sc.parse_frontmatter("\n---\na: b\n---\nBody\n")
        self.assertIsNone(fm)
        self.assertIsNone(err)   # treated as "no frontmatter", not an error

    def test_dashes_inside_values_are_not_delimiters(self):
        text = "---\ndescription: uses --- inside a value\n---\nBody\n"
        fm, err, _ = self.sc.parse_frontmatter(text)
        # the mid-value '---' is not line-anchored; the standalone one closes
        self.assertIsNone(err)
        self.assertIn("---", str(fm["description"]))

    def test_official_key_sets_include_current_platform_keys(self):
        for k in ("license", "metadata", "context", "agent", "hooks",
                  "compatibility", "arguments", "disallowed-tools",
                  "effort", "paths", "shell", "when_to_use"):
            self.assertIn(k, self.sc.OFFICIAL_SKILL_KEYS, k)
        for k in ("tools", "model", "color", "isolation", "disallowedTools",
                  "maxTurns", "skills", "memory", "background", "effort",
                  "initialPrompt"):
            self.assertIn(k, self.sc.OFFICIAL_AGENT_KEYS, k)
        # the pre-2.x kebab-case agent field is NOT official any more
        self.assertNotIn("permission-mode", self.sc.OFFICIAL_AGENT_KEYS)
        # fields IGNORED on plugin-shipped agents are rejected outright
        for k in ("hooks", "mcpServers", "permissionMode"):
            self.assertNotIn(k, self.sc.OFFICIAL_AGENT_KEYS, k)
            self.assertIn(k, self.sc.PLUGIN_AGENT_REJECTED_KEYS, k)

    def test_suite_skill_frontmatter_contract_is_exact(self):
        self.assertEqual(self.sc.SUITE_SKILL_KEYS, {"name", "description"})
        self.assertIn("disable-model-invocation", self.sc.OFFICIAL_SKILL_KEYS)

    def test_shell_values_bash_powershell_only(self):
        self.assertEqual(self.sc.SKILL_FIELD_VALUES["shell"],
                         {"bash", "powershell"})

    def test_schemastore_urls_are_the_official_catalog_entries(self):
        self.assertEqual(self.sc.PLUGIN_SCHEMA_URL,
                         "https://www.schemastore.org/"
                         "claude-code-plugin-manifest.json")
        self.assertEqual(self.sc.MARKETPLACE_SCHEMA_URL,
                         "https://www.schemastore.org/"
                         "claude-code-marketplace.json")


class AgentValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sc = load_self_check()

    def _run_plugin(self, root):
        fails, warns, passes = [], [], []
        self.sc.check_plugin_content(root, "p", fails.append, warns.append,
                                     passes)
        return fails

    def test_agent_with_unknown_key_fails(self):
        tmp = tempfile.mkdtemp(prefix="agentcheck-")
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "agents"))
        with open(os.path.join(tmp, "agents", "room-x.md"), "w",
                  encoding="utf-8") as f:
            f.write("---\nname: room-x\ndescription: d\nbanana: yes\n---\nP\n")
        fails = self._run_plugin(tmp)
        self.assertTrue(any("banana" in x for x in fails), fails)

    def test_agent_with_glued_delimiter_fails(self):
        tmp = tempfile.mkdtemp(prefix="agentcheck-")
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "agents"))
        with open(os.path.join(tmp, "agents", "room-y.md"), "w",
                  encoding="utf-8") as f:
            f.write("---\nname: room-y\ndescription: d---\nP\n")
        fails = self._run_plugin(tmp)
        self.assertTrue(any("standalone" in x for x in fails), fails)

    def test_invalid_isolation_value_fails(self):
        tmp = tempfile.mkdtemp(prefix="agentcheck-")
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "agents"))
        with open(os.path.join(tmp, "agents", "room-w.md"), "w",
                  encoding="utf-8") as f:
            f.write("---\nname: room-w\ndescription: d\n"
                    "isolation: container\n---\nP\n")
        fails = self._run_plugin(tmp)
        self.assertTrue(any("isolation" in x and "documented value" in x
                            for x in fails), fails)

    def test_rejected_plugin_agent_fields_fail(self):
        """hooks / mcpServers / permissionMode are IGNORED on plugin-shipped
        agents — self_check must fail them, whatever their value."""
        for key, value in (("permissionMode", "default"),
                           ("mcpServers", "slack"),
                           ("hooks", "x")):
            tmp = tempfile.mkdtemp(prefix="agentcheck-")
            self.addCleanup(shutil.rmtree, tmp, True)
            os.makedirs(os.path.join(tmp, "agents"))
            with open(os.path.join(tmp, "agents", "room-v.md"), "w",
                      encoding="utf-8") as f:
                f.write("---\nname: room-v\ndescription: d\n"
                        "%s: %s\n---\nP\n" % (key, value))
            fails = self._run_plugin(tmp)
            self.assertTrue(any(key in x and "IGNORED" in x for x in fails),
                            (key, fails))

    def test_skill_frontmatter_extra_key_is_rejected(self):
        tmp = tempfile.mkdtemp(prefix="skillcheck-")
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "skills", "s1"))
        with open(os.path.join(tmp, "skills", "s1", "SKILL.md"), "w",
                  encoding="utf-8") as f:
            f.write("---\nname: s1\ndescription: d\nshell: none\n---\nB\n")
        fails = self._run_plugin(tmp)
        self.assertTrue(any("exactly name + description" in x and
                            "shell" in x for x in fails), fails)

    def test_platform_supported_skill_keys_are_still_rejected_by_suite_policy(self):
        tmp = tempfile.mkdtemp(prefix="skillcheck-")
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "skills", "s2"))
        with open(os.path.join(tmp, "skills", "s2", "SKILL.md"), "w",
                  encoding="utf-8") as f:
            f.write("---\nname: s2\ndescription: d\nshell: powershell\n"
                    "when_to_use: when testing field acceptance\n---\nB\n")
        fails = self._run_plugin(tmp)
        self.assertTrue(any("exactly name + description" in x and
                            "shell" in x and "when_to_use" in x
                            for x in fails), fails)

    def test_isolation_worktree_is_official(self):
        tmp = tempfile.mkdtemp(prefix="agentcheck-")
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "agents"))
        with open(os.path.join(tmp, "agents", "room-z.md"), "w",
                  encoding="utf-8") as f:
            f.write("---\nname: room-z\ndescription: d\nisolation: worktree\n---\nP\n")
        self.assertEqual(self._run_plugin(tmp), [])



if __name__ == "__main__":
    unittest.main()
