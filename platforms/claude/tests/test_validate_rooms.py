"""AgentRooms validator tests — the four bundled templates must pass, and each
rule must catch a synthetic violation. v1.0.13 adds: schema-first validation
(malformed types return errors, never exceptions), required run identity,
exactly-one exit-gate executor, exact path/fnmatch producer semantics,
category-specific evidence producers, entry->exit reachability for all six
profiles, and the worktree execution contract."""
import copy
import glob
import importlib.util
import json
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VPATH = os.path.join(REPO, "plugins", "ai", "skills", "agent-room-templates",
                     "scripts", "validate_rooms.py")
spec = importlib.util.spec_from_file_location("validate_rooms", VPATH)
vr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vr)

CEPATH = os.path.join(REPO, "plugins", "gate", "skills",
                      "production-readiness-reviewer", "scripts",
                      "check_evidence.py")
cespec = importlib.util.spec_from_file_location("check_evidence_m", CEPATH)
cem = importlib.util.module_from_spec(cespec)
cespec.loader.exec_module(cem)


def load_room(name):
    path = os.path.join(REPO, "plugins", "ai", "skills",
                        "agent-room-templates", "agentsrooms", name)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def seat(sid, handoff, writes, commands=None):
    return {"id": sid, "role": "r", "reads": [], "writes": writes,
            "agent_note": "synthetic test seat — no agent needed",
            "commands": commands or ["/ai:prompt-improve"],
            "deliverable": "d",
            "handoff_to": handoff, "handoff_check": "/ai:handoff-check"}


def base_room():
    return {
        "schema": "solo-suite/agentroom-v1", "name": "t",
        "run": {"id_prefix": "t", "id_required": True},
        "stages": [["a"], ["b"]],
        "seats": [seat("a", "b", ["x.md"]),
                  seat("b", None, ["y.md", ".solo/risks.md",
                                    ".solo/tasks.md"],
                       ["/gate:before-code"])],
        "exit_gate": "/gate:before-code",
        "exit_criteria": "done",
    }


class BundledTemplates(unittest.TestCase):
    def test_all_bundled_templates_valid(self):
        rooms = sorted(glob.glob(os.path.join(
            REPO, "plugins", "*", "skills", "*", "agentsrooms", "*.json")))
        self.assertEqual(len(rooms), 4)
        self.assertEqual(vr.validate_files(rooms, suite_root=REPO), [])

    def test_matrix_agrees_with_check_evidence(self):
        """The applicability matrix must be IDENTICAL in the validator and
        the gate checker — one normative source, two enforcers."""
        self.assertEqual(vr.NA_ALLOWED, cem.NA_ALLOWED)
        self.assertEqual(vr.MANDATORY, cem.MANDATORY)
        self.assertEqual(vr.CATEGORIES, cem.CATEGORIES)
        self.assertEqual(vr.RECOGNIZED_PROFILES, cem.RECOGNIZED_PROFILES)


class Rules(unittest.TestCase):
    def check(self, room, fragment):
        problems = vr.validate_room(room, "t.json")
        self.assertTrue(any(fragment in p for p in problems),
                        "expected %r in %r" % (fragment, problems))

    def test_valid_base(self):
        self.assertEqual(vr.validate_room(base_room(), "t.json"), [])

    def test_same_stage_handoff(self):
        r = base_room()
        r["stages"] = [["a", "b"]]
        self.check(r, "SAME stage")

    def test_backward_handoff(self):
        r = base_room()
        r["seats"][0]["handoff_to"] = None
        r["seats"][1]["handoff_to"] = "a"
        self.check(r, "BACKWARD")

    def test_seat_in_two_stages(self):
        r = base_room()
        r["stages"] = [["a"], ["a", "b"]]
        self.check(r, "exactly one stage")

    def test_seat_in_no_stage(self):
        r = base_room()
        r["stages"] = [["a"]]
        self.check(r, "not placed in any stage")

    def test_unknown_stage_member(self):
        r = base_room()
        r["stages"] = [["a"], ["b", "ghost"]]
        self.check(r, "unknown seat")

    def test_handoff_target_missing(self):
        r = base_room()
        r["seats"][0]["handoff_to"] = "ghost"
        self.check(r, "unknown seat")

    def test_handoff_fanout_list_accepted(self):
        r = base_room()
        r["stages"] = [["a"], ["b", "c"], ["d"]]
        r["seats"] = [seat("a", ["b", "c"], ["x.md"]),
                      seat("b", "d", [".solo/y.md"]),
                      seat("c", "d", [".solo/c.md"]),
                      seat("d", None,
                           ["z.md", ".solo/risks.md", ".solo/tasks.md"],
                           ["/gate:before-code"])]
        self.assertEqual(vr.validate_room(r, "t.json"), [])

    def test_duplicate_writer_same_stage(self):
        r = base_room()
        r["stages"] = [["a", "b"], ["c"]]
        r["seats"] = [seat("a", "c", ["x.md"]), seat("b", "c", ["x.md"]),
                      seat("c", None, ["z.md", ".solo/risks.md",
                                        ".solo/tasks.md"],
                           ["/gate:before-code"])]
        self.check(r, "one writer per artifact")

    def test_null_gate_needs_note(self):
        r = base_room()
        r["exit_gate"] = None
        self.check(r, "exit_gate_note")

    def test_null_gate_with_note_ok(self):
        r = base_room()
        r["exit_gate"] = None
        r["exit_gate_note"] = "exploratory spike room; exit is human judgement"
        problems = [p for p in vr.validate_room(r, "t.json")
                    if "exit_gate" in p]
        self.assertEqual(problems, [])

    def test_missing_exit_criteria(self):
        r = base_room()
        del r["exit_criteria"]
        self.check(r, "exit_criteria")

    def test_missing_gate_key(self):
        r = base_room()
        del r["exit_gate"]
        self.check(r, "missing 'exit_gate' key")

    def test_loop_unknown_seat(self):
        r = base_room()
        r["loop"] = {"repeat_stages": [["ghost"]], "until": "fixed",
                     "max_iterations": 3}
        self.check(r, "loop repeats unknown seat")

    def test_loop_needs_until(self):
        r = base_room()
        r["loop"] = {"repeat_stages": [["a"]], "max_iterations": 3}
        self.check(r, "until")

    def test_command_existence_with_suite(self):
        r = base_room()
        r["seats"][0]["commands"] = ["/nope:not-a-command"]
        problems = vr.validate_room(r, "t.json", known=vr.known_commands(REPO))
        self.assertTrue(any("does not exist" in p for p in problems), problems)


