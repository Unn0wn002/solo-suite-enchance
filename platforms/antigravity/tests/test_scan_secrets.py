"""Secret-scanner leakage regression: scan_secrets.py must DETECT realistic
fake secrets while never emitting any complete secret value on stdout,
stderr, JSON output, or in exceptions/test reports.

The fake secrets are assembled at runtime from fragments so that neither
this test file nor any captured test output ever contains a full "secret"
literal (which would itself trip repository secret scans)."""
import json
import importlib.util as importlib_util
import os
import subprocess
import sys
import tempfile
import shutil
import time
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCANNER = os.path.join(REPO, "plugins", "site-doctor", "skills",
                       "security-review", "scripts", "scan_secrets.py")


def load_scanner_module():
    """Load a fresh scanner module so test-only constant patches cannot leak."""
    name = "scan_secrets_test_%d" % time.time_ns()
    spec = importlib_util.spec_from_file_location(name, SCANNER)
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_fixtures(root):
    """Write realistic fake secrets; return {rule_hint: full_secret_value}."""
    secrets = {}
    # assembled at runtime, never a single literal
    aws = "AKIA" + "IOSF" + "ODNN" + "7EXAMPLQ"                    # 16 after AKIA
    gh = "ghp_" + "a1B2c3D4e5F6g7H8i9J0" + "k1L2m3N4o5P6q7R8"      # 36 chars
    stripe = "sk_live_" + "4eC39HqLyjWDarjtT1zdp7dc"
    pg_pass = "sup3r" + "Secr3t" + "Pa55"
    conn = "postgres://appuser:" + pg_pass + "@db.internal.example:5432/app"
    pem_body = "MIIEowIBAAKCAQEA" + "x" * 24
    pem = ("-----BEGIN RSA PRIVATE KEY-----\n" + pem_body +
           "\n-----END RSA PRIVATE KEY-----\n")
    generic = "api_key = \"" + "zq" * 12 + "\""
    secrets["aws"] = aws
    secrets["github"] = gh
    secrets["stripe"] = stripe
    secrets["pg_password"] = pg_pass
    secrets["pem_body"] = pem_body
    secrets["generic_value"] = "zq" * 12

    files = {
        "config.py": 'AWS_KEY = "%s"\n%s\n' % (aws, generic),
        "deploy.sh": 'export GITHUB_TOKEN=%s\n' % gh,
        "payments.js": 'const key = "%s";\n' % stripe,
        "db.env": 'DATABASE_URL=%s\n' % conn,
        "server.key": pem,
    }
    for name, content in files.items():
        with open(os.path.join(root, name), "w", encoding="utf-8") as f:
            f.write(content)
    return secrets


def run_scanner(target, *extra):
    return subprocess.run(
        [sys.executable, SCANNER, target] + list(extra),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120, env=dict(os.environ, PYTHONIOENCODING="utf-8"))


