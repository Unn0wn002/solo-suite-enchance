"""check_headers.py value validation: presence is never enough. Invalid
CSP, x-content-type-options, referrer-policy, x-frame-options, and cookie
SameSite values must NEVER receive PASS. Offline — pure function calls."""
import contextlib
import importlib.util
import io
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CH = os.path.join(REPO, "plugins", "site-doctor", "skills", "website-audit",
                  "scripts", "check_headers.py")
sys.path.insert(0, os.path.join(REPO, "plugins", "site-doctor", "lib"))
spec = importlib.util.spec_from_file_location("check_headers", CH)
ch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ch)


def run(fn, *args):
    for k in ch.results:
        ch.results[k] = 0
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*args)
    return buf.getvalue().splitlines()


def line_for(lines, frag):
    hits = [l for l in lines if frag in l]
    return hits[0] if hits else ""


class HeaderValueValidation(unittest.TestCase):
    def test_invalid_nosniff_never_pass(self):
        for bad in ("nosniffff", "sniff", "yes", "nosniff; charset=utf8x"):
            ln = line_for(run(ch.check_security_headers,
                              {"x-content-type-options": bad}),
                          "x-content-type-options")
            self.assertNotIn("[PASS]", ln, (bad, ln))
            self.assertIn("[FAIL]", ln, (bad, ln))

    def test_valid_nosniff_passes(self):
        ln = line_for(run(ch.check_security_headers,
                          {"x-content-type-options": "NoSniff"}),
                      "x-content-type-options")
        self.assertIn("[PASS]", ln)

    def test_invalid_referrer_policy_never_pass(self):
        for bad in ("whatever-origin", "none", "strict-origin-when-x",
                    "no-referrer, bogus-token"):
            ln = line_for(run(ch.check_security_headers,
                              {"referrer-policy": bad}), "referrer-policy")
            self.assertNotIn("[PASS]", ln, (bad, ln))
            self.assertIn("[FAIL]", ln, (bad, ln))

    def test_valid_referrer_policy_passes(self):
        ln = line_for(run(ch.check_security_headers,
                          {"referrer-policy":
                           "strict-origin-when-cross-origin"}),
                      "referrer-policy")
        self.assertIn("[PASS]", ln)

    def test_unsafe_url_referrer_policy_warns_not_passes(self):
        ln = line_for(run(ch.check_security_headers,
                          {"referrer-policy": "unsafe-url"}), "referrer")
        self.assertIn("[WARN]", ln)

    def test_garbage_csp_never_pass(self):
        for bad in ("lolnothing here", "defaultsrc self",
                    "; ; ;", "upgrade insecure requests please"):
            lines = run(ch.check_security_headers,
                        {"content-security-policy": bad})
            ln = line_for(lines, "content-security-policy")
            self.assertNotIn("[PASS]", ln, (bad, lines))
            self.assertIn("INVALID", ln, (bad, lines))

    def test_valid_csp_passes(self):
        ln = line_for(run(ch.check_security_headers,
                          {"content-security-policy":
                           "default-src 'self'; img-src *"}),
                      "recognized directives")
        self.assertIn("[PASS]", ln)

    def test_unsafe_inline_csp_warns(self):
        lines = run(ch.check_security_headers,
                    {"content-security-policy":
                     "default-src 'self'; script-src 'unsafe-inline'"})
        self.assertTrue(any("[WARN]" in l and "unsafe-inline" in l
                            for l in lines), lines)

    def test_invalid_xfo_never_pass(self):
        ln = line_for(run(ch.check_security_headers,
                          {"x-frame-options": "ALLOWALL"}), "x-frame-options")
        self.assertIn("[FAIL]", ln)


class CookieSameSiteValidation(unittest.TestCase):
    def test_invalid_samesite_never_pass(self):
        for bad in ("Whatever", "TRUEISH", "0"):
            lines = run(ch.check_cookies,
                        ["sid=abc; Secure; HttpOnly; SameSite=%s" % bad])
            self.assertTrue(any("[FAIL]" in l and "INVALID SameSite" in l
                                for l in lines), (bad, lines))
            self.assertFalse(any("[PASS]" in l for l in lines), (bad, lines))

    def test_samesite_none_without_secure_fails(self):
        lines = run(ch.check_cookies, ["sid=abc; HttpOnly; SameSite=None"])
        self.assertTrue(any("[FAIL]" in l and "Secure" in l for l in lines),
                        lines)

    def test_samesite_none_with_secure_passes(self):
        lines = run(ch.check_cookies,
                    ["sid=abc; Secure; HttpOnly; SameSite=None"])
        self.assertTrue(any("[PASS]" in l for l in lines), lines)

    def test_good_cookie_passes(self):
        lines = run(ch.check_cookies,
                    ["sid=abc; Secure; HttpOnly; SameSite=Lax"])
        self.assertTrue(any("[PASS]" in l for l in lines), lines)

    def test_value_containing_secure_is_not_a_flag(self):
        lines = run(ch.check_cookies, ["sid=xsecurex-samesite-httponly"])
        self.assertTrue(any("missing flags" in l for l in lines), lines)


class PermissionsPolicyAndCspQuality(unittest.TestCase):
    """Acceptance test K: `permissions-policy: banana` and
    `content-security-policy: default-src *` can NEVER receive PASS."""

    def test_K_banana_permissions_policy_never_pass(self):
        level, msg = ch.validate_permissions_policy("banana")
        self.assertEqual(level, "FAIL", msg)
        for bad in ("banana, camera", "geolocation=whenever",
                    "=(self)", "camera=(self unquoted.example)"):
            level, msg = ch.validate_permissions_policy(bad)
            self.assertNotEqual(level, "PASS", (bad, msg))

    def test_valid_permissions_policy_passes(self):
        level, msg = ch.validate_permissions_policy(
            "geolocation=(self), camera=(), fullscreen=*")
        self.assertEqual(level, "PASS", msg)

    def test_unknown_feature_warns_never_passes_clean(self):
        level, msg = ch.validate_permissions_policy(
            "geolocation=(self), bananas=(self)")
        self.assertEqual(level, "WARN", msg)

    def test_K_default_src_star_never_pass(self):
        level, msg = ch.validate_csp("default-src *")
        self.assertEqual(level, "FAIL", msg)
        level, msg = ch.validate_csp("default-src 'self'; script-src *")
        self.assertEqual(level, "FAIL", msg)
        level, msg = ch.validate_csp("default-src 'self'; script-src https:")
        self.assertEqual(level, "FAIL", msg)

    def test_unsafe_eval_warns(self):
        level, msg = ch.validate_csp(
            "default-src 'self'; script-src 'self' 'unsafe-eval'")
        self.assertEqual(level, "WARN", msg)
        self.assertIn("unsafe-eval", msg)

    def test_materially_incomplete_csp_fails(self):
        level, msg = ch.validate_csp("img-src 'self'; font-src 'self'")
        self.assertEqual(level, "FAIL", msg)

    def test_solid_csp_passes(self):
        level, msg = ch.validate_csp(
            "default-src 'self'; script-src 'self'; object-src 'none'")
        self.assertEqual(level, "PASS", msg)


class StructuredLevels(unittest.TestCase):
    def test_unverified_level_exists(self):
        self.assertIn("UNVERIFIED", ch.results)

    def test_docstring_documents_exit_codes(self):
        self.assertIn("3 = ", ch.__doc__)
        self.assertIn("UNVERIFIED", ch.__doc__)


if __name__ == "__main__":
    unittest.main()
