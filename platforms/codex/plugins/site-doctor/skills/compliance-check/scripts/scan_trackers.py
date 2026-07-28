#!/usr/bin/env python3
"""scan_trackers.py — fetch a page and surface cookies set and third-party
tracker/script origins, to support a privacy/consent compliance review.

Stdlib only. Outbound requests go through lib/url_guard.py (SSRF guard) —
private/internal/metadata targets and unsafe redirects are refused with a
BLOCKED result. Usage:
    python3 scan_trackers.py https://example.com

This is a FLOOR, not a ceiling: it sees server-set cookies and static
third-party references in the initial HTML. Client-set cookies and tags
injected by JavaScript need a real browser (or consent-mode testing) to
catch fully.

Exit codes: 0 = no known trackers statically; 1 = trackers fire with no
consent tool detected (FAIL); 2 = usage/unreachable/HTTP error; 3 = coverage
UNVERIFIED (non-HTML, empty, truncated, unparsable, or trackers plus a CMP
whose consent gating needs a real browser).
"""
import os
import sys
import re
import hashlib
from urllib.parse import urlparse, urldefrag
from html.parser import HTMLParser

sys.path.insert(0, os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "lib")))
try:
    from url_guard import safe_get, BlockedUrlError
except ImportError:
    sys.exit("url_guard.py not found — run from an intact site-doctor plugin")

UA = "Mozilla/5.0 (compatible; site-doctor-privacy/1.0)"
TIMEOUT = 15
MAX_BYTES = 2 * 1024 * 1024  # response read cap

# Known tracker/ad/analytics host fragments -> friendly label
KNOWN_TRACKERS = {
    "google-analytics.com": "Google Analytics",
    "googletagmanager.com": "Google Tag Manager",
    "analytics.google.com": "Google Analytics 4",
    "doubleclick.net": "Google Ads / DoubleClick",
    "googlesyndication.com": "Google AdSense",
    "googleadservices.com": "Google Ads",
    "connect.facebook.net": "Meta (Facebook) Pixel",
    "facebook.com/tr": "Meta Pixel",
    "hotjar.com": "Hotjar",
    "clarity.ms": "Microsoft Clarity",
    "segment.com": "Segment",
    "segment.io": "Segment",
    "mixpanel.com": "Mixpanel",
    "amplitude.com": "Amplitude",
    "fullstory.com": "FullStory",
    "mouseflow.com": "Mouseflow",
    "linkedin.com/px": "LinkedIn Insight",
    "snap.licdn.com": "LinkedIn Insight",
    "ads-twitter.com": "X (Twitter) Ads",
    "static.ads-twitter.com": "X Ads",
    "tiktok.com": "TikTok Pixel",
    "bing.com": "Microsoft/Bing Ads",
    "bat.bing.com": "Bing Ads",
    "cdn.segment": "Segment",
    "intercom.io": "Intercom",
    "hs-scripts.com": "HubSpot",
    "hubspot.com": "HubSpot",
    "cookiebot.com": "Cookiebot (CMP)",
    "onetrust.com": "OneTrust (CMP)",
    "cookielaw.org": "OneTrust (CMP)",
    "usercentrics": "Usercentrics (CMP)",
    "klaviyo.com": "Klaviyo",
    "matomo": "Matomo",
    "plausible.io": "Plausible (privacy-friendly)",
    "cloudflareinsights.com": "Cloudflare Web Analytics",
}


class SrcParser(HTMLParser):
    """Collects each referenced resource URL exactly once (deduplicated) —
    an <img> src is not counted twice, and repeated references to the same
    URL don't inflate tracker counts."""
    def __init__(self):
        super().__init__()
        self.srcs = []
        self._seen = set()
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        tag = tag.lower()
        attributes = []
        if tag in ("script", "img", "iframe", "source", "video", "audio"):
            attributes.append("src")
        if tag == "link":
            attributes.append("href")
        if tag == "object":
            attributes.append("data")
        for attr in attributes:
            u = a.get(attr)
            normalized = urldefrag(u)[0] if u else ""
            if normalized and normalized not in self._seen:
                self._seen.add(normalized)
                self.srcs.append(normalized)


