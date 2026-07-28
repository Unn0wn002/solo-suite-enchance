"""record_evidence.py: evidence records come from REAL execution of
POLICY-VALIDATED commands — no git no-ops, no --allow-dirty, source
identity derived from git objects, single untracked-evidence workflow.
Adversarial acceptance tests D, E, F, G live here (A/B in
test_gate_policy.py; H in test_evidence_lifecycle.py)."""
import importlib.util
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import shutil
import time
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "plugins", "gate", "skills",
                       "production-readiness-reviewer", "scripts")
RE_PY = os.path.join(SCRIPTS, "record_evidence.py")
CE_PY = os.path.join(SCRIPTS, "check_evidence.py")
GP_PY = os.path.join(REPO, "plugins", "gate", "lib", "gate_policy.py")

gspec = importlib.util.spec_from_file_location("gp_re", GP_PY)
gp = importlib.util.module_from_spec(gspec)
gspec.loader.exec_module(gp)
rspec = importlib.util.spec_from_file_location("record_evidence_test", RE_PY)
record_module = importlib.util.module_from_spec(rspec)
rspec.loader.exec_module(record_module)
xfspec = importlib.util.spec_from_file_location(
    "exe_fixtures_re",
    os.path.join(REPO, "tests", "exe_fixtures.py"))
xf = importlib.util.module_from_spec(xfspec)
xfspec.loader.exec_module(xf)


def git(cwd, *args):
    return subprocess.run(["git"] + list(args), cwd=cwd,
                          capture_output=True, text=True, timeout=30)


def run_re(root, category="testing", reviewer="qa seat", *cmd):
    base = [sys.executable, RE_PY, "--category", category,
            "--project", "demo", "--environment", "production",
            "--root", root, "--reviewer", reviewer]
    network = category in {"deployment", "monitoring"} or any(
        str(t).startswith(("http://", "https://")) for t in cmd)
    if network:
        base.append("--allow-network")
    preview = subprocess.run(base + ["--preview", "--"] + list(cmd),
                             capture_output=True, text=True, timeout=120)
    if preview.returncode != 0:
        return preview
    match = re.search(r"preview token: ([0-9a-f]{64})", preview.stdout)
    if not match:
        return preview
    return subprocess.run(base + ["--confirm-execution", match.group(1),
                                  "--"] + list(cmd),
                          capture_output=True, text=True, timeout=120)


def run_ce(root, *extra):
    argv = [sys.executable, CE_PY,
            os.path.join(root, ".solo", "gate-evidence"),
            "--root", root, "--environment", "production",
            "--project", "demo", "--profile", "api-service"] + list(extra)
    return subprocess.run(argv, capture_output=True, text=True, timeout=120)