class SchemaFirst(unittest.TestCase):
    """Malformed root/seat/stage/run/profile/gate-map/loop types must come
    back as validation errors and NEVER as exceptions."""

    def errors_of(self, room):
        try:
            return vr.validate_room(room, "t.json")
        except Exception as e:      # pragma: no cover - the failure we forbid
            self.fail("validator CRASHED (%s: %s)" % (type(e).__name__, e))

    def assert_rejected(self, room):
        problems = self.errors_of(room)
        self.assertTrue(problems, "malformed room accepted: %r" % (room,))
        return problems

    def test_root_not_object(self):
        for bad in (["x"], "room", 7, None, True):
            self.assert_rejected(bad)

    def test_run_identity_required_and_typed(self):
        r = base_room(); del r["run"]
        self.assert_rejected(r)
        for bad in ("yes", 5, [], {"id_prefix": "t"},
                    {"id_prefix": "t", "id_required": False},
                    {"id_prefix": "", "id_required": True},
                    {"id_prefix": "T!", "id_required": True}):
            r = base_room(); r["run"] = bad
            self.assert_rejected(r)

    def test_profiles_must_be_recognized_enums(self):
        for bad in ("saas", [123], ["my-vibes"], {"p": 1}):
            r = base_room(); r["profiles"] = bad
            self.assert_rejected(r)

    def test_applies_to_must_be_recognized(self):
        r = base_room()
        r["profiles"] = ["saas-application"]
        r["seats"][0]["applies_to"] = ["not-a-profile"]
        self.assert_rejected(r)

    def test_gate_map_types(self):
        for bad in ([1, 2], "map", {"security": 5}, {"nonsense-cat": "x.md"}):
            r = base_room(); r["gate_evidence_map"] = bad
            self.assert_rejected(r)

    def test_seat_types(self):
        for bad_seats in ("seats", [1], [{"id": 1}], [{"id": "a"}],
                          [{"id": "a", "role": 5, "reads": "x",
                            "writes": {}, "commands": "c",
                            "deliverable": 1, "handoff_check": 2}]):
            r = base_room(); r["seats"] = bad_seats
            self.assert_rejected(r)

    def test_stage_types(self):
        for bad in ("stages", [7], [[]], [{"id": "x"}],
                    [{"id": "X!", "seats": ["a"]}],
                    [{"id": "x", "seats": ["a"], "extra": 1}]):
            r = base_room(); r["stages"] = bad
            self.assert_rejected(r)

    def test_loop_types(self):
        for bad in ("forever", 3, [], {"repeat_stages": "a"},
                    {"repeat_stages": [["a"]], "until": "x"},
                    {"repeat_stages": [["a"]], "until": "x",
                     "max_iterations": 0},
                    {"repeat_stages": [["a"]], "until": "x",
                     "max_iterations": True}):
            r = base_room(); r["loop"] = bad
            self.assert_rejected(r)

    def test_unknown_root_key_rejected(self):
        r = base_room(); r["banana"] = 1
        problems = self.assert_rejected(r)
        self.assertTrue(any("banana" in p for p in problems), problems)

    def test_worktrees_types(self):
        r = base_room()
        r["seats"][0]["workspace"] = "worktree:one"
        for bad in ("contract", [], {"base_sha": "x"},
                    {"base_sha": {"recorded_by": "o", "rule": "r"},
                     "builder_payload": ["worktree_path"],
                     "proposal_transport": "t",
                     "integration": {"seat": "b", "mode": "bogus-mode",
                                     "ref": "r"},
                     "verify_at_integration_sha": ["b"]}):
            rr = copy.deepcopy(r); rr["worktrees"] = bad
            self.assert_rejected(rr)


class ExitGateExecutor(unittest.TestCase):
    def check(self, room, fragment):
        problems = vr.validate_room(room, "t.json")
        self.assertTrue(any(fragment in p for p in problems),
                        "expected %r in %r" % (fragment, problems))

    def test_no_executor_fails(self):
        r = base_room()
        r["seats"][1]["commands"] = ["/ai:prompt-improve"]
        self.check(r, "NO executing seat")

    def test_two_executors_fail(self):
        r = base_room()
        r["seats"][0]["commands"] = ["/gate:before-code"]
        self.check(r, "exactly one seat must own the gate")

    def test_no_last_stage_fallback(self):
        """Without an executor the gate-requires readable check must NOT
        silently fall back to the last stage's seats."""
        r = base_room()
        r["seats"][1]["commands"] = ["/ai:prompt-improve"]
        r["gate_requires"] = ["x.md"]
        r["seats"][1]["reads"] = ["x.md"]
        problems = vr.validate_room(r, "t.json")
        self.assertTrue(any("NO executing seat" in p for p in problems))
        self.assertFalse(any("lacks evidence" in p for p in problems),
                         "fallback executor sneaked back in: %r" % problems)

    def test_dead_end_seat_fails(self):
        r = base_room()
        r["stages"] = [["a"], ["b", "c"], ["d"]]
        r["seats"] = [seat("a", ["b", "c"], ["x.md"]),
                      seat("b", "d", ["y.md"]),
                      seat("c", None, ["c.md"]),      # dead end, not the gate
                      seat("d", None, ["z.md"], ["/gate:before-code"])]
        self.check(r, "dead end")