def parse_cookie_header(value):
    """Return a legacy structured cookie list without substring matching."""
    segments = [segment.strip() for segment in (value or "").split(";")]
    first = segments[0] if segments else ""
    name, separator, cookie_value = first.partition("=")
    attributes = {}
    for segment in segments[1:]:
        key, _separator, item_value = segment.partition("=")
        if key.strip():
            attributes[key.strip().lower()] = item_value.strip()
    flags = [name for name in ("secure", "httponly", "samesite")
             if name in attributes]
    return [{
        "name": name.strip(),
        "value": cookie_value if separator else "",
        "flags": flags,
        "attributes": attributes,
        "malformed": not bool(separator and name.strip()),
    }]


def _host_id(host):
    """Return a stable, non-raw identifier for an untrusted hostname."""
    if not host:
        return "missing"
    return hashlib.sha256(host.encode("utf-8", "replace")).hexdigest()[:12]


def describe_url(value):
    """Describe URL structure without echoing attacker-controlled values.

    URLs can carry credentials in userinfo, query strings, fragments, paths,
    and even host labels.  Audit output therefore exposes only fixed-shape
    classifications and a stable hostname fingerprint.
    """
    try:
        parsed = urlparse(value)
        scheme = parsed.scheme.lower()
        scheme = scheme if scheme in ("http", "https") else "other"
        host = normalized_hostname(value)
        try:
            port = parsed.port
        except ValueError:
            port_kind = "invalid"
        else:
            default = 443 if scheme == "https" else 80 if scheme == "http" else None
            port_kind = "default" if port in (None, default) else "custom"
        query_count = len(parsed.query.split("&")) if parsed.query else 0
        return ("scheme=%s host-id=%s port=%s path=%s query-fields=%d "
                "fragment=%s userinfo=%s" %
                (scheme, _host_id(host), port_kind,
                 "present" if parsed.path not in ("", "/") else "root",
                 query_count, "present" if parsed.fragment else "absent",
                 "present" if (parsed.username is not None or
                                parsed.password is not None) else "absent"))
    except Exception:
        return ("scheme=invalid host-id=missing port=invalid path=unknown "
                "query-fields=unknown fragment=unknown userinfo=unknown")


def describe_origin(value):
    """Return a non-raw structural label for a third-party resource URL."""
    try:
        parsed = urlparse(value)
        scheme = parsed.scheme.lower()
        scheme = scheme if scheme in ("http", "https") else "other"
        host = normalized_hostname(value)
        try:
            port = parsed.port
        except ValueError:
            port_kind = "invalid"
        else:
            default = 443 if scheme == "https" else 80 if scheme == "http" else None
            port_kind = "default" if port in (None, default) else "custom"
        return "scheme=%s host-id=%s port=%s" % (
            scheme, _host_id(host), port_kind)
    except Exception:
        return "scheme=invalid host-id=missing port=invalid"


def cookie_summary(value):
    """Return safe structural facts for one Set-Cookie header.

    Cookie names, values, dates, and arbitrary attribute values are all
    untrusted and may contain credentials.  Only fixed allowlist labels are
    emitted.
    """
    parsed = parse_cookie_header(value)[0]
    attrs = parsed["attributes"]
    flags = [flag for flag in ("secure", "httponly") if flag in attrs]
    if "samesite" in attrs:
        same_site = attrs["samesite"].strip().lower()
        flags.append("samesite=" + same_site
                     if same_site in ("lax", "strict", "none")
                     else "samesite=invalid")
    if "max-age" in attrs:
        lifetime = ("persistent-max-age" if
                    attrs["max-age"].lstrip("-").isdigit() else
                    "persistent-max-age-invalid")
    elif "expires" in attrs:
        lifetime = "persistent-expires"
    else:
        lifetime = "session"
    return parsed["malformed"], flags, lifetime