class RecordEvidence(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="record-evidence-")
        self.addCleanup(xf.force_rmtree, self.root)
        git(self.root, "init", "-q", ".")
        git(self.root, "config", "user.email", "t@example.invalid")
        git(self.root, "config", "user.name", "t")
        with open(os.path.join(self.root, "test_x.py"), "w",
                  encoding="utf-8") as f:
            f.write("import unittest\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_ok(self):\n        pass\n")
        with open(os.path.join(self.root, ".gitignore"), "w",
                  encoding="utf-8") as f:
            f.write(".solo/gate-evidence/\n__pycache__/\n*.pyc\n")
        os.makedirs(os.path.join(self.root, ".solo"), exist_ok=True)
        with open(os.path.join(self.root, ".solo", "project.md"), "w",
                  encoding="utf-8") as f:
            f.write("# Project\n\nProject profile: api-service\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")
        self.head = git(self.root, "rev-parse", "HEAD").stdout.strip()

    def record_path(self, cat="testing"):
        return os.path.join(self.root, ".solo", "gate-evidence",
                            "%s.json" % cat)

    def load_record(self, cat="testing"):
        with open(self.record_path(cat), encoding="utf-8") as f:
            return json.load(f)

    # ---- policy refusals (full argv, shared module) -------------------------
    def test_git_noop_refused_and_writes_nothing(self):
        r = run_re(self.root, "testing", "qa",
                   "git", "ls-files", "--error-unmatch", "test_x.py")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("REFUSED", r.stdout)
        self.assertFalse(os.path.exists(self.record_path()))

    def test_echo_refused(self):
        r = run_re(self.root, "testing", "qa", "echo", "ok")
        self.assertEqual(r.returncode, 2)

    def test_allow_dirty_flag_no_longer_exists(self):
        argv = [sys.executable, RE_PY, "--category", "testing",
                "--project", "demo", "--environment", "production",
                "--root", self.root, "--reviewer", "qa", "--allow-dirty",
                "--", "python3", "-m", "unittest", "discover"]
        r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 2, "argparse must reject the "
                         "removed --allow-dirty flag")

    def test_expiry_window_cannot_exceed_gate_policy(self):
        argv = [sys.executable, RE_PY, "--category", "testing",
                "--project", "demo", "--environment", "production",
                "--root", self.root, "--reviewer", "qa",
                "--expires-days", "8", "--preview", "--",
                sys.executable, "-m", "unittest", "discover"]
        r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("between 1 and 7", r.stderr)

    def test_execution_is_manual_preview_then_bound_confirmation(self):
        base = [sys.executable, RE_PY, "--category", "testing",
                "--project", "demo", "--environment", "production",
                "--root", self.root, "--reviewer", "qa"]
        cmd = ["--", sys.executable, "-m", "unittest", "discover"]
        unconfirmed = subprocess.run(base + cmd, capture_output=True,
                                     text=True, timeout=60)
        self.assertEqual(unconfirmed.returncode, 2, unconfirmed.stdout)
        self.assertIn("manual-only", unconfirmed.stdout)
        preview = subprocess.run(base + ["--preview"] + cmd,
                                 capture_output=True, text=True, timeout=60)
        self.assertEqual(preview.returncode, 0, preview.stdout)
        token = re.search(r"preview token: ([0-9a-f]{64})", preview.stdout)
        self.assertIsNotNone(token)
        self.assertFalse(os.path.exists(self.record_path()),
                         "preview must execute/write nothing")
        confirmed = subprocess.run(
            base + ["--confirm-execution", token.group(1)] + cmd,
            capture_output=True, text=True, timeout=120)
        self.assertEqual(confirmed.returncode, 0,
                         confirmed.stdout + confirmed.stderr)
        self.assertTrue(os.path.isfile(self.record_path()))

    def test_ambient_secret_environment_is_not_inherited(self):
        name = "SOLO_SUITE_TEST_AMBIENT_SECRET"
        os.environ[name] = "must-not-reach-child"
        self.addCleanup(os.environ.pop, name, None)
        with open(os.path.join(self.root, "test_x.py"), "w") as f:
            f.write("import os, unittest\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_env(self):\n"
                    "        self.assertNotIn(%r, os.environ)\n" % name)
        git(self.root, "add", "test_x.py")
        git(self.root, "commit", "-qm", "environment test")
        r = run_re(self.root, "testing", "qa", sys.executable, "-m",
                   "unittest", "discover")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_captured_secret_like_output_is_redacted(self):
        value = "super" + "secret-output"
        with open(os.path.join(self.root, "test_x.py"), "w") as f:
            f.write("import unittest\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_output(self):\n"
                    "        value = 'super' + 'secret-output'\n"
                    "        print('password=' + value)\n")
        git(self.root, "add", "test_x.py")
        git(self.root, "commit", "-qm", "redaction test")
        r = run_re(self.root, "testing", "qa", sys.executable, "-m",
                   "unittest", "discover")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        artifact = os.path.join(self.root, ".solo", "gate-evidence",
                                "artifacts", "testing.log")
        with open(artifact, encoding="utf-8") as f:
            captured = f.read()
        self.assertNotIn(value, captured)
        self.assertIn("password=[REDACTED]", captured)

    def test_explicit_config_reference_is_redacted_from_capture(self):
        profile = (r"C:\Users\Example\AppData\gh-profile" if
                   os.name == "nt" else "/home/example/.config/gh")
        variants = [profile, profile.replace("\\", "/"),
                    json.dumps(profile)[1:-1]]
        if os.name == "nt":
            variants.append(profile.lower())
        captured = record_module._redact_capture(
            ("\n".join(variants)).encode("utf-8"), (profile,)
        ).decode("utf-8")
        self.assertNotIn("gh-profile", captured.lower())
        self.assertNotIn(".config/gh", captured.lower())
        self.assertIn("[REDACTED-CONFIG-DIR]", captured)

    def test_stream_capture_is_bounded_while_pipe_is_drained(self):
        env = record_module._child_environment(
            self.root, tempfile.mkdtemp(prefix="record-home-"), False)
        (rc, out, err, out_cut, err_cut, timed_out, cleanup_ok,
         cleanup_reason) = \
            record_module._run_bounded(
                [sys.executable, "-c", "print('x' * 20000)"], self.root,
                env, 30, 4096)
        self.assertEqual(rc, 0)
        self.assertEqual(len(out), 4096)
        self.assertTrue(out_cut)
        self.assertFalse(err_cut)
        self.assertFalse(timed_out)
        self.assertTrue(cleanup_ok, cleanup_reason)

    def test_timeout_terminates_descendant_tree_and_drains_capture(self):
        """A timed-out parent and its pipe-inheriting child both die.

        This is deliberately a real descendant regression, not a mocked
        terminate() assertion: the child PID is written outside the checkout,
        and cleanup succeeds only after the process container is empty and
        both capture readers have observed EOF.
        """
        outside = tempfile.mkdtemp(prefix="record-descendant-")
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        pid_file = os.path.join(outside, "child.pid")
        child = "import time; time.sleep(60)"
        parent = ("import subprocess,sys,time; "
                  "p=subprocess.Popen([sys.executable,'-c',%r]); "
                  "open(%r,'w').write(str(p.pid)); time.sleep(60)"
                  % (child, pid_file))
        home = tempfile.mkdtemp(prefix="record-tree-home-")
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        env = record_module._child_environment(self.root, home, False)
        (rc, _out, _err, _out_cut, _err_cut, timed_out, cleanup_ok,
         cleanup_reason) = record_module._run_bounded(
             [sys.executable, "-c", parent], self.root, env, 3, 4096)
        self.assertEqual(rc, 124)
        self.assertTrue(timed_out)
        self.assertTrue(cleanup_ok, cleanup_reason)
        self.assertTrue(os.path.isfile(pid_file),
                        "parent must have created the real descendant")
        with open(pid_file, encoding="ascii") as f:
            child_pid = int(f.read())
        deadline = time.monotonic() + 3
        while True:
            try:
                os.kill(child_pid, 0)
                alive = True
            except OSError:
                alive = False
            if not alive or time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        self.assertFalse(alive, "timed-out descendant survived containment")

    def test_cleanup_failure_refuses_record_write(self):
        base = ["--category", "testing", "--project", "demo",
                "--environment", "production", "--root", self.root,
                "--reviewer", "qa", "--", sys.executable, "-m",
                "unittest", "discover"]
        preview_out = io.StringIO()
        with contextlib.redirect_stdout(preview_out):
            self.assertEqual(record_module.main(base[:10] + ["--preview"] +
                                                base[10:]), 0)
        token = re.search(r"preview token: ([0-9a-f]{64})",
                          preview_out.getvalue()).group(1)
        confirmed = base[:10] + ["--confirm-execution", token] + base[10:]
        unsafe = (0, b"", b"", False, False, False, False,
                  "simulated surviving reader")
        with mock.patch.object(record_module, "_run_bounded",
                               return_value=unsafe):
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                rc = record_module.main(confirmed)
        self.assertEqual(rc, 2)
        self.assertIn("cleanup failed", capture.getvalue())
        self.assertFalse(os.path.exists(self.record_path()))

    # ---- real execution ------------------------------------------------------
    def test_success_records_and_checker_accepts(self):
        r = run_re(self.root, "testing", "qa seat",
                   sys.executable, "-m", "unittest", "discover")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.load_record()
        self.assertEqual(rec["exit_code"], 0)
        self.assertEqual(rec["status"], "verified")
        self.assertEqual(rec["recorder"], "record_evidence.py/v1")
        self.assertEqual(rec["commit"], self.head)
        self.assertEqual(rec["tree_digest"],
                         gp.committed_tree_digest(self.root))
        out = run_ce(self.root)
        self.assertIn("PASS", out.stdout)
        self.assertIn("1 verified", out.stdout)

    def test_failing_command_records_real_nonzero(self):
        with open(os.path.join(self.root, "test_x.py"), "w") as f:
            f.write("import unittest\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_no(self):\n        self.fail('x')\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "failing test")
        r = run_re(self.root, "testing", "qa",
                   sys.executable, "-m", "unittest", "discover")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotEqual(self.load_record()["exit_code"], 0)
        out = run_ce(self.root)
        self.assertIn("FAILED", out.stdout)
        self.assertEqual(out.returncode, 1)

    # ---- D: caller-provided fake commit vs derived HEAD --------------------
    def test_D_fake_commit_fails_against_real_head(self):
        run_re(self.root, "testing", "qa",
               sys.executable, "-m", "unittest", "discover")
        r = run_ce(self.root, "--commit", "a" * 40)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("never trusted", r.stdout)
        # tampering with the record's commit field also fails (exact HEAD)
        rec = self.load_record()
        rec["commit"] = "a" * 40
        with open(self.record_path(), "w", encoding="utf-8") as f:
            json.dump(rec, f)
        r = run_ce(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("derived HEAD", r.stdout)

    # ---- E: dirty tracked files ---------------------------------------------
    def test_E_dirty_tracked_file_refused_and_fails_checker(self):
        run_re(self.root, "testing", "qa",
               sys.executable, "-m", "unittest", "discover")
        with open(os.path.join(self.root, "test_x.py"), "a") as f:
            f.write("# drift\n")
        r = run_re(self.root, "testing", "qa",
                   sys.executable, "-m", "unittest", "discover")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no --allow-dirty", r.stdout)
        c = run_ce(self.root)
        self.assertEqual(c.returncode, 1)
        self.assertIn("no longer matches HEAD", c.stdout)

    def test_E_deleted_tracked_file_refused(self):
        os.remove(os.path.join(self.root, "test_x.py"))
        r = run_re(self.root, "documentation", "docs",
                   sys.executable, GP_PY, "verify-artifact", "documentation")
        self.assertEqual(r.returncode, 2, r.stdout)

    # ---- F: new untracked source/config outside gate-evidence --------------
    def test_F_untracked_file_outside_evidence_refused(self):
        with open(os.path.join(self.root, "new-config.env"), "w") as f:
            f.write("SECRET=x\n")
        r = run_re(self.root, "testing", "qa",
                   sys.executable, "-m", "unittest", "discover")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("untracked", r.stdout)
        os.remove(os.path.join(self.root, "new-config.env"))
        c = run_ce(self.root)   # empty evidence dir + clean tree
        self.assertEqual(c.returncode, 1)  # missing categories, but no crash

    def test_F_evidence_dir_files_never_count_as_dirt(self):
        r1 = run_re(self.root, "testing", "qa",
                    sys.executable, "-m", "unittest", "discover")
        self.assertEqual(r1.returncode, 0, r1.stdout)
        r2 = run_re(self.root, "testing", "qa",
                    sys.executable, "-m", "unittest", "discover")
        self.assertEqual(r2.returncode, 0,
                         "evidence artifacts from run 1 blocked run 2:\n"
                         + r2.stdout)

    # ---- G: committing evidence is an unsupported, refused state -----------
    def test_G_tracked_evidence_refused_by_recorder_and_checker(self):
        run_re(self.root, "testing", "qa",
               sys.executable, "-m", "unittest", "discover")
        git(self.root, "add", "-f", self.record_path())
        git(self.root, "commit", "-qm", "track evidence (unsupported)")
        r = run_re(self.root, "testing", "qa",
                   sys.executable, "-m", "unittest", "discover")
        self.assertEqual(r.returncode, 2)
        self.assertIn("TRACKED in HEAD", r.stdout)
        c = run_ce(self.root)
        self.assertEqual(c.returncode, 1)
        self.assertIn("TRACKED in HEAD", c.stdout)
        self.assertIn("unsupported", c.stdout)

    # ---- misc ---------------------------------------------------------------
    def test_not_a_git_repo_refused(self):
        plain = tempfile.mkdtemp(prefix="not-a-repo-")
        self.addCleanup(shutil.rmtree, plain, ignore_errors=True)
        r = run_re(plain, "testing", "qa",
                   sys.executable, "-m", "unittest", "discover")
        self.assertEqual(r.returncode, 2)

    def test_empty_reviewer_refused(self):
        r = run_re(self.root, "testing", "   ",
                   sys.executable, "-m", "unittest", "discover")
        self.assertEqual(r.returncode, 2)

    def test_no_temp_leftovers(self):
        run_re(self.root, "testing", "qa",
               sys.executable, "-m", "unittest", "discover")
        ev = os.path.join(self.root, ".solo", "gate-evidence")
        stray = [n for n in os.listdir(ev) if ".tmp." in n]
        self.assertEqual(stray, [])

    def test_produced_record_passes_bundled_schema(self):
        run_re(self.root, "testing", "qa",
               sys.executable, "-m", "unittest", "discover")
        self.assertEqual(gp.schema_validate(self.load_record()), [])

    # ---- v1.0.16: canonical executable identity is RECORDED ----------------
    def test_resolved_executable_recorded_and_checker_revalidates(self):
        r = run_re(self.root, "testing", "qa",
                   sys.executable, "-m", "unittest", "discover")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.load_record()
        self.assertTrue(os.path.isabs(rec["resolved_executable"]), rec)
        self.assertEqual(rec["resolved_executable"],
                         os.path.realpath(sys.executable))
        self.assertEqual(run_ce(self.root).returncode, 1)  # 13 missing cats
        # tamper the identity -> the checker rejects the record
        rec["resolved_executable"] = os.path.realpath(
            xf.make_exe(tempfile.mkdtemp(prefix="swap-"), "swapped"))
        with open(self.record_path(), "w", encoding="utf-8") as f:
            json.dump(rec, f)
        out = run_ce(self.root)
        self.assertIn("EXECUTABLE IDENTITY MISMATCH", out.stdout)

    def test_unresolvable_command_refused_before_execution(self):
        r = run_re(self.root, "database", "dba",
                   "definitely-not-a-real-tool-xyz", "check")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertFalse(os.path.exists(self.record_path("database")))


class SafePathsAndFailClosedV1015(RecordEvidence):
    """v1.0.15: output-path containment, staged-rename dirt, ignored-file
    policy, git fail-closed, and the post-execution repository re-check."""

    def test_out_and_artifact_escapes_refused(self):
        base = [sys.executable, "-m", "unittest", "discover"]
        for flag, value in (
                ("--out", "/tmp/evil-record.json"),
                ("--out", ".solo/gate-evidence/../../evil.json"),
                ("--out", "test_x.py"),
                ("--artifact", "/tmp/evil.log"),
                ("--artifact", ".solo/gate-evidence/../../../evil.log"),
                ("--artifact", "test_x.py")):
            argv = [sys.executable, RE_PY, "--category", "testing",
                    "--project", "demo", "--environment", "production",
                    "--root", self.root, "--reviewer", "qa",
                    flag, value, "--"] + base
            r = subprocess.run(argv, capture_output=True, text=True,
                               timeout=60)
            self.assertEqual(r.returncode, 2, (flag, value, r.stdout))
            self.assertIn("REFUSED", r.stdout)
            self.assertFalse(os.path.exists("/tmp/evil-record.json"))
            self.assertFalse(os.path.exists("/tmp/evil.log"))

    def test_symlink_escape_refused(self):
        if not hasattr(os, "symlink"):
            self.skipTest("platform without symlink support")
        outside = tempfile.mkdtemp(prefix="leak-target-")
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        ev = os.path.join(self.root, ".solo", "gate-evidence")
        os.makedirs(ev, exist_ok=True)
        link = os.path.join(ev, "leak")
        try:
            os.symlink(outside, link)
        except OSError:
            self.skipTest("environment refuses symlink creation")
        self.addCleanup(lambda: os.path.islink(link) and os.remove(link))
        r = subprocess.run(
            [sys.executable, RE_PY, "--category", "testing",
             "--project", "demo", "--environment", "production",
             "--root", self.root, "--reviewer", "qa",
             "--artifact", ".solo/gate-evidence/leak/x.log", "--",
             sys.executable, "-m", "unittest", "discover"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertEqual(os.listdir(outside), [],
                         "nothing may be written through the symlink")

    def test_staged_rename_into_evidence_refused(self):
        os.makedirs(os.path.join(self.root, ".solo", "gate-evidence"),
                    exist_ok=True)
        git(self.root, "mv", "test_x.py",
            ".solo/gate-evidence/test_x.py")
        r = run_re(self.root, "documentation", "docs",
                   sys.executable, GP_PY, "verify-artifact",
                   "documentation")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("not clean", r.stdout)

    def test_ignored_files_exempt_per_documented_policy(self):
        with open(os.path.join(self.root, ".gitignore"), "a") as f:
            f.write("production.env\n")
        git(self.root, "add", ".gitignore")
        git(self.root, "commit", "-qm", "ignore production.env")
        with open(os.path.join(self.root, "production.env"), "w") as f:
            f.write("SECRET=x\n")
        r = run_re(self.root, "testing", "qa",
                   sys.executable, "-m", "unittest", "discover")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_git_failure_refuses_never_clean(self):
        with open(os.path.join(self.root, ".git", "HEAD"), "w") as f:
            f.write("garbage not a ref\n")
        r = run_re(self.root, "testing", "qa",
                   sys.executable, "-m", "unittest", "discover")
        self.assertEqual(r.returncode, 2, r.stdout)
        c = run_ce(self.root)
        self.assertEqual(c.returncode, 2, c.stdout)

    def test_command_that_mutates_repo_is_refused_post_execution(self):
        """The post-execution re-check: a 'test suite' that edits a tracked
        file produces NO record."""
        with open(os.path.join(self.root, "test_x.py"), "w") as f:
            f.write("import unittest, pathlib\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_mutate(self):\n"
                    "        p = pathlib.Path('tracked-extra.txt')\n"
                    "        p.write_text('mutated by tests')\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "self-mutating test")
        r = run_re(self.root, "testing", "qa",
                   sys.executable, "-m", "unittest", "discover")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("DIRTIED", r.stdout)
        self.assertFalse(os.path.exists(self.record_path()),
                         "no record may exist after a mutating command")
        os.remove(os.path.join(self.root, "tracked-extra.txt"))

    def test_V16_evidence_dir_swapped_mid_run_refuses_record(self):
        """Regression (item 14): the evidence command itself replaces the
        (gitignored) artifacts directory with a symlink to an OUTSIDE
        directory between the initial --out/--artifact validation and the
        write. The post-execution revalidation must refuse — nothing may
        land outside <root>/.solo/gate-evidence/."""
        if not hasattr(os, "symlink"):
            self.skipTest("platform without symlink support")
        outside = tempfile.mkdtemp(prefix="swap-target-")
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        # the 'test suite' swaps .solo/gate-evidence/artifacts -> symlink
        with open(os.path.join(self.root, "test_x.py"), "w") as f:
            f.write(
                "import os, pathlib, unittest\n"
                "class T(unittest.TestCase):\n"
                "    def test_swap(self):\n"
                "        ev = pathlib.Path('.solo/gate-evidence')\n"
                "        ev.mkdir(parents=True, exist_ok=True)\n"
                "        art = ev / 'artifacts'\n"
                "        try:\n"
                "            os.symlink(%r, str(art))\n"
                "        except OSError:\n"
                "            pass\n" % outside)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "dir-swapping test")
        try:
            os.makedirs(os.path.join(self.root, ".solo"), exist_ok=True)
            probe = os.path.join(self.root, ".solo", "probe-link")
            os.symlink(outside, probe)
            os.remove(probe)
        except OSError:
            self.skipTest("environment refuses symlink creation")
        r = run_re(self.root, "testing", "qa",
                   sys.executable, "-m", "unittest", "discover")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("post-exec", r.stdout)
        self.assertEqual(os.listdir(outside), [],
                         "artifact leaked through the swapped directory")
        self.assertFalse(os.path.exists(self.record_path()))

    def test_checker_rejects_input_records_outside_evidence_dir(self):
        stray = os.path.join(self.root, "stray.json")
        with open(stray, "w") as f:
            f.write("{}")
        r = subprocess.run(
            [sys.executable, CE_PY, stray, "--root", self.root,
             "--environment", "production", "--project", "demo",
             "--profile", "api-service"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("outside", r.stdout)
        os.remove(stray)


class GhRunBindingV1016(RecordEvidence):
    """v1.0.16 (item 15): gh-run evidence is BOUND to the derived HEAD and
    a successful conclusion — recorder-side at execution and checker-side
    from the hashed artifact. Uses an inert fake gh that prints the JSON
    named by a fixture file (never the real GitHub CLI), while exercising
    gh's real GH_CONFIG_DIR auth-discovery contract."""

    def setUp(self):
        super().setUp()
        # committed stack target for the live-binding of other categories
        ext = tempfile.mkdtemp(prefix="ext-bin-")
        self.addCleanup(shutil.rmtree, ext, ignore_errors=True)
        self.extbin = xf.make_bin_dir(ext, names=("gh",))
        self._oldpath = os.environ.get("PATH", "")
        os.environ["PATH"] = self.extbin + os.pathsep + self._oldpath
        self.addCleanup(os.environ.__setitem__, "PATH", self._oldpath)
        self.outfile = os.path.join(ext, "gh-output.json")
        self.gh_config = tempfile.mkdtemp(prefix="explicit-gh-profile-")
        self.addCleanup(shutil.rmtree, self.gh_config, ignore_errors=True)
        os.chmod(self.gh_config, 0o700)
        hosts = os.path.join(self.gh_config, "hosts.yml")
        with open(hosts, "w", encoding="utf-8") as f:
            f.write("github.com:\n  oauth_token: fixture-profile-value\n")
        os.chmod(hosts, 0o600)
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_CONFIG_DIR"):
            old = os.environ.get(name)
            os.environ[name] = "ambient-value-that-must-not-be-inherited"
            if old is None:
                self.addCleanup(os.environ.pop, name, None)
            else:
                self.addCleanup(os.environ.__setitem__, name, old)
        gh_path = shutil.which("gh", path=self.extbin)
        if os.name == "nt":
            with open(gh_path, "w", encoding="ascii") as f:
                f.write('@echo off\r\n'
                        'if not defined GH_CONFIG_DIR exit /b 91\r\n'
                        'if defined GH_TOKEN exit /b 92\r\n'
                        'if defined GITHUB_TOKEN exit /b 93\r\n'
                        'if not exist "%GH_CONFIG_DIR%\\hosts.yml" '
                        'exit /b 94\r\n'
                        'findstr /c:"oauth_token:" '
                        '"%GH_CONFIG_DIR%\\hosts.yml" >nul || exit /b 95\r\n'
                        'type "%~dp0..\\gh-output.json"\r\n'
                        'exit /b 0\r\n')
        else:
            with open(gh_path, "w", encoding="ascii") as f:
                f.write('#!/bin/sh\n'
                        'test -n "${GH_CONFIG_DIR:-}" || exit 91\n'
                        'test -z "${GH_TOKEN:-}" || exit 92\n'
                        'test -z "${GITHUB_TOKEN:-}" || exit 93\n'
                        'test -f "$GH_CONFIG_DIR/hosts.yml" || exit 94\n'
                        'grep -q "oauth_token:" '
                        '"$GH_CONFIG_DIR/hosts.yml" || exit 95\n'
                        'cat "$(dirname "$0")/../gh-output.json"\n'
                        'exit 0\n')
            os.chmod(gh_path, 0o755)
        self.argv = ["gh", "run", "view", "8675309", "--exit-status",
                     "--json", "headSha,conclusion,status"]

    def gh_prints(self, obj):
        with open(self.outfile, "w", encoding="utf-8") as f:
            json.dump(obj, f)

    def run_gh(self):
        base = [sys.executable, RE_PY, "--category", "deployment",
                "--project", "demo", "--environment", "production",
                "--root", self.root, "--reviewer", "release seat",
                "--allow-network", "--gh-config-dir", self.gh_config]
        preview = subprocess.run(
            base + ["--preview", "--"] + self.argv,
            capture_output=True, text=True, timeout=120)
        if preview.returncode != 0:
            return preview
        token = re.search(r"preview token: ([0-9a-f]{64})", preview.stdout)
        if token is None:
            return preview
        return subprocess.run(
            base + ["--confirm-execution", token.group(1), "--"] + self.argv,
            capture_output=True, text=True, timeout=120)

    def test_gh_requires_explicit_external_config_profile(self):
        self.gh_prints({"headSha": self.head, "conclusion": "success",
                        "status": "completed"})
        r = run_re(self.root, "deployment", "release seat", *self.argv)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("--gh-config-dir", r.stdout)
        self.assertFalse(os.path.exists(self.record_path("deployment")))

    def test_non_gh_command_rejects_gh_config_profile(self):
        argv = [sys.executable, RE_PY, "--category", "testing",
                "--project", "demo", "--environment", "production",
                "--root", self.root, "--reviewer", "qa",
                "--gh-config-dir", self.gh_config, "--preview", "--",
                sys.executable, "-m", "unittest", "discover"]
        r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("only", r.stdout)

    def test_project_controlled_gh_profile_is_refused(self):
        local = os.path.join(self.root, ".gh-profile")
        os.makedirs(local)
        with open(os.path.join(local, "hosts.yml"), "w") as f:
            f.write("github.com:\n  oauth_token: local\n")
        base = [sys.executable, RE_PY, "--category", "deployment",
                "--project", "demo", "--environment", "production",
                "--root", self.root, "--reviewer", "release seat",
                "--allow-network", "--gh-config-dir", local, "--preview",
                "--"] + self.argv
        r = subprocess.run(base, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("outside the project", r.stdout)

    def test_bound_success_run_recorded_and_checked(self):
        self.gh_prints({"headSha": self.head, "conclusion": "success",
                        "status": "completed"})
        r = self.run_gh()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.load_record("deployment")
        self.assertEqual(rec["command_id"],
                         "gh run view --exit-status --json")
        self.assertIn("explicit external GH_CONFIG_DIR profile", r.stdout)
        self.assertNotIn(self.gh_config, r.stdout)
        artifact = os.path.join(self.root, rec["artifact"])
        with open(artifact, encoding="utf-8") as f:
            artifact_text = f.read()
        self.assertNotIn(self.gh_config, artifact_text)
        self.assertNotIn("fixture-profile-value", artifact_text)
        self.assertNotIn(self.gh_config, json.dumps(rec))
        out = run_ce(self.root)
        self.assertIn("PASS", out.stdout)

    def test_foreign_head_run_refused_by_recorder(self):
        self.gh_prints({"headSha": "b" * 40, "conclusion": "success",
                        "status": "completed"})
        r = self.run_gh()
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("output binding", r.stdout)
        self.assertFalse(os.path.exists(self.record_path("deployment")))

    def test_unsuccessful_run_refused_by_recorder(self):
        self.gh_prints({"headSha": self.head, "conclusion": "failure",
                        "status": "completed"})
        r = self.run_gh()
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("output binding", r.stdout)

    def test_old_run_cannot_prove_a_new_commit_checker_side(self):
        """A record minted at SHA1 never survives a new commit: the
        checker rejects on STALE head AND on the artifact's stale
        headSha binding."""
        self.gh_prints({"headSha": self.head, "conclusion": "success",
                        "status": "completed"})
        r = self.run_gh()
        self.assertEqual(r.returncode, 0, r.stdout)
        with open(os.path.join(self.root, "test_x.py"), "a") as f:
            f.write("# new work\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "new commit")
        out = run_ce(self.root)
        self.assertEqual(out.returncode, 1)
        self.assertIn("STALE", out.stdout)


class CanonicalNaOperation(RecordEvidence):
    """v1.0.17 (blocker 3): the supported workflow produces an N/A record
    through the recorder's canonical N/A operation. It derives the commit,
    validates the matrix cell, rejects mandatory categories, generates
    timestamps, validates against the bundled schema, and writes
    atomically. There is no flag to supply a commit, tree digest, exit code,
    or timestamp; the unsigned output remains self-attested."""

    def run_na(self, *extra, **kw):
        argv = [sys.executable, RE_PY, "--not-applicable",
                "--category", kw.get("category", "seo"),
                "--project", "demo", "--environment", "production",
                "--root", self.root, "--reviewer",
                kw.get("reviewer", "finalizer"),
                "--profile", kw.get("profile", "api-service"),
                "--reason", kw.get("reason",
                                   "API service exposes no public HTML "
                                   "pages; nothing to index"),
                "--checked", kw.get("checked",
                                    "router exposes JSON endpoints only"),
                ] + list(extra)
        return subprocess.run(argv, capture_output=True, text=True,
                              timeout=120)

    def test_mints_schema_valid_record_with_derived_identity(self):
        r = self.run_na("--run-id", "run-7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.load_record("seo")
        self.assertEqual(rec["status"], "not-applicable")
        self.assertEqual(rec["recorder"], "record_evidence.py/v1")
        self.assertEqual(rec["commit"], self.head,
                         "commit must be DERIVED from git, never supplied")
        self.assertEqual(rec["applicability"]["matrix"], "seo:api-service")
        self.assertEqual(rec["run_id"], "run-7")
        self.assertEqual(gp.schema_validate(rec), [])
        # timestamps were generated by the tool
        self.assertTrue(rec["timestamp"] and rec["expires"])
        # the record round-trips through the checker's N/A branch
        out = run_ce(self.root, "--profile", "api-service")
        self.assertIn("PASS", out.stdout)
        self.assertIn("1 N/A", out.stdout)

    def test_profile_must_match_committed_project_file(self):
        r = self.run_na(profile="library-package")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("does not match", r.stdout)
        self.assertIn("committed .solo/project.md", r.stdout)
        self.assertFalse(os.path.exists(self.record_path("seo")))

    def test_profile_source_is_canonical_not_caller_selected(self):
        r = self.run_na("--profile-source", "docs/profile.md")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("must be exactly", r.stdout)
        self.assertIn(".solo/project.md", r.stdout)
        self.assertFalse(os.path.exists(self.record_path("seo")))

    def test_mandatory_categories_are_refused(self):
        for cat in sorted(gp.MANDATORY):
            r = self.run_na(category=cat, profile="api-service")
            self.assertEqual(r.returncode, 2, (cat, r.stdout))
            self.assertIn("MANDATORY", r.stdout, cat)
            self.assertFalse(os.path.exists(self.record_path(cat)), cat)

    def test_matrix_rejected_cells_are_refused(self):
        r = self.run_na(category="design", profile="saas-application")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("matrix", r.stdout)
        self.assertFalse(os.path.exists(self.record_path("design")))

    def test_profile_reason_and_checked_are_required(self):
        argv = [sys.executable, RE_PY, "--not-applicable",
                "--category", "seo", "--project", "demo",
                "--environment", "production", "--root", self.root,
                "--reviewer", "finalizer",
                "--reason", "API service exposes no public HTML pages",
                "--checked", "router exposes JSON endpoints only"]
        r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 2, r.stdout)     # no --profile
        self.assertIn("--profile", r.stdout)
        r = self.run_na(reason="x")
        self.assertEqual(r.returncode, 2)
        self.assertIn("substantive", r.stdout)
        r = self.run_na(checked="   ")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--checked", r.stdout)

    def test_caller_supplied_identity_is_impossible(self):
        """There are NO flags for commit / tree digest / exit code /
        timestamp — argparse refuses them outright."""
        for flag in ("--commit", "--tree-digest", "--exit-code",
                     "--timestamp", "--expires"):
            r = self.run_na(flag, "a" * 40)
            self.assertEqual(r.returncode, 2,
                             "%s must be rejected (%s)" % (flag, r.stderr))
            self.assertFalse(os.path.exists(self.record_path("seo")), flag)

    def test_na_takes_no_command(self):
        r = self.run_na("--", "echo", "ok")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("no command", r.stdout)

    def test_dirty_tree_refused(self):
        with open(os.path.join(self.root, "test_x.py"), "a") as f:
            f.write("# drift\n")
        r = self.run_na()
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("not clean", r.stdout)
        self.assertFalse(os.path.exists(self.record_path("seo")))

    def test_out_path_containment(self):
        r = self.run_na("--out", "/tmp/evil-na.json")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("REFUSED", r.stdout)
        self.assertFalse(os.path.exists("/tmp/evil-na.json"))

    def test_reason_flag_requires_na_mode(self):
        r = subprocess.run(
            [sys.executable, RE_PY, "--category", "testing",
             "--project", "demo", "--environment", "production",
             "--root", self.root, "--reviewer", "qa",
             "--reason", "this only belongs to the N/A operation",
             "--", sys.executable, "-m", "unittest", "discover"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("--not-applicable", r.stdout)

    def test_no_temp_leftovers_after_na(self):
        self.assertEqual(self.run_na().returncode, 0)
        ev = os.path.join(self.root, ".solo", "gate-evidence")
        self.assertEqual([n for n in os.listdir(ev) if ".tmp." in n], [])


if __name__ == "__main__":
    unittest.main()
