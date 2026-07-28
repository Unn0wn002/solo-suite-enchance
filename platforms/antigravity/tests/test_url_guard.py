"""url_guard policy tests — schemes, private/metadata addresses, hostname
blocklist, DNS-answer validation (mocked resolver: no real lookups), redirect
re-validation, redirect loops, and the response-size cap. Network I/O only to
the 127.0.0.1 fixture server."""
import os
import socket
import sys
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "plugins", "site-doctor", "lib"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import url_guard  # noqa: E402
from url_guard import BlockedUrlError, check_url, safe_get  # noqa: E402
import fixture_server  # noqa: E402

LOOP = ("127.0.0.1",)

BLOCKED_V4 = ["127.0.0.1", "127.8.8.8", "0.0.0.0", "10.0.0.1", "172.16.0.1",
              "172.31.255.255", "192.168.1.1", "169.254.169.254", "100.64.0.1",
              "100.100.100.200", "192.0.0.170", "198.18.0.1", "198.19.255.255",
              "168.63.129.16", "224.0.0.1", "240.0.0.1", "255.255.255.255"]
BLOCKED_V6 = ["::1", "::", "fe80::1", "fd00::1", "ff02::1",
              "::ffff:10.0.0.1", "::ffff:169.254.169.254",
              "64:ff9b::a00:1", "2001::1"]
BLOCKED_HOSTS = ["localhost", "sub.localhost", "foo.internal",
                 "metadata.google.internal", "printer.local", "wpad"]


class SchemePolicy(unittest.TestCase):
    def test_non_http_schemes_blocked(self):
        for u in ("ftp://example.com/x", "file:///etc/passwd",
                  "gopher://example.com/", "javascript:alert(1)",
                  "data:text/html,x", "//example.com/x"):
            with self.assertRaises(BlockedUrlError, msg=u):
                check_url(u)

    def test_http_requires_opt_in(self):
        with self.assertRaises(BlockedUrlError):
            check_url("http://example.com/")


class AddressPolicy(unittest.TestCase):
    def test_blocked_ipv4_literals(self):
        for ip in BLOCKED_V4:
            with self.assertRaises(BlockedUrlError, msg=ip):
                check_url("https://%s/x" % ip)

    def test_blocked_ipv6_literals(self):
        for ip in BLOCKED_V6:
            with self.assertRaises(BlockedUrlError, msg=ip):
                check_url("https://[%s]/x" % ip)

    def test_blocked_hostnames_without_dns(self):
        def boom(*a, **k):
            raise AssertionError("DNS must not be consulted for blocklisted names")
        with mock.patch.object(url_guard.socket, "getaddrinfo", boom):
            for host in BLOCKED_HOSTS:
                with self.assertRaises(BlockedUrlError, msg=host):
                    check_url("https://%s/" % host)

    def test_invalid_port_blocked(self):
        with self.assertRaises(BlockedUrlError):
            check_url("https://example.com:99999/")


class ResolutionPolicy(unittest.TestCase):
    @staticmethod
    def _ai(*addrs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 443)) for a in addrs]

    def test_hostname_resolving_private_blocked(self):
        with mock.patch.object(url_guard.socket, "getaddrinfo",
                               return_value=self._ai("10.9.9.9")):
            with self.assertRaisesRegex(BlockedUrlError, "private"):
                check_url("https://internal-lb.example.com/")

    def test_any_bad_answer_blocks_the_whole_host(self):
        with mock.patch.object(url_guard.socket, "getaddrinfo",
                               return_value=self._ai("93.184.216.34", "192.168.0.7")):
            with self.assertRaises(BlockedUrlError):
                check_url("https://rebind.example.com/")

    def test_public_answers_pass(self):
        with mock.patch.object(url_guard.socket, "getaddrinfo",
                               return_value=self._ai("93.184.216.34")):
            self.assertEqual(check_url("https://ok.example.com/"),
                             "https://ok.example.com/")

    def test_unresolvable_blocked(self):
        def gaierror(*a, **k):
            raise socket.gaierror("NXDOMAIN")
        with mock.patch.object(url_guard.socket, "getaddrinfo", gaierror):
            with self.assertRaisesRegex(BlockedUrlError, "cannot resolve"):
                check_url("https://nx.example.com/")