class NewRules(unittest.TestCase):
    """agentroom-v1 semantic rules added in v1.0.11."""

    def check(self, room, fragment):
        problems = vr.validate_room(room, "t.json")
        self.assertTrue(any(fragment in p for p in problems),
                        "expected %r in %r" % (fragment, problems))

    def test_wrong_field_types_rejected(self):
        r = base_room()
        r["seats"][0]["reads"] = "not-a-list"
        problems = vr.validate_room(r, "t.json")
        self.assertTrue(problems)

    def test_wrong_stage_object_types_rejected(self):
        r = base_room()
        r["stages"] = [{"id": "s1"}, ["b"]]          # missing seats
        problems = vr.validate_room(r, "t.json")
        self.assertTrue(problems)

    def test_duplicate_stage_ids_rejected(self):
        r = base_room()
        r["stages"] = [{"id": "one", "seats": ["a"]},
                       {"id": "one", "seats": ["b"]}]
        self.check(r, "duplicate stage id")

    def test_disconnected_stage_rejected(self):
        r = base_room()
        r["stages"] = [["a"], ["b"], ["c"]]
        r["seats"] = [seat("a", "b", ["x.md"]),
                      seat("b", None, ["y.md"], ["/gate:before-code"]),
                      seat("c", None, ["z.md"])]     # nothing hands to c
        self.check(r, "unreachable")

    def test_invalid_loop_target(self):
        r = base_room()
        r["loop"] = {"repeat_stages": [["ghost"]], "until": "fixed",
                     "max_iterations": 3}
        self.check(r, "loop repeats unknown seat")

    def test_unbounded_loop_rejected(self):
        r = base_room()
        r["loop"] = {"repeat_stages": [["a"]], "until": "fixed"}
        self.check(r, "max_iterations")

    def steward_room(self):
        r = base_room()
        r["stages"] = [["a", "b"], ["c"]]
        r["seats"] = [seat("a", "c", []), seat("b", "c", []),
                      seat("c", None, [".solo/tasks.md", ".solo/decisions.md",
                                       ".solo/handoff.md", ".solo/risks.md"],
                           ["/gate:before-code"])]
        r["memory_steward"] = {"seat": "c",
                               "owns": [".solo/tasks.md", ".solo/decisions.md",
                                        ".solo/handoff.md"],
                               "allocates_task_ids": True}
        return r

    def test_undeclared_implicit_write_rejected(self):
        r = self.steward_room()
        r["seats"][0]["commands"] = ["/site-doctor:full-checkup"]
        self.check(r, "implicitly write steward-owned")

    def test_proposes_satisfies_implicit_write(self):
        r = self.steward_room()
        r["seats"][0]["commands"] = ["/site-doctor:full-checkup"]
        r["seats"][0]["proposes"] = [".solo/tasks.md", ".solo/decisions.md",
                                     ".solo/handoff.md"]
        problems = vr.validate_room(r, "t.json")
        self.assertEqual([p for p in problems if "implicitly" in p], [])

    def test_implement_feature_models_tasks_and_decisions(self):
        self.assertEqual(
            vr.implicit_writes_of(["/dev:implement-feature"]),
            {".solo/tasks.md", ".solo/decisions.md"})

    def test_representative_lifecycle_writes_are_complete(self):
        expected = {
            "/project:prd": {".solo/prd.md", ".solo/decisions.md"},
            "/stack:connector-check": {
                ".solo/stack.md", ".solo/tasks.md", ".solo/decisions.md"},
            "/test:integration": {".solo/tests.md", ".solo/tasks.md"},
            "/docs:update": {".solo/handoff.md"},
            "/repo:risk-map": {".solo/tasks.md", ".solo/decisions.md"},
            "/growth:conversion-audit": {".solo/tasks.md"},
            "/gate:score-project": {
                ".solo/project.md", ".solo/risks.md", ".solo/tasks.md",
                ".solo/decisions.md"},
            "/release:preflight": {
                ".solo/release.md", ".solo/tasks.md", ".solo/decisions.md",
                ".solo/handoff.md"},
        }
        for command, writes in expected.items():
            with self.subTest(command=command):
                self.assertEqual(vr.implicit_writes_of([command]), writes)

    def test_nonstewarded_implicit_write_must_be_declared(self):
        r = base_room()
        r["seats"][0]["commands"] = ["/dev:implement-feature"]
        self.check(r, "implicitly write")

    def test_proposal_requires_a_steward(self):
        r = base_room()
        r["seats"][0]["proposes"] = [".solo/tasks.md"]
        self.check(r, "no memory_steward")

    def test_proposal_target_must_be_owned_by_steward(self):
        r = self.steward_room()
        r["seats"][0]["proposes"] = [".solo/project.md"]
        self.check(r, "steward does not own")

    def test_two_proposals_are_not_direct_write_collision(self):
        r = self.steward_room()
        for s in r["seats"][:2]:
            s["commands"] = ["/growth:conversion-audit"]
            s["proposes"] = [".solo/tasks.md"]
        problems = vr.validate_room(r, "t.json")
        self.assertEqual([p for p in problems
                          if "one writer per artifact" in p], [])

    def test_direct_write_of_steward_file_rejected(self):
        r = self.steward_room()
        r["seats"][0]["writes"] = [".solo/tasks.md"]
        self.check(r, "use 'proposes'")

    def test_manual_only_metadata_is_discovered(self):
        manual = vr.manual_only_commands(REPO)
        for command in ("/gate:finalize-evidence", "/security:secrets-fix",
                        "/security:rls-test", "/browser:smoke-test",
                        "/browser:form-submit-test"):
            self.assertIn(command, manual)

    def test_manual_only_command_cannot_be_a_seat_command(self):
        r = base_room()
        r["seats"][0]["commands"] = ["/gate:finalize-evidence"]
        problems = vr.validate_room(
            r, "t.json", manual_commands_set={"/gate:finalize-evidence"})
        self.assertTrue(any("manual-only command" in p for p in problems),
                        problems)

    def test_manual_only_command_may_be_a_human_handoff(self):
        r = base_room()
        r["seats"][0]["commands"] = []
        r["seats"][0]["human_handoff"] = {
            "command": "/gate:finalize-evidence", "executor": "user",
            "preview_required": True, "confirmation_required": True,
            "resume_on": "successful completion"}
        problems = vr.validate_room(
            r, "t.json", manual_commands_set={"/gate:finalize-evidence"})
        self.assertEqual([p for p in problems if "manual-only" in p], [])

    def test_simultaneous_implicit_writers_rejected(self):
        r = base_room()
        r["stages"] = [["a", "b"], ["c"]]
        r["seats"] = [seat("a", "c", []), seat("b", "c", []),
                      seat("c", None, ["z.md"], ["/gate:before-code"])]
        r["seats"][0]["commands"] = ["/test:unit"]
        r["seats"][1]["commands"] = ["/test:e2e"]
        self.check(r, "one writer per artifact")

    def test_missing_gate_evidence_rejected(self):
        r = base_room()
        r["gate_requires"] = [".solo/tests.md", ".solo/risks.md"]
        self.check(r, "lacks evidence")

    def test_gatekeeper_with_sufficient_reads_passes(self):
        r = base_room()
        r["gate_requires"] = [".solo/tests.md"]
        r["seats"][1]["reads"] = [".solo/tests.md"]
        problems = vr.validate_room(r, "t.json")
        self.assertEqual([p for p in problems if "lacks evidence" in p], [])

    def test_lock_violation_rejected(self):
        r = base_room()
        r["locks"] = {"x.md": "b"}                    # a writes x.md but b owns it
        self.check(r, "locked artifact")

    def test_shared_workspace_rejected(self):
        r = base_room()
        r["stages"] = [["a", "b"], ["c"]]
        r["seats"] = [seat("a", "c", ["src/app"]), seat("b", "c", ["src/lib"]),
                      seat("c", None, ["z.md"], ["/gate:before-code"])]
        r["seats"][0]["workspace"] = "shared-space"
        r["seats"][1]["workspace"] = "shared-space"
        self.check(r, "workspace")

    def test_parallel_code_writers_need_workspace(self):
        r = base_room()
        r["stages"] = [["a", "b"], ["c"]]
        r["seats"] = [seat("a", "c", ["src/app"]), seat("b", "c", ["src/lib"]),
                      seat("c", None, ["z.md"], ["/gate:before-code"])]
        self.check(r, "'workspace'")

    def test_steward_must_allocate_task_ids(self):
        r = self.steward_room()
        r["memory_steward"]["allocates_task_ids"] = False
        self.check(r, "allocates_task_ids")

    def test_steward_must_be_a_real_seat(self):
        r = self.steward_room()
        r["memory_steward"]["seat"] = "ghost"
        self.check(r, "not a defined seat")

    def test_duplicate_task_ids_detected(self):
        text = "## Todo\n- T-1 fix x\n- T-2 fix y\n## Done\n- T-1 old\n"
        self.assertEqual(vr.check_tasks_file(text), ["T-1"])

    def test_unique_task_ids_pass(self):
        self.assertEqual(vr.check_tasks_file("- T-1 a\n- T-2 b\n"), [])

    def test_applies_to_unknown_profile_rejected(self):
        r = base_room()
        r["profiles"] = ["saas-application"]
        r["seats"][0]["applies_to"] = ["e-commerce"]
        self.check(r, "not declared in the room's 'profiles'")


