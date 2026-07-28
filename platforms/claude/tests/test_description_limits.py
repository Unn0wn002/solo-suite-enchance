"""Description-length and synchronization contracts (T-008, T-009, T-016).

Anthropic's plugin-dev guidance sets two limits that this suite had drifted far
past: command `description` should stay within ~60 characters because /help and
the command picker truncate it, and a plugin manifest `description` should stay
under 200 because that is what the marketplace browser shows. Before this test
114 of 125 commands and 15 of 19 manifests were over.

The limits are asserted mechanically so they cannot drift back. Note that
several descriptions also carry MANDATED content -- the gate entry must disclose
the self-attested evidence limit and name its six commands, `stack` must name
/stack:connector-check, and the `ai` entry must state its room-agent count --
which tests/test_semantic_regressions.py and tests/test_documentation_truth.py
enforce independently. Shortening must never drop those; these limits are a
ceiling, not a licence to delete a contract.
"""
import glob
import io
import json
import os
import re
import unittest


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMAND_LIMIT = 60
MANIFEST_LIMIT = 200

FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)


def frontmatter(path):
    with io.open(path, encoding="utf-8") as stream:
        text = stream.read()
    match = FRONTMATTER.match(text)
    if match is None:
        return None
    fields, key = {}, None
    for line in match.group(1).split("\n"):
        if re.match(r"^[A-Za-z0-9_.-]+\s*:", line):
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
        elif key and line.strip():
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


class CommandDescriptions(unittest.TestCase):
    def commands(self):
        return sorted(glob.glob(os.path.join(REPO, "plugins", "*",
                                             "commands", "*.md")))

    def test_every_command_has_a_description(self):
        missing = [os.path.relpath(p, REPO) for p in self.commands()
                   if not (frontmatter(p) or {}).get("description")]
        self.assertEqual(missing, [])

    def test_no_command_description_exceeds_the_help_limit(self):
        over = []
        for path in self.commands():
            desc = frontmatter(path)["description"]
            if len(desc) > COMMAND_LIMIT:
                over.append("%s (%d)" % (os.path.relpath(path, REPO),
                                         len(desc)))
        self.assertEqual(
            over, [],
            "command descriptions over %d chars truncate in /help: %s"
            % (COMMAND_LIMIT, over))

    def test_descriptions_are_yaml_safe(self):
        """An unquoted YAML scalar cannot contain ': '."""
        bad = []
        for path in self.commands():
            desc = frontmatter(path)["description"]
            if ": " in desc:
                bad.append(os.path.relpath(path, REPO))
        self.assertEqual(bad, [], "quote these or use ' - ': %s" % bad)

    def test_descriptions_are_distinct(self):
        seen = {}
        for path in self.commands():
            desc = frontmatter(path)["description"].strip().lower()
            seen.setdefault(desc, []).append(os.path.relpath(path, REPO))
        dupes = {d: p for d, p in seen.items() if len(p) > 1}
        self.assertEqual(dupes, {},
                         "identical descriptions cannot be told apart")

    def test_near_neighbour_commands_stay_distinguishable(self):
        """Pairs that compete for the same request must not read alike."""
        def desc(rel):
            return frontmatter(os.path.join(REPO, rel))["description"]
        pairs = [
            ("plugins/gate/commands/production-ready.md",
             "plugins/gate/commands/score-project.md"),
            ("plugins/seo/commands/page.md",
             "plugins/site-doctor/commands/seo.md"),
            ("plugins/seo/commands/local.md",
             "plugins/seo/commands/maps.md"),
            ("plugins/site-doctor/commands/audit-site.md",
             "plugins/site-doctor/commands/full-checkup.md"),
        ]
        for left, right in pairs:
            self.assertNotEqual(desc(left).lower(), desc(right).lower(),
                                "%s vs %s" % (left, right))


class SkillDescriptions(unittest.TestCase):
    """Skills have no length ceiling (they are the model's routing text), but
    they share the commands' YAML hazard: an unquoted scalar cannot contain
    ': '. Three skill descriptions were silently dropped by the official
    loader during T-013 before this guard existed."""

    def skills(self):
        return sorted(glob.glob(os.path.join(REPO, "plugins", "*", "skills",
                                             "*", "SKILL.md")))

    def test_every_skill_has_name_and_description(self):
        bad = []
        for path in self.skills():
            fields = frontmatter(path) or {}
            if not fields.get("name") or not fields.get("description"):
                bad.append(os.path.relpath(path, REPO))
        self.assertEqual(bad, [])

    def test_skill_descriptions_are_yaml_safe(self):
        bad = []
        for path in self.skills():
            desc = frontmatter(path)["description"]
            if ": " in desc:
                bad.append(os.path.relpath(path, REPO))
        self.assertEqual(
            bad, [],
            "': ' makes the frontmatter invalid YAML and the loader drops the "
            "whole block - use ' - ' instead: %s" % bad)

    def test_skill_name_matches_its_directory(self):
        bad = []
        for path in self.skills():
            expected = os.path.basename(os.path.dirname(path))
            if frontmatter(path)["name"] != expected:
                bad.append(os.path.relpath(path, REPO))
        self.assertEqual(bad, [])


