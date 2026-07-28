"""Windows/default-encoding regressions for packaged command-line tools.

These tests use only disposable local fixtures. They deliberately force the
ordinary Windows cp1252 stream encoding instead of relying on PYTHONUTF8=1.
"""
import glob
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE_POLICY = os.path.join(REPO, "plugins", "gate", "lib",
                           "gate_policy.py")
RECORD_EVIDENCE = os.path.join(
    REPO, "plugins", "gate", "skills", "production-readiness-reviewer",
    "scripts", "record_evidence.py")
SCANNER = os.path.join(
    REPO, "plugins", "site-doctor", "skills", "security-review",
    "scripts", "scan_secrets.py")
VALIDATE_ROOMS = os.path.join(
    REPO, "plugins", "ai", "skills", "agent-room-templates", "scripts",
    "validate_rooms.py")


README = """# Demo library documentation

## Installation and setup

Create a virtual environment, activate it, and install the package from the
checked-out directory. This small library has no network service, database,
background worker, or runtime configuration. Maintainers can review every
module before installation and can reproduce the setup on a clean machine.

```bash
python -m pip install .
```

## Usage and API

Import the public function and pass two integers. The operation returns their
sum without changing either input. Callers receive normal Python type errors
for unsupported values. The command below demonstrates the complete public
interface and provides a quick smoke check for a newly installed package.

```python
from demo import add
assert add(20, 22) == 42
```

Run the standard unit-test discovery command before publishing. The suite is
offline, deterministic, dependency-free, and suitable for developer laptops
as well as continuous integration workers. Release maintainers should review
the result, package metadata, source commit, and generated evidence together.
"""


def cp1252_env():
    env = dict(os.environ)
    env["PYTHONUTF8"] = "0"
    env["PYTHONIOENCODING"] = "cp1252"
    return env


def git(root, *args):
    return subprocess.run(["git"] + list(args), cwd=root,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=30)