class ScannerLeakage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="scan-secrets-fixture-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.secrets = make_fixtures(self.tmp)

    def assert_no_leak(self, text):
        for name, value in self.secrets.items():
            # generic assertion message on purpose: never echo the value
            self.assertNotIn(value, text,
                             "complete fake secret leaked (rule: %s)" % name)

    def test_detects_and_redacts_text_output(self):
        r = run_scanner(self.tmp)
        self.assertEqual(r.returncode, 1, "hits must exit 1")
        out = r.stdout + r.stderr
        for rule in ("AWS Access Key ID", "GitHub token", "Stripe live key",
                     "Connection string with creds", "Private key block"):
            self.assertIn(rule, out)
        self.assertIn("hmac-sha256:", out)
        self.assertIn("preview:", out)
        self.assert_no_leak(out)

    def test_json_output_redacted_and_structured(self):
        r = run_scanner(self.tmp, "--json")
        self.assertEqual(r.returncode, 1)
        self.assert_no_leak(r.stdout + r.stderr)
        data = json.loads(r.stdout)
        self.assertGreaterEqual(len(data["findings"]), 5)
        for f in data["findings"]:
            self.assertEqual(
                sorted(f), ["fingerprint", "line", "path", "placeholder_hint",
                            "preview", "rule"],
                "finding may carry ONLY the approved redacted fields")
            self.assertTrue(f["fingerprint"].startswith("hmac-sha256:"))
            self.assertNotIn("\n", f["preview"])
            self.assert_no_leak(json.dumps(f))

    def test_clean_tree_exits_zero(self):
        clean = os.path.join(self.tmp, "clean")
        os.makedirs(clean)
        with open(os.path.join(clean, "app.py"), "w", encoding="utf-8") as f:
            f.write("print('no secrets here')\n")
        r = run_scanner(clean)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_no_self_referential_hits_on_own_plugin(self):
        """Scanning the security-review skill itself must not report the
        scanner's own rule definitions."""
        skill_dir = os.path.join(REPO, "plugins", "site-doctor", "skills",
                                 "security-review")
        r = run_scanner(skill_dir)
        self.assertEqual(r.returncode, 0,
                         "self-referential false positives:\n" + r.stdout)

    def test_repository_pragma_cannot_suppress_a_finding(self):
        with open(os.path.join(self.tmp, "fixture.py"), "w",
                  encoding="utf-8") as f:
            f.write('key = "%s"  # secretscan:ignore\n' % self.secrets["aws"])
        r = run_scanner(self.tmp, "--json")
        data = json.loads(r.stdout)
        self.assertIn("fixture.py", [x["path"] for x in data["findings"]])


