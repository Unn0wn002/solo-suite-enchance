"""Semantic regression tripwires (v1.0.16, item 17) — these fail on
REINTRODUCTION of repaired defects, independent of the validator:

  * SHA-carrier language: no plugin doc/template may describe BASE_SHA /
    INTEGRATION_SHA / FINAL_SHA as stored in .solo/handoff.md, tasks.md,
    or decisions.md — the ONLY carrier is untracked .solo/run-state/.
  * early specialist evidence records: no non-finalizer seat may claim a
    final gate-evidence JSON record was written mid-flow.
  * gatekeeper/steward discipline after finalization.
  * the evidence finalizer must be a REAL shipped agent in both
    production rooms.
  * room-agent SHA prerequisites must be conditional on a room-supplied
    contract (a non-worktree room never creates an INTEGRATION_SHA).
  * narrative counts (README / rooms SKILL / marketplace / full-team
    description) must match the filesystem and the room JSON.
  * v1.0.17: EVERY count-bearing marketplace entry AND plugin.json
    description is checked against the actual inventory — never only the
    root marketplace description (the v1.0.16 audit found 'Ships 20
    room-* agent definitions' surviving while the root said 24).
  * v1.0.17: run-state writes go through update_run_state.py — the
    finalization docs name the helper, and no doc instructs writing
    .solo/run-state JSON by hand.
"""
import glob
import io
import json
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOMS = os.path.join(REPO, "plugins", "ai", "skills",
                     "agent-room-templates", "agentsrooms")

SHA_WORDS = ("BASE_SHA", "INTEGRATION_SHA", "FINAL_SHA", "BASE SHA",
             "INTEGRATION SHA", "FINAL SHA")
TRACKED_CARRIERS = ("handoff.md", "tasks.md", "decisions.md")
# words that mark a line as NEGATING the carrier pattern (e.g. "never a
# tracked file", "no tasks.md", "cannot contain its own SHA")
NEGATION_MARKERS = ("never", "NEVER", "not ", "NOT ", "no ", "cannot",
                    "impossible", "untracked", "UNTRACKED", "structurally")


def _iter_plugin_text_files():
    for pat in ("plugins/**/*.md", "plugins/**/*.json"):
        for p in glob.glob(os.path.join(REPO, pat), recursive=True):
            yield p


def load_room(name):
    with io.open(os.path.join(ROOMS, name), encoding="utf-8") as f:
        return json.load(f)


