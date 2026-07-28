"""Regression guards for implementation-backed documentation claims."""
import json
import os
import unittest
import zipfile


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as stream:
        return stream.read()


class DocumentationTruth(unittest.TestCase):
    def test_readme_full_solo_loop_is_complete_and_fenced(self):
        readme = read("README.md")
        fences = [line for line in readme.splitlines()
                  if line.strip().startswith("```")]
        self.assertEqual(len(fences) % 2, 0, "README has an unclosed fence")
        self.assertIn("## A full solo loop", readme)
        loop = readme.split("## A full solo loop", 1)[1]
        for command in ("/stack:intake", "/gate:before-code",
                        "/dev:implement-feature", "/gate:before-merge",
                        "/gate:before-deploy", "/gate:production-ready"):
            self.assertIn(command, loop)

    def test_readme_vendor_audit_count_is_five(self):
        readme = read("README.md")
        self.assertIn("The five vendor audits", readme)
        self.assertNotIn("The four vendor audits", readme)

    def test_v1026_public_tag_binding_is_recorded(self):
        record = read("release", "v1.0.26-tag-verification.md")
        self.assertIn("`v1.0.26`", record)
        self.assertIn("99eb54f9113a1dab279135024ced11dc88970ef5", record)
        self.assertIn("releases/tag/v1.0.26", record)
        self.assertNotIn("<40-hex", record)

    def test_full_team_does_not_invent_dependency_floors(self):
        with open(os.path.join(REPO, "plugins", "full-team",
                               ".claude-plugin", "plugin.json"),
                  encoding="utf-8") as stream:
            manifest = json.load(stream)
        self.assertTrue(manifest["dependencies"])
        self.assertTrue(all(isinstance(name, str)
                            for name in manifest["dependencies"]))
        command = read("plugins", "full-team", "commands", "verify.md")
        self.assertIn("declares plugin **names only**", command)
        self.assertNotIn("dependency floors", command)

    def test_agentrooms_writer_scope_is_per_stage(self):
        skill = read("plugins", "ai", "skills", "agent-room-templates",
                     "SKILL.md")
        command = read("plugins", "ai", "commands", "agent-rooms.md")
        for text in (skill, command):
            self.assertIn("one writer per artifact per stage", text.lower())
        self.assertIn("declared later stage may update", skill)
        self.assertNotIn("same `.solo/` file or code area in the same room",
                         skill)

    def test_full_team_sha_bands_match_room_contract(self):
        flow = read("plugins", "solo", "commands", "full-team-dev.md")
        self.assertIn("phases 8-15 (review through docs)", flow)
        self.assertIn("update_run_state.py verify integration", flow)
        self.assertIn("update_run_state.py verify final", flow)
        self.assertNotIn("phases 8-16 all verify", flow)

    def test_connector_check_discloses_its_local_write(self):
        command = read("plugins", "stack", "commands", "connector-check.md")
        self.assertIn("External probes are read-only", command)
        self.assertIn("only write is the idempotent local project-memory",
                      command)
        with open(os.path.join(REPO, "plugins", "stack", ".claude-plugin",
                               "plugin.json"), encoding="utf-8") as stream:
            manifest = json.load(stream)
        self.assertIn("/stack:connector-check", manifest["description"])

    def test_contributing_names_the_actual_environment_boundary(self):
        contributing = read("CONTRIBUTING.md")
        self.assertIn("`release-signing` intentionally has no reviewer gate",
                      contributing)
        self.assertIn("`release-publishing` is the human approval boundary",
                      contributing)

    def test_changelog_uses_component_and_meta_plugin_terms(self):
        changelog = read("CHANGELOG.md")
        self.assertNotIn("all 18 component plugins", changelog)
        self.assertNotIn("other 17 component plugins", changelog)

    def test_project_memory_owns_the_canonical_gate_profile(self):
        memory = read("plugins", "solo", "skills",
                      "project-memory-manager", "SKILL.md")
        self.assertIn("Project profile: <slug>", memory)
        self.assertIn("HEAD:.solo/project.md", memory)
        self.assertIn("never infer it from repository", memory)
        for profile in ("public-marketing-site", "saas-application",
                        "e-commerce", "internal-application",
                        "api-service", "library-package"):
            self.assertIn("`%s`" % profile, memory)

    def test_cheatsheet_core_subject_matches_release_versions(self):
        with open(os.path.join(REPO, ".claude-plugin", "marketplace.json"),
                  encoding="utf-8") as stream:
            suite_version = json.load(stream)["metadata"]["version"]
        with open(os.path.join(REPO, "plugins", "site-doctor",
                               ".claude-plugin", "plugin.json"),
                  encoding="utf-8") as stream:
            site_version = json.load(stream)["version"]
        with zipfile.ZipFile(os.path.join(
                REPO, "site-doctor-cheatsheet.docx")) as archive:
            core = archive.read("docProps/core.xml").decode("utf-8")
            document = archive.read("word/document.xml").decode("utf-8")
        expected = ("site-doctor v%s command and prompt reference "
                    "(solo-suite %s)" % (site_version, suite_version))
        self.assertIn(expected, core)
        self.assertIn("v%s" % site_version, document)
        self.assertIn("solo-suite %s" % suite_version, document)


if __name__ == "__main__":
    unittest.main()
