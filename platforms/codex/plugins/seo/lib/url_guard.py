#!/usr/bin/env python3
"""url_guard.py — shared SSRF guard for site-doctor helper scripts. Stdlib only.

Every outbound HTTP request made by the bundled scripts goes through this
module, which enforces one policy in one place:

  * scheme allowlist — https by default; http only when the caller opts in
    (the page-audit scripts do, because auditing an http site is their job)
  * hostname blocklist — localhost, *.localhost, *.local, *.internal,
    metadata.google.internal, wpad
  * every resolved address must be globally routable — loopback, RFC1918,
    link-local (which covers 169.254.169.254 cloud metadata), CGNAT
    100.64.0.0/10, benchmarking 198.18.0.0/15, IETF 192.0.0.0/24, the Azure
    wireserver 168.63.129.16, multicast, reserved, unspecified, NAT64
    64:ff9b::/96 and Teredo 2001::/32 (and their embedded IPv4), and
    IPv4-mapped IPv6 are all refused; ALL addresses in a DNS answer must pass
  * every redirect hop is re-validated before it is followed, with a hop cap
  * response bodies are read through a hard size cap (never an unbounded read)

A refused target raises BlockedUrlError — callers print a clear
"BLOCKED unsafe target" result instead of silently trying it.

Known residual risk (stdlib limitation, documented deliberately): the socket
layer re-resolves the hostname at connect time, so a hostile DNS server could
in principle rebind between our check and the connection (TOCTOU). This is an
operator-run audit tool, not a multi-tenant proxy — do not reuse this module
as a security boundary for untrusted callers.

Test seam: the loopback fixture addresses 127.0.0.1 and ::1 can be admitted
only when *both* ``URL_GUARD_TEST_MODE=1`` and
``URL_GUARD_EXTRA_ALLOWED=<loopback>`` are present. Either variable by itself
is ignored with a RuntimeWarning, and the environment seam never admits a
non-loopback address. In-process tests should still prefer dependency
injection through ``extra_allowed``. Ambient HTTP(S) proxy variables are also
ignored so a caller's process environment cannot redirect guarded requests
outside the validated route.
"""
import ipaddress
import os
import socket
import warnings
import urllib.error
import urllib.parse
import urllib.request
from collections import namedtuple

DEFAULT_TIMEOUT = 15
DEFAULT_MAX_BYTES = 2 * 1024 * 1024   # 2 MiB
DEFAULT_MAX_REDIRECTS = 5

_EXPLICIT_BLOCKED = [ipaddress.ip_network(n) for n in (
    "100.64.0.0/10",     # CGNAT / shared address space (incl. Alibaba metadata)
    "192.0.0.0/24",      # IETF protocol assignments
    "198.18.0.0/15",     # benchmarking
    "168.63.129.16/32",  # Azure wireserver/metadata
    "64:ff9b::/96",      # NAT64
    "2001::/32",         # Teredo
)]
_BLOCKED_HOSTS = {"localhost", "metadata", "metadata.google.internal", "wpad"}
_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal")
_TEST_LOOPBACKS = frozenset((ipaddress.ip_address("127.0.0.1"),
                             ipaddress.ip_address("::1")))

SafeResponse = namedtuple("SafeResponse",
                          "status headers body url hops truncated")