class ShaCarrierLanguage(unittest.TestCase):
    def test_no_tracked_file_is_ever_named_as_a_sha_carrier(self):
        offenders = []
        for path in _iter_plugin_text_files():
            with io.open(path, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if not any(w in line for w in SHA_WORDS):
                        continue
                    if not any(c in line for c in TRACKED_CARRIERS):
                        continue
                    if any(m in line for m in NEGATION_MARKERS):
                        continue
                    offenders.append("%s:%d: %s"
                                     % (os.path.relpath(path, REPO), i,
                                        line.strip()[:160]))
        self.assertEqual(offenders, [],
                         "tracked-file SHA-carrier language is back:\n"
                         + "\n".join(offenders))

    def test_run_state_is_the_declared_carrier_in_both_production_rooms(self):
        for name in ("full-team-website.json", "production-release.json"):
            room = load_room(name)
            ev = room["evidence"]
            self.assertTrue(ev["final_sha_recorded_in"]
                            .startswith(".solo/run-state/"), name)
            self.assertEqual(ev["freeze"]["stored_in"],
                             ev["final_sha_recorded_in"], name)
            fin_id = ev["finalizer"]
            fin = next(s for s in room["seats"] if s["id"] == fin_id)
            self.assertIn("run-state", fin["deliverable"], name)
            self.assertNotIn("handoff.md", fin["deliverable"], name)


class EarlySpecialistRecords(unittest.TestCase):
    RECORD_CLAIM = re.compile(
        r"gate-evidence record(?:s)? (?:written|minted|produced|dropped)",
        re.I)

    def test_no_specialist_deliverable_claims_a_written_record(self):
        for name in sorted(os.listdir(ROOMS)):
            if not name.endswith(".json"):
                continue
            room = load_room(name)
            fin_id = (room.get("evidence") or {}).get("finalizer")
            for s in room["seats"]:
                if s["id"] == fin_id:
                    continue
                m = self.RECORD_CLAIM.search(s.get("deliverable", ""))
                self.assertIsNone(
                    m, "%s seat %r claims an early evidence record: %r"
                    % (name, s["id"], s.get("deliverable")))
                offending = [w for w in (list(s.get("writes") or [])
                                         + list(s.get("proposes") or []))
                             if isinstance(w, str)
                             and w.startswith(".solo/gate-evidence")]
                self.assertEqual(offending, [], (name, s["id"]))

    def test_gate_skill_no_longer_says_specialists_write_records(self):
        p = os.path.join(REPO, "plugins", "gate", "skills",
                         "production-readiness-reviewer", "SKILL.md")
        with io.open(p, encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("Each specialist phase writes its own category "
                         "record", text)
        self.assertIn("No specialist phase ever writes a category record",
                      text)

    def test_finalize_command_never_shows_standalone_verify_artifact(self):
        """verify-artifact may appear ONLY wrapped through
        record_evidence.py in the finalization docs."""
        for rel in (("plugins", "gate", "commands", "finalize-evidence.md"),
                    ("plugins", "gate", "skills",
                     "production-readiness-reviewer", "SKILL.md")):
            p = os.path.join(REPO, *rel)
            with io.open(p, encoding="utf-8") as f:
                text = f.read()
            for block in re.findall(r"```bash\n(.*?)```", text, re.S):
                if "verify-artifact" not in block:
                    continue
                self.assertIn("record_evidence.py", block,
                              "%s shows verify-artifact outside a "
                              "record_evidence.py wrapper:\n%s"
                              % (os.path.join(*rel), block))


class PostFinalDiscipline(unittest.TestCase):
    def test_gatekeeper_and_steward_have_no_post_freeze_tracked_work(self):
        for name in ("full-team-website.json", "production-release.json"):
            room = load_room(name)
            stages = [st["id"] for st in room["stages"]]
            fin_stage = stages.index("finalize")
            seat_stage = {}
            for i, st in enumerate(room["stages"]):
                for sid in st["seats"]:
                    seat_stage[sid] = i
            for s in room["seats"]:
                if seat_stage.get(s["id"], -1) < fin_stage:
                    continue
                tracked = [w for w in s.get("writes", [])
                           if not w.startswith(".solo/gate-evidence")
                           and not w.startswith(".solo/run-state")]
                self.assertEqual(tracked, [], (name, s["id"]))
                self.assertEqual(s.get("proposes", []), [],
                                 (name, s["id"]))
            steward = (room.get("memory_steward") or {})
            if steward:
                cutoff = steward["active_through_stage"]
                self.assertLess(stages.index(cutoff), fin_stage, name)


class RealFinalizerAgent(unittest.TestCase):
    def test_shipped_agent_exists_with_required_contract(self):
        p = os.path.join(REPO, "plugins", "ai", "agents",
                         "room-evidence-finalizer.md")
        self.assertTrue(os.path.isfile(p), "room-evidence-finalizer.md "
                        "must ship")
        with io.open(p, encoding="utf-8") as f:
            text = f.read()
        for needle in (".solo/run-state/<run_id>.json",
                       "HEAD == FINAL_SHA",
                       "/gate:finalize-evidence",
                       "untracked",
                       "REFUSE tracked",
                       "gatekeeper"):
            self.assertIn(needle, text.replace("HEAD equals FINAL_SHA",
                                               "HEAD == FINAL_SHA")
                          .replace("`git rev-parse HEAD` must equal "
                                   "FINAL_SHA", "HEAD == FINAL_SHA"),
                          needle)

    def test_both_production_rooms_map_finalizer_seats_to_it(self):
        for name in ("full-team-website.json", "production-release.json"):
            room = load_room(name)
            fin_id = room["evidence"]["finalizer"]
            fin = next(s for s in room["seats"] if s["id"] == fin_id)
            self.assertEqual(fin.get("agent"), "room-evidence-finalizer",
                             "%s must map the finalizer seat to the real "
                             "agent, not rely on agent_note" % name)


class ConditionalShaPrerequisites(unittest.TestCase):
    def test_no_agent_carries_the_unconditional_integration_sha_demand(self):
        for p in glob.glob(os.path.join(REPO, "plugins", "ai", "agents",
                                        "room-*.md")):
            with io.open(p, encoding="utf-8") as f:
                text = f.read()
            self.assertNotIn(
                "Integration-SHA contract:", text,
                "%s still demands an INTEGRATION_SHA unconditionally — a "
                "non-worktree room never creates one" % p)
            if "Run-SHA contract" in text:
                self.assertIn("conditional", text.split(
                    "Run-SHA contract", 1)[1][:40].lower(), p)
                self.assertIn("no SHA contract for this seat", text, p)

    def test_conditional_wording_present_in_reusable_room_agents(self):
        for name in ("room-release-manager", "room-documentation-writer",
                     "room-site-doctor", "room-devops-engineer",
                     "room-qa-engineer", "room-security-engineer",
                     "room-git-pr-manager", "room-code-reviewer",
                     "room-browser-qa-engineer", "room-ai-agent-reviewer"):
            p = os.path.join(REPO, "plugins", "ai", "agents",
                             name + ".md")
            with io.open(p, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("Run-SHA contract (conditional", text, name)
            self.assertIn("verify_at_final_sha", text, name)


class NarrativeCountDrift(unittest.TestCase):
    def setUp(self):
        self.agents = sorted(glob.glob(os.path.join(
            REPO, "plugins", "*", "agents", "*.md")))
        self.ft = load_room("full-team-website.json")
        self.staged = [s for st in self.ft["stages"] for s in st["seats"]]
        self.stages = [st["id"] for st in self.ft["stages"]]

    def test_room_json_matches_the_canonical_shape(self):
        self.assertEqual(len(self.agents), 24)
        self.assertEqual(len(self.staged), 21)
        self.assertEqual(len(self.ft["seats"]), 22)
        self.assertEqual(len(self.stages), 15)
        self.assertLess(self.stages.index("review"),
                        self.stages.index("ai-review"))
        self.assertLess(self.stages.index("ai-review"),
                        self.stages.index("qa"))
        self.assertIn("finalize", self.stages)

    def test_readme_agent_count_matches_filesystem(self):
        with io.open(os.path.join(REPO, "README.md"),
                     encoding="utf-8") as f:
            rd = f.read()
        m = re.search(r"\*\*(\d+) room-\* agents\*\*", rd)
        self.assertEqual(int(m.group(1)), len(self.agents))
        m2 = re.search(r"ship with (\d+) `room-\*` agent definitions", rd)
        self.assertIsNotNone(m2, "README narrative agent count missing")
        self.assertEqual(int(m2.group(1)), len(self.agents))

    def test_marketplace_description_count_matches_filesystem(self):
        with io.open(os.path.join(REPO, ".claude-plugin",
                                  "marketplace.json"),
                     encoding="utf-8") as f:
            mk = json.load(f)
        m = re.search(r"(\d+) room-\* agents", mk["metadata"]["description"])
        self.assertIsNotNone(m, "marketplace description agent count "
                             "missing")
        self.assertEqual(int(m.group(1)), len(self.agents))

    def test_rooms_skill_counts_match_the_room_json(self):
        p = os.path.join(REPO, "plugins", "ai", "skills",
                         "agent-room-templates", "SKILL.md")
        with io.open(p, encoding="utf-8") as f:
            text = f.read()
        m = re.search(r"(\d+) staged seats across (\d+) stages", text)
        self.assertIsNotNone(m, "rooms SKILL.md count line missing")
        self.assertEqual(int(m.group(1)), len(self.staged))
        self.assertEqual(int(m.group(2)), len(self.stages))
        m2 = re.search(r"(\d+) seat definitions total", text)
        self.assertIsNotNone(m2)
        self.assertEqual(int(m2.group(1)), len(self.ft["seats"]))
        self.assertNotIn("13 stages", text)

    def test_full_team_description_matches_its_own_json(self):
        desc = self.ft["description"]
        m = re.search(r"(\d+) staged seats", desc)
        self.assertEqual(int(m.group(1)), len(self.staged))
        m2 = re.search(r"(\d+) seat definitions total", desc)
        self.assertEqual(int(m2.group(1)), len(self.ft["seats"]))
        m3 = re.search(r"(\d+) stages including finalize", desc)
        self.assertEqual(int(m3.group(1)), len(self.stages))
        for sid in self.staged:
            seat = next(s for s in self.ft["seats"] if s["id"] == sid)
            self.assertTrue(seat.get("agent"),
                            "staged seat %r must map to a shipped agent"
                            % sid)


class CountBearingDescriptions(unittest.TestCase):
    """v1.0.17 (blocker 2): every count-bearing description — the root
    marketplace metadata, EVERY marketplace plugin entry, and EVERY
    plugins/*/.claude-plugin/plugin.json — is checked against the actual
    filesystem inventory. A count in prose that the filesystem does not
    back is a failure, wherever it appears."""

    @classmethod
    def setUpClass(cls):
        with io.open(os.path.join(REPO, ".claude-plugin",
                                  "marketplace.json"),
                     encoding="utf-8") as f:
            cls.mk = json.load(f)
        with io.open(os.path.join(
                REPO, "plugins", "gate", "skills",
                "production-readiness-reviewer", "schema",
                "gate-evidence-v1.schema.json"), encoding="utf-8") as f:
            cls.categories = len(
                json.load(f)["definitions"]["category"]["enum"])
        sc = os.path.join(REPO, "plugins", "solo", "skills",
                          "suite-integrity", "scripts", "self_check.py")
        import importlib.util
        spec = importlib.util.spec_from_file_location("sc_counts", sc)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.memory_files = len(mod.MEMORY_FILES)

    @staticmethod
    def counts_for(plugin=None):
        """Filesystem inventory, suite-wide (plugin=None) or scoped to one
        plugin directory."""
        base = os.path.join(REPO, "plugins", plugin or "*")
        g = lambda pat: len(glob.glob(pat))
        return {
            "plugins": g(os.path.join(REPO, "plugins", "*",
                                      ".claude-plugin", "plugin.json")),
            "skills": g(os.path.join(base, "skills", "*", "SKILL.md")),
            "commands": g(os.path.join(base, "commands", "*.md")),
            "scripts": g(os.path.join(base, "skills", "*", "scripts",
                                      "*.py")),
            "agents": g(os.path.join(REPO, "plugins", "*", "agents",
                                     "*.md")),
            "rooms": g(os.path.join(REPO, "plugins", "ai", "skills",
                                    "agent-room-templates", "agentsrooms",
                                    "*.json")),
        }

    def claims(self, desc, scope):
        """(claimed, actual, label) triples for every count-bearing
        pattern found in one description."""
        inv = self.counts_for(scope)
        out = []
        for m in re.finditer(r"(\d+) room-\* agents?", desc):
            out.append((int(m.group(1)), inv["agents"], "room-* agents"))
        for m in re.finditer(r"(\d+) component plugins", desc):
            out.append((int(m.group(1)), inv["plugins"] - 1,
                        "component plugins"))
        for m in re.finditer(r"(?<!component )(\d+) plugins\b", desc):
            out.append((int(m.group(1)), inv["plugins"], "plugins"))
        for m in re.finditer(r"(\d+) ((?:[a-z][a-z/-]* ){0,3})skills\b",
                             desc):
            out.append((int(m.group(1)), inv["skills"],
                        (m.group(2) + "skills").strip()))
        for m in re.finditer(r"(\d+) (?:slash )?commands\b", desc):
            out.append((int(m.group(1)), inv["commands"], "commands"))
        for m in re.finditer(r"(\d+) stdlib (?:helper )?scripts\b", desc):
            out.append((int(m.group(1)), inv["scripts"],
                        "stdlib scripts"))
        for m in re.finditer(r"(\d+) agentsrooms/\*\.json rooms", desc):
            out.append((int(m.group(1)), inv["rooms"], "agentsrooms"))
        for m in re.finditer(r"(\d+) categories\b", desc):
            out.append((int(m.group(1)), self.categories, "categories"))
        for m in re.finditer(r"(\d+)-file \.solo/", desc):
            out.append((int(m.group(1)), self.memory_files,
                        ".solo memory files"))
        for m in re.finditer(r"(\d+)-role cycle", desc):
            out.append((int(m.group(1)), self.counts_for()["plugins"] - 1,
                        "role cycle (= component plugins)"))
        return out

    def assert_counts(self, where, desc, scope):
        bad = ["%s: claims %d %s, filesystem has %d"
               % (where, claimed, label, actual)
               for claimed, actual, label in self.claims(desc, scope)
               if claimed != actual]
        self.assertEqual(bad, [], "\n".join(bad))

    def test_marketplace_metadata_description(self):
        self.assert_counts("marketplace metadata",
                           self.mk["metadata"]["description"], None)

    def test_every_marketplace_entry_description(self):
        checked = 0
        for entry in self.mk["plugins"]:
            scope = entry["source"].split("/")[-1]
            claims = self.claims(entry["description"], scope)
            checked += len(claims)
            self.assert_counts("marketplace entry %r" % entry["name"],
                               entry["description"], scope)
        self.assertGreater(checked, 0,
                           "no count-bearing entry claims found — the "
                           "patterns have gone stale")

    def test_every_plugin_json_description(self):
        checked = 0
        for pj in sorted(glob.glob(os.path.join(
                REPO, "plugins", "*", ".claude-plugin", "plugin.json"))):
            scope = os.path.basename(os.path.dirname(os.path.dirname(pj)))
            with io.open(pj, encoding="utf-8") as f:
                desc = json.load(f).get("description", "")
            claims = self.claims(desc, scope)
            checked += len(claims)
            self.assert_counts("plugins/%s/plugin.json" % scope, desc,
                               scope)
        self.assertGreater(checked, 0)

    def test_the_v1016_defect_cannot_recur(self):
        """The exact v1.0.16 audit finding: the AI entry and ai plugin.json
        must claim the SAME agent count the filesystem has (24), not a
        stale narrative number."""
        agents = self.counts_for()["agents"]
        ai_entry = next(p for p in self.mk["plugins"]
                        if p["name"] == "ai")["description"]
        m = re.search(r"(\d+) room-\* agent", ai_entry)
        self.assertIsNotNone(m, "AI entry lost its agent-count claim")
        self.assertEqual(int(m.group(1)), agents)
        with io.open(os.path.join(REPO, "plugins", "ai", ".claude-plugin",
                                  "plugin.json"), encoding="utf-8") as f:
            desc = json.load(f)["description"]
        m = re.search(r"(\d+) room-\* agent", desc)
        self.assertIsNotNone(m, "ai plugin.json lost its agent-count claim")
        self.assertEqual(int(m.group(1)), agents)


class LaunchControlScope(unittest.TestCase):
    """A complete category set must never be sold as subcontrol proof."""

    def test_public_launch_contract_states_machine_boundary_and_fail_closed(self):
        paths = (
            os.path.join(REPO, "plugins", "gate", "commands",
                         "production-ready.md"),
            os.path.join(REPO, "plugins", "gate", "skills",
                         "production-readiness-reviewer", "SKILL.md"),
        )
        required = ("error tracking", "mobile", "accessibility", "payments",
                    "transactional email", "backup", "rollback")
        for path in paths:
            with io.open(path, encoding="utf-8") as stream:
                text = stream.read().lower()
            self.assertIn("necessary but not sufficient", text, path)
            self.assertIn("separate evidence", text, path)
            self.assertIn("blocked", text, path)
            for control in required:
                self.assertIn(control, text, "%s: %s" % (path, control))


class EvidenceTrustLanguage(unittest.TestCase):
    """v1.0.19: local evidence is useful self-attestation, not a
    cryptographic origin claim. Keep the canonical-writer workflow without
    claiming that a copyable JSON field proves which process wrote a file."""

    CONTRACT_DOCS = (
        ("plugins", "gate", ".claude-plugin", "plugin.json"),
        ("plugins", "gate", "skills", "production-readiness-reviewer",
         "schema", "gate-evidence-v1.schema.json"),
        ("plugins", "gate", "skills", "production-readiness-reviewer",
         "scripts", "check_evidence.py"),
        ("plugins", "gate", "skills", "production-readiness-reviewer",
         "SKILL.md"),
        ("plugins", "gate", "commands", "finalize-evidence.md"),
        ("plugins", "gate", "commands", "production-ready.md"),
        ("plugins", "ai", "agents", "room-evidence-finalizer.md"),
        ("plugins", "ai", "agents", "room-production-gatekeeper.md"),
        ("plugins", "solo", "commands", "full-team-dev.md"),
        (".claude-plugin", "marketplace.json"),
    )

    @classmethod
    def contract_text(cls):
        chunks = []
        for rel in cls.CONTRACT_DOCS:
            with io.open(os.path.join(REPO, *rel), encoding="utf-8") as f:
                chunks.append((os.path.join(*rel), f.read()))
        return chunks

    def test_public_contracts_do_not_claim_recorder_label_proves_origin(self):
        forbidden = (
            "TRUSTED N/A OPERATION",
            "trusted N/A operation",
            "hand-written N/A JSON fails outright",
            "schema rejects any N/A record",
            "so hand-written records fail",
            "minted ONLY by the trusted",
        )
        executed_and_attested = re.compile(
            r"executed(?:\s+|-)+and(?:\s+|-)+attested", re.IGNORECASE)
        offenders = []
        for rel, text in self.contract_text():
            for phrase in forbidden:
                if phrase in text:
                    offenders.append("%s: %r" % (rel, phrase))
            if executed_and_attested.search(text):
                offenders.append("%s: executed-and-attested overclaim" % rel)
        self.assertEqual(offenders, [], "origin overclaim returned:\n"
                         + "\n".join(offenders))

    def test_public_contracts_disclose_self_attested_limit(self):
        required = {
            "plugin.json": ("self-attested", "copyable", "not proof"),
            "gate-evidence-v1.schema.json": ("copyable", "not proof"),
            "check_evidence.py": ("copyable", "cannot prove"),
            "SKILL.md": ("copyable", "cannot distinguish"),
            "finalize-evidence.md": ("copyable", "not cryptographic proof"),
            "production-ready.md": ("copyable", "cannot prove"),
            "room-evidence-finalizer.md": ("copyable", "cannot prove"),
            "room-production-gatekeeper.md": ("copyable", "cannot prove"),
            "full-team-dev.md": ("copyable", "cannot prove"),
        }
        by_name = {os.path.basename(rel): text
                   for rel, text in self.contract_text()}
        for name, needles in required.items():
            for needle in needles:
                self.assertIn(needle, by_name[name], "%s: %s" %
                              (name, needle))

    def test_gate_marketplace_entry_discloses_limit_and_exact_commands(self):
        with io.open(os.path.join(REPO, ".claude-plugin", "marketplace.json"),
                     encoding="utf-8") as f:
            marketplace = json.load(f)
        gate = next(plugin for plugin in marketplace["plugins"]
                    if plugin["name"] == "gate")
        description = gate["description"]
        for needle in ("self-attested", "copyable", "not proof"):
            self.assertIn(needle, description)
        commands = re.findall(r"/gate:[a-z-]+", description)
        self.assertEqual(commands, [
            "/gate:before-code",
            "/gate:before-merge",
            "/gate:before-deploy",
            "/gate:finalize-evidence",
            "/gate:production-ready",
            "/gate:score-project",
        ])

    def test_release_identity_comes_from_trusted_repository_metadata(self):
        with io.open(os.path.join(REPO, "README.md"),
                     encoding="utf-8") as f:
            readme = f.read()
        self.assertIn(
            'CANONICAL_REPO="$(gh api repos/unn0wn002/solo-suite '
            '--jq .full_name)"', readme)
        self.assertIn('CERT_ID="https://github.com/${CANONICAL_REPO}/',
                      readme)
        self.assertIn('--certificate-identity "$CERT_ID"', readme)
        self.assertIn('--bundle "$payload.sigstore.json"', readme)
        outer = readme.index(
            "cosign verify-blob SIGNED-BUNDLE-SHA256SUMS")
        release = readme.index("cosign verify-blob RELEASE-SHA256SUMS")
        self.assertLess(outer, release)
        self.assertIn("release does not contain the exact 18 assets", readme)
        self.assertIn('for payload in "${payloads[@]}"', readme)
        self.assertNotIn("done < RELEASE-SHA256SUMS", readme)
        self.assertIn("never\nfrom the untrusted bundle", readme)

    def test_superseded_root_patch_notes_do_not_ship(self):
        self.assertFalse(os.path.exists(os.path.join(
            REPO, "PATCH-NOTES-c1-c3.md")))
        with io.open(os.path.join(REPO, "release", "build_release.py"),
                     encoding="utf-8") as f:
            builder = f.read()
        self.assertNotIn('"PATCH-NOTES-c1-c3.md"', builder)


class RunStateHelperDiscipline(unittest.TestCase):
    """v1.0.17 (blocker 4): the finalization docs and both production
    rooms route run-state writes through update_run_state.py."""

    def test_helper_and_schema_ship(self):
        base = os.path.join(REPO, "plugins", "gate", "skills",
                            "production-readiness-reviewer")
        self.assertTrue(os.path.isfile(os.path.join(
            base, "scripts", "update_run_state.py")))
        with io.open(os.path.join(base, "schema",
                                  "run-state-v1.schema.json"),
                     encoding="utf-8") as f:
            schema = json.load(f)
        self.assertEqual(schema["properties"]["schema"]["const"],
                         "run-state-v1")
        self.assertEqual(
            sorted(schema["properties"]),
            ["base_sha", "final_sha", "integration_sha", "run_id",
             "schema"], "exact lowercase keys are the contract")
        self.assertFalse(schema.get("additionalProperties", True))

    def test_finalization_docs_name_the_helper(self):
        for rel in (("plugins", "gate", "commands", "finalize-evidence.md"),
                    ("plugins", "ai", "agents", "room-evidence-finalizer.md"),
                    ("plugins", "ai", "skills", "agent-room-templates",
                     "references", "runner.md"),
                    ("plugins", "gate", "skills",
                     "production-readiness-reviewer", "SKILL.md"),
                    ("plugins", "solo", "commands", "full-team-dev.md"),
                    ("plugins", "gate", "commands", "production-ready.md")):
            with io.open(os.path.join(REPO, *rel), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("update_run_state.py", text, os.path.join(*rel))

    def test_no_doc_instructs_hand_writing_final_sha(self):
        """The v1.0.16 phrasing 'write FINAL_SHA = git rev-parse HEAD to
        …' (a hand-write instruction) must not come back."""
        offenders = []
        for path in _iter_plugin_text_files():
            with io.open(path, encoding="utf-8") as f:
                text = f.read()
            for bad in ("write FINAL_SHA = git rev-parse HEAD",
                        "writes FINAL_SHA = git rev-parse HEAD",
                        "write `FINAL_SHA = git rev-parse HEAD`"):
                if bad in text:
                    offenders.append("%s: %r"
                                     % (os.path.relpath(path, REPO), bad))
        self.assertEqual(offenders, [], offenders)


if __name__ == "__main__":
    unittest.main()
