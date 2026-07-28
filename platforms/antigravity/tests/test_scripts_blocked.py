"""End-to-end script behavior: every network script refuses private/metadata
targets with a clear BLOCKED result (pre-connect, so fully offline), and runs
correctly against the loopback fixture server."""
import os
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixture_server  # noqa: E402

SD = os.path.join(REPO, "plugins", "site-doctor", "skills")
S = {
    "headers": os.path.join(SD, "website-audit", "scripts", "check_headers.py"),
    "links": os.path.join(SD, "website-audit", "scripts", "check_links.py"),
    "trackers": os.path.join(SD, "compliance-check", "scripts", "scan_trackers.py"),
    "mobile": os.path.join(SD, "mobile-audit", "scripts", "check_mobile.py"),
    "meta": os.path.join(SD, "seo-optimization", "scripts", "extract_meta.py"),
    "email": os.path.join(SD, "email-deliverability", "scripts", "check_email_dns.py"),
}
URL_GUARD_LIB = os.path.join(REPO, "plugins", "site-doctor", "lib")

# The production URL guard deliberately has no environment-variable bypass.
# Local fixture happy paths therefore run through this test-process-only
# harness, which injects the documented ``extra_allowed`` function argument
# before executing the real CLI script. Nothing in the shipped helpers reads
# this harness or admits private addresses from ambient process state.
FIXTURE_HARNESS = r"""
import runpy
import sys

lib_dir, script, *script_args = sys.argv[1:]
sys.path.insert(0, lib_dir)
import url_guard

real_check_url = url_guard.check_url

def fixture_check_url(url, allow_http=False, extra_allowed=()):
    allowed = tuple(extra_allowed) + ("127.0.0.1", "::1")
    return real_check_url(url, allow_http=allow_http, extra_allowed=allowed)

url_guard.check_url = fixture_check_url
sys.argv = [script] + script_args
runpy.run_path(script, run_name="__main__")
"""


def run(script, args, env_extra=None, allow_fixture=False):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("URL_GUARD_EXTRA_ALLOWED", None)
    env.pop("URL_GUARD_TEST_MODE", None)
    env.update(env_extra or {})
    command = ([sys.executable, "-c", FIXTURE_HARNESS,
                URL_GUARD_LIB, script] + args if allow_fixture
               else [sys.executable, script] + args)
    return subprocess.run(command, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=120, cwd=REPO, env=env)


