"""One-to-one legacy command to native Codex skill conversion checks."""

import glob
import hashlib
import json
import os
import re
import unittest

import yaml


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_ROOT = os.path.abspath(
    os.environ.get(
        "SOLO_SUITE_SOURCE_ROOT",
        os.path.join(REPO, "..", "solo-suite-v1.0.27-work"),
    )
)
MAP_FILE = os.path.join(REPO, "command-map.json")
LEGACY_SOURCE_PATHS_FIXTURE = os.path.join(
    REPO, "tests", "fixtures", "legacy_command_source_paths.json"
)

LEGACY_INVOCATION = re.compile(r"/[a-z0-9-]+:[a-z0-9*-]+", re.I)
SENSITIVE_WORKFLOW = re.compile(
    r"\b(?:fix|repair|migrat\w*|deploy\w*|sync\w*|submit\w*|secret\w*|"
    r"push\w*|commit\w*|create[- ]branch|delete\w*|overwrite\w*|rollback\w*)\b",
    re.I,
)


def read_yaml(path):
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def skill_frontmatter(path):
    with open(path, encoding="utf-8") as handle:
        content = handle.read()
    match = re.match(r"^---\n(.*?)\n---\n", content, re.S)
    if not match:
        raise AssertionError("invalid SKILL.md frontmatter: " + path)
    return yaml.safe_load(match.group(1)), content


def sorted_paths_sha256(paths):
    """Fingerprint an exact path set using the fixture's canonical encoding."""
    payload = "".join(path + "\n" for path in sorted(paths)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class CommandSkills(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(MAP_FILE, encoding="utf-8") as handle:
            cls.mapping = json.load(handle)
        with open(LEGACY_SOURCE_PATHS_FIXTURE, encoding="utf-8") as handle:
            cls.legacy_source_paths = json.load(handle)

    def test_every_source_command_has_exactly_one_mapped_skill(self):
        fixture = self.legacy_source_paths
        self.assertEqual(
            fixture,
            {
                "schema": "solo-suite/legacy-command-source-paths-v1",
                "algorithm": "sha256",
                "canonicalization": (
                    "UTF-8 forward-slash paths, ordinal sort, one LF after every path"
                ),
                "path_count": 125,
                "sorted_paths_sha256": (
                    "cbb853ba7326f25fcb989d65e4a7d0c1947ecd4ed8f99c6fc8d2dd0b7b2037fa"
                ),
            },
        )
        mapped_sources = [item["source_path"] for item in self.mapping]

        self.assertEqual(len(mapped_sources), fixture["path_count"])
        self.assertEqual(len(mapped_sources), len(set(mapped_sources)))
        self.assertEqual(
            sorted_paths_sha256(mapped_sources), fixture["sorted_paths_sha256"]
        )

        for item in self.mapping:
            self.assertFalse(item["source_path"].startswith(("../", "/")))
            self.assertEqual(item["source_path"], item["source_path"].replace("\\", "/"))
            expected_target = os.path.join(
                "plugins",
                item["plugin"],
                "skills",
                item["plugin"] + "-" + item["command"],
                "SKILL.md",
            ).replace(os.sep, "/")
            self.assertEqual(item["target_path"], expected_target)
            self.assertTrue(os.path.isfile(os.path.join(REPO, item["target_path"])))

    def test_mapping_keys_are_unique_and_invocations_are_native(self):
        self.assertEqual(len(self.mapping), 125)
        for key in (
            "legacy_invocation",
            "skill_invocation",
            "codex_invocation",
            "skill_name",
            "source_path",
            "target_path",
        ):
            values = [item[key] for item in self.mapping]
            self.assertEqual(len(values), len(set(values)), key)

        for item in self.mapping:
            self.assertEqual(
                item["legacy_invocation"],
                "/{}:{}".format(item["plugin"], item["command"]),
            )
            self.assertEqual(item["skill_name"], item["plugin"] + "-" + item["command"])
            self.assertEqual(item["skill_invocation"], "$" + item["skill_name"])
            self.assertEqual(item["codex_invocation"], item["skill_invocation"])

    def test_skill_metadata_and_explicit_policy(self):
        for item in self.mapping:
            target = os.path.join(REPO, item["target_path"])
            frontmatter, _content = skill_frontmatter(target)
            self.assertEqual(set(frontmatter), {"name", "description"}, target)
            self.assertEqual(frontmatter["name"], item["skill_name"])

            agent_yaml = read_yaml(
                os.path.join(os.path.dirname(target), "agents", "openai.yaml")
            )
            interface = agent_yaml["interface"]
            short_description = interface["short_description"]
            self.assertGreaterEqual(len(short_description), 25, target)
            self.assertLessEqual(len(short_description), 64, target)
            self.assertIn("$" + item["skill_name"], interface["default_prompt"])
            self.assertIs(
                agent_yaml["policy"]["allow_implicit_invocation"], False, target
            )
            self.assertIs(item["allow_implicit_invocation"], False, target)

    def test_sensitive_workflows_are_never_implicit(self):
        sensitive = []
        for item in self.mapping:
            source = os.path.abspath(os.path.join(SOURCE_ROOT, item["source_path"]))
            if not os.path.isfile(source):
                continue
            with open(source, encoding="utf-8") as handle:
                source_text = handle.read()
            if not SENSITIVE_WORKFLOW.search(source_text):
                continue
            sensitive.append(item["skill_name"])
            target = os.path.join(REPO, item["target_path"])
            agent_yaml = read_yaml(
                os.path.join(os.path.dirname(target), "agents", "openai.yaml")
            )
            self.assertIs(
                agent_yaml["policy"]["allow_implicit_invocation"], False, target
            )
        if os.path.isdir(SOURCE_ROOT):
            self.assertGreater(len(sensitive), 0)

    def test_claude_command_runtime_tokens_are_removed(self):
        for item in self.mapping:
            target = os.path.join(REPO, item["target_path"])
            _frontmatter, content = skill_frontmatter(target)
            self.assertNotIn("$ARGUMENTS", content, target)
            self.assertNotIn("CLAUDE_PLUGIN_ROOT", content, target)
            self.assertNotRegex(content, LEGACY_INVOCATION, target)
            self.assertNotRegex(content.lower(), r"slash commands?", target)
            self.assertNotIn("Next Recommended Command", content, target)
            self.assertNotIn("$plugin-command", content, target)
            self.assertNotRegex(content, r"(?m)^/…$", target)


    def test_converter_never_emits_a_generic_followup_placeholder(self):
        converter = os.path.join(REPO, "tools", "convert_commands_to_skills.mjs")
        with open(converter, encoding="utf-8") as handle:
            content = handle.read()
        self.assertNotIn("$plugin-command", content)

    def test_recommended_followup_skills_resolve(self):
        known = {
            os.path.basename(path)
            for path in glob.glob(os.path.join(REPO, "plugins", "*", "skills", "*"))
            if os.path.isdir(path)
        }
        pattern = re.compile(
            r"## Next Recommended Skill\s+\$([a-z0-9-]+)", re.I
        )
        for item in self.mapping:
            target = os.path.join(REPO, item["target_path"])
            _frontmatter, content = skill_frontmatter(target)
            match = pattern.search(content)
            if match:
                self.assertIn(match.group(1), known, target)


if __name__ == "__main__":
    unittest.main()