class V1012Rules(unittest.TestCase):
    """Per-profile reachability with skipped-seat contraction, same-stage
    read-after-write, gate-artifact producers, and seat->agent mapping."""

    def check(self, room, fragment):
        problems = vr.validate_room(room, "t.json")
        self.assertTrue(any(fragment in p for p in problems),
                        "expected %r in %r" % (fragment, problems))

    def clean(self, room):
        return vr.validate_room(room, "t.json")

    def growth_room(self, growth_hands_to="d"):
        r = base_room()
        r["profiles"] = ["saas-application", "internal-application"]
        r["stages"] = [["a"], ["b"], ["c"], ["d"]]
        r["seats"] = [seat("a", "b", []), seat("b", "c", []),
                      seat("c", growth_hands_to, []),
                      seat("d", None, ["z.md"], ["/gate:before-code"])]
        r["seats"][2]["applies_to"] = ["saas-application"]   # conditional stage
        return r

    def test_conditional_stage_does_not_disconnect_other_profiles(self):
        r = self.growth_room()
        problems = [p for p in self.clean(r) if "unreachable" in p]
        self.assertEqual(problems, [], problems)

    def test_profile_disconnect_detected(self):
        r = self.growth_room(growth_hands_to=None)
        r["seats"][1]["handoff_to"] = "c"     # b -> c(skipped, dead end)
        problems = self.clean(r)
        self.assertTrue(any("unreachable" in p and "internal-application" in p
                            for p in problems), problems)

    def test_fully_connected_profile_still_passes(self):
        r = self.growth_room()
        problems = [p for p in self.clean(r)
                    if "unreachable" in p and "saas-application" in p]
        self.assertEqual(problems, [])

    def test_same_stage_read_after_write_detected(self):
        r = base_room()
        r["stages"] = [["a", "b"], ["c"]]
        r["seats"] = [seat("a", "c", ["x.md"]), seat("b", "c", ["y.md"]),
                      seat("c", None, ["z.md"], ["/gate:before-code"])]
        r["seats"][1]["reads"] = ["x.md"]     # b reads what a writes NOW
        self.check(r, "SAME stage")

    def test_sequential_read_after_write_is_fine(self):
        r = base_room()
        r["seats"][1]["reads"] = ["x.md"]     # b (stage 2) reads a's stage-1 write
        problems = [p for p in self.clean(r) if "READS" in p]
        self.assertEqual(problems, [])

    def test_gate_artifact_without_producer_rejected(self):
        r = base_room()
        r["gate_requires"] = ["ghost.md"]
        r["seats"][1]["reads"] = ["ghost.md"]
        self.check(r, "NO seat in an earlier stage produces it")

    def test_gate_artifact_with_producer_passes(self):
        r = base_room()
        r["gate_requires"] = ["x.md"]          # seat a writes x.md in stage 1
        r["seats"][1]["reads"] = ["x.md"]
        problems = [p for p in self.clean(r) if "produces it" in p]
        self.assertEqual(problems, [])

    def test_assumes_preexisting_satisfies_producer_check(self):
        r = base_room()
        r["gate_requires"] = ["ghost.md"]
        r["seats"][1]["reads"] = ["ghost.md"]
        r["assumes_preexisting"] = {"ghost.md": "produced by an earlier room"}
        problems = [p for p in self.clean(r) if "produces it" in p]
        self.assertEqual(problems, [])

    def test_glob_prefix_producer_matches(self):
        r = base_room()
        r["gate_requires"] = [".solo/gate-evidence/*.json"]
        r["seats"][0]["writes"] = [".solo/gate-evidence/security.json"]
        r["seats"][1]["reads"] = [".solo/gate-evidence/*.json"]
        problems = [p for p in self.clean(r) if "produces it" in p]
        self.assertEqual(problems, [])

    def test_descriptive_directory_string_never_satisfies_glob(self):
        """Exact path/fnmatch semantics: a human-readable directory NOTE must
        not satisfy a *.json requirement."""
        r = base_room()
        r["gate_requires"] = [".solo/gate-evidence/*.json"]
        r["seats"][0]["writes"] = [
            ".solo/gate-evidence/ (records written here)"]
        r["seats"][1]["reads"] = [".solo/gate-evidence/*.json"]
        self.check(r, "NO seat in an earlier stage produces it")

    def test_executors_own_writes_never_satisfy_its_gate(self):
        r = base_room()
        r["gate_requires"] = ["ghost.md"]
        r["seats"][1]["reads"] = ["ghost.md"]
        r["seats"][1]["writes"] = ["ghost.md", "y.md"]
        self.check(r, "NO seat in an earlier stage produces it")

    def test_seat_without_agent_or_note_rejected(self):
        r = base_room()
        del r["seats"][0]["agent_note"]
        self.check(r, "no 'agent'")

    def test_unknown_agent_rejected_when_agents_known(self):
        r = base_room()
        r["seats"][0]["agent"] = "room-not-real"
        problems = vr.validate_room(r, "t.json",
                                    known_agents_set={"room-product-manager"})
        self.assertTrue(any("does not exist" in p and "agents" in p
                            for p in problems), problems)

    def test_known_agent_accepted(self):
        r = base_room()
        r["seats"][0]["agent"] = "room-product-manager"
        problems = vr.validate_room(r, "t.json",
                                    known_agents_set={"room-product-manager"})
        self.assertEqual([p for p in problems if "agent" in p], [])

    def test_bundled_template_seats_all_map_to_real_agents(self):
        agents = vr.known_agents(REPO)
        self.assertTrue(agents)
        for room in glob.glob(os.path.join(
                REPO, "plugins", "*", "skills", "*", "agentsrooms", "*.json")):
            with open(room, encoding="utf-8") as f:
                data = json.load(f)
            for st in data["seats"]:
                a = st.get("agent")
                self.assertTrue(a or st.get("agent_note"),
                                (room, st["id"]))
                if a:
                    self.assertIn(a, agents, (room, st["id"], a))