class BlockedTargets(unittest.TestCase):
    """Private/metadata IP literals: refused before any socket operation."""

    def test_url_scripts_block_private_and_metadata(self):
        cases = [
            ("headers", ["https://10.0.0.1/"], 2),
            ("links", ["https://169.254.169.254/", "--max-pages", "2",
                       "--delay", "0"], 2),
            ("trackers", ["https://192.168.1.10/"], 2),
            ("mobile", ["https://169.254.169.254/latest/meta-data/"], 2),
            ("meta", ["https://100.100.100.200/", "--max-pages", "2",
                      "--delay", "0"], 2),
        ]
        for name, args, want_rc in cases:
            r = run(S[name], args)
            self.assertEqual(r.returncode, want_rc, (name, r.stdout, r.stderr))
            self.assertIn("BLOCKED", r.stdout, name)

    def test_email_blocks_unsafe_doh_override(self):
        r = run(S["email"], ["example.com"],
                {"SITE_DOCTOR_DOH": "https://10.0.0.99/dns-query"})
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("BLOCKED unsafe DoH endpoint", r.stdout, r.stderr)

    def test_scheme_refused(self):
        r = run(S["headers"], ["ftp://example.com/"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("BLOCKED", r.stdout)


class FixtureHappyPaths(unittest.TestCase):
    """The scripts still do their jobs against a loopback fixture site."""

    @classmethod
    def setUpClass(cls):
        cls.srv, cls.base = fixture_server.start()

    @classmethod
    def tearDownClass(cls):
        fixture_server.stop(cls.srv)

    def test_check_headers_reports(self):
        r = run(S["headers"], [self.base + "/ok"], allow_fixture=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)  # fixture lacks sec headers
        self.assertIn("Missing header: strict-transport-security", r.stdout)
        self.assertIn("Cookie 'sid'", r.stdout)

    def test_check_headers_fails_unsuccessful_target(self):
        r = run(S["headers"], [self.base + "/missing"], allow_fixture=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("Target returned HTTP 404", r.stdout)
        self.assertNotIn("[PASS]", r.stdout)

    def test_check_headers_rejects_terminal_redirect_status(self):
        r = run(S["headers"], [self.base + "/terminal-redirect"],
                allow_fixture=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("Target returned HTTP 302", r.stdout)
        self.assertNotIn("Missing header", r.stdout)

    def test_check_links_finds_broken(self):
        r = run(S["links"], [self.base + "/linkcheck", "--max-pages", "5",
                             "--delay", "0"], allow_fixture=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("BROKEN", r.stdout)
        self.assertIn("/missing", r.stdout)

    def test_scan_trackers_detects_gtm(self):
        r = run(S["trackers"], [self.base + "/ok"], allow_fixture=True)
        # a tracker with NO consent tool is a FAIL verdict -> exit 1
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("Google Tag Manager", r.stdout)
        self.assertIn("[FAIL]", r.stdout)
        self.assertIn("RESULT: ", r.stdout)
        self.assertIn("cookie #1", r.stdout)
        self.assertNotIn("sid", r.stdout)

    def test_scan_trackers_rejects_incomplete_coverage(self):
        cases = [
            ("/missing", 2, "HTTP 404"),
            ("/terminal-redirect", 2, "HTTP 302"),
            ("/health", 3, "not HTML"),
            ("/empty", 3, "body is empty"),
            ("/big", 3, "scan limit"),
            ("/utf16", 3, "unsupported HTML charset"),
        ]
        for path, want_rc, marker in cases:
            r = run(S["trackers"], [self.base + path], allow_fixture=True)
            self.assertEqual(r.returncode, want_rc,
                             (path, r.stdout, r.stderr))
            self.assertIn(marker, r.stdout, path)
            self.assertIn("unverified=1", r.stdout, path)
            self.assertNotIn("[PASS]", r.stdout, path)

    def test_check_mobile_sees_viewport(self):
        r = run(S["mobile"], [self.base + "/ok"], allow_fixture=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("viewport meta tag", r.stdout)
        self.assertIn("[PASS]", r.stdout)

    def test_extract_meta_crawls(self):
        r = run(S["meta"], [self.base + "/seo-clean", "--max-pages", "3",
                            "--delay", "0"], allow_fixture=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("SEO Start", r.stdout)
        self.assertIn("Page Two", r.stdout)

    def test_extract_meta_failed_page_is_incomplete(self):
        r = run(S["meta"], [self.base + "/ok", "--max-pages", "3",
                            "--delay", "0"], allow_fixture=True)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("attempted page(s) could not be completely audited",
                      r.stdout)
        self.assertIn("HTTP 404", r.stdout)

    def test_extract_meta_truncated_page_is_incomplete(self):
        r = run(S["meta"], [self.base + "/big", "--max-pages", "1",
                            "--delay", "0"], allow_fixture=True)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("crawl limit", r.stdout)
        self.assertIn("[UNVERIFIED]", r.stdout)

    def test_extract_meta_rejects_terminal_redirect_and_unsupported_charset(self):
        for path, marker in (("/terminal-redirect", "HTTP 302"),
                             ("/utf16", "unsupported HTML charset")):
            r = run(S["meta"], [self.base + path, "--max-pages", "1",
                                "--delay", "0"], allow_fixture=True)
            self.assertEqual(r.returncode, 3, (path, r.stdout, r.stderr))
            self.assertIn(marker, r.stdout)
            self.assertIn("[UNVERIFIED]", r.stdout)

    def test_extract_meta_preserves_subdirectory_trailing_slash(self):
        r = run(S["meta"], [self.base + "/docs/", "--max-pages", "2",
                            "--delay", "0"], allow_fixture=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(self.base + "/docs/child", r.stdout)
        self.assertIn("Docs Child", r.stdout)
        self.assertNotIn(self.base + "/child", r.stdout)

    def test_check_email_dns_via_fixture_doh(self):
        env = {"SITE_DOCTOR_DOH": self.base + "/dns-query"}
        r = run(S["email"], ["example.com", "--dkim-selector", "s1"], env,
                allow_fixture=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("SPF present", r.stdout)
        self.assertIn("DMARC present", r.stdout)
        self.assertIn("DKIM key found", r.stdout)

    def test_check_email_dns_meaningful_exit_codes(self):
        env = {"SITE_DOCTOR_DOH": self.base + "/dns-query"}
        failed = run(S["email"], ["missing.example", "--dkim-selector",
                                  "s1"], env, allow_fixture=True)
        self.assertEqual(failed.returncode, 1,
                         failed.stdout + failed.stderr)
        self.assertIn("fail=", failed.stdout)

        incomplete = run(S["email"], ["example.com"], env,
                         allow_fixture=True)
        self.assertEqual(incomplete.returncode, 3,
                         incomplete.stdout + incomplete.stderr)
        self.assertIn("DKIM can't be checked", incomplete.stdout)
        self.assertIn("unverified=1", incomplete.stdout)

        unavailable = run(
            S["email"], ["example.com", "--dkim-selector", "s1"],
            {"SITE_DOCTOR_DOH": self.base + "/missing"},
            allow_fixture=True)
        self.assertEqual(unavailable.returncode, 2,
                         unavailable.stdout + unavailable.stderr)
        self.assertIn("DoH endpoint returned HTTP 404", unavailable.stdout)

        for path, marker in (("/terminal-redirect", "HTTP 302"),
                             ("/dns-truncated", "TC=true"),
                             ("/dns-nxdomain-answer", "NXDOMAIN")):
            unsafe = run(
                S["email"], ["example.com", "--dkim-selector", "s1"],
                {"SITE_DOCTOR_DOH": self.base + path},
                allow_fixture=True)
            self.assertEqual(unsafe.returncode, 2,
                             (path, unsafe.stdout, unsafe.stderr))
            self.assertIn(marker, unsafe.stdout)

    def test_check_email_dns_rejects_invalid_domain(self):
        r = run(S["email"], ["not a domain"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("Invalid domain", r.stdout)


if __name__ == "__main__":
    unittest.main()
