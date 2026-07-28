"""gate_policy.py — the shared command policy, git-derived source identity,
and built-in schema evaluator used by BOTH record_evidence.py and
check_evidence.py. Adversarial acceptance tests A and B live here."""
import importlib.util
import json
import os
import subprocess
import tempfile
import shutil
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GP = os.path.join(REPO, "plugins", "gate", "lib", "gate_policy.py")
spec = importlib.util.spec_from_file_location("gate_policy_t", GP)
gp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gp)
xfspec = importlib.util.spec_from_file_location(
    "exe_fixtures_t", os.path.join(REPO, "tests", "exe_fixtures.py"))
xf = importlib.util.module_from_spec(xfspec)
xfspec.loader.exec_module(xf)

# bare interpreter token that actually resolves on this machine
def _usable_interpreter():
    r"""Pick an interpreter token that actually runs.

    ``shutil.which("python3")`` SUCCEEDS on a stock Windows box because
    %LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe is a zero-byte
    Microsoft Store App Execution Alias. Selecting it here made these tests
    assert against a stub that exits 9009, which is exactly the defect
    gate_policy now refuses. Skip a zero-length WindowsApps entry.
    """
    for name in ("python3", "python"):
        found = shutil.which(name)
        if not found:
            continue
        low = found.replace("/", "\\").lower()
        if "\\microsoft\\windowsapps\\" in low:
            try:
                if os.path.getsize(found) == 0:
                    continue
            except OSError:
                continue
        return name
    return "python"


PYTOK = _usable_interpreter()


def git(cwd, *args):
    return subprocess.run(["git"] + list(args), cwd=cwd,
                          capture_output=True, text=True, timeout=30)