class WindowsDefaultEncoding(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="windows-encoding-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_validate_rooms_help_succeeds_under_cp1252(self):
        result = subprocess.run(
            [sys.executable, VALIDATE_ROOMS, "--help"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=cp1252_env(), timeout=60)
        self.assertEqual(result.returncode, 0,
                         (result.stdout + result.stderr).decode(
                             "cp1252", "replace"))
        self.assertIn(b"usage:", result.stdout.lower())

    def test_cp1252_gate_output_is_stored_as_utf8(self):
        with open(os.path.join(self.root, "README.md"), "w",
                  encoding="utf-8") as stream:
            stream.write(README)
        with open(os.path.join(self.root, "demo.py"), "w",
                  encoding="utf-8") as stream:
            stream.write("def add(a, b):\n    return a + b\n")
        with open(os.path.join(self.root, ".gitignore"), "w",
                  encoding="utf-8") as stream:
            stream.write(".solo/gate-evidence/\n.solo/run-state/\n")
        git(self.root, "init", "-q", ".")
        git(self.root, "config", "user.email", "test@example.invalid")
        git(self.root, "config", "user.name", "test")
        git(self.root, "add", "-A")
        committed = git(self.root, "commit", "-qm", "fixture")
        self.assertEqual(committed.returncode, 0, committed.stderr)

        base = [sys.executable, RECORD_EVIDENCE,
                "--category", "documentation", "--project", "demo",
                "--environment", "production", "--root", self.root,
                "--reviewer", "documentation seat"]
        command = ["--", sys.executable, GATE_POLICY, "verify-artifact",
                   "documentation"]
        preview = subprocess.run(
            base + ["--preview"] + command,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=cp1252_env(), timeout=120)
        token = re.search(rb"preview token: ([0-9a-f]{64})", preview.stdout)
        self.assertEqual(preview.returncode, 0,
                         (preview.stdout + preview.stderr).decode(
                             "cp1252", "replace"))
        self.assertIsNotNone(token)
        result = subprocess.run(
            base + ["--confirm-execution", token.group(1).decode("ascii")]
            + command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=cp1252_env(), timeout=120)
        self.assertEqual(result.returncode, 0,
                         (result.stdout + result.stderr).decode(
                             "cp1252", "replace"))

        artifact = os.path.join(self.root, ".solo", "gate-evidence",
                                "artifacts", "documentation.log")
        with open(artifact, "rb") as stream:
            captured = stream.read()
        text = captured.decode("utf-8")  # strict: mixed encodings must fail
        self.assertIn("# capture_encoding: utf-8", text)
        self.assertIn("headings \u2014 all", text)

        # The generated CP1252-origin capture is outside scanner coverage by
        # exact runtime-path policy, so it cannot poison a repository scan.
        scanned = subprocess.run(
            [sys.executable, SCANNER, self.root, "--json"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=cp1252_env(), timeout=120)
        self.assertEqual(scanned.returncode, 0,
                         (scanned.stdout + scanned.stderr).decode(
                             "cp1252", "replace"))

    def test_scanner_includes_generated_runtime_dirs(self):
        with open(os.path.join(self.root, "clean.py"), "w",
                  encoding="utf-8") as stream:
            stream.write("print('clean fixture')\n")
        for relative in (os.path.join(".solo", "gate-evidence", "bad.log"),
                         os.path.join(".solo", "run-state", "bad.json")):
            path = os.path.join(self.root, relative)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as stream:
                stream.write(b"cp1252 punctuation: \x97\n")

        utf8_env = dict(os.environ, PYTHONUTF8="0", PYTHONIOENCODING="utf-8")
        excluded = subprocess.run(
            [sys.executable, SCANNER, self.root, "--json"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=utf8_env, timeout=120)
        self.assertEqual(excluded.returncode, 3,
                         (excluded.stdout + excluded.stderr).decode(
                             "utf-8", "replace"))
        coverage = json.loads(excluded.stdout.decode("utf-8"))["coverage"]
        self.assertEqual(coverage["inspected"], 1, coverage)
        self.assertEqual(coverage["unsupported_encoding"], 2, coverage)

        # Similar names outside the two exact paths must remain in scope.
        for relative in (
                os.path.join(".solo", "gate-evidence-copy", "bad.log"),
                os.path.join("nested", "gate-evidence", "bad.log")):
            path = os.path.join(self.root, relative)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as stream:
                stream.write(b"cp1252 punctuation: \x97\n")
        included = subprocess.run(
            [sys.executable, SCANNER, self.root, "--json"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=utf8_env, timeout=120)
        self.assertEqual(included.returncode, 3,
                         (included.stdout + included.stderr).decode(
                             "utf-8", "replace"))
        coverage = json.loads(included.stdout.decode("utf-8"))["coverage"]
        self.assertEqual(coverage["unsupported_encoding"], 4, coverage)

    def test_scanner_reports_findings_for_non_cp1252_paths(self):
        """A finding whose PATH cannot be encoded must still be reported.

        The text report used to interpolate the raw path and preview, so on a
        cp1252 stream the scanner printed the "POTENTIAL SECRETS (n)" banner
        and then died with UnicodeEncodeError before emitting the location --
        announcing a secret and losing where it is.  Both fields are now
        JSON-escaped, matching the historical-findings branch.
        """
        name = "設定ファイル.py"
        with open(os.path.join(self.root, name), "w",
                  encoding="utf-8") as stream:
            stream.write('KEY = "AKIAIOSFODNN7EXAMPLE"\n')

        result = subprocess.run(
            [sys.executable, SCANNER, self.root],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=cp1252_env(), timeout=120)
        report = result.stdout.decode("cp1252", "replace")
        errors = result.stderr.decode("cp1252", "replace")

        self.assertNotIn("UnicodeEncodeError", errors, errors)
        self.assertEqual(result.returncode, 1, report + errors)
        self.assertIn("POTENTIAL SECRETS (1)", report)
        # The location survives, escaped rather than raw.
        self.assertIn(json.dumps(name), report)
        self.assertIn("preview:", report)
        self.assertIn("AKIA", report)
        self.assertIn("hmac-sha256:", report)
        # Redaction still holds: the literal secret must never be printed.
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", report)

    def test_scanner_rejects_a_missing_non_cp1252_path_cleanly(self):
        """The not-found exit must report the path, not crash encoding it."""
        missing = os.path.join(self.root, "存在しない")
        result = subprocess.run(
            [sys.executable, SCANNER, missing],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=cp1252_env(), timeout=60)
        errors = result.stderr.decode("cp1252", "replace")
        self.assertNotIn("UnicodeEncodeError", errors, errors)
        self.assertEqual(result.returncode, 2,
                         result.stdout.decode("cp1252", "replace") + errors)
        self.assertIn("Path not found:",
                      result.stdout.decode("cp1252", "replace"))


# ---------------------------------------------------------------------------
# T-023: every shipped script, not just the original four.
#
# The four scripts above were the entire cp1252 surface, which is why the
# scan_secrets crash survived: nothing fed a non-cp1252 PATH or PAYLOAD to
# anything. These cases run the remaining scripts under the same forced
# cp1252 streams and assert that an encoding assumption surfaces as a real
# failure rather than being skipped or silently replaced.
#
# Everything here is offline: local fixture trees only, no sockets.
# ---------------------------------------------------------------------------

def shipped_scripts():
    """Every .py this suite ships to users."""
    found = []
    for pattern in ("plugins/*/skills/*/scripts/*.py", "plugins/*/lib/*.py"):
        found.extend(glob.glob(os.path.join(REPO, *pattern.split("/"))))
    return sorted(found)


# A filename and a payload that cp1252 cannot represent.
NON_CP1252_NAME = "設定ファイル"
NON_CP1252_TEXT = "見出し → naïve ✓ Ω"


def entry_point_scripts():
    """Shipped scripts that are runnable as programs."""
    found = []
    for path in shipped_scripts():
        with io.open(path, encoding="utf-8", newline="") as stream:
            if 'if __name__ == "__main__":' in stream.read():
                found.append(path)
    return sorted(found)


class StreamHardeningPolicy(unittest.TestCase):
    """T-SUGGEST-006: make the cp1252 crash class structurally impossible.

    Two scripts shipped the same UnicodeEncodeError -- scan_secrets.py and
    animation_check.py -- and both were fixed one print-site at a time. Every
    entry point now reconfigures stdout/stderr to escape rather than raise, so
    a future unescaped path or payload degrades to \\uXXXX instead of killing
    the report mid-write.

    Deliberate design points asserted here:
      * the call sits inside the __main__ guard, so importing a module (which
        several tests do) never mutates the importing process's streams;
      * only `errors` is changed, never `encoding`, so the CP1252 CI matrix
        leg still exercises cp1252 and ASCII output stays byte-identical;
      * the helper is byte-identical everywhere, like url_guard.py -- plugins
        install independently so it cannot be imported from one shared place.
    """

    def test_every_entry_point_hardens_its_streams(self):
        missing = []
        for path in entry_point_scripts():
            with io.open(path, encoding="utf-8", newline="") as stream:
                text = stream.read()
            tail = text.split('if __name__ == "__main__":')[-1]
            if "def _harden_streams():" not in text or \
                    "_harden_streams()" not in tail:
                missing.append(os.path.relpath(path, REPO))
        self.assertEqual(missing, [],
                         "entry points without stream hardening: %s" % missing)

    def test_there_are_the_expected_number_of_entry_points(self):
        self.assertEqual(len(entry_point_scripts()), 17,
                         [os.path.relpath(p, REPO)
                          for p in entry_point_scripts()])

    def test_the_helper_is_byte_identical_everywhere(self):
        bodies = set()
        for path in entry_point_scripts():
            with io.open(path, encoding="utf-8", newline="") as stream:
                text = stream.read()
            start = text.index("def _harden_streams():")
            end = text.index('if __name__ == "__main__":', start)
            bodies.add(text[start:end])
        self.assertEqual(len(bodies), 1,
                         "the hardening helper has drifted between scripts")

    def test_hardening_is_not_applied_at_import_time(self):
        """Importing a helper must not reconfigure the caller's streams."""
        for path in entry_point_scripts():
            with io.open(path, encoding="utf-8", newline="") as stream:
                text = stream.read()
            head = text.split('if __name__ == "__main__":')[0]
            # the definition may appear at module level; the CALL may not
            self.assertNotRegex(
                head, r"(?m)^_harden_streams\(\)",
                "%s calls _harden_streams() at import time"
                % os.path.relpath(path, REPO))

    def test_encoding_is_never_overridden_only_errors(self):
        """Forcing UTF-8 would defeat the cp1252 CI matrix leg."""
        for path in entry_point_scripts():
            with io.open(path, encoding="utf-8", newline="") as stream:
                text = stream.read()
            start = text.index("def _harden_streams():")
            end = text.index('if __name__ == "__main__":', start)
            helper = text[start:end]
            self.assertIn('reconfigure(errors="backslashreplace")', helper)
            self.assertNotIn("encoding=", helper)

    def test_hardening_survives_a_stream_without_reconfigure(self):
        """A replaced stream (StringIO) must not raise on startup."""
        probe = (
            "import io, sys\n"
            "sys.stdout = io.StringIO()\n"
            "for s in (sys.stdout, sys.stderr):\n"
            "    try:\n"
            "        s.reconfigure(errors='backslashreplace')\n"
            "    except (AttributeError, ValueError, OSError):\n"
            "        pass\n"
            "sys.stderr.write('survived\\n')\n"
        )
        result = subprocess.run([sys.executable, "-c", probe],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=cp1252_env(), timeout=60)
        self.assertEqual(result.returncode, 0,
                         result.stderr.decode("cp1252", "replace"))
        self.assertIn(b"survived", result.stderr)


class AllShippedScriptsUnderCp1252(unittest.TestCase):
    """Import- and usage-path encoding assumptions across every script."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cp1252-sweep-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_the_suite_ships_the_expected_script_surface(self):
        """Guard the guard: if a script is added, it must be swept too."""
        names = sorted(os.path.basename(p) for p in shipped_scripts())
        self.assertGreaterEqual(len(names), 19, names)
        for expected in ("scan_secrets.py", "url_guard.py", "extract_meta.py",
                         "check_headers.py", "check_links.py",
                         "schema_check.py", "sitemap_check.py",
                         "animation_check.py", "check_deps.py",
                         "check_email_dns.py", "check_mobile.py",
                         "scan_trackers.py", "self_check.py",
                         "check_evidence.py", "update_run_state.py",
                         "validate_rooms.py", "record_evidence.py"):
            self.assertIn(expected, names, expected)

    def test_no_script_crashes_on_its_own_usage_path(self):
        """`--help` and the no-argument usage path must survive cp1252.

        This is the cheapest way to catch an encoding assumption in a
        module-level docstring, an argparse help string, or an import-time
        print -- all of which are emitted before any real work starts.
        """
        failures = []
        for path in shipped_scripts():
            for argv in (["--help"], []):
                result = subprocess.run(
                    [sys.executable, path] + argv,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=self.root, env=cp1252_env(), timeout=120)
                combined = (result.stdout + result.stderr).decode(
                    "cp1252", "replace")
                if "UnicodeEncodeError" in combined or \
                        "UnicodeDecodeError" in combined:
                    failures.append("%s %s -> %s" % (
                        os.path.relpath(path, REPO), argv,
                        combined.strip().splitlines()[-1:]))
        self.assertEqual(failures, [], "\n".join(failures))

    def test_scripts_that_take_a_path_survive_a_non_cp1252_tree(self):
        """Feed real non-cp1252 filenames AND file content, not just
        non-cp1252 source literals."""
        tree = os.path.join(self.root, "proj")
        os.makedirs(os.path.join(tree, NON_CP1252_NAME), exist_ok=True)
        with io.open(os.path.join(tree, NON_CP1252_NAME, "index.js"), "w",
                     encoding="utf-8") as stream:
            stream.write("// %s\ngsap.to('.x', {opacity: 1});\n"
                         % NON_CP1252_TEXT)
        with io.open(os.path.join(tree, "%s.py" % NON_CP1252_NAME), "w",
                     encoding="utf-8") as stream:
            stream.write("VALUE = %r\n" % NON_CP1252_TEXT)
        with io.open(os.path.join(tree, "package.json"), "w",
                     encoding="utf-8") as stream:
            stream.write('{"name": "x", "dependencies": {"gsap": "^3.0.0"}}\n')

        path_takers = {
            "animation_check.py": [tree],
            "check_deps.py": [tree],
            "scan_secrets.py": [tree],
        }
        failures = []
        for path in shipped_scripts():
            name = os.path.basename(path)
            if name not in path_takers:
                continue
            result = subprocess.run(
                [sys.executable, path] + path_takers[name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=self.root, env=cp1252_env(), timeout=180)
            combined = (result.stdout + result.stderr).decode("cp1252",
                                                              "replace")
            if "UnicodeEncodeError" in combined or \
                    "UnicodeDecodeError" in combined:
                failures.append("%s -> %s" % (name, combined.strip()[-400:]))
        self.assertEqual(failures, [], "\n".join(failures))

    def test_url_guard_handles_non_cp1252_hostnames_offline(self):
        """The origin helpers take attacker-controlled hostnames; IDN input
        must not raise, and must fail closed rather than match."""
        probe = (
            "import sys, io, json\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "import url_guard as g\n"
            "host = '\\u8a2d\\u5b9a.example'\n"
            "url = 'https://' + host\n"
            "out = {\n"
            "  'norm': g.normalized_hostname(url),\n"
            "  'same_self': g.same_audit_origin(url, url),\n"
            "  'same_other': g.same_audit_origin(url, 'https://evil.test'),\n"
            "}\n"
            "print(json.dumps(out, ensure_ascii=True))\n"
        )
        for lib in sorted(glob.glob(os.path.join(REPO, "plugins", "*", "lib",
                                                 "url_guard.py"))):
            result = subprocess.run(
                [sys.executable, "-c", probe, os.path.dirname(lib)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=self.root, env=cp1252_env(), timeout=60)
            err = result.stderr.decode("cp1252", "replace")
            self.assertEqual(result.returncode, 0,
                             "%s: %s" % (lib, err))
            data = json.loads(result.stdout.decode("ascii"))
            self.assertTrue(data["same_self"], lib)
            self.assertFalse(data["same_other"], lib)

    def test_self_check_prints_its_whole_report_under_cp1252(self):
        """self_check emits every plugin/skill/command path it inspects, so
        it is the widest path-printing surface in the suite. Run it against
        the real repository (it needs a genuine layout) with cp1252 streams
        and require the full report, not a truncated one."""
        script = os.path.join(REPO, "plugins", "solo", "skills",
                              "suite-integrity", "scripts", "self_check.py")
        result = subprocess.run(
            [sys.executable, script, REPO, "-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=self.root, env=cp1252_env(), timeout=180)
        combined = (result.stdout + result.stderr).decode("cp1252", "replace")
        self.assertNotIn("UnicodeEncodeError", combined, combined[-600:])
        self.assertNotIn("Traceback", combined, combined[-600:])
        # the trailing summary proves it reached the end rather than dying
        self.assertRegex(combined, r"== \d+ pass, \d+ warn, \d+ fail ==")
        self.assertEqual(result.returncode, 0, combined[-600:])


if __name__ == "__main__":
    unittest.main()