class BlockedUrlError(ValueError):
    """Target refused by the URL safety policy (never contacted)."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 3xx surfaces as HTTPError; safe_get validates each hop


def _env_test_loopbacks():
    """Return an explicitly enabled, loopback-only fixture allowlist.

    Requiring two independently named variables prevents one stray ambient
    setting from weakening the guard. The seam is intentionally incapable of
    admitting RFC1918, link-local, metadata, or any other non-loopback target.
    """
    mode = os.environ.get("URL_GUARD_TEST_MODE")
    raw = os.environ.get("URL_GUARD_EXTRA_ALLOWED")
    if mode is None and raw is None:
        return set()
    if mode != "1" or not raw:
        warnings.warn(
            "loopback fixture access requires both URL_GUARD_TEST_MODE=1 "
            "and URL_GUARD_EXTRA_ALLOWED; incomplete test seam ignored",
            RuntimeWarning, stacklevel=3)
        return set()

    out = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            address = ipaddress.ip_address(part)
        except ValueError:
            warnings.warn("invalid URL_GUARD_EXTRA_ALLOWED address %r ignored"
                          % part, RuntimeWarning, stacklevel=3)
            continue
        if address not in _TEST_LOOPBACKS:
            warnings.warn(
                "URL_GUARD_EXTRA_ALLOWED admits loopback fixtures only; %s ignored"
                % address, RuntimeWarning, stacklevel=3)
            continue
        out.add(address)
    return out


def _ip_block_reason(ip):
    if ip.version == 6:
        mapped = ip.ipv4_mapped
        if mapped is not None:
            inner = _ip_block_reason(mapped)
            return inner and "ipv4-mapped %s (%s)" % (mapped, inner)
    for net in _EXPLICIT_BLOCKED:
        if ip.version == net.version and ip in net:
            return "blocked range %s" % net
    for flag, label in (("is_loopback", "loopback"),
                        ("is_link_local", "link-local"),
                        ("is_multicast", "multicast"),
                        ("is_unspecified", "unspecified"),
                        ("is_reserved", "reserved"),
                        ("is_private", "private")):
        if getattr(ip, flag, False):
            return label
    if not ip.is_global:
        return "not globally routable"
    return None


def check_url(url, allow_http=False, extra_allowed=()):
    """Validate scheme, hostname, and every resolved address of *url*.

    Returns the url unchanged if safe; raises BlockedUrlError otherwise.
    Performs DNS resolution but never opens an HTTP connection.
    """
    parts = urllib.parse.urlsplit(url)
    scheme = (parts.scheme or "").lower()
    allowed_schemes = ("https", "http") if allow_http else ("https",)
    if scheme not in allowed_schemes:
        raise BlockedUrlError("scheme %r not allowed (want %s): %s"
                              % (scheme or "none", "/".join(allowed_schemes), url))
    host = parts.hostname
    if not host:
        raise BlockedUrlError("no hostname in %r" % url)
    try:
        port = parts.port
    except ValueError:
        raise BlockedUrlError("invalid port in %r" % url)
    host = host.rstrip(".").lower()
    if host in _BLOCKED_HOSTS or host.endswith(_BLOCKED_HOST_SUFFIXES):
        raise BlockedUrlError("hostname %r is a blocked internal/metadata name" % host)

    allow = _env_test_loopbacks()
    for a in extra_allowed:
        try:
            allow.add(ipaddress.ip_address(a) if isinstance(a, str) else a)
        except ValueError:
            pass

    try:
        ips = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, port or (443 if scheme == "https" else 80),
                                       proto=socket.IPPROTO_TCP)
        except socket.gaierror as e:
            raise BlockedUrlError("cannot resolve %r (%s)" % (host, e))
        ips = []
        for _family, _t, _p, _c, sockaddr in infos:
            addr = sockaddr[0]
            if "%" in addr:  # scoped IPv6 (fe80::1%eth0)
                addr = addr.split("%", 1)[0]
            try:
                ips.append(ipaddress.ip_address(addr))
            except ValueError:
                raise BlockedUrlError("unparseable address %r for host %r" % (addr, host))
        if not ips:
            raise BlockedUrlError("no addresses resolved for %r" % host)
    for ip in ips:
        if ip in allow:
            continue
        reason = _ip_block_reason(ip)
        if reason:
            raise BlockedUrlError("%s resolves to %s (%s)" % (host, ip, reason))
    return url


def _read_capped(resp, max_bytes):
    buf = b""
    while len(buf) <= max_bytes:
        chunk = resp.read(min(65536, max_bytes + 1 - len(buf)))
        if not chunk:
            return buf, False
        buf += chunk
    return buf[:max_bytes], True


def _build_direct_opener():
    """Return an opener that never consumes HTTP(S)_PROXY from the environment."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                       _NoRedirect())


def safe_get(url, headers=None, timeout=DEFAULT_TIMEOUT, allow_http=False,
             follow_redirects=True, max_redirects=DEFAULT_MAX_REDIRECTS,
             max_bytes=DEFAULT_MAX_BYTES, method="GET", read_body=True,
             extra_allowed=()):
    """Guarded fetch. Validates *url* and every redirect hop, then returns
    SafeResponse(status, headers, body, url, hops, truncated).

    * headers is an email.message.Message (supports .get / .get_all / .items)
    * body is bytes capped at max_bytes (None for HEAD or read_body=False)
    * 4xx/5xx come back as normal SafeResponses, not exceptions
    * raises BlockedUrlError for policy refusals; network errors propagate
    """
    opener = _build_direct_opener()
    current, hops = url, 0
    while True:
        check_url(current, allow_http=allow_http, extra_allowed=extra_allowed)
        req = urllib.request.Request(current, headers=dict(headers or {}),
                                     method=method)
        try:
            resp = opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            resp = e
        status = resp.getcode()
        if follow_redirects and status in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            if location:
                resp.close()
                hops += 1
                if hops > max_redirects:
                    raise BlockedUrlError("too many redirects (>%d) starting from %s"
                                          % (max_redirects, url))
                current = urllib.parse.urljoin(current, location)
                if status == 303:
                    method = "GET"
                continue
        body, truncated = None, False
        try:
            if read_body and method != "HEAD":
                body, truncated = _read_capped(resp, max_bytes)
        finally:
            resp.close()
        return SafeResponse(status, resp.headers, body, current, hops, truncated)
