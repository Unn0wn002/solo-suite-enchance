"""Regression tests for the v1.0.11 helper-script defect fixes (one test
class per script; every repaired defect has a test)."""
import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from email.message import Message
from types import SimpleNamespace
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SD = os.path.join(REPO, "plugins", "site-doctor", "skills")


def load(name, *parts):
    path = os.path.join(SD, *parts)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


headers_mod = load("check_headers_mod", "website-audit", "scripts", "check_headers.py")
links_path = os.path.join(SD, "website-audit", "scripts", "check_links.py")
links_mod = load("check_links_mod", "website-audit", "scripts", "check_links.py")
email_mod = load("check_email_mod", "email-deliverability", "scripts", "check_email_dns.py")
meta_mod = load("extract_meta_mod", "seo-optimization", "scripts", "extract_meta.py")
trackers_mod = load("scan_trackers_mod", "compliance-check", "scripts", "scan_trackers.py")
deps_mod = load("check_deps_mod", "dependency-audit", "scripts", "check_deps.py")


def capture(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*a, **kw)
    return buf.getvalue()


class CheckHeaders(unittest.TestCase):
    def setUp(self):
        headers_mod.results.update(PASS=0, WARN=0, FAIL=0, UNVERIFIED=0)
        self._fetch = headers_mod.fetch
        self.addCleanup(lambda: setattr(headers_mod, "fetch", self._fetch))

    def test_sensitive_path_timeout_is_not_pass(self):
        """Defect 1: timeout/error used to be reported as PASS."""
        headers_mod.fetch = lambda url, **kw: (None, {"_error": "timed out"}, [])
        out = capture(headers_mod.check_sensitive_paths, "https://example.com/")
        self.assertIn("could not be verified", out)
        self.assertIn("NOT a pass", out)
        self.assertNotIn("[PASS]", out)

    def test_sensitive_path_404_still_passes(self):
        headers_mod.fetch = lambda url, **kw: (404, {}, [])
        out = capture(headers_mod.check_sensitive_paths, "https://example.com/")
        self.assertIn("[PASS]", out)

    def test_hsts_max_age_zero_fails(self):
        h = {"strict-transport-security": "max-age=0",
             "x-content-type-options": "nosniff"}
        out = capture(headers_mod.check_security_headers, h)
        self.assertIn("DISABLES HSTS", out)

    def test_hsts_missing_max_age_fails(self):
        h = {"strict-transport-security": "includeSubDomains"}
        out = capture(headers_mod.check_security_headers, h)
        self.assertIn("NO max-age", out)

    def test_hsts_non_numeric_max_age_fails(self):
        h = {"strict-transport-security": "max-age=banana"}
        out = capture(headers_mod.check_security_headers, h)
        self.assertIn("not a valid number", out)

    def test_hsts_duplicate_directive_fails(self):
        h = {"strict-transport-security": "max-age=63072000; max-age=1"}
        out = capture(headers_mod.check_security_headers, h)
        self.assertIn("duplicate directive", out)

    def test_hsts_preload_requirements(self):
        h = {"strict-transport-security": "max-age=15552000; preload"}
        out = capture(headers_mod.check_security_headers, h)
        self.assertIn("preload", out.lower())
        self.assertIn("includeSubDomains", out)

    def test_redirect_to_unrelated_https_host_fails(self):
        """Defect 3: redirect to an unrelated HTTPS host counted as success."""
        headers_mod.fetch = lambda url, **kw: (
            301, {"location": "https://evil.example/phish"}, [])
        out = capture(headers_mod.check_https_redirect, "https://example.com/")
        self.assertIn("UNRELATED origin", out)
        self.assertNotIn("redirects permanently to HTTPS (same site)", out)

    def test_redirect_to_www_variant_passes(self):
        headers_mod.fetch = lambda url, **kw: (
            301, {"location": "https://www.example.com/"}, [])
        out = capture(headers_mod.check_https_redirect, "https://example.com/")
        self.assertIn("(same site)", out)

    def test_same_site_parses_ipv6_structurally(self):
        # T-006: check_headers' local `same_site` was consolidated into
        # url_guard.same_site_url, which it now imports.
        self.assertTrue(headers_mod.same_site_url(
            "[2001:db8::1]:443", "[2001:db8::1]:8443"))
        self.assertFalse(headers_mod.same_site_url(
            "[2001:db8::1]:443", "[2001:db8::2]:443"))

    def test_fetch_rejects_unrelated_final_redirect_host(self):
        headers = Message()
        response = SimpleNamespace(
            status=200, headers=headers,
            url="https://elsewhere.example/", body=None, truncated=False)
        with mock.patch.object(headers_mod, "safe_get", return_value=response):
            status, returned, _cookies = headers_mod.fetch(
                "https://target.example/")
        self.assertIsNone(status)
        self.assertIn("unrelated origin", returned["_error"])

        response.url = "https://target.example:8443/"
        with mock.patch.object(headers_mod, "safe_get", return_value=response):
            status, returned, _cookies = headers_mod.fetch(
                "https://target.example/")
        self.assertIsNone(status)
        self.assertIn("unrelated origin", returned["_error"])

    def test_https_upgrade_rejects_alt_port_and_hostless_destination(self):
        for location in ("https://example.com:8443/", "https:garbage"):
            headers_mod.results.update(PASS=0, WARN=0, FAIL=0, UNVERIFIED=0)
            headers_mod.fetch = lambda url, **kw: (
                301, {"location": location}, [])
            out = capture(headers_mod.check_https_redirect,
                          "https://example.com/")
            self.assertIn("[FAIL]", out, location)
            self.assertNotIn("redirects permanently to HTTPS", out, location)

    def test_every_redirect_hop_validated(self):
        """Defect 4: only the first hop used to be inspected."""
        hops = {"http://example.com/": "http://example.com/a",
                "http://example.com/a": "https://other-host.example/b"}
        headers_mod.fetch = lambda url, **kw: (
            (301, {"location": hops[url]}, []) if url in hops
            else (200, {}, []))
        out = capture(headers_mod.check_https_redirect, "https://example.com/")
        self.assertIn("UNRELATED origin at hop 2", out)

    def test_duplicate_csp_directive_fails_with_unsafe_first_value(self):
        value = "default-src 'self'; script-src *; script-src 'self'"
        level, message = headers_mod.validate_csp(value)
        self.assertEqual(level, "FAIL")
        self.assertIn("duplicate directive", message)
        self.assertIn("script-src", message)

        headers_mod.results.update(PASS=0, WARN=0, FAIL=0, UNVERIFIED=0)
        capture(headers_mod.check_security_headers, {
            "strict-transport-security": "max-age=63072000",
            "x-content-type-options": "nosniff",
            "content-security-policy": value,
        })
        self.assertGreater(headers_mod.results["FAIL"], 0)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = headers_mod.main([])
        self.assertEqual(rc, 1)