class CommandPolicy(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="policy-root-")
        self.addCleanup(xf.force_rmtree, self.root)
        with open(os.path.join(self.root, "test_x.py"), "w",
                  encoding="utf-8") as f:
            f.write("import unittest\n")
        with open(os.path.join(self.root, "requirements-dev.lock"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write("demo-package==1.2.3 \\\n"
                    "    --hash=sha256:%s\n" % ("a" * 64))
        # live-target binding reads the COMMITTED .solo/stack.md at HEAD
        os.makedirs(os.path.join(self.root, ".solo"))
        with open(os.path.join(self.root, ".solo", "stack.md"), "w",
                  encoding="utf-8") as f:
            f.write("# Stack\nProd: https://x.example\n"
                    "Mail domain: example.com\n"
                    "version-endpoint: https://x.example/version\n"
                    "health-endpoint: https://x.example/health\n"
                    "health-expect: demo-service healthy\n")
        git(self.root, "init", "-q", ".")
        git(self.root, "config", "user.email", "t@example.invalid")
        git(self.root, "config", "user.name", "t")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "fixture")
        # inert EXTERNAL executables so PATH resolution has real targets
        ext = tempfile.mkdtemp(prefix="ext-bin-")
        self.addCleanup(shutil.rmtree, ext, ignore_errors=True)
        self.extbin = xf.make_bin_dir(ext, names=(
            "pytest", "gh", "npm", "npx", "curl", "cargo", "make", "go",
            "alembic", "pip-audit", "govulncheck"))
        self._oldpath = os.environ.get("PATH", "")
        os.environ["PATH"] = self.extbin + os.pathsep + self._oldpath
        self.addCleanup(os.environ.__setitem__, "PATH", self._oldpath)

    def refuse(self, category, argv):
        ok, why = gp.validate_command(category, argv, self.root)
        self.assertFalse(ok, (category, argv, why))
        return why

    def accept(self, category, argv):
        ok, why = gp.validate_command(category, argv, self.root)
        self.assertTrue(ok, (category, argv, why))
        return why

    # ---- acceptance test A: git log refused for EVERY category ----------
    def test_A_git_log_refused_for_every_category(self):
        for cat in sorted(gp.CATEGORIES):
            self.refuse(cat, ["git", "log", "-1", "--format=%H", "--"])

    # ---- acceptance test B: git ls-files refused as testing evidence ----
    def test_B_git_ls_files_refused_everywhere(self):
        self.refuse("testing",
                    ["git", "ls-files", "--error-unmatch", "tracked.txt"])
        for cat in sorted(gp.CATEGORIES):
            self.refuse(cat, ["git", "ls-files", "--error-unmatch", "x"])

    def test_no_policy_entry_mentions_git(self):
        for cat, validators in gp.COMMAND_POLICY.items():
            for argv in (["git", "status"], ["git", "diff"],
                         ["git", "show", "HEAD"]):
                ok, _ = gp.validate_command(cat, argv, self.root)
                self.assertFalse(ok, (cat, argv))

    # ---- no-op / info tokens ---------------------------------------------
    def test_help_version_and_noop_tokens_refused(self):
        for argv in ([PYTOK, "-m", "pytest", "--help"],
                     [PYTOK, "-m", "pytest", "--version"],
                     [PYTOK, "-m", "pytest", "--collect-only"],
                     ["npm", "test", "--version"],
                     ["npx", "--no-install", "jest", "--listTests"],
                     ["cargo", "test", "--list"]):
            why = self.refuse("testing", argv)
            self.assertTrue("no-op" in why or "policy entry" in why, why)

    def test_arbitrary_suffixes_and_paths_refused(self):
        self.refuse("testing", [PYTOK, "-m", "pytest", "/etc"])
        self.refuse("testing", [PYTOK, "-m", "pytest",
                                "../outside-the-root"])
        self.refuse("frontend", ["npm", "run", "build", "&&", "curl",
                                 "evil.example"])
        self.refuse("database", ["npx", "--no-install", "prisma",
                                 "migrate", "status", "--force", "extra"])
        self.refuse("monitoring", ["curl", "-sSf", "not-a-url"])
        self.refuse("seo", ["curl", "-sSfI", "https://a.example",
                            "https://b.example"])

    def test_full_argv_not_prefix(self):
        # a permitted prefix with a smuggled tail must NOT pass
        self.refuse("database", ["alembic", "check", ";", "rm", "-rf", "/"])
        self.refuse("security", ["npm", "audit", "--registry=http://evil"])

    def test_npx_requires_no_install_and_exact_runner_shape(self):
        why = self.refuse("testing", ["npx", "jest"])
        self.assertIn("--no-install", why)
        self.accept("testing", ["npx", "--no-install", "jest"])
        self.refuse("testing", ["npx", "--no-install", "jest",
                                "--config", "/tmp/foreign.js"])

    def test_url_credentials_and_sensitive_query_are_refused_offline(self):
        for url in ("https://user:pass@x.example/health",
                    "https://x.example/health?access_token=value"):
            why = self.refuse("monitoring",
                              ["curl", "-sSf", "-m", "10", url])
            self.assertTrue("credential" in why.lower() or
                            "userinfo" in why.lower(), why)

    def test_execution_url_guard_blocks_loopback(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            ok, why = gp.check_http_targets_safe(
                ["curl", "-sSf", "-m", "10",
                 "http://127.0.0.1/health"])
        self.assertFalse(ok)
        self.assertIn("unsafe HTTP target", why)

    def test_success_paths(self):
        self.accept("testing", [PYTOK, "-m", "unittest", "discover"])
        self.accept("testing", [PYTOK, "-m", "pytest", "-q", "test_x.py"])
        self.accept("backend", ["cargo", "test"])
        self.accept("frontend", ["npm", "run", "build"])
        self.accept("database", ["alembic", "check"])
        self.accept("security", ["npm", "audit", "--audit-level=high"])
        self.accept("security", ["pip-audit", "--strict",
                                 "--require-hashes", "-r",
                                 "requirements-dev.lock"])
        self.accept("monitoring", ["curl", "-sSf", "-m", "10",
                                   "https://x.example/health"])
        self.accept("performance", ["npx", "--no-install", "lighthouse",
                                    "https://x.example"])
        self.accept("product", [PYTOK, GP, "verify-artifact", "product"])
        # deployment accepts ONLY the committed version-endpoint (bounded
        # timeout mandatory) — the response binding to FINAL_SHA is
        # enforced post-execution by bind_version_endpoint_output
        self.accept("deployment", ["curl", "-sSf", "-m", "10",
                                   "https://x.example/version"])

    def test_email_dns_is_not_monitoring_evidence(self):
        """Email authentication can be healthy while every monitor is off."""
        self.refuse("monitoring", [
            PYTOK, gp.canonical_helper("check_email_dns.py"), "example.com"])
        self.accept("monitoring", ["curl", "-sSf", "-m", "10",
                                   "https://x.example/health"])

    def test_pip_audit_requires_committed_recognized_nonempty_target(self):
        why = self.refuse("security", ["pip-audit", "--strict"])
        self.assertIn("requires exactly one", why)
        why = self.refuse("security", ["pip-audit", "--strict", "-r",
                                       "test_x.py"])
        self.assertIn("recognized project requirements", why)

        with open(os.path.join(self.root, "requirements.txt"), "w",
                  encoding="utf-8", newline="\n") as stream:
            stream.write("demo-package==1.2.3\n")
        why = self.refuse("security", ["pip-audit", "--strict", "-r",
                                       "requirements.txt"])
        self.assertIn("committed in HEAD", why)

        git(self.root, "add", "requirements.txt")
        git(self.root, "commit", "-qm", "requirements target")
        self.accept("security", ["pip-audit", "--strict", "-r",
                                 "requirements.txt"])

        with open(os.path.join(self.root, "requirements.txt"), "w",
                  encoding="utf-8", newline="\n") as stream:
            stream.write("")
        git(self.root, "add", "requirements.txt")
        git(self.root, "commit", "-qm", "empty requirements target")
        why = self.refuse("security", ["pip-audit", "--strict", "-r",
                                       "requirements.txt"])
        self.assertIn("no dependency requirements", why)

    def test_pip_audit_hash_lock_requires_hash_mode_and_valid_lock(self):
        why = self.refuse("security", ["pip-audit", "--strict", "-r",
                                       "requirements-dev.lock"])
        self.assertIn("--require-hashes", why)
        self.accept("security", ["pip-audit", "--progress-spinner=off",
                                 "--require-hashes", "-r",
                                 "requirements-dev.lock"])

        lock_path = os.path.join(self.root, "requirements-dev.lock")
        with open(lock_path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write("demo-package==1.2.3\n")
        git(self.root, "add", "requirements-dev.lock")
        git(self.root, "commit", "-qm", "unhashed lock")
        why = self.refuse("security", ["pip-audit", "--strict",
                                       "--require-hashes", "-r",
                                       "requirements-dev.lock"])
        self.assertIn("exact pins with SHA-256 hashes", why)

    def test_pip_audit_rejects_worktree_target_different_from_head(self):
        lock_path = os.path.join(self.root, "requirements-dev.lock")
        with open(lock_path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write("different==9.9.9 \\\n"
                         "  --hash=sha256:%s\n" % ("b" * 64))
        why = self.refuse("security", ["pip-audit", "--strict",
                                       "--require-hashes", "-r",
                                       "requirements-dev.lock"])
        self.assertIn("differs from its committed HEAD blob", why)

    def test_pip_audit_rejects_requirement_file_options_and_includes(self):
        path = os.path.join(self.root, "requirements.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write("--index-url https://packages.example/simple\n"
                         "demo-package==1.2.3\n")
        git(self.root, "add", "requirements.txt")
        git(self.root, "commit", "-qm", "requirements option")
        why = self.refuse("security", ["pip-audit", "--strict", "-r",
                                       "requirements.txt"])
        self.assertIn("may not contain requirement-file options", why)

    def test_verify_artifact_no_longer_accepted_for_deploy_monitoring(self):
        """v1.0.16: release.md/monitoring.md byte counts are NOT deployment
        or monitoring evidence — verify-artifact is refused there."""
        self.refuse("deployment", [PYTOK, GP, "verify-artifact",
                                   "deployment"])
        self.refuse("monitoring", [PYTOK, GP, "verify-artifact",
                                   "monitoring"])

    def test_gh_release_view_removed_from_deployment(self):
        """An arbitrary old release can never prove the current commit."""
        self.refuse("deployment", ["gh", "release", "view", "v1.0.0"])

    def test_live_url_must_match_committed_stack(self):
        self.refuse("monitoring", ["curl", "-sSf", "-m", "10",
                                   "https://evil.example/"])
        self.refuse("deployment", ["curl", "-sSf", "-m", "10",
                                   "https://evil.example/"])
        # v1.0.17: even a stack-recorded HOST is not enough — monitoring
        # must hit the EXACT committed health-endpoint
        self.refuse("monitoring", ["curl", "-sSf", "-m", "10",
                                   "https://api.x.example/health"])

    def test_generic_homepage_and_unbounded_curl_refused(self):
        """v1.0.17: a generic homepage fetch is not deployment or
        monitoring evidence, and endpoint curls REQUIRE a bounded
        timeout."""
        why = self.refuse("monitoring",
                          ["curl", "-sSf", "-m", "10",
                           "https://x.example/"])
        self.assertIn("health-endpoint", why)
        why = self.refuse("deployment",
                          ["curl", "-sSf", "-m", "10",
                           "https://x.example/"])
        self.assertIn("version-endpoint", why)
        why = self.refuse("monitoring",
                          ["curl", "-sSf", "https://x.example/health"])
        self.assertIn("timeout", why)
        why = self.refuse("deployment",
                          ["curl", "-sSf", "https://x.example/version"])
        self.assertIn("timeout", why)
        self.refuse("monitoring", ["curl", "-sSf", "-m", "0",
                                   "https://x.example/health"])
        self.refuse("monitoring", ["curl", "-sSf", "-m", "301",
                                   "https://x.example/health"])
        self.refuse("monitoring", ["curl", "-sSfL", "-m", "10",
                                   "https://x.example/health"])

    def test_endpoint_declaration_is_fail_closed(self):
        """Without a committed `health-endpoint:`/`version-endpoint:` in
        stack.md the categories cannot use curl at all."""
        bare = tempfile.mkdtemp(prefix="no-endpoints-")
        self.addCleanup(xf.force_rmtree, bare)
        git(bare, "init", "-q", ".")
        git(bare, "config", "user.email", "t@example.invalid")
        git(bare, "config", "user.name", "t")
        os.makedirs(os.path.join(bare, ".solo"))
        with open(os.path.join(bare, ".solo", "stack.md"), "w") as f:
            f.write("# Stack\nProd: https://x.example\n")
        git(bare, "add", "-A")
        git(bare, "commit", "-qm", "stack without endpoints")
        for cat, key in (("monitoring", "health-endpoint"),
                         ("deployment", "version-endpoint")):
            ok, why = gp.validate_command(
                cat, ["curl", "-sSf", "-m", "10",
                      "https://x.example/health"], bare)
            self.assertFalse(ok)
            self.assertIn(key, str(why))

    def test_live_url_fails_closed_without_committed_stack(self):
        bare = tempfile.mkdtemp(prefix="no-stack-")
        self.addCleanup(xf.force_rmtree, bare)
        git(bare, "init", "-q", ".")
        git(bare, "config", "user.email", "t@example.invalid")
        git(bare, "config", "user.name", "t")
        with open(os.path.join(bare, "a.txt"), "w") as f:
            f.write("x\n")
        git(bare, "add", "-A")
        git(bare, "commit", "-qm", "no stack.md")
        ok, why = gp.validate_command(
            "monitoring", ["curl", "-sSf", "-m", "10",
                           "https://x.example/"], bare)
        self.assertFalse(ok)
        self.assertIn("stack.md", str(why))

    def test_verify_artifact_category_must_match(self):
        ok, why = gp.validate_command(
            "product", [PYTOK, GP, "verify-artifact", "security"],
            self.root)
        self.assertFalse(ok, why)

    def test_every_category_has_at_least_one_validator(self):
        self.assertEqual(set(gp.COMMAND_POLICY), set(gp.CATEGORIES))
        for cat, vs in gp.COMMAND_POLICY.items():
            self.assertTrue(vs, cat)

    def test_matrix_total_and_disjoint(self):
        self.assertEqual(set(gp.NA_ALLOWED) | gp.MANDATORY, gp.CATEGORIES)
        self.assertEqual(set(gp.NA_ALLOWED) & gp.MANDATORY, set())


class GitDerivedIdentity(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="gitid-")
        self.addCleanup(xf.force_rmtree, self.root)
        git(self.root, "init", "-q", ".")
        git(self.root, "config", "user.email", "t@example.invalid")
        git(self.root, "config", "user.name", "t")
        with open(os.path.join(self.root, "a.txt"), "w") as f:
            f.write("one\n")
        with open(os.path.join(self.root, ".gitignore"), "w") as f:
            f.write(".solo/gate-evidence/\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")

    def test_head_is_derived_and_full_length(self):
        head = gp.git_head(self.root)
        self.assertRegex(head, r"^[0-9a-f]{40}$")
        self.assertIsNone(gp.git_head(tempfile.gettempdir()))

    def test_committed_tree_digest_ignores_working_tree_mutation(self):
        """The digest comes from git OBJECTS: mutating a tracked file
        WITHOUT committing must not change it."""
        before = gp.committed_tree_digest(self.root)
        with open(os.path.join(self.root, "a.txt"), "a") as f:
            f.write("mutation\n")
        self.assertEqual(gp.committed_tree_digest(self.root), before)
        git(self.root, "checkout", "--", "a.txt")

    def test_committed_tree_digest_changes_with_commits(self):
        before = gp.committed_tree_digest(self.root)
        with open(os.path.join(self.root, "b.txt"), "w") as f:
            f.write("two\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "second")
        self.assertNotEqual(gp.committed_tree_digest(self.root), before)

    def test_evidence_dir_excluded_from_digest(self):
        os.makedirs(os.path.join(self.root, ".solo", "gate-evidence"),
                    exist_ok=True)
        before = gp.committed_tree_digest(self.root)
        with open(os.path.join(self.root, ".solo", "gate-evidence",
                               "x.json"), "w") as f:
            f.write("{}")
        self.assertEqual(gp.committed_tree_digest(self.root), before)

    def test_dirty_paths_reported_outside_evidence_only(self):
        self.assertEqual(gp.dirty_paths_outside_evidence(self.root), [])
        os.makedirs(os.path.join(self.root, ".solo", "gate-evidence"),
                    exist_ok=True)
        with open(os.path.join(self.root, ".solo", "gate-evidence",
                               "t.json"), "w") as f:
            f.write("{}")
        self.assertEqual(gp.dirty_paths_outside_evidence(self.root), [],
                         "evidence-dir files must never count as dirt")
        with open(os.path.join(self.root, "new.env"), "w") as f:
            f.write("X=1\n")
        dirty = gp.dirty_paths_outside_evidence(self.root)
        self.assertEqual(len(dirty), 1)
        self.assertIn("new.env", dirty[0])

    def test_evidence_tracked_in_head_detection(self):
        self.assertFalse(gp.evidence_tracked_in_head(self.root))
        os.makedirs(os.path.join(self.root, ".solo", "gate-evidence"),
                    exist_ok=True)
        p = os.path.join(self.root, ".solo", "gate-evidence", "t.json")
        with open(p, "w") as f:
            f.write("{}")
        git(self.root, "add", "-f", p)
        git(self.root, "commit", "-qm", "track evidence")
        self.assertTrue(gp.evidence_tracked_in_head(self.root))


class BuiltinSchemaEvaluator(unittest.TestCase):
    """The bundled schema is enforced WITHOUT the jsonschema package."""

    def test_ref_resolution_and_oneof(self):
        schema = gp.load_schema()
        bad = {"schema": "solo-suite/gate-evidence-v1"}
        errs = gp.schema_validate(bad, schema)
        self.assertTrue(errs)
        self.assertTrue(any("oneOf" in e or "missing required" in e
                            for e in errs), errs)

    def test_unknown_property_rejected(self):
        schema = gp.load_schema()
        errs = gp.schema_validate({"banana": 1}, schema)
        self.assertTrue(errs)

    def test_agrees_with_jsonschema_when_available(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed — builtin path already "
                          "covered above")
        schema = gp.load_schema()
        samples = [
            {"schema": "solo-suite/gate-evidence-v1"},
            {"schema": "wrong"},
            {"banana": 1},
        ]
        for rec in samples:
            builtin_ok = not gp.schema_validate(rec, schema)
            try:
                jsonschema.validate(rec, schema)
                lib_ok = True
            except jsonschema.ValidationError:
                lib_ok = False
            self.assertEqual(builtin_ok, lib_ok, rec)


GOOD_PRD = """# PRD — demo

## Problem and goals
Developers who script against machine-readable evidence records lack a
small dependable arithmetic helper library; this package gives solo teams
a tested, documented, dependency-free building block they can vendor
quickly and audit line by line without pulling in a framework.

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


class VerifyArtifact(unittest.TestCase):
    """v1.0.17: the generic '200 bytes and two headings' check is GONE —
    every document category enforces required headings, substantive
    content, placeholder rejection, and required identifier/decision
    fields."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="va-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        os.makedirs(os.path.join(self.root, ".solo"))

    def write(self, rel, text):
        with open(os.path.join(self.root, rel), "w", encoding="utf-8") as f:
            f.write(text)

    def test_missing_artifact_fails(self):
        self.assertEqual(gp.verify_artifact("product", self.root), 1)

    def test_trivial_artifact_fails(self):
        self.write(".solo/prd.md", "# PRD\nshort\n")
        self.assertEqual(gp.verify_artifact("product", self.root), 1)

    def test_repeated_filler_fails_the_vocabulary_floor(self):
        """The old check PASSED this document — 356 bytes, 3 headings of
        'content content content …'. The category-specific check fails it
        (no scope/acceptance headings, no list items, ~10 distinct
        words)."""
        self.write(".solo/prd.md", "# PRD\n\n## Goals\n"
                   + "content " * 40 + "\n\n## Non-goals\nmore\n")
        self.assertEqual(gp.verify_artifact("product", self.root), 1)

    def test_placeholder_markers_fail(self):
        for marker in ("TBD", "TODO", "lorem ipsum", "coming soon",
                       "to be written"):
            self.write(".solo/prd.md",
                       GOOD_PRD.replace("No floating point guarantees",
                                        marker + " floating point"))
            self.assertEqual(gp.verify_artifact("product", self.root), 1,
                             marker)

    def test_missing_required_heading_fails(self):
        self.write(".solo/prd.md", GOOD_PRD.replace("## Non-goals",
                                                    "## Something else"))
        self.assertEqual(gp.verify_artifact("product", self.root), 1)

    def test_missing_required_fields_fail(self):
        # product: needs at least three concrete bullets
        self.write(".solo/prd.md",
                   GOOD_PRD.replace("- AC-", "AC-").replace("- US-", "US-")
                   .replace("- No floating", "No floating"))
        self.assertEqual(gp.verify_artifact("product", self.root), 1)
        # architecture: needs a recorded decision (ADR-n/DEC-n/'Decision:')
        arch = """# Architecture

## Components and modules
A single module exposes two pure functions; the unit tests live beside it
and no services, schedulers, or background workers exist anywhere.

## Data and API contracts
Both functions accept integers and return integers; type errors propagate
from the interpreter unchanged; there is no storage layer to version.

## Decisions and tradeoffs
We talked about several options at length during planning meetings.
"""
        self.write(".solo/architecture.md", arch)
        self.assertEqual(gp.verify_artifact("architecture", self.root), 1)
        self.write(".solo/architecture.md",
                   arch.replace("We talked about several options at "
                                "length during planning meetings.",
                                "- DEC-1: stay stdlib-only so evidence "
                                "commands remain reproducible."))
        self.assertEqual(gp.verify_artifact("architecture", self.root), 0)

    def test_substantive_category_specific_artifact_passes(self):
        self.write(".solo/prd.md", GOOD_PRD)
        self.assertEqual(gp.verify_artifact("product", self.root), 0)

    def test_documentation_requires_runnable_example(self):
        readme = """# lib — a tiny arithmetic helper

## Install / setup
Install the wheel from your registry and import the module directly; the
package is dependency-free and tested with the standard unittest runner,
so the whole suite executes offline in a few seconds on any machine.

## Usage
Call add or sub with two integers and read the returned integer result.
"""
        self.write("README.md", readme)
        self.assertEqual(gp.verify_artifact("documentation", self.root), 1)
        self.write("README.md", readme + "\n```python\nfrom lib import "
                   "add\nassert add(1, 2) == 3\n```\n")
        self.assertEqual(gp.verify_artifact("documentation", self.root), 0)

    def test_tool_backed_category_refuses_verify_artifact(self):
        self.assertEqual(gp.verify_artifact("testing", self.root), 2)


class EndpointBindingsV1017(unittest.TestCase):
    """v1.0.17 output bindings: deployment responses must contain the
    derived HEAD; monitoring responses must be an explicit health
    contract. Generic curl output fails both."""

    HEAD = "a" * 40

    def test_version_endpoint_binding(self):
        ok, _ = gp.bind_version_endpoint_output(
            b"deployed commit: " + self.HEAD.encode(), self.HEAD)
        self.assertTrue(ok)
        ok, _ = gp.bind_version_endpoint_output(
            b"HTTP/1.1 200 OK\r\nX-Commit: " + self.HEAD.upper().encode()
            + b"\r\n\r\nready", self.HEAD)
        self.assertTrue(ok, "case-insensitive header match must bind")
        for generic in (b"<html><body>Welcome!</body></html>",
                        b"OK", b"deployed commit: " + b"b" * 40):
            ok, why = gp.bind_version_endpoint_output(generic, self.HEAD)
            self.assertFalse(ok, generic)
            self.assertIn("not bound", why)

    def test_health_endpoint_binding(self):
        for good in (b'{"status": "ok"}', b'{"state": "HEALTHY"}',
                     b'{"health": "pass", "uptime": 1}',
                     b'HTTP/1.1 200 OK\r\nA: b\r\n\r\n{"status": "up"}'):
            ok, _ = gp.bind_health_endpoint_output(good, self.HEAD)
            self.assertTrue(ok, good)
        for generic in (b"<html><h1>ok</h1></html>", b"it works",
                        b'{"status": "degraded"}', b'{"foo": "ok"}',
                        b"[1, 2, 3]"):
            ok, why = gp.bind_health_endpoint_output(generic, self.HEAD)
            self.assertFalse(ok, generic)
            self.assertIn("not monitoring evidence", why)

    def test_health_expect_marker_from_committed_stack(self):
        root = tempfile.mkdtemp(prefix="expect-")
        self.addCleanup(xf.force_rmtree, root)
        git(root, "init", "-q", ".")
        git(root, "config", "user.email", "t@example.invalid")
        git(root, "config", "user.name", "t")
        os.makedirs(os.path.join(root, ".solo"))
        with open(os.path.join(root, ".solo", "stack.md"), "w") as f:
            f.write("# Stack\nhealth-endpoint: https://x.example/health\n"
                    "health-expect: demo-service healthy\n")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "stack")
        ok, _ = gp.bind_health_endpoint_output(
            b"all good: demo-service healthy", self.HEAD, root)
        self.assertTrue(ok)
        ok, _ = gp.bind_health_endpoint_output(
            b"all good: some other service", self.HEAD, root)
        self.assertFalse(ok)


class CanonicalIdentityV1015(unittest.TestCase):
    """v1.0.15 regressions: basenames are never trusted; fake helpers,
    fake interpreters, zero-test flags, and `gh run list` are refused."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="canon-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.ev = os.path.join(self.root, ".solo", "gate-evidence")
        os.makedirs(self.ev)
        self.installed_scanner = os.path.join(
            REPO, "plugins", "site-doctor", "skills", "security-review",
            "scripts", "scan_secrets.py")
        ext = tempfile.mkdtemp(prefix="ext-bin-")
        self.addCleanup(shutil.rmtree, ext, ignore_errors=True)
        self.extbin = xf.make_bin_dir(ext, names=("gh", "npx", "npm",
                                                  "curl"))
        self._oldpath = os.environ.get("PATH", "")
        os.environ["PATH"] = self.extbin + os.pathsep + self._oldpath
        self.addCleanup(os.environ.__setitem__, "PATH", self._oldpath)

    def refuse(self, cat, argv):
        ok, why = gp.validate_command(cat, argv, self.root)
        self.assertFalse(ok, (cat, argv, why))
        return str(why)

    def accept(self, cat, argv):
        ok, why = gp.validate_command(cat, argv, self.root)
        self.assertTrue(ok, (cat, argv, why))

    def test_fake_helper_inside_evidence_dir_refused(self):
        for name, cat, extra in (
                ("scan_secrets.py", "security", ["."]),
                ("gate_policy.py", "product", ["verify-artifact",
                                               "product"])):
            fake = os.path.join(self.ev, name)
            shutil.copy({"scan_secrets.py": self.installed_scanner,
                         "gate_policy.py": GP}[name], fake)
            why = self.refuse(cat, ["python",
                                    ".solo/gate-evidence/%s" % name]
                              + extra)
            self.assertIn("INSIDE the project root", why)

    def test_fake_helper_anywhere_inside_project_refused(self):
        fake = os.path.join(self.root, "scan_secrets.py")
        shutil.copy(self.installed_scanner, fake)
        why = self.refuse("security", [PYTOK, "scan_secrets.py", "."])
        self.assertIn("INSIDE the project root", why)

    def test_fake_python_inside_project_refused(self):
        fake = os.path.join(self.ev, "python")
        with open(fake, "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(fake, 0o755)
        self.refuse("testing",
                    [".solo/gate-evidence/python", "-m", "unittest",
                     "discover"])
        self.refuse("testing", ["./python", "-m", "unittest", "discover"])

    def test_relative_interpreter_path_refused_even_outside(self):
        self.refuse("testing",
                    ["../somewhere/python3", "-m", "unittest", "discover"])

    def test_tampered_helper_outside_project_refused(self):
        tmp = tempfile.mkdtemp(prefix="tampered-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        bad = os.path.join(tmp, "scan_secrets.py")
        with open(self.installed_scanner, encoding="utf-8") as f:
            body = f.read()
        with open(bad, "w", encoding="utf-8") as f:
            f.write(body + "\n# tampered\n")
        why = self.refuse("security", [PYTOK, bad, "."])
        self.assertIn("digest", why.lower())

    def test_byte_identical_helper_outside_project_accepted(self):
        tmp = tempfile.mkdtemp(prefix="copy-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        good = os.path.join(tmp, "scan_secrets.py")
        shutil.copy(self.installed_scanner, good)
        self.accept("security", [PYTOK, good, "."])

    def test_installed_canonical_paths_accepted(self):
        self.accept("security", [PYTOK, self.installed_scanner, "."])
        self.accept("product", [PYTOK, GP, "verify-artifact",
                                "product"])

    def test_pass_with_no_tests_flags_refused_all_runners(self):
        for argv in (["npx", "--no-install", "jest", "--passWithNoTests"],
                     ["npx", "--no-install", "jest", "--passWithNoTests=true"],
                     ["npx", "--no-install", "vitest", "run", "--passWithNoTests"],
                     ["npx", "--no-install", "playwright", "test",
                      "--pass-with-no-tests"],
                     ["npm", "test", "--if-present"],
                     ["npx", "--no-install", "jest", "--PASSWITHNOTESTS"]):
            why = self.refuse("testing", argv)
            self.assertTrue("no-op" in why or "policy" in why, why)

    def test_gh_run_list_refused_everywhere(self):
        for cat in ("deployment", "monitoring"):
            self.refuse(cat, ["gh", "run", "list"])
            self.refuse(cat, ["gh", "run", "list", "--limit=5"])

    def test_gh_run_view_requires_exact_run_exit_status_and_binding(self):
        self.accept("deployment",
                    ["gh", "run", "view", "8675309", "--exit-status",
                     "--json", "headSha,conclusion,status"])
        self.accept("deployment",
                    ["gh", "run", "view", "8675309", "--exit-status",
                     "--json=headSha,conclusion,status,displayTitle"])
        # the unbound v1.0.15 form is refused: without the --json binding
        # fields an arbitrary old run could "prove" the current commit
        self.refuse("deployment",
                    ["gh", "run", "view", "8675309", "--exit-status"])
        self.refuse("deployment",
                    ["gh", "run", "view", "8675309", "--exit-status",
                     "--json", "conclusion"])
        self.refuse("deployment", ["gh", "run", "view", "8675309"])
        self.refuse("deployment", ["gh", "run", "view", "--exit-status"])
        self.refuse("deployment", ["gh", "run", "view", "main",
                                   "--exit-status",
                                   "--json", "headSha,conclusion,status"])

    def test_gh_run_output_binding_logic(self):
        head = "a" * 40
        ok, _ = gp.bind_gh_run_output(
            json.dumps({"headSha": head, "conclusion": "success",
                        "status": "completed"}).encode(), head)
        self.assertTrue(ok)
        for bad in ({"headSha": "b" * 40, "conclusion": "success"},
                    {"headSha": head, "conclusion": "failure"},
                    {"headSha": head},
                    ["not-an-object"]):
            ok, why = gp.bind_gh_run_output(json.dumps(bad).encode(), head)
            self.assertFalse(ok, bad)
        ok, why = gp.bind_gh_run_output(b"not json at all", head)
        self.assertFalse(ok)


class FailClosedRepoState(unittest.TestCase):
    """v1.0.15 regressions: index-vs-HEAD, worktree-vs-index, renames with
    BOTH sides, documented ignored-file policy, and git failures that can
    never mean clean."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="repostate-")
        self.addCleanup(xf.force_rmtree, self.root)
        git(self.root, "init", "-q", ".")
        git(self.root, "config", "user.email", "t@example.invalid")
        git(self.root, "config", "user.name", "t")
        with open(os.path.join(self.root, "app.txt"), "w") as f:
            f.write("hello\n")
        with open(os.path.join(self.root, ".gitignore"), "w") as f:
            f.write(".solo/gate-evidence/\n.solo/run-state/\n"
                    "production.env\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")

    def dirt(self):
        state = gp.repo_state(self.root)
        self.assertIsNotNone(state)
        return state["dirty"]

    def test_clean_baseline(self):
        self.assertEqual(self.dirt(), [])

    def test_staged_rename_into_evidence_is_dirty(self):
        os.makedirs(os.path.join(self.root, ".solo", "gate-evidence"),
                    exist_ok=True)
        git(self.root, "mv", "app.txt", ".solo/gate-evidence/app.txt")
        d = self.dirt()
        self.assertTrue(any("app.txt" in x and "gate-evidence" in x
                            for x in d), d)
        self.assertTrue(any(x.startswith("staged:R") for x in d), d)

    def test_staged_change_inside_evidence_is_dirty(self):
        """No evidence-dir exemption on the INDEX side."""
        os.makedirs(os.path.join(self.root, ".solo", "gate-evidence"),
                    exist_ok=True)
        p = os.path.join(self.root, ".solo", "gate-evidence", "x.json")
        with open(p, "w") as f:
            f.write("{}")
        git(self.root, "add", "-f", p)
        self.assertTrue(any("staged:A" in x for x in self.dirt()))

    def test_unstaged_modification_and_deletion_dirty(self):
        with open(os.path.join(self.root, "app.txt"), "a") as f:
            f.write("drift\n")
        self.assertTrue(any("unstaged:M" in x for x in self.dirt()))
        git(self.root, "checkout", "--", "app.txt")
        os.remove(os.path.join(self.root, "app.txt"))
        self.assertTrue(any("unstaged:D" in x for x in self.dirt()))

    def test_ignored_file_exempt_by_documented_policy(self):
        """production.env is gitignored -> exempt BY DESIGN; the docstring
        documents exactly this policy."""
        with open(os.path.join(self.root, "production.env"), "w") as f:
            f.write("SECRET=x\n")
        self.assertEqual(self.dirt(), [])
        self.assertIn("IGNORED-FILE POLICY", gp.repo_state.__doc__)
        self.assertIn("production.env", gp.repo_state.__doc__)
        # ...and a NON-ignored untracked file is dirt
        with open(os.path.join(self.root, "other.env"), "w") as f:
            f.write("X=1\n")
        self.assertTrue(any("untracked" in x and "other.env" in x
                            for x in self.dirt()))

    def test_git_failure_fails_closed_never_clean(self):
        # RENAME .git instead of rmtree: on Windows, read-only object files
        # make a direct shutil.rmtree raise PermissionError mid-test.
        xf.disable_git_dir(self.root)
        self.assertIsNone(gp.repo_state(self.root))
        self.assertIsNone(gp.dirty_paths_outside_evidence(self.root))
        self.assertIsNone(gp.git_head(self.root))
        self.assertIsNone(gp.committed_tree_digest(self.root))
        self.assertIsNone(gp.evidence_tracked_in_head(self.root))
        self.assertIsNone(gp.tracked_in_head(self.root, "app.txt"))

    def test_corrupted_git_dir_fails_closed(self):
        with open(os.path.join(self.root, ".git", "HEAD"), "w") as f:
            f.write("garbage not a ref\n")
        self.assertIsNone(gp.repo_state(self.root))


class PathResolutionRegression(unittest.TestCase):
    """v1.0.16 acceptance (item 13): EVERY supported executable family goes
    through the canonical PATH resolver. Project-local resolution is
    REJECTED (never silently used); external resolution is accepted and
    the verified external absolute path is what gets recorded. Fixtures
    are INERT (exit 0) — resolution targets only, never executed."""

    # (family argv, category) — one accepted shape per family
    FAMILIES = [
        (["python3", "-m", "unittest", "discover"], "testing", "python3"),
        (["python", "-m", "unittest", "discover"], "testing", "python"),
        (["pytest", "-q", "test_x.py"], "testing", "pytest"),
        (["gh", "run", "view", "8675309", "--exit-status",
          "--json", "headSha,conclusion,status"], "deployment", "gh"),
        (["npm", "test"], "testing", "npm"),
        (["npx", "--no-install", "jest"], "testing", "npx"),
        (["curl", "-sSf", "-m", "10", "https://x.example/health"],
         "monitoring", "curl"),
        (["cargo", "test"], "backend", "cargo"),
        (["make", "test"], "backend", "make"),
        (["go", "test", "./..."], "backend", "go"),
        (["alembic", "check"], "database", "alembic"),
        (["pip-audit", "--strict", "--require-hashes", "-r",
          "requirements-dev.lock"], "security", "pip-audit"),
        (["govulncheck", "./..."], "security", "govulncheck"),
    ]

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="resolve-root-")
        self.addCleanup(xf.force_rmtree, self.root)
        with open(os.path.join(self.root, "test_x.py"), "w") as f:
            f.write("import unittest\n")
        with open(os.path.join(self.root, "requirements-dev.lock"), "w",
                  newline="\n") as f:
            f.write("demo-package==1.2.3 \\\n"
                    "  --hash=sha256:%s\n" % ("a" * 64))
        os.makedirs(os.path.join(self.root, ".solo"))
        with open(os.path.join(self.root, ".solo", "stack.md"), "w") as f:
            f.write("# Stack\nProd: https://x.example\n"
                    "version-endpoint: https://x.example/version\n"
                    "health-endpoint: https://x.example/health\n")
        git(self.root, "init", "-q", ".")
        git(self.root, "config", "user.email", "t@example.invalid")
        git(self.root, "config", "user.name", "t")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "fixture")
        self._oldpath = os.environ.get("PATH", "")
        self.addCleanup(os.environ.__setitem__, "PATH", self._oldpath)
        # a PROJECT-LOCAL bin full of correctly-named fakes...
        self.projbin = xf.make_bin_dir(self.root, names=xf.FAMILY_NAMES)
        # ...and an EXTERNAL one
        ext = tempfile.mkdtemp(prefix="ext-bin-")
        self.addCleanup(shutil.rmtree, ext, ignore_errors=True)
        self.extbin = xf.make_bin_dir(ext, names=xf.FAMILY_NAMES)

    def test_project_local_resolution_rejected_for_every_family(self):
        os.environ["PATH"] = self.projbin + os.pathsep + self._oldpath
        for argv, cat, name in self.FAMILIES:
            ok, why = gp.validate_command(cat, list(argv), self.root)
            self.assertFalse(ok, (name, why))
            self.assertIn("INSIDE the project root", str(why), (name, why))

    def test_external_resolution_accepted_and_identity_recorded(self):
        os.environ["PATH"] = self.extbin + os.pathsep + self._oldpath
        for argv, cat, name in self.FAMILIES:
            ok, why = gp.validate_command(cat, list(argv), self.root)
            self.assertTrue(ok, (name, why))
            resolved, err = gp.resolve_executable(argv[0], self.root)
            self.assertIsNone(err, (name, err))
            self.assertTrue(os.path.isabs(resolved), (name, resolved))
            self.assertTrue(resolved.startswith(
                os.path.realpath(self.extbin)), (name, resolved))

    def test_external_beats_project_local_only_by_path_order_rejection(self):
        """Project dir FIRST on PATH: rejected, not silently replaced."""
        os.environ["PATH"] = (self.projbin + os.pathsep + self.extbin
                              + os.pathsep + self._oldpath)
        ok, why = gp.validate_command(
            "testing", ["pytest", "-q", "test_x.py"], self.root)
        self.assertFalse(ok)
        self.assertIn("INSIDE the project root", str(why))

    def test_unresolvable_executable_rejected(self):
        os.environ["PATH"] = self.extbin
        ok, why = gp.validate_command(
            "database", ["no-such-tool-xyz", "check"], self.root)
        self.assertFalse(ok)
        resolved, err = gp.resolve_executable("definitely-not-here-xyz",
                                              self.root)
        self.assertIsNone(resolved)
        self.assertIn("does not resolve", err)

    def test_relative_path_executable_rejected(self):
        os.environ["PATH"] = self.extbin + os.pathsep + self._oldpath
        resolved, err = gp.resolve_executable(
            os.path.join("..", "somewhere", "pytest"), self.root)
        self.assertIsNone(resolved)
        self.assertIn("refused", err)

    def test_evidence_dir_executable_rejected(self):
        ev = os.path.join(self.root, ".solo", "gate-evidence")
        evbin = xf.make_bin_dir(ev, names=("gh",))
        os.environ["PATH"] = evbin + os.pathsep + self._oldpath
        ok, why = gp.validate_command(
            "deployment",
            ["gh", "run", "view", "1", "--exit-status",
             "--json", "headSha,conclusion,status"], self.root)
        self.assertFalse(ok)
        self.assertIn("INSIDE the project root", str(why))


if __name__ == "__main__":
    unittest.main()