class FixtureServerBehavior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv, cls.base = fixture_server.start()

    @classmethod
    def tearDownClass(cls):
        fixture_server.stop(cls.srv)

    def test_plain_fetch(self):
        r = safe_get(self.base + "/ok", allow_http=True, extra_allowed=LOOP)
        self.assertEqual(r.status, 200)
        self.assertIn(b"OK Page", r.body)
        self.assertFalse(r.truncated)
        self.assertEqual(r.hops, 0)

    def test_redirect_followed_and_revalidated(self):
        r = safe_get(self.base + "/redir-ok", allow_http=True, extra_allowed=LOOP)
        self.assertEqual(r.status, 200)
        self.assertEqual(r.hops, 1)
        self.assertTrue(r.url.endswith("/ok"))

    def test_redirect_to_metadata_ip_blocked(self):
        with self.assertRaisesRegex(BlockedUrlError, "link-local"):
            safe_get(self.base + "/redir-private", allow_http=True,
                     extra_allowed=LOOP)

    def test_redirect_loop_capped(self):
        with self.assertRaisesRegex(BlockedUrlError, "too many redirects"):
            safe_get(self.base + "/redir-loop", allow_http=True,
                     extra_allowed=LOOP)

    def test_oversized_response_capped_before_full_read(self):
        cap = 100 * 1024
        r = safe_get(self.base + "/big", allow_http=True, extra_allowed=LOOP,
                     max_bytes=cap)
        self.assertTrue(r.truncated)
        self.assertEqual(len(r.body), cap)

    def test_no_follow_returns_redirect_response(self):
        r = safe_get(self.base + "/redir-ok", allow_http=True,
                     extra_allowed=LOOP, follow_redirects=False)
        self.assertEqual(r.status, 302)
        self.assertTrue(r.headers.get("Location"))

    def test_environment_pair_enables_loopback_fixture(self):
        with mock.patch.dict(os.environ, {
                "URL_GUARD_EXTRA_ALLOWED": "127.0.0.1",
                "URL_GUARD_TEST_MODE": "1"}):
            r = safe_get(self.base + "/ok", allow_http=True)
            self.assertEqual(r.status, 200)

    def test_allowlist_only_does_not_enable_seam(self):
        with mock.patch.dict(os.environ, {
                "URL_GUARD_EXTRA_ALLOWED": "127.0.0.1"}):
            os.environ.pop("URL_GUARD_TEST_MODE", None)
            with self.assertWarns(RuntimeWarning):
                with self.assertRaises(BlockedUrlError):
                    check_url("https://127.0.0.1/")

    def test_test_mode_only_does_not_enable_seam(self):
        with mock.patch.dict(os.environ, {"URL_GUARD_TEST_MODE": "1"}):
            os.environ.pop("URL_GUARD_EXTRA_ALLOWED", None)
            with self.assertWarns(RuntimeWarning):
                with self.assertRaises(BlockedUrlError):
                    check_url("https://127.0.0.1/")

    def test_environment_seam_rejects_non_loopback(self):
        with mock.patch.dict(os.environ, {
                "URL_GUARD_EXTRA_ALLOWED": "10.0.0.1",
                "URL_GUARD_TEST_MODE": "1"}):
            with self.assertWarns(RuntimeWarning):
                with self.assertRaises(BlockedUrlError):
                    check_url("https://10.0.0.1/")

    def test_environment_seam_still_blocks_unlisted_loopback(self):
        with mock.patch.dict(os.environ, {
                "URL_GUARD_EXTRA_ALLOWED": "127.0.0.1",
                "URL_GUARD_TEST_MODE": "1"}):
            with self.assertRaises(BlockedUrlError):
                check_url("https://127.0.0.2/")

    def test_direct_opener_disables_ambient_proxies(self):
        with mock.patch.dict(os.environ, {
                "HTTPS_PROXY": "http://127.0.0.1:9999",
                "HTTP_PROXY": "http://127.0.0.1:9999"}):
            opener = url_guard._build_direct_opener()
        handlers = [h for h in opener.handlers
                    if isinstance(h, url_guard.urllib.request.ProxyHandler)]
        self.assertFalse([h for h in handlers if h.proxies], handlers)