class CheckLinks(unittest.TestCase):
    def run_script(self, *args):
        return subprocess.run(
            [sys.executable, links_path] + list(args), capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=60,
            env=dict(os.environ, PYTHONIOENCODING="utf-8"))

    def test_rejects_non_positive_max_pages(self):
        r = self.run_script("https://example.com", "--max-pages", "0")
        self.assertEqual(r.returncode, 2)
        self.assertIn("positive", r.stderr)

    def test_rejects_negative_delay(self):
        r = self.run_script("https://example.com", "--delay", "-1")
        self.assertEqual(r.returncode, 2)

    def test_source_enforces_redirect_and_mixed_flags(self):
        with open(links_path, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("--max-redirect-hops", src)
        self.assertIn("long_chains", src)
        self.assertNotIn("chains collapse in urllib", src,
                         "redirect chains must be enforced, not ignored")
        self.assertIn("args.fail_on_mixed and bool(mixed)", src)

    def test_rejects_non_positive_global_budgets(self):
        for flag in ("--max-urls", "--max-requests", "--max-total-bytes",
                     "--max-seconds", "--max-output-findings"):
            r = self.run_script("https://example.com", flag, "0")
            self.assertEqual(r.returncode, 2, (flag, r.stdout, r.stderr))

    def test_source_enforces_global_request_byte_and_output_budgets(self):
        with open(links_path, encoding="utf-8") as f:
            src = f.read()
        for token in ("--max-urls", "--max-requests", "--max-total-bytes",
                      "--max-seconds", "--max-output-findings",
                      "_budget_exhausted"):
            self.assertIn(token, src)

    def test_request_uses_remaining_time_and_byte_budget(self):
        seen = {}

        def fake_get(url, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(
                status=200, url=url, hops=0, headers={}, body=b"x",
                truncated=True)

        budget = {
            "deadline": links_mod.time.monotonic() + 2.0,
            "requests": 0,
            "max_requests": 3,
            "bytes": 9,
            "max_bytes": 10,
            "reason": None,
        }
        with mock.patch.object(links_mod, "safe_get", fake_get):
            result = links_mod.request("https://example.com", "GET", budget)
        self.assertEqual(seen["max_bytes"], 1)
        self.assertGreater(seen["timeout"], 0)
        self.assertLessEqual(seen["timeout"], 2.0)
        self.assertTrue(result[-1])
        self.assertIn("truncated", budget["reason"])

    def test_delay_is_capped_by_remaining_wall_clock_budget(self):
        budget = {"deadline": 0.25, "reason": None}
        with mock.patch.object(links_mod.time, "monotonic",
                               side_effect=[0.0, 0.25]), \
                mock.patch.object(links_mod.time, "sleep") as sleeper:
            usable = links_mod._sleep_with_budget(5.0, budget)
        self.assertFalse(usable)
        sleeper.assert_called_once_with(0.25)
        self.assertEqual(budget["reason"], "wall-clock budget reached")


class CheckEmailDns(unittest.TestCase):
    def setUp(self):
        email_mod.results.update(PASS=0, WARN=0, FAIL=0, UNVERIFIED=0)
        self._q = email_mod.dns_query
        self.addCleanup(lambda: setattr(email_mod, "dns_query", self._q))

    def fake_dns(self, table):
        email_mod.dns_query = lambda name, rrtype: table.get(name.lower(), [])

    def test_sp_reject_does_not_masquerade_as_p_reject(self):
        """Defect: 'sp=reject' contains the substring 'p=reject'."""
        self.fake_dns({"_dmarc.example.com":
                       ["v=DMARC1; p=none; sp=reject; rua=mailto:d@example.com"]})
        out = capture(email_mod.check_dmarc, "example.com")
        self.assertIn("p=none", out)
        self.assertIn("MONITOR ONLY", out)
        self.assertNotIn("p=reject — strongest", out)
        self.assertIn("sp=reject", out)
        self.assertIn("SUBDOMAINS only", out)

    def test_missing_base_policy_fails(self):
        self.fake_dns({"_dmarc.example.com": ["v=DMARC1; sp=reject"]})
        out = capture(email_mod.check_dmarc, "example.com")
        self.assertIn("no base 'p='", out)

    def test_real_p_reject_still_passes(self):
        self.fake_dns({"_dmarc.example.com": ["v=DMARC1; p=reject; rua=mailto:d@e.com"]})
        out = capture(email_mod.check_dmarc, "example.com")
        self.assertIn("p=reject — strongest", out)

    def test_dmarc_rejects_multiple_duplicate_and_misordered_records(self):
        cases = [
            ["v=DMARC1; p=reject", "v=DMARC1; p=none"],
            ["v=DMARC1; p=reject; p=none"],
            ["p=reject; v=DMARC1; rua=mailto:d@example.com"],
        ]
        for records in cases:
            email_mod.results.update(PASS=0, WARN=0, FAIL=0, UNVERIFIED=0)
            self.fake_dns({"_dmarc.example.com": records})
            out = capture(email_mod.check_dmarc, "example.com")
            self.assertIn("[FAIL]", out, records)
            self.assertNotIn("DMARC present", out, records)

    def test_dkim_requires_one_exact_nonempty_p_tag(self):
        cases = [
            ["v=DKIM1; p=; t=y"],
            ["v=DKIM1; np=abc; p="],
            ["v=DKIM1; p=abc; p="],
            ["p=abc; v=DKIM1"],
            ["v=DKIM1; p=abc", "v=DKIM1; p=def"],
        ]
        name = "s1._domainkey.example.com"
        for records in cases:
            email_mod.results.update(PASS=0, WARN=0, FAIL=0, UNVERIFIED=0)
            self.fake_dns({name: records})
            out = capture(email_mod.check_dkim, "example.com", "s1")
            self.assertIn("[FAIL]", out, records)
            self.assertNotIn("DKIM key found", out, records)

    def test_ambiguous_auth_record_makes_full_helper_fail(self):
        def query(name, rrtype):
            if rrtype == "MX":
                return ["10 mail.example.com."]
            if name == "example.com":
                return ["v=spf1 -all"]
            if name == "_dmarc.example.com":
                return ["v=DMARC1; p=reject; p=none"]
            if name == "s1._domainkey.example.com":
                return ["v=DKIM1; p=abc"]
            return []

        email_mod.dns_query = query
        with mock.patch.object(sys, "argv", [
                "check_email_dns.py", "example.com", "--dkim-selector",
                "s1"]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                rc = email_mod.main()
        self.assertEqual(rc, 1, output.getvalue())
        self.assertIn("duplicate tag(s): p", output.getvalue())

    def test_spf_exact_version_and_default_all_qualifier_fail_closed(self):
        def run_with_spf(spf):
            def query(name, rrtype):
                if rrtype == "MX":
                    return ["10 mail.example.com."]
                if name == "example.com":
                    return [spf]
                if name == "_dmarc.example.com":
                    return ["v=DMARC1; p=reject; rua=mailto:d@example.com"]
                if name == "s1._domainkey.example.com":
                    return ["v=DKIM1; p=abc"]
                return []

            email_mod.dns_query = query
            with mock.patch.object(sys, "argv", [
                    "check_email_dns.py", "example.com", "--dkim-selector",
                    "s1"]):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    rc = email_mod.main()
            return rc, output.getvalue()

        for record in ("v=spf1 all", "v=spf10 -all"):
            rc, out = run_with_spf(record)
            self.assertNotEqual(rc, 0, (record, out))
            self.assertIn("[FAIL]", out, record)

        email_mod.results.update(PASS=0, WARN=0, FAIL=0, UNVERIFIED=0)
        self.fake_dns({"example.com": [
            "v=spf1 include:mail-all.example ~all"]})
        out = capture(email_mod.check_spf, "example.com")
        self.assertIn("exact '~all' softfail", out)
        self.assertNotIn("hardfail mechanism", out)

    def test_nested_spf_lookups_counted(self):
        """Defect: nested include: lookups were not counted."""
        self.fake_dns({
            "example.com": ["v=spf1 include:a.example -all"],
            "a.example": ["v=spf1 include:b.example a mx -all"],
            "b.example": ["v=spf1 exists:%{i}.x.example ptr -all"],
        })
        total, capped = email_mod.count_spf_lookups(
            "example.com", "v=spf1 include:a.example -all")
        # include:a(1) + [include:b(1) + a(1) + mx(1)] + [exists(1) + ptr(1)] = 6
        self.assertEqual(total, 6)
        # exists:/ptr count as lookups but are never recursed into, so the
        # count is complete (not capped) here
        self.assertFalse(capped)

    def test_spf_cycle_protection(self):
        self.fake_dns({
            "example.com": ["v=spf1 include:loop.example -all"],
            "loop.example": ["v=spf1 include:example.com -all"],
        })
        total, capped = email_mod.count_spf_lookups(
            "example.com", "v=spf1 include:loop.example -all")
        self.assertTrue(capped)
        self.assertLessEqual(total, 3)

    def test_bare_a_and_mx_counted(self):
        total, _ = email_mod.count_spf_lookups(
            "example.com", "v=spf1 a mx ip4:1.2.3.4 -all")
        self.assertEqual(total, 2)  # ip4 costs no lookup


class ExtractMeta(unittest.TestCase):
    def parse(self, html):
        p = meta_mod.MetaParser()
        p.feed(html)
        return p

    def test_h1_with_nested_spans_counted_once(self):
        """Defect: each text node inside one H1 was counted as its own H1."""
        p = self.parse("<h1>Hello <span>World</span> <em>Again</em></h1>")
        self.assertEqual(len(p.h1s), 1)
        self.assertEqual(p.h1s[0], "Hello World Again")

    def test_two_real_h1s_counted_twice(self):
        p = self.parse("<h1>One</h1><p>x</p><h1>Two <b>Bold</b></h1>")
        self.assertEqual(p.h1s, ["One", "Two Bold"])

    def test_empty_h1_still_counted(self):
        p = self.parse("<h1></h1>")
        self.assertEqual(p.h1s, [""])

    def test_fetch_rejects_terminal_statuses_and_cross_host_final(self):
        headers = Message()
        headers["Content-Type"] = "text/html; charset=utf-8"
        body = (b"<html><head><title>x</title></head><body><h1>x</h1>"
                b"</body></html>")
        for status in (300, 302, 304):
            response = SimpleNamespace(
                status=status, headers=headers, body=body, truncated=False,
                url="https://target.example/")
            with mock.patch.object(meta_mod, "safe_get",
                                   return_value=response):
                result = meta_mod.fetch("https://target.example/")
            self.assertIsNone(result[1], status)
            self.assertEqual(result[3][0], "http-error", status)
        response = SimpleNamespace(
            status=200, headers=headers, body=body, truncated=False,
            url="https://elsewhere.example/")
        with mock.patch.object(meta_mod, "safe_get", return_value=response):
            result = meta_mod.fetch("https://target.example/")
        self.assertEqual(result[3][0], "redirect-host")
        self.assertIsNone(result[1])

        response.url = "https://target.example:8443/"
        with mock.patch.object(meta_mod, "safe_get", return_value=response):
            result = meta_mod.fetch("https://target.example/")
        self.assertEqual(result[3][0], "redirect-host")
        self.assertIsNone(result[1])

    def test_alt_port_link_is_not_enqueued(self):
        headers = Message()
        headers["Content-Type"] = "text/html; charset=utf-8"
        body = (b"<html><head><title>x</title>"
                b"<meta name='description' content='x'></head>"
                b"<body><h1>x</h1>"
                b"<a href='https://target.example:8443/secret'>bad</a>"
                b"</body></html>")
        calls = []

        def safe_get(url, **_kwargs):
            calls.append(url)
            return SimpleNamespace(status=200, headers=headers, body=body,
                                   truncated=False, url=url)

        argv = ["extract_meta.py", "https://target.example/",
                "--max-pages", "2", "--delay", "0"]
        with mock.patch.object(meta_mod, "safe_get", side_effect=safe_get), \
                mock.patch.object(meta_mod, "check_url"), \
                mock.patch.object(sys, "argv", argv):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                rc = meta_mod.main()
        self.assertEqual(rc, 0, output.getvalue())
        # A bare origin is canonically queued without the redundant root
        # slash; the alternate-port URL must still never be fetched.
        self.assertEqual(calls, ["https://target.example"])


class ScanTrackers(unittest.TestCase):
    def test_img_src_not_double_counted(self):
        """Defect: <img src> was appended twice; duplicates inflated counts."""
        p = trackers_mod.SrcParser()
        p.feed('<img src="https://t.example/px.gif">'
               '<img src="https://t.example/px.gif">'
               '<script src="https://t.example/px.gif"></script>')
        self.assertEqual(p.srcs, ["https://t.example/px.gif"])

    def test_cookie_flags_parsed_structurally(self):
        """Defect: substring matching flagged cookie VALUES like 'xsecurex'."""
        with open(os.path.join(SD, "compliance-check", "scripts",
                               "scan_trackers.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("Structural parse", src)
        self.assertIn('partition("=")', src)
        self.assertNotIn('if f in low', src)

    def test_fetch_rejects_terminal_statuses_and_cross_host_final(self):
        headers = Message()
        headers["Content-Type"] = "text/html; charset=utf-8"
        body = b"<html><head><title>x</title></head><body></body></html>"
        for status in (300, 302, 304):
            response = SimpleNamespace(
                status=status, headers=headers, body=body, truncated=False,
                url="https://target.example/")
            with mock.patch.object(trackers_mod, "safe_get",
                                   return_value=response):
                result = trackers_mod.fetch("https://target.example/")
            self.assertIn("HTTP %s" % status, result[3])
            self.assertFalse(result[2])
        response = SimpleNamespace(
            status=200, headers=headers, body=body, truncated=False,
            url="https://elsewhere.example/")
        with mock.patch.object(trackers_mod, "safe_get",
                               return_value=response):
            result = trackers_mod.fetch("https://target.example/")
        self.assertIn("unrelated origin", result[3])
        self.assertFalse(result[2])

    def test_output_redacts_url_cookie_origin_and_header_values(self):
        secret_url = ("https://URLUSERSECRET:URLPASSWORD@target.example/SECRET_PATH"
                      "?access_token=URLSECRET#SECRET_FRAGMENT")
        cookies = [
            "SECRET_COOKIE=COOKIE_VALUE; SameSite=SECRET_SAMESITE; "
            "Expires=SECRET_DATE",
            "MALFORMED_COOKIE_SECRET",
        ]
        html = ("<script src='https://ORIGINUSERSECRET:ORIGIN_PASSWORD@evil.example/"
                "SECRET_RESOURCE?token=RESOURCE_SECRET'></script>")
        fetched = (200, cookies, html, None, "https://target.example/")
        with mock.patch.object(trackers_mod, "fetch", return_value=fetched):
            out = capture(trackers_mod.main, secret_url)
        for secret in (
                "URLUSERSECRET", "URLPASSWORD", "SECRET_PATH", "URLSECRET",
                "SECRET_FRAGMENT", "SECRET_COOKIE", "COOKIE_VALUE",
                "SECRET_SAMESITE", "SECRET_DATE", "MALFORMED_COOKIE_SECRET",
                "ORIGINUSERSECRET", "ORIGIN_PASSWORD", "evil.example",
                "SECRET_RESOURCE", "RESOURCE_SECRET"):
            self.assertNotIn(secret, out)
        self.assertIn("host-id=", out)
        self.assertIn("query-fields=1", out)
        self.assertIn("userinfo=present", out)
        self.assertIn("cookie #1", out)
        self.assertIn("samesite=invalid", out)
        self.assertIn("persistent-expires", out)
        self.assertIn("cookie #2 (malformed)", out)

    def test_fetch_errors_never_echo_target_or_exception(self):
        target = "https://target.example/?token=URLSECRET"
        with mock.patch.object(trackers_mod, "safe_get",
                               side_effect=RuntimeError("EXCEPTION_SECRET")):
            out = capture(trackers_mod.fetch, target, detailed=True)
        self.assertIn("details redacted", out)
        self.assertNotIn("URLSECRET", out)
        self.assertNotIn("EXCEPTION_SECRET", out)

        with mock.patch.object(
                trackers_mod, "safe_get",
                side_effect=trackers_mod.BlockedUrlError("BLOCKED_SECRET")):
            out = capture(trackers_mod.fetch, target, detailed=True)
        self.assertIn("details redacted", out)
        self.assertNotIn("URLSECRET", out)
        self.assertNotIn("BLOCKED_SECRET", out)

    def test_redirect_problem_does_not_echo_destination(self):
        headers = Message()
        headers["Content-Type"] = "text/html; charset=utf-8"
        response = SimpleNamespace(
            status=200, headers=headers, body=b"<html></html>",
            truncated=False,
            url="https://elsewhere.example/?token=REDIRECT_SECRET")
        with mock.patch.object(trackers_mod, "safe_get",
                               return_value=response):
            result = trackers_mod.fetch("https://target.example/")
        self.assertEqual(result[3], "redirected to an unrelated origin")
        self.assertNotIn("REDIRECT_SECRET", result[3])

        response.url = "https://target.example:8443/"
        with mock.patch.object(trackers_mod, "safe_get",
                               return_value=response):
            result = trackers_mod.fetch("https://target.example/")
        self.assertIn("unrelated origin", result[3])
        self.assertFalse(result[2])


class CheckDeps(unittest.TestCase):
    def test_full_versions_are_exact(self):
        for spec in ("1.2.3", "v1.2.3", "0.0.1", "1.2.3-beta.1", "1.2.3+build5"):
            self.assertEqual(deps_mod.pin_kind(spec), "exact", spec)

    def test_digit_leading_ranges_are_not_exact(self):
        """Defect: any spec starting with a digit was classified 'exact'."""
        for spec in ("1.x", "1.2.x", "1.2.*", "1.2", "1",
                     "1.2.3 - 2.0.0", "1.2.3 || 2.0.0"):
            self.assertNotEqual(deps_mod.pin_kind(spec), "exact", spec)

    def test_other_kinds_unchanged(self):
        self.assertIn("caret", deps_mod.pin_kind("^1.2.3"))
        self.assertIn("tilde", deps_mod.pin_kind("~1.2.3"))
        self.assertIn("unpinned", deps_mod.pin_kind("*"))
        self.assertEqual(deps_mod.pin_kind("git+https://x.example/r.git"),
                         "non-registry")

    def test_hash_locked_requirements_dev_is_recognized(self):
        with tempfile.TemporaryDirectory() as root:
            lock = os.path.join(root, "requirements-dev.lock")
            with open(lock, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("demo-package==1.2.3 \\\n")
                fh.write("    --hash=sha256:" + "a" * 64 + "\n")
            out = capture(deps_mod.main, root)
        self.assertIn("=== Python ===", out)
        self.assertIn("requirements-dev.lock entries: 1", out)
        self.assertIn("[ok] hash-locked requirements file", out)
        self.assertNotIn("No recognized dependency manifests", out)
        self.assertIn("--require-hashes -r requirements-dev.lock", out)


if __name__ == "__main__":
    unittest.main()


class AdversarialV1012(unittest.TestCase):
    """v1.0.12 adversarial helper-defect regressions."""

    # ---- scan_secrets: max-bytes must be positive --------------------------
    def test_scan_secrets_rejects_non_positive_max_bytes(self):
        scanner = os.path.join(SD, "security-review", "scripts",
                               "scan_secrets.py")
        for bad in ("0", "-5"):
            r = subprocess.run(
                [sys.executable, scanner, ".", "--max-bytes", bad],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60, cwd=REPO,
                env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            self.assertEqual(r.returncode, 2, (bad, r.stdout, r.stderr))
            self.assertIn("positive", r.stdout)

    # ---- check_headers: structural cookie attribute parsing ----------------
    def setUp(self):
        headers_mod.results.update(PASS=0, WARN=0, FAIL=0, UNVERIFIED=0)

    def test_cookie_value_containing_flag_words_is_not_flagged(self):
        """A VALUE containing 'secure'/'httponly'/'samesite' must not count
        as the flags being present."""
        out = capture(headers_mod.check_cookies,
                      ["sid=xxsecurexx-httponly-samesite; Path=/"])
        self.assertIn("missing flags", out)
        self.assertIn("secure", out)
        self.assertIn("httponly", out)
        self.assertIn("samesite", out)

    def test_real_flags_parsed_structurally(self):
        out = capture(headers_mod.check_cookies,
                      ["sid=abc; Secure; HttpOnly; SameSite=Lax"])
        self.assertIn("has Secure/HttpOnly/SameSite", out)

    def test_parse_cookie_attributes_shape(self):
        name, attrs = headers_mod.parse_cookie_attributes(
            "tok=v; Secure; Max-Age=3600; SameSite=Strict")
        self.assertEqual(name, "tok")
        self.assertEqual(attrs["max-age"], "3600")
        self.assertEqual(attrs["samesite"], "Strict")
        self.assertIn("secure", attrs)

    # ---- check_headers: malformed HSTS must never crash --------------------
    def test_malformed_hsts_with_preload_does_not_crash(self):
        h = {"strict-transport-security": "max-age=banana; preload"}
        out = capture(headers_mod.check_security_headers, h)  # no exception
        self.assertIn("not a valid number", out)

    def test_hsts_preload_without_numeric_age_warns_not_crashes(self):
        h = {"strict-transport-security": "max-age=; includeSubDomains; preload"}
        out = capture(headers_mod.check_security_headers, h)
        self.assertIn("preload", out.lower())

    # ---- SPF: repeated branches count each evaluation; capped never PASS ---
    def _fake(self, table):
        self._saved = email_mod.dns_query
        email_mod.dns_query = lambda name, rrtype: table.get(name.lower(), [])
        self.addCleanup(lambda: setattr(email_mod, "dns_query", self._saved))

    def test_repeated_spf_branch_counted_each_time(self):
        """a and b BOTH include common: common's lookups cost twice (RFC 7208
        counts evaluations, not unique domains)."""
        self._fake({
            "example.com": ["v=spf1 include:a.example include:b.example -all"],
            "a.example": ["v=spf1 include:common.example -all"],
            "b.example": ["v=spf1 include:common.example -all"],
            "common.example": ["v=spf1 a mx -all"],
        })
        total, capped = email_mod.count_spf_lookups(
            "example.com", "v=spf1 include:a.example include:b.example -all")
        # include:a(1)+include:common(1)+a(1)+mx(1) + include:b(1)+include:common(1)+a(1)+mx(1) = 8
        self.assertEqual(total, 8)
        self.assertFalse(capped)

    def test_true_cycle_still_capped(self):
        self._fake({
            "example.com": ["v=spf1 include:loop.example -all"],
            "loop.example": ["v=spf1 include:example.com -all"],
        })
        total, capped = email_mod.count_spf_lookups(
            "example.com", "v=spf1 include:loop.example -all")
        self.assertTrue(capped)

    def test_capped_count_never_reports_pass(self):
        email_mod.results.update(PASS=0, WARN=0, FAIL=0, UNVERIFIED=0)
        self._fake({
            "example.com": ["v=spf1 include:gone.example ~all"],
            # gone.example resolves to nothing -> capped
        })
        out = capture(email_mod.check_spf, "example.com")
        self.assertIn("INCOMPLETE", out)
        self.assertNotIn("DNS-lookup mechanism(s) incl. nested includes (limit 10)",
                         [l for l in out.splitlines() if "[PASS]" in l])
        pass_lines = [l for l in out.splitlines()
                      if "[PASS]" in l and "lookup" in l.lower()]
        self.assertEqual(pass_lines, [], out)

    # ---- crawler numeric options --------------------------------------------
    def run_meta(self, *args):
        meta_path = os.path.join(SD, "seo-optimization", "scripts",
                                 "extract_meta.py")
        return subprocess.run(
            [sys.executable, meta_path] + list(args), capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=60,
            env=dict(os.environ, PYTHONIOENCODING="utf-8"))

    def test_extract_meta_rejects_non_positive_max_pages(self):
        r = self.run_meta("https://example.com", "--max-pages", "0")
        self.assertEqual(r.returncode, 2)
        self.assertIn("positive", r.stderr)

    def test_extract_meta_rejects_nan_and_inf_delay(self):
        for bad in ("nan", "inf", "-inf", "-1"):
            r = self.run_meta("https://example.com", "--delay=" + bad)
            self.assertEqual(r.returncode, 2, bad)
            self.assertIn("finite", r.stderr)

    def test_check_links_rejects_nan_and_inf_delay(self):
        links = os.path.join(SD, "website-audit", "scripts", "check_links.py")
        for bad in ("nan", "inf"):
            r = subprocess.run(
                [sys.executable, links, "https://example.com", "--delay", bad],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60,
                env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            self.assertEqual(r.returncode, 2, bad)
            self.assertIn("finite", r.stderr)
