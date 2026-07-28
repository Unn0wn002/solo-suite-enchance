"""Acceptance test H — the evidence LIFECYCLE, end to end, offline:

  1. Build a library-package fixture repo and mint an EARLY testing record
     against commit SHA1.
  2. Change tracked files and commit (SHA2 = FINAL_SHA). The early record
     must now be INVALID (wrong HEAD + wrong committed-tree digest).
  3. Run the finalization workflow: regenerate every applicable category
     at FINAL_SHA — 7 verified records via record_evidence.py (mandatory
     categories, all runnable offline) + 7 matrix-permitted N/A records
     created through the canonical record_evidence.py --not-applicable
     workflow. These are unsigned, self-attested records.
  4. check_evidence.py exits 0 on the complete regenerated set, and the
     early record could never have survived.

v1.0.17 additions exercised here:
  * deployment evidence = bounded-timeout curl of the COMMITTED
    `version-endpoint:` whose response contains FINAL_SHA (the loopback
    fixture server serves it);
  * monitoring evidence = bounded-timeout curl of the COMMITTED
    `health-endpoint:` answering an explicit JSON health contract;
  * run-state travels through update_run_state.py (run-state-v1) —
    see also tests/test_run_state.py for the helper's own contract.

Also proves acceptance test L: the bug reproducer contract references
BASE_SHA only and never requests a fixer commit."""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "plugins", "gate", "skills",
                       "production-readiness-reviewer", "scripts")
RE_PY = os.path.join(SCRIPTS, "record_evidence.py")
CE_PY = os.path.join(SCRIPTS, "check_evidence.py")
URS_PY = os.path.join(SCRIPTS, "update_run_state.py")
GP_PY = os.path.join(REPO, "plugins", "gate", "lib", "gate_policy.py")
SCANNER = os.path.join(REPO, "plugins", "site-doctor", "skills",
                       "security-review", "scripts", "scan_secrets.py")

gspec = importlib.util.spec_from_file_location("gp_lc", GP_PY)
gp = importlib.util.module_from_spec(gspec)
gspec.loader.exec_module(gp)
_fs_spec = importlib.util.spec_from_file_location(
    "fixture_server_lc", os.path.join(REPO, "tests", "fixture_server.py"))
fixture_server = importlib.util.module_from_spec(_fs_spec)
_fs_spec.loader.exec_module(fixture_server)

_SERVER = None
BASE_URL = None


def setUpModule():
    """Use a globally routable literal for URL-policy validation; an inert
    external fake curl below supplies deterministic endpoint bytes and never
    opens a socket."""
    global BASE_URL
    BASE_URL = "https://8.8.8.8"


def tearDownModule():
    if _SERVER is not None:
        _SERVER.shutdown()
        _SERVER.server_close()


PROFILE = "library-package"
VERIFIED = {          # category -> argv factory (loopback-only)
    "product": lambda root: [sys.executable, GP_PY, "verify-artifact",
                             "product"],
    "architecture": lambda root: [sys.executable, GP_PY, "verify-artifact",
                                  "architecture"],
    "security": lambda root: [sys.executable, SCANNER, "."],
    "testing": lambda root: [sys.executable, "-m", "unittest", "discover"],
    # endpoint-bound: the deployed/monitored target is the loopback fixture
    # server, whose endpoints are DECLARED in the COMMITTED .solo/stack.md
    # at HEAD (version-endpoint / health-endpoint) — v1.0.17 contract
    "deployment": lambda root: ["curl", "-sSf", "-m", "10",
                                BASE_URL + "/version"],
    "monitoring": lambda root: ["curl", "-sSf", "-m", "10",
                                BASE_URL + "/health"],
    "documentation": lambda root: [sys.executable, GP_PY, "verify-artifact",
                                   "documentation"],
}
NA_CATS = sorted(gp.NA_ALLOWED)          # the 7 non-mandatory categories
assert set(VERIFIED) == gp.MANDATORY


def git(cwd, *args):
    return subprocess.run(["git"] + list(args), cwd=cwd,
                          capture_output=True, text=True, timeout=30)


