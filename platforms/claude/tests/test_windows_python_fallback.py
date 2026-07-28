"""Windows interpreter-resolution contracts (T-014).

`python3` is not the interpreter on a stock Windows 11 install. Worse, it is
not simply ABSENT: %LOCALAPPDATA%\\Microsoft\\WindowsApps\\python3.exe exists as
a Microsoft Store App Execution Alias, so `shutil.which("python3")` SUCCEEDS and
a which()-style guard passes. The stub then prints "Python was not found; run
without arguments to install from the Microsoft Store" and exits 9009, which
surfaces as an unexplained gate failure rather than a missing-interpreter error.

Two defences are asserted here:
  * every gate command that shells out documents the `python` / `py -3`
    fallback, and
  * gate_policy refuses a resolved interpreter that is a WindowsApps alias.

The alias predicate is exercised on every platform through a fabricated path so
the contract is tested on Linux CI too, not only on the maintainer's laptop.
"""
import glob
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE_POLICY = os.path.join(REPO, "plugins", "gate", "lib", "gate_policy.py")


def load_gate_policy():
    spec = importlib.util.spec_from_file_location("gate_policy_under_test",
                                                  GATE_POLICY)
    module = importlib.util.module_from_spec(spec)
    sys.modules["gate_policy_under_test"] = module
    spec.loader.exec_module(module)
    return module


class GateCommandsDocumentTheFallback(unittest.TestCase):
    """Commands whose fenced blocks invoke python3 must say what to do when
    it is missing or is the Store alias."""

    def shelling_commands(self):
        out = []
        for path in sorted(glob.glob(os.path.join(REPO, "plugins", "gate",
                                                  "commands", "*.md"))):
            with io.open(path, encoding="utf-8") as stream:
                text = stream.read()
            if re.search(r"```bash\b", text) and "python3 " in text:
                out.append((path, text))
        return out

    def test_there_are_gate_commands_that_shell_out(self):
        self.assertGreaterEqual(len(self.shelling_commands()), 2)

    def test_each_documents_python_and_py_dash_3(self):
        for path, text in self.shelling_commands():
            rel = os.path.relpath(path, REPO)
            self.assertIn("`python`", text, rel)
            self.assertIn("`py -3`", text, rel)

    def test_each_warns_about_the_store_alias(self):
        for path, text in self.shelling_commands():
            rel = os.path.relpath(path, REPO)
            self.assertIn("9009", text,
                          "%s must name the alias exit code" % rel)


class StoreAliasRejection(unittest.TestCase):
    """T-014: gate_policy must refuse the WindowsApps stub."""

    @classmethod
    def setUpClass(cls):
        cls.policy = load_gate_policy()

    def fake_alias(self, tmp, size=0):
        """Build a path that looks exactly like the Store alias."""
        d = os.path.join(tmp, "AppData", "Local", "Microsoft", "WindowsApps")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "python3.exe")
        with open(p, "wb") as stream:
            stream.write(b"" if size == 0 else b"\x00" * size)
        return p

    def test_zero_byte_windowsapps_stub_is_an_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            alias = self.fake_alias(tmp)
            with mock.patch.object(os, "name", "nt"):
                self.assertTrue(self.policy._is_windows_store_alias(alias))

    def test_a_real_interpreter_in_windowsapps_is_not_rejected(self):
        """Only the zero-length stub is refused; a genuine binary that
        happens to live there stays usable."""
        with tempfile.TemporaryDirectory() as tmp:
            real = self.fake_alias(tmp, size=4096)
            with mock.patch.object(os, "name", "nt"):
                self.assertFalse(self.policy._is_windows_store_alias(real))

    def test_a_normal_python_path_is_never_an_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "python3")
            with open(p, "wb") as stream:
                stream.write(b"")
            with mock.patch.object(os, "name", "nt"):
                self.assertFalse(self.policy._is_windows_store_alias(p))

    def test_predicate_is_inert_off_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            alias = self.fake_alias(tmp)
            with mock.patch.object(os, "name", "posix"):
                self.assertFalse(self.policy._is_windows_store_alias(alias))

    def test_resolve_executable_refuses_the_alias_with_an_actionable_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            alias = self.fake_alias(tmp)
            project = os.path.join(tmp, "project")
            os.makedirs(project, exist_ok=True)
            with mock.patch.object(os, "name", "nt"):
                resolved, reason = self.policy.resolve_executable(alias,
                                                                  project)
            self.assertIsNone(resolved)
            self.assertIn("9009", reason)
            self.assertIn("py -3", reason)

    def test_a_working_interpreter_still_resolves(self):
        """The guard must not break the normal path."""
        with tempfile.TemporaryDirectory() as tmp:
            project = os.path.join(tmp, "project")
            os.makedirs(project, exist_ok=True)
            resolved, reason = self.policy.resolve_executable(
                os.path.realpath(sys.executable), project)
            self.assertIsNone(reason, reason)
            self.assertTrue(os.path.isfile(resolved))


class RealInterpreterBehaviour(unittest.TestCase):
    """Observed behaviour of the interpreters actually present here.

    These assert what IS true on this machine rather than skipping: on
    non-Windows the alias cannot exist, which is itself the contract.
    """

    def test_missing_interpreter_name_does_not_resolve(self):
        self.assertIsNone(shutil.which("python3-definitely-not-installed"))

    @unittest.skipUnless(os.name == "nt", "Windows-only alias behaviour")
    def test_py_launcher_or_python_is_usable_here(self):
        """At least one documented fallback must actually work."""
        working = []
        for argv in (["python", "--version"], ["py", "-3", "--version"]):
            exe = shutil.which(argv[0])
            if not exe:
                continue
            try:
                r = subprocess.run([exe] + argv[1:], capture_output=True,
                                   timeout=60)
            except OSError:
                continue
            if r.returncode == 0 and b"Python 3" in (r.stdout + r.stderr):
                working.append(argv[0])
        self.assertTrue(working,
                        "neither `python` nor `py -3` works, so the "
                        "documented fallback is wrong for this machine")


if __name__ == "__main__":
    unittest.main()