class FullTeamTemplateAdversarial(unittest.TestCase):
    """Adversarial mutations of the shipped full-team-website template."""

    def setUp(self):
        self.ft = load_room("full-team-website.json")

    def problems(self, room):
        return vr.validate_room(room, "t.json")

    def test_every_profile_fully_connected(self):
        """Every active seat is reachable AND reaches the exit for the
        profile-free pass and ALL SIX profiles (asserted per profile)."""
        self.assertEqual(len(self.ft["profiles"]), 6)
        problems = self.problems(self.ft)
        for tag in [""] + ["[profile %s]" % p for p in self.ft["profiles"]]:
            hits = [p for p in problems
                    if tag in p and ("unreachable" in p
                                     or "cannot reach" in p)]
            self.assertEqual(hits, [], (tag, hits))
        self.assertEqual(problems, [])

    def test_removing_one_category_record_from_finalizer_fails(self):
        r = copy.deepcopy(self.ft)
        for s in r["seats"]:
            if s["id"] == "evidence_finalizer":
                s["writes"] = [w for w in s["writes"]
                               if "database.json" not in w]
        problems = self.problems(r)
        self.assertTrue(any("category 'database'" in p for p in problems),
                        problems)

    def test_stripping_the_finalizer_fails_despite_gatekeeper_glob_write(self):
        """Even giving the gate executor a .solo/gate-evidence/*.json write
        cannot substitute for the finalizer's concrete records."""
        r = copy.deepcopy(self.ft)
        for s in r["seats"]:
            if s["id"] == "evidence_finalizer":
                s["writes"] = []
            if s["id"] == "gatekeeper":
                s["writes"] = s.get("writes", []) + [
                    ".solo/gate-evidence/*.json"]
        problems = self.problems(r)
        missing = [c for c in sorted(vr.CATEGORIES)
                   if any("category %r" % c in p for p in problems)]
        self.assertEqual(missing, sorted(vr.CATEGORIES), problems[:5])

    def test_specialist_writing_final_record_fails(self):
        r = copy.deepcopy(self.ft)
        for s in r["seats"]:
            if s["id"] == "pm":
                s["writes"] = s["writes"] + [
                    ".solo/gate-evidence/product.json"]
        problems = self.problems(r)
        self.assertTrue(any("intermediate commits" in p for p in problems),
                        problems)

    def test_missing_evidence_block_fails(self):
        r = copy.deepcopy(self.ft)
        del r["evidence"]
        problems = self.problems(r)
        self.assertTrue(any("'evidence' lifecycle block" in p
                            for p in problems), problems)

    def test_production_gate_requires_full_category_map(self):
        r = copy.deepcopy(self.ft)
        del r["gate_evidence_map"]["testing"]
        problems = self.problems(r)
        self.assertTrue(any("does not cover category 'testing'" in p
                            for p in problems), problems)

    # ---- v1.0.16: structured freeze contract ------------------------------
    def test_missing_freeze_contract_rejected(self):
        r = copy.deepcopy(self.ft)
        del r["evidence"]["freeze"]
        problems = self.problems(r)
        self.assertTrue(any("freeze" in p for p in problems), problems)

    def test_freeze_must_sit_immediately_before_finalize(self):
        r = copy.deepcopy(self.ft)
        r["evidence"]["freeze"]["after_stage"] = "release"
        problems = self.problems(r)
        self.assertTrue(any("IMMEDIATELY" in p for p in problems), problems)
        r = copy.deepcopy(self.ft)
        r["evidence"]["freeze"]["after_stage"] = "finalize"
        r["evidence"]["freeze"]["before_stage"] = "launch-gate"
        problems = self.problems(r)
        self.assertTrue(any("finalizer's stage" in p for p in problems),
                        problems)

    def test_freeze_producer_must_be_orchestrator(self):
        r = copy.deepcopy(self.ft)
        r["evidence"]["freeze"]["producer"] = "gatekeeper"
        self.assertTrue(self.problems(r))   # schema enum rejects

    def test_freeze_carrier_must_match_final_sha_carrier(self):
        r = copy.deepcopy(self.ft)
        r["evidence"]["freeze"]["stored_in"] = ".solo/run-state/other.json"
        problems = self.problems(r)
        self.assertTrue(any("one carrier" in p for p in problems), problems)

    # ---- v1.0.16: structured steward cutoff --------------------------------
    def test_missing_steward_cutoff_rejected(self):
        r = copy.deepcopy(self.ft)
        del r["memory_steward"]["active_through_stage"]
        problems = self.problems(r)
        self.assertTrue(any("active_through_stage" in p for p in problems),
                        problems)

    def test_steward_cutoff_at_or_after_finalize_rejected(self):
        for late in ("finalize", "launch-gate"):
            r = copy.deepcopy(self.ft)
            r["memory_steward"]["active_through_stage"] = late
            problems = self.problems(r)
            self.assertTrue(any("STRICTLY BEFORE" in p for p in problems),
                            (late, problems))

    def test_steward_cutoff_unknown_stage_rejected(self):
        r = copy.deepcopy(self.ft)
        r["memory_steward"]["active_through_stage"] = "ghost-stage"
        problems = self.problems(r)
        self.assertTrue(any("not a declared stage" in p for p in problems),
                        problems)

    # ---- v1.0.16: the finalizer needs a REAL agent -------------------------
    def test_finalizer_without_real_agent_rejected(self):
        r = copy.deepcopy(self.ft)
        for s in r["seats"]:
            if s["id"] == "evidence_finalizer":
                del s["agent"]
                s["agent_note"] = "mechanical executor (note only)"
        problems = self.problems(r)
        self.assertTrue(any("no real 'agent'" in p for p in problems),
                        problems)

    def test_finalizer_is_coordination_only_with_empty_commands(self):
        r = copy.deepcopy(self.ft)
        for s in r["seats"]:
            if s["id"] == "evidence_finalizer":
                s["commands"] = ["/ai:handoff-check"]
        problems = self.problems(r)
        self.assertTrue(any("must have commands: []" in p
                            for p in problems), problems)

    def test_finalizer_maps_to_shipped_room_evidence_finalizer(self):
        agents = vr.known_agents(REPO)
        self.assertIn("room-evidence-finalizer", agents)
        for name in ("full-team-website.json", "production-release.json"):
            room = load_room(name)
            fin_id = room["evidence"]["finalizer"]
            fin = next(s for s in room["seats"] if s["id"] == fin_id)
            self.assertEqual(fin.get("agent"), "room-evidence-finalizer",
                             name)

    # ---- v1.0.16: read provenance ------------------------------------------
    def test_unprovenanced_read_rejected(self):
        r = copy.deepcopy(self.ft)
        for s in r["seats"]:
            if s["id"] == "pm":
                s["reads"] = list(s["reads"]) + [".solo/ghost-input.md"]
        problems = self.problems(r)
        self.assertTrue(any("NO earlier stage produces" in p
                            for p in problems), problems)

    def test_assumes_preexisting_satisfies_read_provenance(self):
        r = copy.deepcopy(self.ft)
        for s in r["seats"]:
            if s["id"] == "pm":
                s["reads"] = list(s["reads"]) + [".solo/ghost-input.md"]
        r["assumes_preexisting"][".solo/ghost-input.md"] = \
            "produced by an earlier room"
        problems = [p for p in self.problems(r)
                    if "NO earlier stage produces" in p]
        self.assertEqual(problems, [])

    def test_removing_assumed_entry_breaks_provenance(self):
        r = copy.deepcopy(self.ft)
        del r["assumes_preexisting"][".solo/project.md"]
        problems = self.problems(r)
        self.assertTrue(any(".solo/project.md" in p
                            and "NO earlier stage produces" in p
                            for p in problems), problems)

    def test_run_state_read_needs_a_sha_contract(self):
        """A seat reading .solo/run-state/ in a room with NEITHER a
        worktrees.base_sha contract NOR an evidence.freeze contract has an
        unprovenanced SHA read — nothing ever produces that file."""
        r = base_room()
        r["seats"][1]["reads"] = [".solo/run-state/<run_id>.json"]
        problems = vr.validate_room(r, "t.json")
        self.assertTrue(any("no structured SHA contract" in p
                            for p in problems), problems)