def fetch(url, detailed=None):
    try:
        r = safe_get(url, timeout=TIMEOUT, allow_http=True, max_bytes=MAX_BYTES,
                     headers={"User-Agent": UA})
        legacy = detailed is False or (detailed is None and not hasattr(r, "truncated"))
        def result(status, cookies, html, problem=None, final_url=None):
            return ((status, cookies, html) if legacy else
                    (status, cookies, html, problem, final_url))
        get_all = getattr(r.headers, "get_all", None)
        cookies = get_all("Set-Cookie") or [] if callable(get_all) else []
        final_url = getattr(r, "url", url)
        if not same_audit_origin(url, final_url, allow_http_upgrade=True):
            return result(r.status, cookies, "",
                          "redirected to an unrelated origin",
                          final_url)
        if not 200 <= r.status < 300:
            return result(r.status, cookies, "", "HTTP %s" % r.status, final_url)
        if getattr(r, "truncated", False):
            return result(r.status, cookies, "",
                          "response exceeded the %d-byte scan limit" % MAX_BYTES,
                          final_url)
        content_type = r.headers.get("Content-Type", "")
        ctype = content_type.split(";", 1)[0].strip().lower()
        if ctype not in ("text/html", "application/xhtml+xml"):
            return result(r.status, cookies, "",
                          "response Content-Type is not HTML", final_url)
        body = r.body or b""
        if not body.strip():
            return result(r.status, cookies, "", "HTML response body is empty",
                          final_url)
        charset = "utf-8"
        for parameter in content_type.split(";")[1:]:
            key, separator, value = parameter.partition("=")
            if separator and key.strip().lower() == "charset":
                charset = value.strip().strip('"\'').lower()
                break
        aliases = {"utf-8": "utf-8", "utf8": "utf-8",
                   "us-ascii": "ascii", "ascii": "ascii"}
        codec = aliases.get(charset)
        if codec is None:
            return result(r.status, cookies, "",
                          "unsupported HTML charset", final_url)
        try:
            html = body.decode(codec, "strict")
        except UnicodeDecodeError:
            return result(r.status, cookies, "",
                          "HTML body is not valid %s" % charset, final_url)
        return result(r.status, cookies, html, None, final_url)
    except BlockedUrlError:
        print("BLOCKED unsafe target (details redacted)")
        return ((None, [], "") if detailed is not True else
                (None, [], "", "blocked unsafe target", None))
    except Exception:
        print("Could not fetch target (details redacted)")
        return ((None, [], "") if detailed is not True else
                (None, [], "", "request failed", None))


def normalized_hostname(value):
    """Return a structural lower-case hostname for a URL or netloc."""
    try:
        parsed = urlparse(value if "://" in value else "//" + value)
        host = parsed.hostname
        if not host:
            return None
        return host.rstrip(".").encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError):
        return None


def same_site_url(left, right):
    """Accept only the same hostname or its explicit www variant."""
    a, b = normalized_hostname(left), normalized_hostname(right)
    if not a or not b:
        return False
    strip_www = lambda host: host[4:] if host.startswith("www.") else host
    return strip_www(a) == strip_www(b)


def same_audit_origin(left, right, allow_http_upgrade=False):
    """Bind evidence to a host and effective port, with optional HTTPS upgrade."""
    try:
        a, b = urlparse(left), urlparse(right)
        a_port = a.port or (443 if a.scheme.lower() == "https" else 80)
        b_port = b.port or (443 if b.scheme.lower() == "https" else 80)
    except ValueError:
        return False
    if not same_site_url(left, right):
        return False
    if a.scheme.lower() == b.scheme.lower():
        return a_port == b_port
    return bool(allow_http_upgrade and a.scheme.lower() == "http" and
                b.scheme.lower() == "https" and a_port == 80 and b_port == 443)