# --- fixture documents that satisfy the v1.0.17 CATEGORY-SPECIFIC
# verify-artifact requirements (headings, substance, identifiers) ------------
PRD_MD = """# PRD — demo library

## Problem and goals
Developers who script against machine-readable evidence records lack a
small dependable arithmetic helper library; this package gives solo teams
a tested, documented, dependency-free building block they can vendor
quickly and audit line by line without pulling a framework.

## Scope (MVP)
- AC-1: add(a, b) returns the exact integer sum for machine-size integers.
- AC-2: sub(a, b) returns the exact difference and never mutates inputs.
- AC-3: the public API stays two pure functions with stable signatures.

## Acceptance criteria and user stories
- US-1: as a maintainer I import the library and call add without setup.
- US-2: as a reviewer I run the whole unit suite offline in under a minute.

## Non-goals
- No floating point guarantees, no bignum optimizations, no CLI surface.
"""

ARCH_MD = """# Architecture

## Components and modules
A single module lib.py exposes two pure functions; the unit tests live
beside it in test_lib.py; no services, schedulers, or background workers
exist anywhere in this package.

## Data and API contracts
Both functions accept integers and return integers; type errors propagate
from the interpreter unchanged; there is no storage layer, network call,
or serialization format to version.

## Decisions and tradeoffs
- DEC-1: stay stdlib-only so evidence commands remain reproducible.
- Decision: ship two functions now; a divide helper waits for a real user.
"""

README_MD = """# lib — a tiny arithmetic helper

## Install / setup
```bash
pip install demo-lib
```

## Usage
```python
from lib import add, sub
assert add(1, 2) == 3
assert sub(5, 2) == 3
```

The package is dependency-free, typed by convention, and tested with the
standard unittest runner; run `python -m unittest discover` to execute
the whole suite offline in seconds. Both functions are pure, accept two
integers, and return an integer; type errors propagate unchanged from
the interpreter, and there is no configuration, environment variable, or
service dependency to document beyond this page.
"""