class MirroredCopiesStayIdentical(unittest.TestCase):
    """T-005: the SSRF guard must never drift between its plugin copies.

    Each plugin ships its own copy because plugins install independently
    (``seo`` must work without ``site-doctor``), so the guarantee cannot be
    "one file" -- it has to be "every file byte-identical to the canonical
    one".  A security fix that lands in only one copy fails here.
    """

    CANONICAL = os.path.join(REPO, "plugins", "site-doctor", "lib",
                             "url_guard.py")

    def copies(self):
        found = []
        for dirpath, dirnames, filenames in os.walk(
                os.path.join(REPO, "plugins")):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            if "url_guard.py" in filenames:
                found.append(os.path.join(dirpath, "url_guard.py"))
        return sorted(found)

    def test_canonical_copy_exists(self):
        self.assertTrue(os.path.isfile(self.CANONICAL), self.CANONICAL)

    def test_every_copy_is_byte_identical_to_the_canonical_one(self):
        with open(self.CANONICAL, "rb") as stream:
            canonical = stream.read()
        copies = self.copies()
        # Discovered dynamically: a third copy added later is caught here.
        self.assertGreaterEqual(len(copies), 2, copies)
        for path in copies:
            with open(path, "rb") as stream:
                body = stream.read()
            self.assertEqual(
                body, canonical,
                "%s has drifted from the canonical url_guard.py; edit the "
                "canonical file and mirror it verbatim" % path)

    def test_copies_are_exactly_the_documented_set(self):
        expected = sorted([
            os.path.join(REPO, "plugins", "seo", "lib", "url_guard.py"),
            self.CANONICAL,
        ])
        self.assertEqual(self.copies(), expected)

    def test_canonical_header_names_both_paths(self):
        with open(self.CANONICAL, encoding="utf-8") as stream:
            head = stream.read(2000)
        self.assertIn("CANONICAL SOURCE: plugins/site-doctor/lib/url_guard.py",
                      head)
        self.assertIn("MIRRORED COPY:    plugins/seo/lib/url_guard.py", head)