class ManifestDescriptions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with io.open(os.path.join(REPO, ".claude-plugin", "marketplace.json"),
                     encoding="utf-8") as stream:
            cls.marketplace = json.load(stream)
        cls.manifests = {}
        for path in sorted(glob.glob(os.path.join(
                REPO, "plugins", "*", ".claude-plugin", "plugin.json"))):
            with io.open(path, encoding="utf-8") as stream:
                data = json.load(stream)
            cls.manifests[data["name"]] = data

    def test_no_plugin_description_exceeds_the_marketplace_limit(self):
        over = ["%s (%d)" % (name, len(data["description"]))
                for name, data in sorted(self.manifests.items())
                if len(data["description"]) > MANIFEST_LIMIT]
        self.assertEqual(over, [],
                         "plugin.json descriptions over %d chars: %s"
                         % (MANIFEST_LIMIT, over))

    def test_no_marketplace_entry_exceeds_the_limit(self):
        over = ["%s (%d)" % (e["name"], len(e["description"]))
                for e in self.marketplace["plugins"]
                if len(e["description"]) > MANIFEST_LIMIT]
        self.assertEqual(over, [])

    def test_every_entry_description_mirrors_its_plugin_json(self):
        """T-009: the two copies must never diverge."""
        drift = []
        for entry in self.marketplace["plugins"]:
            manifest = self.manifests[entry["name"]]
            if entry["description"] != manifest["description"]:
                drift.append(entry["name"])
        self.assertEqual(
            drift, [],
            "marketplace entry and plugin.json descriptions differ: %s"
            % drift)

    def test_every_entry_carries_the_plugin_display_name(self):
        """T-016: displayName is a marketplace-ENTRY key. All 19 labels sat
        only in plugin.json, where the published manifest schema defines
        displayName under channels/userConfig and not at the root, so the
        intended "solo-suite <x>" names never reached the plugin browser --
        16 of the 19 plugin names are single generic words (dev, test, git,
        docs, ...) with nothing to disambiguate them."""
        missing, drift = [], []
        for entry in self.marketplace["plugins"]:
            manifest = self.manifests[entry["name"]]
            if "displayName" not in entry:
                missing.append(entry["name"])
            elif entry["displayName"] != manifest.get("displayName"):
                drift.append(entry["name"])
        self.assertEqual(missing, [], "marketplace entries without a "
                                      "displayName: %s" % missing)
        self.assertEqual(drift, [], "displayName differs between the "
                                    "marketplace entry and plugin.json: %s"
                         % drift)

    def test_display_names_do_not_replace_the_name_slug(self):
        """The immutable install identity must stay the slug."""
        for entry in self.marketplace["plugins"]:
            self.assertRegex(entry["name"], r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
            self.assertNotEqual(entry["name"], entry.get("displayName"))

    def test_every_declared_plugin_has_a_manifest(self):
        self.assertEqual(
            sorted(e["name"] for e in self.marketplace["plugins"]),
            sorted(self.manifests))

    def test_seo_metadata_lists_its_orchestrator_and_new_skills(self):
        """T-010: seo, seo-flow and seo-maps must be discoverable."""
        manifest = self.manifests["seo"]
        entry = next(e for e in self.marketplace["plugins"]
                     if e["name"] == "seo")
        for needed in ("seo", "seo-flow", "seo-maps"):
            self.assertIn(needed, manifest["keywords"], needed)
            self.assertIn(needed, entry["tags"], needed)
        self.assertEqual(manifest["keywords"], entry["tags"],
                         "seo keywords and marketplace tags must match")
        for skill in ("seo", "seo-flow", "seo-maps"):
            self.assertTrue(
                os.path.isfile(os.path.join(REPO, "plugins", "seo", "skills",
                                            skill, "SKILL.md")),
                "declared skill does not exist: %s" % skill)


if __name__ == "__main__":
    unittest.main()