def main(url):
    fetched = fetch(url, detailed=True)
    if len(fetched) == 3:  # legacy/mock adapter
        status, cookies, html = fetched
        problem, final_url = None, url
    else:
        status, cookies, html, problem, final_url = fetched
    if status is None:
        print("RESULT: pass=0 warn=0 fail=0 unverified=1")
        return 2
    print("=== Privacy/tracker scan: %s (status %s) ===\n" %
          (describe_url(url), status))
    if problem:
        http_error = not 200 <= status < 300
        level = "ERROR" if http_error else "UNVERIFIED"
        print(f"[{level}] {problem}; tracker coverage is not a pass")
        print("RESULT: pass=0 warn=0 fail=0 unverified=1")
        return 2 if http_error else 3

    # --- cookies set on initial load ---
    print("Cookies set by the server on load "
          "(these fire BEFORE any consent interaction):")
    if not cookies:
        print("  (none set via response headers — client JS may still set some)")
    for index, c in enumerate(cookies, 1):
        # Structural parse: first segment is name=value; the rest are
        # attributes.  Neither the name/value nor arbitrary attributes are
        # emitted: Set-Cookie is an attacker-controlled credential surface.
        malformed, flags, life = cookie_summary(c)
        marker = " (malformed)" if malformed else ""
        print("  - cookie #%d%s  [%s]  %s" %
              (index, marker, ", ".join(flags) or "no flags", life))
    print()

    # --- third-party origins & known trackers ---
    p = SrcParser()
    try:
        p.feed(html)
        p.close()
    except Exception:
        print("[UNVERIFIED] HTML parser failed (details redacted); tracker coverage is "
              "not a pass")
        print("RESULT: pass=0 warn=0 fail=0 unverified=1")
        return 3

    third_party = {}
    trackers_found = {}
    for src in p.srcs:
        if src.startswith("//"):
            src = "https:" + src
        netloc = urlparse(src).netloc
        src_host = normalized_hostname(netloc) if netloc else None
        if not src_host or same_audit_origin(final_url, src):
            continue
        origin = describe_origin(src)
        third_party.setdefault(origin, 0)
        third_party[origin] += 1
        for frag, label in KNOWN_TRACKERS.items():
            if frag in src.lower():
                trackers_found[label] = trackers_found.get(label, 0) + 1

    print("Known trackers / analytics / ad tech detected in initial HTML:")
    if not trackers_found:
        print("  (none detected statically — JS-injected tags need a browser to confirm)")
    for label, n in sorted(trackers_found.items(), key=lambda x: -x[1]):
        cmp_note = "  <- consent tool (good sign)" if "CMP" in label else ""
        print(f"  - {label}  (x{n}){cmp_note}")
    print()

    print("All third-party origins referenced on load "
          "(each may receive user data such as IP/behavior):")
    for origin, n in sorted(third_party.items(), key=lambda x: -x[1])[:30]:
        print(f"  - {origin}  (x{n})")
    print()

    # ---- structured verdict -------------------------------------------------
    cmp_present = any("CMP" in label for label in trackers_found)
    hard_trackers = {l: n for l, n in trackers_found.items() if "CMP" not in l}
    if hard_trackers and not cmp_present:
        print(f"[FAIL] {len(hard_trackers)} tracker(s) load in the initial "
              "HTML with NO consent tool detected - classic GDPR/ePrivacy gap")
        verdict = 1
    elif hard_trackers:
        print(f"[UNVERIFIED] {len(hard_trackers)} tracker(s) plus a consent "
              "tool detected - whether the CMP actually GATES them needs a "
              "real browser with consent unaccepted")
        verdict = 3
    else:
        print("[PASS] no known trackers in the initial HTML "
              "(JS-injected tags still need a browser check)")
        verdict = 0
    print(f"RESULT: pass={0 if hard_trackers else 1} warn={len(third_party)} "
          f"fail={1 if (hard_trackers and not cmp_present) else 0} "
          f"unverified={1 if (hard_trackers and cmp_present) else 0}")
    print()
    print("REVIEW GUIDANCE:")
    print("  * Any analytics/ad tracker firing on load without prior consent is")
    print("    the classic GDPR/ePrivacy gap. Confirm whether a consent tool")
    print("    gates them, or whether they fire regardless.")
    print("  * Third-party origins loading before consent can leak user data to")
    print("    those parties (IP, page, behavior). Verify each is disclosed and")
    print("    consent-gated where required.")
    print("  * This is a static floor — run a real browser with the consent")
    print("    banner UNaccepted to see what actually fires pre-consent.")
    return verdict


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