class OriginBinding(unittest.TestCase):
    """T-006: the origin helpers now live beside the policy they complement."""

    def test_normalized_hostname(self):
        for value, want in [
                ("https://Example.COM", "example.com"),
                ("example.com", "example.com"),
                # A protocol-relative "//host" has no "://", so it is treated
                # as a netloc and double-prefixed -> no host -> None. That
                # fails closed (None never compares equal), so it is the
                # conservative answer, not a match.
                ("//example.com", None),
                ("https://example.com.", "example.com"),
                ("https://example.com:8443", "example.com"),
                ("https://user:pw@example.com", "example.com"),
                ("https://[::1]", "::1"),
                ("", None),
                ("https://", None)]:
            self.assertEqual(url_guard.normalized_hostname(value), want, value)

    def test_unparseable_host_is_never_a_match(self):
        # None must mean "cannot compare", never "equal".
        self.assertFalse(url_guard.same_site_url("", ""))
        self.assertFalse(url_guard.same_site_url("https://", "https://"))
        self.assertFalse(url_guard.same_audit_origin("", ""))

    def test_www_variant_only_not_arbitrary_subdomains(self):
        self.assertTrue(url_guard.same_site_url("https://example.com",
                                                "https://www.example.com"))
        for other in ("https://sub.example.com", "https://a.www.example.com",
                      "https://example.com.evil.test",
                      "https://wwwexample.com"):
            self.assertFalse(
                url_guard.same_site_url("https://example.com", other), other)

    def test_scheme_and_port_binding(self):
        same = url_guard.same_audit_origin
        # identical scheme: effective port must match
        self.assertTrue(same("https://example.com", "https://example.com:443"))
        self.assertTrue(same("http://example.com", "http://example.com:80"))
        self.assertFalse(same("https://example.com", "https://example.com:8443"))
        self.assertFalse(same("http://example.com:8080", "http://example.com"))
        # cross-scheme is refused unless the caller opts into the upgrade
        self.assertFalse(same("http://example.com", "https://example.com"))
        self.assertTrue(same("http://example.com", "https://example.com",
                             allow_http_upgrade=True))

    def test_upgrade_allowance_is_only_80_to_443(self):
        same = url_guard.same_audit_origin
        # non-default ports must not ride the upgrade allowance
        self.assertFalse(same("http://example.com:8080", "https://example.com",
                              allow_http_upgrade=True))
        self.assertFalse(same("http://example.com", "https://example.com:8443",
                              allow_http_upgrade=True))
        # downgrade is never allowed
        self.assertFalse(same("https://example.com", "http://example.com",
                              allow_http_upgrade=True))

    def test_ssrf_sensitive_redirect_targets_are_not_same_origin(self):
        """A redirect off-host must never be accepted as the same origin."""
        for hostile in ("http://169.254.169.254/latest/meta-data/",
                        "http://127.0.0.1:8080/", "http://localhost/",
                        "http://[::1]/", "http://metadata.google.internal/",
                        "https://evil.test/example.com"):
            self.assertFalse(
                url_guard.same_audit_origin("https://example.com", hostile,
                                            allow_http_upgrade=True), hostile)

    def test_malformed_inputs_do_not_raise(self):
        for bad in ("http://[", "https://example.com:notaport",
                    "https://example.com:99999", ":", "///", "http://:80"):
            # must return a bool, never propagate ValueError
            self.assertIn(
                url_guard.same_audit_origin("https://example.com", bad),
                (True, False), bad)
            self.assertIn(url_guard.same_site_url("https://example.com", bad),
                          (True, False), bad)

    def test_helpers_are_importable_from_the_mirrored_copy(self):
        import importlib.util
        path = os.path.join(REPO, "plugins", "seo", "lib", "url_guard.py")
        spec = importlib.util.spec_from_file_location("seo_url_guard", path)
        mirror = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mirror)
        for name in ("normalized_hostname", "same_site_url",
                     "same_audit_origin", "safe_get", "check_url",
                     "BlockedUrlError"):
            self.assertTrue(hasattr(mirror, name), name)


class NoDuplicateOriginHelpers(unittest.TestCase):
    """T-006: exactly the mirrored libs may define the origin helpers."""

    def test_only_url_guard_defines_them(self):
        import re
        pattern = re.compile(
            r"^def (same_audit_origin|same_site_url|normalized_hostname"
            r"|same_site)\b", re.M)
        offenders = []
        for dirpath, dirnames, filenames in os.walk(
                os.path.join(REPO, "plugins")):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for filename in filenames:
                if not filename.endswith(".py") or filename == "url_guard.py":
                    continue
                path = os.path.join(dirpath, filename)
                with open(path, encoding="utf-8") as stream:
                    if pattern.search(stream.read()):
                        offenders.append(os.path.relpath(path, REPO))
        self.assertEqual(
            offenders, [],
            "origin helpers must be imported from url_guard.py, not "
            "redefined: %s" % offenders)


if __name__ == "__main__":
    unittest.main()
