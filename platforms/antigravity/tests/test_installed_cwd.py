"""Installed-plugin path regression: helper scripts must work when the
current working directory is OUTSIDE the plugin directory (the normal case
for an installed plugin, where SKILL.md invokes them via
${CLAUDE_PLUGIN_ROOT}/...). Also verifies the scripts still resolve the
shared lib/url_guard.py when the whole plugin tree is copied elsewhere,
exactly as the plugin cache does on install."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SD = os.path.join(REPO, "plugins", "site-doctor")


def run_from(cwd, script, args, env_extra=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("URL_GUARD_EXTRA_ALLOWED", None)
    env.pop("URL_GUARD_TEST_MODE", None)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, script] + args, cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120, env=env)


class InstalledCwd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="solo-suite-cwd-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # a scratch "user project" directory, far away from the repo
        self.project = os.path.join(self.tmp, "some-user-project")
        os.makedirs(self.project)

    def test_url_guard_script_runs_from_foreign_cwd(self):
        """check_headers.py invoked with CWD = user project, script path
        absolute (as ${CLAUDE_PLUGIN_ROOT} expansion produces)."""
        script = os.path.join(SD, "skills", "website-audit", "scripts",
                              "check_headers.py")
        r = run_from(self.project, script, ["https://10.0.0.1/"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("BLOCKED", r.stdout)
        self.assertNotIn("url_guard.py not found", r.stdout + r.stderr)

    def test_plugin_copied_to_cache_still_finds_url_guard(self):
        """Simulate the installed-plugin cache: copy the whole plugin tree
        elsewhere and run a helper from an unrelated CWD."""
        cache = os.path.join(self.tmp, "cache", "plugins", "site-doctor")
        shutil.copytree(SD, cache)
        script = os.path.join(cache, "skills", "website-audit", "scripts",
                              "check_headers.py")
        r = run_from(self.project, script, ["https://169.254.169.254/"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("BLOCKED", r.stdout)
        self.assertNotIn("url_guard.py not found", r.stdout + r.stderr)

    def test_offline_helpers_run_from_foreign_cwd(self):
        """check_deps.py and scan_secrets.py take filesystem targets and must
        not depend on the CWD either."""
        # fixture project for check_deps
        with open(os.path.join(self.project, "package.json"), "w",
                  encoding="utf-8") as f:
            f.write('{"dependencies": {"left-pad": "^1.3.0"}}')
        deps = os.path.join(SD, "skills", "dependency-audit", "scripts",
                            "check_deps.py")
        r = run_from(self.tmp, deps, [self.project])
        # a manifest without live vulnerability data is UNVERIFIED -> exit 3
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("Direct dependencies: 1", r.stdout)
        self.assertIn("[UNVERIFIED]", r.stdout)

        scanner = os.path.join(SD, "skills", "security-review", "scripts",
                               "scan_secrets.py")
        clean = os.path.join(self.tmp, "clean-src")
        os.makedirs(clean)
        with open(os.path.join(clean, "app.py"), "w", encoding="utf-8") as f:
            f.write("print('hello')\n")
        r = run_from(self.project, scanner, [clean])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_skill_docs_use_plugin_root_not_cwd_relative(self):
        """No SKILL.md may instruct a CWD-relative helper invocation."""
        import glob
        offenders = []
        for path in glob.glob(os.path.join(REPO, "plugins", "*", "skills",
                                           "*", "SKILL.md")):
            with open(path, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if "python3 scripts/" in line or "python scripts/" in line:
                        offenders.append("%s:%d" % (path, i))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