class WorktreeContract(unittest.TestCase):
    """The worktree execution contract — including proof that the bug-fix
    verifier is bound to the fixer's EXACT commit."""

    def setUp(self):
        self.bf = load_room("bug-fix-loop.json")
        self.ft = load_room("full-team-website.json")

    def problems(self, room):
        return vr.validate_room(room, "t.json")

    def test_worktree_seats_require_contract(self):
        r = copy.deepcopy(self.bf)
        del r["worktrees"]
        problems = self.problems(r)
        self.assertTrue(any("worktrees" in p and "execution" in p
                            for p in problems), problems)

    def test_bugfix_verifier_pins_the_fixers_exact_commit(self):
        """The shipped template binds verification to checkout-exact-sha by
        the verifier; weakening any part of that binding fails validation."""
        wt = self.bf["worktrees"]
        self.assertEqual(wt["integration"]["mode"], "checkout-exact-sha")
        self.assertEqual(wt["integration"]["seat"], "verifier")
        self.assertIn("commit_sha", wt["builder_payload"])
        self.assertIn("verifier", wt["verify_at_integration_sha"])
        self.assertIn("gatekeeper", wt["verify_at_integration_sha"])
        # integration seat must run AFTER the fixer
        r = copy.deepcopy(self.bf)
        r["worktrees"]["integration"]["seat"] = "reproducer"
        self.assertTrue(any("must run AFTER worktree seat" in p
                            for p in self.problems(r)))
        # dropping commit_sha from the payload fails
        r = copy.deepcopy(self.bf)
        r["worktrees"]["builder_payload"] = [
            x for x in r["worktrees"]["builder_payload"]
            if x != "commit_sha"] + ["padding"]
        self.assertTrue(any("commit_sha" in p for p in self.problems(r)))
        # the gate executor must be in the verify list
        r = copy.deepcopy(self.bf)
        r["worktrees"]["verify_at_integration_sha"] = ["verifier"]
        self.assertTrue(any("exit-gate executor" in p
                            for p in self.problems(r)))

    def test_base_sha_rule_documents_default_branch_reality(self):
        for room in (self.bf, self.ft):
            rule = room["worktrees"]["base_sha"]["rule"]
            self.assertIn("DEFAULT branch", rule)
            self.assertTrue("BASE_SHA" in rule or "base" in rule.lower())

    def test_fullteam_verifiers_cover_qa_band_and_final_band(self):
        verify = set(self.ft["worktrees"]["verify_at_integration_sha"])
        for sid in ("tester", "browser_qa", "security", "auditor",
                    "ai_reviewer", "git_manager", "devops",
                    "release_manager", "docs"):
            self.assertIn(sid, verify)
        # v1.0.16: finalize/gate verify FINAL_SHA — an INTEGRATION_SHA
        # requirement at their stage would be unsatisfiable
        final = set(self.ft["worktrees"]["verify_at_final_sha"])
        self.assertEqual(final, {"evidence_finalizer", "gatekeeper"})
        self.assertNotIn("evidence_finalizer", verify)
        self.assertNotIn("gatekeeper", verify)

    def test_gate_seats_in_integration_list_rejected(self):
        r = copy.deepcopy(self.ft)
        r["worktrees"]["verify_at_integration_sha"].append("gatekeeper")
        self.assertTrue(any("unsatisfiable" in p for p in self.problems(r)))

    def test_missing_verify_at_final_sha_rejected(self):
        r = copy.deepcopy(self.ft)
        del r["worktrees"]["verify_at_final_sha"]
        self.assertTrue(any("verify_at_final_sha" in p
                            for p in self.problems(r)))

    def test_verifier_before_integration_rejected(self):
        r = copy.deepcopy(self.ft)
        r["worktrees"]["verify_at_integration_sha"] = ["pm", "gatekeeper"]
        self.assertTrue(any("cannot verify the integration SHA" in p
                            for p in self.problems(r)))