class EvidenceLifecycle(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="lifecycle-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        ext = tempfile.mkdtemp(prefix="lifecycle-curl-")
        self.addCleanup(shutil.rmtree, ext, ignore_errors=True)
        self.curl_output = os.path.join(ext, "output.txt")
        self.curl_bin = os.path.join(ext, "bin")
        os.makedirs(self.curl_bin)
        if os.name == "nt":
            fake = os.path.join(self.curl_bin, "curl.bat")
            with open(fake, "w", encoding="ascii") as f:
                f.write('@echo off\r\ntype "%s"\r\nexit /b 0\r\n'
                        % self.curl_output)
        else:
            fake = os.path.join(self.curl_bin, "curl")
            with open(fake, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\ncat %s\nexit 0\n" %
                        json.dumps(self.curl_output))
            os.chmod(fake, 0o755)
        os.makedirs(os.path.join(self.root, ".solo"))
        for rel, content in {
            "README.md": README_MD,
            ".solo/prd.md": PRD_MD,
            ".solo/architecture.md": ARCH_MD,
            ".solo/release.md": "# Release\n\n## Publish\nTagged wheel "
                                "upload after the gate.\n\n## Rollback\n"
                                "Reinstall the previous tag.\n",
            ".solo/monitoring.md": "# Monitoring\n\n## CI health\nThe "
                                   "loopback health endpoint is polled by "
                                   "the gate evidence command.\n",
            ".solo/stack.md": ("# Stack\n"
                               "Deployed target: %s\n"
                               "version-endpoint: %s/version\n"
                               "health-endpoint: %s/health\n"
                               % (BASE_URL, BASE_URL, BASE_URL)),
            ".solo/project.md": ("# Project\n\n"
                                 "Project profile: library-package\n"),
            "lib.py": "def add(a, b):\n    return a + b\n",
            "test_lib.py": ("import unittest\nimport lib\n"
                            "class T(unittest.TestCase):\n"
                            "    def test_add(self):\n"
                            "        self.assertEqual(lib.add(1, 2), 3)\n"),
            ".gitignore": ".solo/gate-evidence/\n.solo/run-state/\n"
                          "__pycache__/\n*.pyc\n",
        }.items():
            p = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
        git(self.root, "init", "-q", ".")
        git(self.root, "config", "user.email", "t@example.invalid")
        git(self.root, "config", "user.name", "t")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "planning memory + code v1")

    def record(self, category, argv):
        base = [sys.executable, RE_PY, "--category", category,
                "--project", "demo", "--environment", "production",
                "--root", self.root, "--reviewer", "evidence finalizer",
                "--profile", PROFILE]
        if category in {"deployment", "monitoring"}:
            base.append("--allow-network")
        if category == "deployment":
            body = fixture_server.STATE["version_body"]
        elif category == "monitoring":
            body = fixture_server.STATE["health_body"]
        else:
            body = ""
        if category in {"deployment", "monitoring"}:
            with open(self.curl_output, "w", encoding="utf-8") as f:
                f.write(body)
        env = dict(os.environ)
        env["PATH"] = self.curl_bin + os.pathsep + env.get("PATH", "")
        preview = subprocess.run(base + ["--preview", "--"] + argv,
                                 capture_output=True, text=True, timeout=300,
                                 env=env)
        if preview.returncode != 0:
            return preview
        token = re.search(r"preview token: ([0-9a-f]{64})", preview.stdout)
        if token is None:
            return preview
        return subprocess.run(
            base + ["--confirm-execution", token.group(1), "--"] + argv,
            capture_output=True, text=True, timeout=300, env=env)

    def record_na(self, category):
        """v1.0.17: exercise the supported canonical N/A workflow rather
        than constructing its JSON directly."""
        return subprocess.run(
            [sys.executable, RE_PY, "--not-applicable",
             "--category", category, "--project", "demo",
             "--environment", "production", "--root", self.root,
             "--reviewer", "evidence finalizer", "--profile", PROFILE,
             "--profile-source", ".solo/project.md",
             "--reason", "library package: no deployed runtime surface "
                         "for this category to apply to",
             "--checked", "package exposes a Python API only; no served "
                          "pages"],
            capture_output=True, text=True, timeout=300)

    def check(self):
        # Evidence validation re-derives executable identity from PATH. Keep
        # the same inert external curl shim resolvable for that independent
        # validation process; otherwise Windows would resolve system curl.
        env = dict(os.environ)
        env["PATH"] = self.curl_bin + os.pathsep + env.get("PATH", "")
        return subprocess.run(
            [sys.executable, CE_PY,
             os.path.join(self.root, ".solo", "gate-evidence"),
             "--root", self.root, "--environment", "production",
             "--project", "demo", "--profile", PROFILE],
            capture_output=True, text=True, timeout=300, env=env)

    def finalize(self, head):
        """The /gate:finalize-evidence workflow, mechanically. The fixture
        version endpoint answers with the freeze commit so the deployment
        binding (response must contain FINAL_SHA) holds."""
        fixture_server.set_version("deployed commit: %s\n" % head)
        for cat, argv_of in sorted(VERIFIED.items()):
            r = self.record(cat, argv_of(self.root))
            self.assertEqual(r.returncode, 0,
                             "%s: %s%s" % (cat, r.stdout, r.stderr))
        for cat in NA_CATS:
            r = self.record_na(cat)
            self.assertEqual(r.returncode, 0,
                             "%s N/A: %s%s" % (cat, r.stdout, r.stderr))

    def test_H_early_records_invalidated_then_finalization_passes(self):
        sha1 = git(self.root, "rev-parse", "HEAD").stdout.strip()
        # -- 1) EARLY record against SHA1 (the anti-pattern) ---------------
        r = self.record("testing", [sys.executable, "-m", "unittest",
                                    "discover"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # -- 2) tracked files change; commit FINAL_SHA ----------------------
        with open(os.path.join(self.root, "lib.py"), "w") as f:
            f.write("def add(a, b):\n    return a + b\n\n"
                    "def sub(a, b):\n    return a - b\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "final code")
        final_sha = git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(sha1, final_sha)
        # -- the EARLY record is now invalid: wrong HEAD + wrong tree -------
        c = self.check()
        self.assertEqual(c.returncode, 1)
        self.assertIn("STALE", c.stdout)
        self.assertIn("derived HEAD", c.stdout)
        self.assertIn("TREE MISMATCH", c.stdout)
        # -- 3) finalization regenerates EVERYTHING at FINAL_SHA ------------
        self.finalize(final_sha)
        c = self.check()
        self.assertEqual(c.returncode, 0, c.stdout + c.stderr)
        self.assertIn("7 verified + 7 N/A = 14/14", c.stdout)
        self.assertIn("(7 applicable for scoring)", c.stdout)
        # Every record carries FINAL_SHA exactly, and every N/A record made
        # by this workflow carries the schema-required recorder format label.
        ev = os.path.join(self.root, ".solo", "gate-evidence")
        for name in sorted(os.listdir(ev)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(ev, name), encoding="utf-8") as f:
                rec = json.load(f)
            self.assertEqual(rec["commit"], final_sha, name)
            self.assertEqual(rec["recorder"], "record_evidence.py/v1", name)

    def test_H_post_final_tracked_write_blocks_further_records(self):
        final_sha = git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.finalize(final_sha)
        self.assertEqual(self.check().returncode, 0)
        # a tracked write AFTER finalization poisons the state
        with open(os.path.join(self.root, "lib.py"), "a") as f:
            f.write("# late tracked write\n")
        r = self.record("testing", [sys.executable, "-m", "unittest",
                                    "discover"])
        self.assertEqual(r.returncode, 2)
        c = self.check()
        self.assertEqual(c.returncode, 1)
        self.assertIn("no longer matches HEAD", c.stdout)

    def test_generic_page_is_not_deployment_or_monitoring_evidence(self):
        """v1.0.17: a curl of the site homepage (fixture /ok) is refused by
        the policy for both categories — only the committed endpoints
        count, and the deployment response must name FINAL_SHA."""
        for cat in ("deployment", "monitoring"):
            r = self.record(cat, ["curl", "-sSf", "-m", "10",
                                  BASE_URL + "/ok"])
            self.assertEqual(r.returncode, 2, (cat, r.stdout))
            self.assertIn("endpoint", r.stdout, cat)
        # the version endpoint WITHOUT the deployed FINAL_SHA in its
        # response fails the output binding — a reachable endpoint that
        # serves some other commit proves nothing
        fixture_server.set_version("deployed commit: %s\n" % ("0" * 40))
        r = self.record("deployment", ["curl", "-sSf", "-m", "10",
                                       BASE_URL + "/version"])
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("output binding", r.stdout)

    def test_na_without_required_recorder_fails_the_schema(self):
        """The N/A branch requires its recorder format label. This content
        check is not cryptographic proof that the helper authored the file."""
        final_sha = git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.finalize(final_sha)
        self.assertEqual(self.check().returncode, 0)
        seo = os.path.join(self.root, ".solo", "gate-evidence", "seo.json")
        with open(seo, encoding="utf-8") as f:
            rec = json.load(f)
        del rec["recorder"]          # specifically test a missing label
        with open(seo, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2)
        c = self.check()
        self.assertEqual(c.returncode, 1)
        self.assertIn("SCHEMA", c.stdout)
        self.assertIn("recorder", c.stdout)


class BugReproducerContract(unittest.TestCase):
    """Acceptance test L — the reproducer runs before a fixer exists and
    never requests the fixer's SHA; only the verifier checks it out."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "plugins", "ai", "agents",
                               "room-bug-reproducer.md"),
                  encoding="utf-8") as f:
            cls.agent = f.read()
        with open(os.path.join(REPO, "plugins", "ai", "skills",
                               "agent-room-templates", "agentsrooms",
                               "bug-fix-loop.json"), encoding="utf-8") as f:
            cls.room = json.load(f)

    def test_L_dedicated_reproducer_agent_exists_and_verifies_base_only(self):
        self.assertIn("BASE_SHA", self.agent)
        self.assertIn("before any fixer exists", self.agent)
        self.assertIn("never request", self.agent.lower().replace(
            "must never request or wait", "never request"))
        for forbidden in ("checkout-exact-sha", "fixer's commit_sha",
                          "request the fixer"):
            self.assertNotIn(forbidden, self.agent)

    def test_L_room_binds_reproducer_to_new_agent(self):
        seats = {s["id"]: s for s in self.room["seats"]}
        self.assertEqual(seats["reproducer"]["agent"], "room-bug-reproducer")
        self.assertIn("NEVER asks for or checks out a fixer commit",
                      seats["reproducer"]["deliverable"])
        # only the verifier is the checkout-exact-sha integration seat
        self.assertEqual(self.room["worktrees"]["integration"]["seat"],
                         "verifier")
        self.assertEqual(self.room["worktrees"]["integration"]["mode"],
                         "checkout-exact-sha")
        self.assertNotIn("reproducer",
                         self.room["worktrees"]["verify_at_integration_sha"])


class RunStateShaTransport(EvidenceLifecycle):
    """BASE/FINAL SHAs travel through UNTRACKED run-state, written ONLY by
    update_run_state.py (run-state-v1, v1.0.17): a real builder worktree
    receives BASE_SHA that way; FINAL_SHA needs no self-referential
    tracked write; the finalize+check flow leaves HEAD and the worktree
    unchanged."""

    RUN_ID = "test-run"
    RUN_STATE = ".solo/run-state/test-run.json"

    def urs(self, *args):
        """All run-state writes go through the helper — no test writes the
        JSON by hand any more."""
        return subprocess.run(
            [sys.executable, URS_PY, "--root", self.root,
             "--run-id", self.RUN_ID] + list(args),
            capture_output=True, text=True, timeout=60)

    def test_builder_worktree_receives_base_sha_through_runtime_state(self):
        """A REAL `git worktree` branched from the default branch receives
        BASE_SHA via .solo/run-state (recorded by the helper, which derives
        it from git itself) and fast-forwards onto it — no tracked file
        carries the SHA."""
        base_sha = git(self.root, "rev-parse", "HEAD").stdout.strip()
        r = self.urs("advance", "base")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # builder worktree branches from the DEFAULT branch tip
        wt = tempfile.mkdtemp(prefix="builder-wt-")
        self.addCleanup(shutil.rmtree, wt, ignore_errors=True)
        os.rmdir(wt)
        r = git(self.root, "worktree", "add", "-b", "builder/one", wt)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.addCleanup(lambda: git(self.root, "worktree", "remove",
                                    "--force", wt))
        # the builder reads BASE_SHA from the ORCHESTRATOR's runtime state
        with open(os.path.join(self.root, self.RUN_STATE),
                  encoding="utf-8") as f:
            state = json.load(f)
        self.assertEqual(state["schema"], "run-state-v1")
        self.assertEqual(state["run_id"], self.RUN_ID)
        received = state["base_sha"]
        self.assertEqual(received, base_sha)
        ff = git(wt, "merge", "--ff-only", received)
        self.assertEqual(ff.returncode, 0, ff.stderr)
        anc = git(wt, "merge-base", "--is-ancestor", received, "HEAD")
        self.assertEqual(anc.returncode, 0)
        # and the SHA is in NO tracked file
        tracked = git(self.root, "grep", "-l", base_sha, "HEAD")
        self.assertNotEqual(tracked.returncode, 0,
                            "BASE_SHA leaked into tracked content: %s"
                            % tracked.stdout)

    def test_final_sha_needs_no_self_referential_tracked_write(self):
        """FINAL_SHA lives only in untracked run-state (recorded by the
        helper): the freeze commit does NOT contain its own SHA anywhere in
        tracked content, and the full finalize + check flow passes against
        it."""
        final_sha = git(self.root, "rev-parse", "HEAD").stdout.strip()
        r = self.urs("advance", "final")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.urs("verify", "final").returncode, 0)
        self.finalize(final_sha)
        c = self.check()
        self.assertEqual(c.returncode, 0, c.stdout + c.stderr)
        tracked = git(self.root, "grep", "-l", final_sha, "HEAD")
        self.assertNotEqual(tracked.returncode, 0,
                            "FINAL_SHA appears in tracked content — the "
                            "self-referential-commit bug is back: %s"
                            % tracked.stdout)

    def test_flow_leaves_head_and_worktree_unchanged(self):
        """Acceptance: freeze recording + finalizer + checker (+ gate
        preconditions) leave HEAD, the committed tree digest, and worktree
        cleanliness exactly as they were."""
        import importlib.util as iu
        spec2 = iu.spec_from_file_location("gp_flow", GP_PY)
        gpm = iu.module_from_spec(spec2)
        spec2.loader.exec_module(gpm)
        final_sha = git(self.root, "rev-parse", "HEAD").stdout.strip()
        digest_before = gpm.committed_tree_digest(self.root)
        state_before = gpm.repo_state(self.root)
        self.assertEqual(state_before["dirty"], [])
        r = self.urs("advance", "final")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # finalize (7 verified + 7 N/A) + full checker run
        self.finalize(final_sha)
        c = self.check()
        self.assertEqual(c.returncode, 0, c.stdout)
        # gate precondition re-verification, exactly as the gatekeeper does
        self.assertEqual(self.urs("verify", "final").returncode, 0)
        self.assertEqual(git(self.root, "rev-parse",
                             "HEAD").stdout.strip(), final_sha)
        self.assertEqual(gpm.committed_tree_digest(self.root),
                         digest_before)
        state_after = gpm.repo_state(self.root)
        self.assertIsNotNone(state_after)
        self.assertEqual(state_after["dirty"], [],
                         "the flow dirtied the worktree")
        self.assertEqual(state_after["head"], state_before["head"])


class PostFinalTemplateContracts(unittest.TestCase):
    """v1.0.15: gatekeeper and steward have ZERO tracked writes after
    finalization, in every shipped production-ready room."""

    @classmethod
    def setUpClass(cls):
        base = os.path.join(REPO, "plugins", "ai", "skills",
                            "agent-room-templates", "agentsrooms")
        cls.rooms = {}
        for name in ("full-team-website.json", "production-release.json"):
            with open(os.path.join(base, name), encoding="utf-8") as f:
                cls.rooms[name] = json.load(f)

    @staticmethod
    def untracked(path):
        return path.startswith(".solo/gate-evidence") or \
            path.startswith(".solo/run-state")

    def test_gatekeeper_is_output_only(self):
        for name, room in self.rooms.items():
            gk = next(s for s in room["seats"] if s["id"] == "gatekeeper")
            tracked = [w for w in gk.get("writes", [])
                       if not self.untracked(w)]
            self.assertEqual(tracked, [], (name, tracked))
            self.assertEqual(gk.get("proposes", []), [], name)
            self.assertNotIn("/solo:handoff-memory", gk["commands"], name)
            self.assertEqual(gk["commands"], ["/gate:production-ready"],
                             name)

    def test_steward_never_runs_after_finalizer(self):
        room = self.rooms["full-team-website.json"]
        stages = [st["id"] for st in room["stages"]]
        fin_idx = stages.index("finalize")
        seat_stage = {}
        for i, st in enumerate(room["stages"]):
            for sid in st["seats"]:
                seat_stage[sid] = i
        steward = room["memory_steward"]["seat"]
        self.assertNotIn(steward, seat_stage,
                         "steward is out-of-band (unstaged)")
        # v1.0.16: the cutoff is STRUCTURED, not prose — the runner reads
        # active_through_stage and can never invoke the steward at or
        # after the finalize stage
        cutoff = room["memory_steward"]["active_through_stage"]
        self.assertIn(cutoff, stages)
        self.assertLess(stages.index(cutoff), fin_idx,
                        "steward cutoff must be strictly before finalize")
        self.assertIn("MUST NOT invoke it at or after",
                      room["memory_steward"]["merge_policy"])
        # nothing at/after finalize proposes anything for it to merge
        for s in room["seats"]:
            if seat_stage.get(s["id"], -1) >= fin_idx:
                self.assertEqual(s.get("proposes", []), [],
                                 (s["id"], "proposals after the freeze"))

    def test_sha_carriers_are_untracked_run_state(self):
        for name, room in self.rooms.items():
            self.assertTrue(room["evidence"]["final_sha_recorded_in"]
                            .startswith(".solo/run-state/"), name)
        ft = self.rooms["full-team-website.json"]
        self.assertTrue(ft["worktrees"]["base_sha"]["stored_in"]
                        .startswith(".solo/run-state/"))

    def test_run_state_writes_go_through_the_helper(self):
        """v1.0.17: every prose contract that RECORDS a run SHA names the
        update_run_state.py helper — no room instructs anyone to write
        run-state JSON by hand."""
        for name, room in self.rooms.items():
            freeze = room["evidence"]["freeze"]
            self.assertIn("update_run_state.py", freeze["records"], name)
        ft = self.rooms["full-team-website.json"]
        self.assertIn("update_run_state.py",
                      ft["worktrees"]["base_sha"]["recorded_by"])


if __name__ == "__main__":
    unittest.main()
