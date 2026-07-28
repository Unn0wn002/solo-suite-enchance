"""check_evidence.py: the gate accepts ONLY a complete, schema-valid,
policy-revalidated set bound to the DERIVED HEAD and committed-tree digest.
Acceptance test C (hand-written records missing recorder/command_argv/
status/tree_digest fail) lives here, plus the matrix, N/A, and completeness
rules. All checks run against a real git fixture because the checker
derives HEAD itself."""
import datetime
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import shutil
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GP = os.path.join(REPO, "plugins", "gate", "lib", "gate_policy.py")
CE = os.path.join(REPO, "plugins", "gate", "skills",
                  "production-readiness-reviewer", "scripts",
                  "check_evidence.py")
GP = os.path.join(REPO, "plugins", "gate", "lib", "gate_policy.py")
SCHEMA_PATH = os.path.join(REPO, "plugins", "gate", "skills",
                           "production-readiness-reviewer", "schema",
                           "gate-evidence-v1.schema.json")
spec = importlib.util.spec_from_file_location("check_evidence", CE)
ce = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ce)
gspec = importlib.util.spec_from_file_location("gp_ge", GP)
gp = importlib.util.module_from_spec(gspec)
gspec.loader.exec_module(gp)
xfspec = importlib.util.spec_from_file_location(
    "exe_fixtures_ge", os.path.join(REPO, "tests", "exe_fixtures.py"))
xf = importlib.util.module_from_spec(xfspec)
xfspec.loader.exec_module(xf)

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

try:
    import jsonschema
except ImportError:
    jsonschema = None

_BASE_NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


NOW = iso(_BASE_NOW)
FRESH_TIMESTAMP = iso(_BASE_NOW - datetime.timedelta(days=1))
FRESH_EXPIRES = iso(_BASE_NOW + datetime.timedelta(days=6))
EXPIRED = iso(_BASE_NOW - datetime.timedelta(seconds=1))
OLD_TIMESTAMP = iso(_BASE_NOW - datetime.timedelta(days=30))
OLD_EXPIRES = iso(_BASE_NOW + datetime.timedelta(days=30))


def git(cwd, *args):
    return subprocess.run(["git"] + list(args), cwd=cwd,
                          capture_output=True, text=True, timeout=30)


SCANNER_INSTALLED = os.path.join(REPO, "plugins", "site-doctor", "skills",
                                 "security-review", "scripts",
                                 "scan_secrets.py")