class KeyedFingerprints(unittest.TestCase):
    """Fingerprints must be HMAC-keyed — an unkeyed hash of a low-entropy
    password is a dictionary-attackable oracle."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="scan-fp-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.secrets = make_fixtures(self.tmp)

    def fingerprints(self, env_key=None):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        env.pop("SECRETSCAN_HMAC_KEY", None)
        if env_key:
            env["SECRETSCAN_HMAC_KEY"] = env_key
        r = subprocess.run([sys.executable, SCANNER, self.tmp, "--json"],
                           capture_output=True, text=True, timeout=120,
                           env=env)
        data = json.loads(r.stdout)
        return {f["path"] + ":%d" % f["line"]: f["fingerprint"]
                for f in data["findings"]}, data

    def test_no_unkeyed_sha256_of_the_password(self):
        import hashlib
        _, data = self.fingerprints()
        naked = hashlib.sha256(
            self.secrets["pg_password"].encode()).hexdigest()
        self.assertNotIn(naked, json.dumps(data),
                         "unsalted sha256 of a password was exposed")
        for f in data["findings"]:
            self.assertTrue(f["fingerprint"].startswith("hmac-sha256:"))

    def test_per_run_keys_differ_across_runs(self):
        a, _ = self.fingerprints()
        b, _ = self.fingerprints()
        self.assertNotEqual(a, b, "ephemeral keys must differ per run")

    def test_env_key_gives_stable_fingerprints(self):
        a, da = self.fingerprints("rotation-tracking-key")
        b, db = self.fingerprints("rotation-tracking-key")
        self.assertEqual(a, b)
        self.assertIn("env:SECRETSCAN_HMAC_KEY", da["fingerprint_key"])


class CoverageContract(unittest.TestCase):
    """Every candidate file gets an outcome; incomplete coverage and zero
    inspected files exit nonzero; single-file roots are supported."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="scan-cov-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def write(self, name, content, mode="w"):
        p = os.path.join(self.tmp, name)
        with open(p, mode, encoding=None if "b" in mode else "utf-8") as f:
            f.write(content)
        return p

    def test_max_bytes_1_reports_incomplete_and_exits_nonzero(self):
        self.write("app.py", "print('hello world')\n")
        self.write("lib.py", "x = 1\n")
        r = run_scanner(self.tmp, "--max-bytes", "1")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("INCOMPLETE COVERAGE", r.stdout)
        j = run_scanner(self.tmp, "--max-bytes", "1", "--json")
        data = json.loads(j.stdout)
        self.assertFalse(data["coverage"]["complete"])
        self.assertEqual(data["coverage"]["inspected"], 0)
        self.assertEqual(data["coverage"]["skipped_too_large"], 2)
        self.assertEqual(j.returncode, 3)

    def test_incomplete_exit_precedes_findings_without_hiding_them(self):
        """Exit 3 wins over exit 1 when both conditions are present."""
        secret = "AKIA" + "IOSF" + "ODNN" + "7EXAMPLQ"
        self.write("finding.py", 'credential = "%s"\n' % secret)
        self.write("oversized.txt", "x" * 200)
        result = run_scanner(self.tmp, "--max-bytes", "64", "--json")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertNotIn(secret, result.stdout + result.stderr)
        document = json.loads(result.stdout)
        self.assertFalse(document["coverage"]["complete"])
        self.assertGreaterEqual(len(document["findings"]), 1)
        self.assertEqual(document["coverage"]["skipped_too_large"], 1)

    def test_outcomes_tracked_separately(self):
        self.write("code.py", "print('x')\n")
        self.write("blob", b"\x00\x01\x02binary", "wb")     # extensionless
        self.write("suppressed.py",
                   "# secretscan:ignore-file\npassword = 'topsecret99'\n")
        self.write("long.js", "var x = '" + "a" * 3000 + "';\nok = 1\n")
        r = run_scanner(self.tmp, "--json")
        data = json.loads(r.stdout)
        cov = data["coverage"]
        self.assertEqual(cov["binary"], 1, cov)
        self.assertEqual(cov["suppressed"], 0, cov)
        self.assertGreaterEqual(cov["long_lines_chunked"], 1, cov)
        self.assertEqual(cov["inspected"], 3, cov)
        # J: an extensionless binary means coverage is NOT complete
        self.assertFalse(cov["complete"], cov)
        self.assertEqual(r.returncode, 3, r.stdout)

    def test_I_long_line_with_secret_found_redacted_nonzero(self):
        """Acceptance test I: a 2,100-char line with a realistic secret
        yields a redacted finding and a nonzero exit."""
        aws = "AKIA" + "IOSF" + "ODNN" + "7EXAMPLQ"
        pad = "x" * 1040
        self.write("minified.js", pad + ' aws_key = "' + aws + '" ' + pad
                   + "\n")
        r = run_scanner(self.tmp, "--json")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["coverage"]["long_lines_chunked"], 1)
        self.assertTrue(data["coverage"]["complete"])
        hits = [f for f in data["findings"] if f["path"] == "minified.js"]
        self.assertEqual(len(hits), 1)
        self.assertNotIn(aws, json.dumps(data), "secret value leaked")
        self.assertIn("AKIA", hits[0]["preview"])

    def test_I_secret_straddling_chunk_boundary_found(self):
        aws = "AKIA" + "IOSF" + "ODNN" + "7EXAMPLQ"
        self.write("edge.js", "y" * 4086 + aws + "z" * 600 + "\n")
        r = run_scanner(self.tmp, "--json")
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        self.assertTrue(any(f["path"] == "edge.js"
                            for f in data["findings"]))
        self.assertNotIn(aws, json.dumps(data))

    def test_J_unsupported_encoding_incomplete_not_clean(self):
        """Acceptance test J: undecodable content -> coverage incomplete,
        exit 3 — never a clean report."""
        self.write("latin.txt", "caf\xe9 config".encode("latin-1"), "wb")
        self.write("clean.py", "print('ok')\n")
        r = run_scanner(self.tmp, "--json")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["coverage"]["unsupported_encoding"], 1)
        self.assertFalse(data["coverage"]["complete"])

    def test_J_utf16_with_bom_is_scanned(self):
        aws = "AKIA" + "IOSF" + "ODNN" + "7EXAMPLQ"
        self.write("wide.txt", ('key = "%s"' % aws).encode("utf-16"), "wb")
        r = run_scanner(self.tmp, "--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        data = json.loads(r.stdout)
        self.assertTrue(any(f["path"] == "wide.txt"
                            for f in data["findings"]))
        self.assertTrue(data["coverage"]["complete"])
        self.assertNotIn(aws, json.dumps(data))

    def test_zero_inspected_exits_nonzero(self):
        os.makedirs(os.path.join(self.tmp, "sub"))
        r = run_scanner(self.tmp)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("ZERO files inspected", r.stdout)

    def test_single_file_root_supported(self):
        clean = self.write("one.py", "print('nothing secret')\n")
        r = run_scanner(clean)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        dirty = self.write("two.py",
                           'password = "hunter2-and-more"\n')
        r = run_scanner(dirty)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_text_lockfile_and_gate_evidence_are_scanned(self):
        aws = "AKIA" + "IOSF" + "ODNN" + "7EXAMPLQ"
        self.write("deps.lock", 'credential = "%s"\n' % aws)
        ev = os.path.join(self.tmp, ".solo", "gate-evidence")
        os.makedirs(ev)
        with open(os.path.join(ev, "capture.log"), "w", encoding="utf-8") as f:
            f.write('credential = "%s"\n' % aws)
        r = run_scanner(self.tmp, "--json")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        data = json.loads(r.stdout)
        paths = {x["path"] for x in data["findings"]}
        self.assertIn("deps.lock", paths)
        self.assertIn(".solo/gate-evidence/capture.log", paths)
        self.assertNotIn(aws, r.stdout + r.stderr)

    def test_symlink_is_refused_without_following(self):
        if not hasattr(os, "symlink"):
            self.skipTest("platform has no symlink support")
        outside = tempfile.mkdtemp(prefix="scan-outside-")
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        target = os.path.join(outside, "outside.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("safe outside content\n")
        link = os.path.join(self.tmp, "escape.txt")
        try:
            os.symlink(target, link)
        except OSError:
            self.skipTest("environment refuses symlink creation")
        r = run_scanner(self.tmp, "--json")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        cov = json.loads(r.stdout)["coverage"]
        self.assertEqual(cov["unsafe_symlink"], 1, cov)
        self.assertFalse(cov["complete"])

    def test_invalid_root_rejected(self):
        r = run_scanner(os.path.join(self.tmp, "does-not-exist"))
        self.assertEqual(r.returncode, 2)
        if os.path.exists("/dev/null"):
            r = run_scanner("/dev/null")
            self.assertEqual(r.returncode, 2, r.stdout)

    def test_scan_file_returns_an_outcome_for_every_file(self):
        import importlib.util as iu
        spec = iu.spec_from_file_location("scan_secrets_m", SCANNER)
        m = iu.module_from_spec(spec)
        spec.loader.exec_module(m)
        fp, _ = m.make_fingerprinter()
        p = self.write("f.py", "x = 1\n")
        outcome, findings, longl = m.scan_file(p, self.tmp, 2_000_000, fp)
        self.assertIn(outcome, m.OUTCOMES)
        self.assertEqual(outcome, "inspected")
        big = self.write("g.py", "y" * 100 + "\n")
        outcome, _, _ = m.scan_file(big, self.tmp, 10, fp)
        self.assertEqual(outcome, "skipped_too_large")
        blob = self.write("h", b"\x00\x01", "wb")
        outcome, _, _ = m.scan_file(blob, self.tmp, 2_000_000, fp)
        self.assertEqual(outcome, "binary")


class GitHistoryScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="scan-history-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        subprocess.run(["git", "init", "-q", self.tmp], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", self.tmp, "config", "user.email",
                        "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", self.tmp, "config", "user.name",
                        "test"], check=True)
        self.secret = "AKIA" + "IOSF" + "ODNN" + "7EXAMPLQ"
        app = os.path.join(self.tmp, "app.py")
        with open(app, "w", encoding="utf-8") as f:
            f.write('credential = "%s"\n' % self.secret)
        subprocess.run(["git", "-C", self.tmp, "add", "app.py"], check=True)
        subprocess.run(["git", "-C", self.tmp, "commit", "-qm", "old"],
                       check=True)
        with open(app, "w", encoding="utf-8") as f:
            f.write("print('current tree is clean')\n")
        subprocess.run(["git", "-C", self.tmp, "add", "app.py"], check=True)
        subprocess.run(["git", "-C", self.tmp, "commit", "-qm", "clean"],
                       check=True)

    def write_fake_git(self, source):
        path = os.path.join(self.tmp, "fake_git.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(source)
        return path

    def test_deleted_secret_found_without_preview_or_value(self):
        r = run_scanner(self.tmp, "--git-history",
                        "--history-max-commits", "10", "--json")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn(self.secret, r.stdout + r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["findings"], [], "current tree is clean")
        self.assertTrue(data["history"]["complete"], data["history"])
        self.assertGreaterEqual(len(data["history"]["findings"]), 1)
        for finding in data["history"]["findings"]:
            self.assertEqual(sorted(finding),
                             ["commit", "fingerprint", "line", "path", "rule"])
            self.assertNotIn("preview", finding)
            self.assertTrue(finding["fingerprint"].startswith("hmac-sha256:"))

    def test_commit_and_total_byte_caps_fail_closed(self):
        limited = run_scanner(self.tmp, "--git-history",
                              "--history-max-commits", "1", "--json")
        self.assertEqual(limited.returncode, 3, limited.stdout + limited.stderr)
        history = json.loads(limited.stdout)["history"]
        self.assertFalse(history["complete"])
        self.assertTrue(any("commit cap" in x
                            for x in history["incomplete_reasons"]))
        byte_limited = run_scanner(self.tmp, "--git-history",
                                   "--history-max-bytes", "1", "--json")
        self.assertEqual(byte_limited.returncode, 3,
                         byte_limited.stdout + byte_limited.stderr)
        history = json.loads(byte_limited.stdout)["history"]
        self.assertFalse(history["complete"])
        self.assertTrue(any("byte cap" in x
                            for x in history["incomplete_reasons"]))

    def test_per_blob_skip_has_nonempty_history_reason(self):
        limited = run_scanner(self.tmp, "--git-history", "--max-bytes", "1",
                              "--json")
        self.assertEqual(limited.returncode, 3,
                         limited.stdout + limited.stderr)
        history = json.loads(limited.stdout)["history"]
        self.assertFalse(history["complete"])
        self.assertGreater(history["skipped_too_large"], 0)
        self.assertTrue(any("per-blob byte cap" in reason
                            for reason in history["incomplete_reasons"]))

    def test_oversized_ls_tree_stream_fails_closed(self):
        """A tree listing over its cap is stopped, not captured to a temp file."""
        scanner = load_scanner_module()
        fingerprint, _ = scanner.make_fingerprinter()
        started = time.monotonic()
        with mock.patch.object(scanner, "GIT_TREE_MIN_CAP", 32), \
                mock.patch.object(scanner, "GIT_TREE_ENTRY_BUDGET", 1):
            history = scanner.scan_git_history(
                self.tmp, fingerprint, max_commits=10, max_files=1,
                max_blob_bytes=1024, max_total_bytes=4096,
                max_findings=10)
        self.assertLess(time.monotonic() - started, 5)
        self.assertFalse(history["complete"], history)
        self.assertTrue(any("tree listing failed" in reason
                            for reason in history["incomplete_reasons"]))
        self.assertEqual(history["findings"], [])

    def test_oversized_historical_blob_is_discarded_without_secret_leak(self):
        """A dishonest/compromised Git child cannot overrun the blob cap."""
        fake_git = self.write_fake_git(
            "import os, sys\n"
            "repo, command = sys.argv[2], sys.argv[3]\n"
            "if command == 'rev-parse':\n"
            "    os.write(1, (os.path.realpath(repo) + '\\n').encode())\n"
            "elif command == 'rev-list':\n"
            "    os.write(1, (b'a' * 40) + b'\\n')\n"
            "elif command == 'ls-tree':\n"
            "    os.write(1, b'100644 blob ' + (b'b' * 40) + "
            "b' 8\\tapp.py\\0')\n"
            "elif command == 'cat-file':\n"
            "    payload = ('AKIA' + 'IOSF' + 'ODNN' + "
            "'7EXAMPLQ').encode()\n"
            "    while True:\n"
            "        os.write(1, payload * 64)\n")
        scanner = load_scanner_module()
        fingerprint, _ = scanner.make_fingerprinter()
        with mock.patch.object(
                scanner, "GIT_COMMAND", (sys.executable, fake_git)):
            history = scanner.scan_git_history(
                self.tmp, fingerprint, max_commits=1, max_files=10,
                max_blob_bytes=64, max_total_bytes=1024,
                max_findings=10)
        self.assertFalse(history["complete"], history)
        self.assertTrue(any("blob read failed" in reason
                            for reason in history["incomplete_reasons"]))
        self.assertNotIn(self.secret, json.dumps(history))
        self.assertEqual(history["bytes_scanned"], 0)

    def test_stderr_cap_terminates_descendant_process_tree(self):
        """A noisy Git child and its descendant die promptly at the cap."""
        marker = os.path.join(self.tmp, "descendant-survived.txt")
        fake_git = self.write_fake_git(
            "import os, subprocess, sys\n"
            "marker = os.environ['SECRETSCAN_TEST_MARKER']\n"
            "child = \"import pathlib,sys,time; time.sleep(0.8); "
            "pathlib.Path(sys.argv[1]).write_text('survived')\"\n"
            "subprocess.Popen([sys.executable, '-c', child, marker])\n"
            "payload = ('AKIA' + 'IOSF' + 'ODNN' + "
            "'7EXAMPLQ').encode()\n"
            "while True:\n"
            "    os.write(2, payload * 64)\n")
        scanner = load_scanner_module()
        started = time.monotonic()
        with mock.patch.object(
                scanner, "GIT_COMMAND", (sys.executable, fake_git)), \
                mock.patch.dict(os.environ,
                                {"SECRETSCAN_TEST_MARKER": marker}):
            _rc, captured, truncated = scanner._git_bounded(
                self.tmp, ["rev-parse", "--show-toplevel"], 64,
                timeout=5, stderr_cap=64)
        self.assertLess(time.monotonic() - started, 3)
        self.assertTrue(truncated)
        self.assertEqual(captured, b"")
        self.assertNotIn(self.secret.encode(), captured)
        time.sleep(1.1)
        self.assertFalse(os.path.exists(marker),
                         "bounded Git left a descendant process alive")

    def test_timeout_terminates_descendant_process_tree(self):
        marker = os.path.join(self.tmp, "timeout-descendant-survived.txt")
        fake_git = self.write_fake_git(
            "import os, subprocess, sys, time\n"
            "marker = os.environ['SECRETSCAN_TEST_MARKER']\n"
            "child = \"import pathlib,sys,time; time.sleep(0.8); "
            "pathlib.Path(sys.argv[1]).write_text('survived')\"\n"
            "subprocess.Popen([sys.executable, '-c', child, marker])\n"
            "time.sleep(30)\n")
        scanner = load_scanner_module()
        started = time.monotonic()
        with mock.patch.object(
                scanner, "GIT_COMMAND", (sys.executable, fake_git)), \
                mock.patch.dict(os.environ,
                                {"SECRETSCAN_TEST_MARKER": marker}):
            rc, captured, truncated = scanner._git_bounded(
                self.tmp, ["rev-parse", "--show-toplevel"], 64,
                timeout=0.2, stderr_cap=64)
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(rc, 124)
        self.assertTrue(truncated)
        self.assertEqual(captured, b"")
        time.sleep(1.1)
        self.assertFalse(os.path.exists(marker),
                         "timed-out Git left a descendant process alive")


if __name__ == "__main__":
    unittest.main()
