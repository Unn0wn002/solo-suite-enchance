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


if __name__ == "__main__":
    unittest.main()