class Fixture(unittest.TestCase):
    """A real git repo; HEAD/tree digest derived from it."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="gate-root-")
        self.addCleanup(xf.force_rmtree, self.root)
        os.makedirs(os.path.join(self.root, ".solo"))
        self.artifact_rel = ".solo/risks.md"
        with open(os.path.join(self.root, self.artifact_rel), "w",
                  encoding="utf-8") as f:
            f.write("scan results: PASS\n")
        # live-target binding reads the COMMITTED stack.md at HEAD;
        # v1.0.17: deployment/monitoring curls bind to these endpoints
        with open(os.path.join(self.root, ".solo", "stack.md"), "w",
                  encoding="utf-8") as f:
            f.write("# Stack\nProd: https://x.example\n"
                    "version-endpoint: https://x.example/version\n"
                    "health-endpoint: https://x.example/health\n")
        with open(os.path.join(self.root, ".solo", "project.md"), "w",
                  encoding="utf-8") as f:
            f.write("# Project\n\nProject profile: api-service\n")
        with open(os.path.join(self.root, "test_x.py"), "w",
                  encoding="utf-8") as f:
            f.write("import unittest\n")
        with open(os.path.join(self.root, ".gitignore"), "w",
                  encoding="utf-8") as f:
            f.write(".solo/gate-evidence/\n__pycache__/\n")
        # inert external executables so argv[0] resolution succeeds for
        # every synthetic record family (alembic/npx/curl may be absent)
        ext = tempfile.mkdtemp(prefix="ext-bin-")
        self.addCleanup(shutil.rmtree, ext, ignore_errors=True)
        self.extbin = xf.make_bin_dir(ext, names=("alembic", "npx", "npm",
                                                  "curl", "gh"))
        self._oldpath = os.environ.get("PATH", "")
        os.environ["PATH"] = self.extbin + os.pathsep + self._oldpath
        self.addCleanup(os.environ.__setitem__, "PATH", self._oldpath)
        git(self.root, "init", "-q", ".")
        git(self.root, "config", "user.email", "t@example.invalid")
        git(self.root, "config", "user.name", "t")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")
        self.head = git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.tree = gp.committed_tree_digest(self.root)
        with open(os.path.join(self.root, self.artifact_rel), "rb") as f:
            self.digest = hashlib.sha256(f.read()).hexdigest()
        self.ev = os.path.join(self.root, ".solo", "gate-evidence")
        os.makedirs(self.ev)
        self.now = ce.parse_ts(NOW)
        self.schema = gp.load_schema()

    def record(self, **over):
        argv = over.pop("command_argv",
                        [PYTOK, SCANNER_INSTALLED, "."])
        resolved = over.pop("resolved_executable", None)
        if resolved is None:
            resolved, _err = gp.resolve_executable(argv[0], self.root)
            resolved = resolved or "/unresolvable/" + argv[0]
        base = {
            "schema": "solo-suite/gate-evidence-v1",
            "status": "verified",
            "recorder": "record_evidence.py/v1",
            "project": "demo",
            "commit": self.head,
            "tree_digest": self.tree,
            "environment": "production",
            "timestamp": FRESH_TIMESTAMP,
            "category": "security",
            "command": " ".join(argv),
            "command_argv": argv,
            "command_id": gp.validate_command(
                over.get("category", "security"), argv, self.root)[1],
            "resolved_executable": resolved,
            "exit_code": 0,
            "artifact": self.artifact_rel,
            "artifact_sha256": self.digest,
            "reviewer": "security-seat",
            "expires": FRESH_EXPIRES,
        }
        base.update(over)
        return base

    def na_record(self, category, profile="api-service", **over):
        base = {
            "schema": "solo-suite/gate-evidence-v1",
            "status": "not-applicable",
            "recorder": "record_evidence.py/v1",
            "project": "demo",
            "commit": self.head,
            "environment": "production",
            "timestamp": FRESH_TIMESTAMP,
            "category": category,
            "profile": profile,
            "reason": "API service exposes no public pages; nothing to "
                      "index or track here",
            "applicability": {"matrix": "%s:%s" % (category, profile),
                              "profile_source": ".solo/project.md",
                              "checked": ["router exposes JSON only"]},
            "reviewer": "finalizer",
            "expires": FRESH_EXPIRES,
        }
        base.update(over)
        if "applicability" not in over:
            base["applicability"]["matrix"] = "%s:%s" % (base["category"],
                                                         base["profile"])
        return base

    def reasons(self, rec, profile=None, tree=None):
        return ce.check_record(rec, self.head, "production", self.now, 7,
                               project="demo", root=self.root,
                               profile=profile,
                               expected_tree=tree or self.tree,
                               schema=self.schema)

    def write(self, name, rec):
        with open(os.path.join(self.ev, name), "w", encoding="utf-8") as f:
            json.dump(rec, f)

    def commit_profile(self, profile):
        """Bind a test case to a real committed canonical project profile."""
        project = os.path.join(self.root, ".solo", "project.md")
        with open(project, "w", encoding="utf-8", newline="\n") as stream:
            stream.write("# Project\n\nProject profile: %s\n" % profile)
        self.assertEqual(git(self.root, "add", ".solo/project.md").returncode,
                         0)
        changed = git(self.root, "diff", "--cached", "--quiet").returncode
        if changed:
            committed = git(self.root, "commit", "-qm", "profile " + profile)
            self.assertEqual(committed.returncode, 0, committed.stderr)
        self.head = git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.tree = gp.committed_tree_digest(self.root)

    def run_cli(self, *extra, **kw):
        argv = [sys.executable, CE, self.ev, "--root", self.root,
                "--environment", "production", "--project", "demo",
                ] + list(extra)
        if kw.get("profile"):
            argv += ["--profile", kw["profile"]]
        return subprocess.run(argv, capture_output=True, text=True,
                              timeout=120)


class RecordRules(Fixture):
    def test_fresh_matching_record_accepted(self):
        self.assertEqual(self.reasons(self.record()), [])

    def test_freshness_cutoff_is_exact_not_integer_days(self):
        exact = self.record(timestamp=iso(
            self.now - datetime.timedelta(days=7)))
        self.assertFalse(any("freshness limit" in reason
                             for reason in self.reasons(exact)))

        one_second_stale = self.record(timestamp=iso(
            self.now - datetime.timedelta(days=7, seconds=1)))
        reasons = self.reasons(one_second_stale)
        self.assertTrue(any("exact 7-day freshness limit" in reason
                            for reason in reasons), reasons)

    def test_future_timestamp_still_rejected(self):
        future = self.record(timestamp=iso(
            self.now + datetime.timedelta(seconds=1)))
        self.assertTrue(any("timestamp is in the future" in reason
                            for reason in self.reasons(future)))

    # ---- acceptance test C: hand-written records missing the new
    # required fields fail the bundled schema ------------------------------
    def test_C_missing_recorder_command_argv_status_tree_digest_fail(self):
        for missing in ("recorder", "command_argv", "status", "tree_digest"):
            rec = self.record()
            del rec[missing]
            r = self.reasons(rec)
            self.assertTrue(any("SCHEMA" in x for x in r), (missing, r))

    def test_C_all_four_missing_together_fail(self):
        rec = self.record()
        for k in ("recorder", "command_argv", "status", "tree_digest"):
            del rec[k]
        r = self.reasons(rec)
        self.assertTrue(r and all("SCHEMA" in x for x in r[:1]), r)

    def test_wrong_recorder_const_fails_schema(self):
        r = self.reasons(self.record(recorder="my-own-tool/v9"))
        self.assertTrue(any("SCHEMA" in x for x in r), r)

    def test_short_commit_fails_schema(self):
        r = self.reasons(self.record(commit=self.head[:12]))
        self.assertTrue(any("SCHEMA" in x for x in r), r)

    def test_wrong_commit_rejected_exact_head(self):
        r = self.reasons(self.record(commit="c" * 40))
        self.assertTrue(any("derived HEAD" in x for x in r), r)

    def test_tree_digest_mismatch_rejected(self):
        r = self.reasons(self.record(tree_digest="d" * 64))
        self.assertTrue(any("TREE MISMATCH" in x for x in r), r)

    def test_command_policy_revalidated(self):
        rec = self.record(command_argv=["echo", "ok"])
        rec["command"] = "echo ok"
        rec["command_id"] = "echo"
        r = self.reasons(rec)
        self.assertTrue(any("COMMAND POLICY" in x for x in r), r)

    def test_git_noop_argv_rejected_at_check_time(self):
        rec = self.record(command_argv=["git", "ls-files"])
        rec["command"] = "git ls-files"
        rec["command_id"] = "git ls-files"
        r = self.reasons(rec)
        self.assertTrue(any("COMMAND POLICY" in x for x in r), r)

    def test_command_id_mismatch_rejected(self):
        rec = self.record()
        rec["command_id"] = "some-other-id"
        r = self.reasons(rec)
        self.assertTrue(any("COMMAND ID MISMATCH" in x for x in r), r)

    def test_command_display_mismatch_rejected(self):
        rec = self.record()
        rec["command"] = "prettified display string"
        r = self.reasons(rec)
        self.assertTrue(any("COMMAND DISPLAY MISMATCH" in x for x in r), r)

    def test_missing_command_id_fails_schema(self):
        rec = self.record()
        del rec["command_id"]
        r = self.reasons(rec)
        self.assertTrue(any("SCHEMA" in x for x in r), r)

    def test_failed_command_rejected(self):
        r = self.reasons(self.record(exit_code=1))
        self.assertTrue(any("FAILED" in x for x in r), r)

    def test_wrong_environment_project_expired_old(self):
        self.assertTrue(any("environment" in x for x in self.reasons(
            self.record(environment="staging"))))
        self.assertTrue(any("WRONG PROJECT" in x for x in self.reasons(
            self.record(project="other"))))
        self.assertTrue(any("expired" in x for x in self.reasons(
            self.record(expires=EXPIRED))))
        self.assertTrue(any("days old" in x for x in self.reasons(
            self.record(timestamp=OLD_TIMESTAMP,
                        expires=OLD_EXPIRES))))

    def test_empty_reviewer_rejected(self):
        r = self.reasons(self.record(reviewer="  "))
        self.assertTrue(any("SCHEMA" in x or "reviewer" in x for x in r), r)

    def test_artifact_verification(self):
        r = self.reasons(self.record(artifact_sha256="f" * 64))
        self.assertTrue(any("DIGEST MISMATCH" in x for x in r), r)
        r = self.reasons(self.record(artifact=".solo/nope.md"))
        self.assertTrue(any("missing" in x for x in r), r)
        r = self.reasons(self.record(artifact="../../etc/passwd"))
        self.assertTrue(any("OUTSIDE" in x for x in r), r)

    def test_unknown_properties_fail_schema(self):
        r = self.reasons(self.record(banana=1))
        self.assertTrue(any("SCHEMA" in x for x in r), r)

    def test_checker_valid_records_validate_with_jsonschema_too(self):
        if jsonschema is None:
            self.skipTest("jsonschema not installed; builtin evaluator is "
                          "the always-on path and is covered everywhere")
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        rec = self.record()
        self.assertEqual(self.reasons(rec), [])
        jsonschema.validate(rec, schema)
        na = self.na_record("seo")
        self.assertEqual(self.reasons(na, profile="api-service"), [])
        jsonschema.validate(na, schema)


class ExecutableIdentityRules(Fixture):
    """v1.0.16: the checker re-derives the executable identity and rejects
    swapped, project-local, unresolvable, or missing identities."""

    def test_missing_resolved_executable_fails_schema(self):
        rec = self.record()
        del rec["resolved_executable"]
        r = self.reasons(rec)
        self.assertTrue(any("SCHEMA" in x for x in r), r)

    def test_identity_mismatch_rejected(self):
        other = xf.make_exe(tempfile.mkdtemp(prefix="other-"), "swapped")
        rec = self.record(resolved_executable=other)
        r = self.reasons(rec)
        self.assertTrue(any("EXECUTABLE IDENTITY MISMATCH" in x
                            for x in r), r)

    def test_relative_recorded_identity_rejected(self):
        rec = self.record(resolved_executable="python3")
        r = self.reasons(rec)
        self.assertTrue(any("EXECUTABLE IDENTITY" in x for x in r), r)

    def test_argv0_that_no_longer_resolves_rejected(self):
        rec = self.record(
            command_argv=["alembic", "check"], category="database",
            command="alembic check")
        rec["command_id"] = "alembic check"
        # remove alembic from PATH: identity re-derivation must fail closed
        os.environ["PATH"] = self._oldpath
        try:
            if shutil.which("alembic"):   # pragma: no cover - dev machines
                self.skipTest("a real alembic exists on the base PATH")
            r = self.reasons(rec)
        finally:
            os.environ["PATH"] = self.extbin + os.pathsep + self._oldpath
        self.assertTrue(any("EXECUTABLE IDENTITY" in x
                            or "COMMAND POLICY" in x for x in r), r)

    def test_project_local_argv0_rejected_at_check_time(self):
        projbin = xf.make_bin_dir(self.root, names=("alembic",))
        os.environ["PATH"] = projbin + os.pathsep + self.extbin \
            + os.pathsep + self._oldpath
        try:
            rec = self.record(
                command_argv=["alembic", "check"], category="database",
                command="alembic check",
                command_id="alembic check",
                resolved_executable=os.path.join(projbin, "alembic"))
            r = self.reasons(rec)
        finally:
            os.environ["PATH"] = self.extbin + os.pathsep + self._oldpath
        self.assertTrue(any("INSIDE the project root" in x for x in r), r)


class NaRules(Fixture):
    def test_valid_na_accepted(self):
        self.assertEqual(self.reasons(self.na_record("seo"),
                                      profile="api-service"), [])

    def test_mandatory_never_na(self):
        for cat in sorted(ce.MANDATORY):
            r = self.reasons(self.na_record(cat), profile="api-service")
            self.assertTrue(any("MANDATORY" in x or "SCHEMA" in x
                                for x in r), (cat, r))

    def test_matrix_violation_rejected(self):
        r = self.reasons(self.na_record("design",
                                        profile="saas-application"),
                         profile="saas-application")
        self.assertTrue(any("does not permit" in x for x in r), r)

    def test_one_char_reason_and_empty_reviewer_fail(self):
        r = self.reasons(self.na_record("seo", reason="x"))
        self.assertTrue(any("SCHEMA" in x or "substantive" in x
                            for x in r), r)
        r = self.reasons(self.na_record("seo", reviewer=""))
        self.assertTrue(any("SCHEMA" in x or "reviewer" in x for x in r), r)

    def test_structured_applicability_required(self):
        rec = self.na_record("seo")
        del rec["applicability"]
        r = self.reasons(rec)
        self.assertTrue(any("SCHEMA" in x for x in r), r)

    def test_profile_source_must_be_canonical_committed_path(self):
        rec = self.na_record("seo")
        rec["applicability"]["profile_source"] = "docs/profile.md"
        r = self.reasons(rec, profile="api-service")
        self.assertTrue(any("SCHEMA" in x or "canonical" in x
                            for x in r), r)

    def test_na_check_requires_derived_profile_binding(self):
        r = self.reasons(self.na_record("seo"), profile=None)
        self.assertTrue(any("profile binding" in x for x in r), r)

    def test_na_commit_must_equal_head(self):
        r = self.reasons(self.na_record("seo", commit="d" * 40))
        self.assertTrue(any("derived HEAD" in x for x in r), r)

    def test_na_without_required_recorder_fails_schema(self):
        """The N/A branch requires its recorder format label; this rejects
        missing/wrong values but does not prove which process wrote JSON."""
        rec = self.na_record("seo")
        del rec["recorder"]
        r = self.reasons(rec, profile="api-service")
        self.assertTrue(any("SCHEMA" in x and "recorder" in x
                            for x in r), r)
        rec = self.na_record("seo", recorder="my-own-tool/v9")
        r = self.reasons(rec, profile="api-service")
        self.assertTrue(any("SCHEMA" in x for x in r), r)


class CliCompleteness(Fixture):
    ARGV = {   # policy-conformant argv per verified category (v1.0.17:
        # deployment/monitoring are ENDPOINT-bound — never verify-artifact,
        # never a generic homepage curl)
        "product": [PYTOK, GP, "verify-artifact", "product"],
        "architecture": [PYTOK, GP, "verify-artifact", "architecture"],
        "backend": [PYTOK, "-m", "unittest", "discover"],
        "database": ["alembic", "check"],
        "security": [PYTOK, SCANNER_INSTALLED, "."],
        "testing": [PYTOK, "-m", "unittest", "discover"],
        "performance": ["npx", "--no-install", "@lhci/cli", "autorun"],
        "deployment": ["curl", "-sSf", "-m", "10",
                       "https://x.example/version"],
        "monitoring": ["curl", "-sSf", "-m", "10",
                       "https://x.example/health"],
        "documentation": [PYTOK, GP, "verify-artifact",
                          "documentation"],
    }

    def bound_artifact(self, category):
        """Write a binding-satisfying captured output for the endpoint
        commands (the checker re-applies the output binding from the
        hashed artifact bytes). Lives under .solo/gate-evidence/ so the
        repo stays clean."""
        content = {"deployment": "deployed commit: %s\n" % self.head,
                   "monitoring": '{"status": "ok"}\n'}[category]
        rel = ".solo/gate-evidence/artifacts/%s.log" % category
        full = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        with open(full, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        return rel, digest

    def full_set(self, profile="api-service"):
        cats_na = {"seo", "analytics", "design", "frontend"}
        for cat in sorted(ce.CATEGORIES - cats_na):
            argv = self.ARGV[cat]
            over = {"category": cat, "command_argv": argv}
            if cat in ("deployment", "monitoring"):
                rel, digest = self.bound_artifact(cat)
                over["artifact"] = rel
                over["artifact_sha256"] = digest
            self.write(cat + ".json", self.record(**over))
        for cat in sorted(cats_na):
            self.write(cat + ".json", self.na_record(cat, profile=profile))

    def test_complete_set_passes(self):
        self.full_set()
        r = self.run_cli(profile="api-service")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("10 verified + 4 N/A = 14/14", r.stdout)
        self.assertIn("verifies category records only", r.stdout)
        self.assertIn("accessibility-core-flows", r.stdout)
        self.assertIn("transactional-email", r.stdout)

    def test_json_result_exposes_machine_scope_and_required_controls(self):
        expected = {
            "accessibility-core-flows", "authentication", "backup-restore",
            "committed-secrets", "error-tracking", "mobile-core-flows",
            "payments", "rls-authorization", "rollback",
            "transactional-email",
        }
        self.assertEqual(set(gp.REVIEWER_REQUIRED_CONTROLS), expected)
        self.full_set()
        r = self.run_cli("--json", profile="api-service")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        payload = json.loads(r.stdout)
        self.assertTrue(payload["complete"])
        self.assertEqual(set(payload["reviewer_required_controls"]), expected)
        self.assertIn("necessary but not sufficient", payload["scope"])

    def test_checker_cli_requires_profile_even_for_complete_set(self):
        self.full_set()
        r = self.run_cli()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--profile", r.stderr)

    def test_checker_cli_rejects_caller_controlled_clock(self):
        self.full_set()
        r = self.run_cli("--now", NOW, profile="api-service")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("unrecognized arguments: --now", r.stderr)

    def test_checker_cannot_loosen_freshness_beyond_seven_days(self):
        self.full_set()
        r = self.run_cli("--max-age-days", "8", profile="api-service")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("between 1 and 7", r.stderr)

    def test_tracking_probe_failure_cannot_pass_as_untracked(self):
        """None is the tracking probe's fail-closed sentinel, not False."""
        self.full_set()
        argv = [self.ev, "--root", self.root,
                "--environment", "production", "--project", "demo",
                "--profile", "api-service"]
        out = io.StringIO()
        with mock.patch.object(ce.gp, "evidence_tracked_in_head",
                               return_value=None), \
                contextlib.redirect_stdout(out):
            rc = ce.main(argv, _test_now=self.now)
        self.assertEqual(rc, 1, out.getvalue())
        self.assertIn("tracking check FAILED", out.getvalue())

    def test_missing_category_fails(self):
        self.full_set()
        os.remove(os.path.join(self.ev, "testing.json"))
        self.assertEqual(self.run_cli(profile="api-service").returncode, 1)

    def test_duplicate_category_fails(self):
        self.full_set()
        self.write("security-2.json", self.record(category="security"))
        self.assertEqual(self.run_cli(profile="api-service").returncode, 1)

    def test_all_14_na_fails_for_every_profile(self):
        for prof in sorted(ce.RECOGNIZED_PROFILES):
            for name in os.listdir(self.ev):
                os.remove(os.path.join(self.ev, name))
            self.commit_profile(prof)
            for cat in sorted(ce.CATEGORIES):
                self.write(cat + ".json", self.na_record(cat, profile=prof))
            r = self.run_cli(profile=prof)
            self.assertEqual(r.returncode, 1,
                             (prof, r.stdout, r.stderr))

    def test_D_commit_flag_must_equal_derived_head(self):
        self.full_set()
        ok = self.run_cli("--commit", self.head, profile="api-service")
        self.assertEqual(ok.returncode, 0, ok.stdout)
        bad = self.run_cli("--commit", "a" * 40, profile="api-service")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("never trusted", bad.stdout)

    def test_non_git_root_is_usage_error(self):
        plain = tempfile.mkdtemp(prefix="plain-")
        self.addCleanup(shutil.rmtree, plain, ignore_errors=True)
        r = subprocess.run(
            [sys.executable, CE, self.ev, "--root", plain,
             "--environment", "production", "--project", "demo"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 2)

    def test_unbound_endpoint_artifacts_rejected(self):
        """A deployment record whose captured version-endpoint response
        does not name the derived HEAD — or a monitoring record whose
        response is a generic page — fails the output-binding re-check."""
        self.full_set()
        for cat, body, needle in (
                ("deployment", "deployed commit: %s\n" % ("b" * 40),
                 "OUTPUT BINDING"),
                ("monitoring", "<html><h1>ok</h1></html>\n",
                 "OUTPUT BINDING")):
            rel = ".solo/gate-evidence/artifacts/%s.log" % cat
            full = os.path.join(self.root, *rel.split("/"))
            with open(full, "w", encoding="utf-8") as f:
                f.write(body)
            with open(full, "rb") as f:
                digest = hashlib.sha256(f.read()).hexdigest()
            self.write(cat + ".json", self.record(
                category=cat, command_argv=self.ARGV[cat],
                artifact=rel, artifact_sha256=digest))
            r = self.run_cli(profile="api-service")
            self.assertEqual(r.returncode, 1, (cat, r.stdout))
            self.assertIn(needle, r.stdout, cat)
            # restore the bound artifact for the next loop iteration
            rel2, digest2 = self.bound_artifact(cat)
            self.write(cat + ".json", self.record(
                category=cat, command_argv=self.ARGV[cat],
                artifact=rel2, artifact_sha256=digest2))
        self.assertEqual(self.run_cli(profile="api-service").returncode, 0)

    def test_categories_and_matrix_reexported(self):
        self.assertEqual(len(ce.CATEGORIES), 14)
        self.assertEqual(ce.NA_ALLOWED, gp.NA_ALLOWED)
        self.assertEqual(ce.MANDATORY, gp.MANDATORY)


if __name__ == "__main__":
    unittest.main()