def _load_validator_without_jsonschema():
    import builtins, sys as _sys
    orig = builtins.__import__
    def blocked(name, *a, **k):
        if name == "jsonschema":
            raise ImportError("blocked for the builtin-evaluator path")
        return orig(name, *a, **k)
    builtins.__import__ = blocked
    saved = _sys.modules.pop("jsonschema", None)
    try:
        spec2 = importlib.util.spec_from_file_location("vr_builtin", VPATH)
        m = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(m)
    finally:
        builtins.__import__ = orig
        if saved is not None:
            _sys.modules["jsonschema"] = saved
    return m


class SemanticBypassesBothPaths(unittest.TestCase):
    """Acceptance test M: every semantic bypass is rejected on BOTH the
    jsonschema path and the builtin-evaluator path."""

    @classmethod
    def setUpClass(cls):
        cls.paths = [("jsonschema" if vr._jsonschema else "builtin", vr),
                     ("builtin", _load_validator_without_jsonschema())]
        cls.ft = load_room("full-team-website.json")
        cls.bf = load_room("bug-fix-loop.json")
        cls.iso = vr.agent_isolation(REPO)

    def assert_rejected_both(self, room, name, **kw):
        for tag, mod in self.paths:
            try:
                problems = mod.validate_room(room, "t", **kw)
            except Exception as e:
                self.fail("%s CRASHED on %s path: %s" % (name, tag, e))
            self.assertTrue(problems, "%s accepted on %s path" % (name, tag))

    def test_M_all_bypasses_rejected_on_both_paths(self):
        FT, BF = self.ft, self.bf
        cases = []
        r = copy.deepcopy(FT); r["gate_evidence_map"]["security"] = "banana prose here"
        cases.append(("garbage-gate-map-value", r, {}))
        r = copy.deepcopy(FT)
        for s in r["seats"]:
            if s["id"] == "evidence_finalizer":
                del s["human_handoff"]
        cases.append(("finalizer-without-human-handoff", r, {}))
        r = copy.deepcopy(FT)
        for s in r["seats"]:
            if s["id"] == "evidence_finalizer":
                s["proposes"] = list(s["writes"]); s["writes"] = []
        cases.append(("evidence-from-unmerged-proposals", r, {}))
        r = copy.deepcopy(FT)
        for s in r["seats"]:
            if s["id"] == "designer":
                s["handoff_to"] = ["frontend_dev", "backend_dev"]
        cases.append(("unreachable-producer", r, {}))
        r = copy.deepcopy(FT); r["worktrees"]["integration"]["mode"] = "checkout-exact-sha"
        cases.append(("wrong-integration-mode", r, {}))
        r = copy.deepcopy(BF)
        for s in r["seats"]:
            if s["id"] == "fixer":
                s["agent"] = "room-qa-engineer"
        cases.append(("worktree-seat-non-isolated-agent", r,
                      {"agent_isolation_map": self.iso}))
        r = copy.deepcopy(FT)
        for s in r["seats"]:
            if s["id"] == "growth":
                s["applies_to"] = []
        cases.append(("empty-applies-to", r, {}))
        r = copy.deepcopy(FT); del r["profiles"]
        cases.append(("conditional-without-room-profiles", r, {}))
        r = copy.deepcopy(FT)
        for s in r["seats"]:
            if s["id"] == "growth":
                s["applies_to"] = ["not-a-real-profile"]
        cases.append(("invalid-conditional-profile", r, {}))
        r = copy.deepcopy(BF); r["loop"]["repeat_stages"] = [["fixer", "verifier"]]
        cases.append(("meaningless-loop-stage-ref", r, {}))
        r = copy.deepcopy(BF); r["loop"]["repeat_stages"] = [["ghost"]]
        cases.append(("loop-unknown-seat", r, {}))
        # v1.0.15: post-finalizer tracked writes — NO exemptions
        r = copy.deepcopy(FT)
        for s2 in r["seats"]:
            if s2["id"] == "gatekeeper":
                s2["writes"] = [".solo/risks.md"]
        cases.append(("gatekeeper-tracked-write-post-final", r, {}))
        r = copy.deepcopy(FT)
        for s2 in r["seats"]:
            if s2["id"] == "gatekeeper":
                s2["commands"] = ["/gate:production-ready",
                                  "/solo:handoff-memory"]
        cases.append(("handoff-memory-post-final", r, {}))
        r = copy.deepcopy(FT)
        for s2 in r["seats"]:
            if s2["id"] == "gatekeeper":
                s2["proposes"] = [".solo/handoff.md"]
        cases.append(("steward-work-left-post-final", r, {}))
        # v1.0.15: SHA transport must be untracked run-state
        r = copy.deepcopy(FT)
        r["worktrees"]["base_sha"]["stored_in"] = ".solo/handoff.md"
        cases.append(("base-sha-in-tracked-file", r, {}))
        r = copy.deepcopy(FT)
        r["evidence"]["final_sha_recorded_in"] = ".solo/handoff.md"
        cases.append(("final-sha-in-tracked-file", r, {}))
        r = copy.deepcopy(FT)
        for s2 in r["seats"]:
            if s2["id"] == "tester":
                s2["reads"] = [x for x in s2["reads"]
                               if not x.startswith(".solo/run-state/")]
        cases.append(("verify-seat-without-runtime-state-read", r, {}))
        r = copy.deepcopy(FT)
        for s2 in r["seats"]:
            if s2["id"] == "backend_dev":
                s2["reads"] = [x for x in s2["reads"]
                               if not x.startswith(".solo/run-state/")]
        cases.append(("builder-without-runtime-state-read", r, {}))
        for name, room, kw in cases:
            self.assert_rejected_both(room, name, **kw)

    def test_M_bundled_templates_pass_on_both_paths(self):
        rooms = sorted(glob.glob(os.path.join(
            REPO, "plugins", "*", "skills", "*", "agentsrooms", "*.json")))
        for tag, mod in self.paths:
            self.assertEqual(mod.validate_files(rooms, suite_root=REPO), [],
                             "bundled templates failed on %s path" % tag)


if __name__ == "__main__":
    unittest.main()
