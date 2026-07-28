#!/usr/bin/env python3
"""check_headers.py — audit security/caching headers, HTTPS redirect,
compression, cookie flags, and exposed sensitive paths for one or more URLs.

Stdlib only. Outbound requests go through lib/url_guard.py (SSRF guard) —
private/internal/metadata targets and unsafe redirects are refused with a
BLOCKED result. Usage:
    python3 check_headers.py https://example.com [https://example.com/app ...]

Structured output: every check reports [PASS] / [WARN] / [FAIL] /
[UNVERIFIED] and the run ends with a machine-readable
`RESULT: pass=N warn=N fail=N unverified=N` line. Header VALUES are
validated, not just presence: an invalid CSP, a non-'nosniff'
x-content-type-options, an unknown referrer-policy token, or an invalid /
insecure SameSite can never receive PASS.

Exit codes: 0 = no FAILs and nothing UNVERIFIED; 1 = at least one FAIL;
2 = could not connect / blocked / usage error; 3 = no FAILs but at least
one UNVERIFIED check (never treat as a clean pass).
"""
import os
import re
import sys
from urllib.parse import urlparse, urlunparse

sys.path.insert(0, os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "lib")))
try:
    from url_guard import safe_get, check_url, BlockedUrlError
except ImportError:
    sys.exit("url_guard.py not found — run from an intact site-doctor plugin")

UA = "site-doctor-audit/1.0 (+https://github.com/site-doctor)"
TIMEOUT = 15

SECURITY_HEADERS = {
    "strict-transport-security": "FAIL",
    "content-security-policy": "WARN",
    "x-content-type-options": "FAIL",
    "x-frame-options": "WARN",  # OK if CSP frame-ancestors present
    "referrer-policy": "WARN",
    "permissions-policy": "WARN",
}
LEAKY_HEADERS = ("server", "x-powered-by", "x-aspnet-version")
SENSITIVE_PATHS = ("/.env", "/.git/HEAD", "/.git/config", "/wp-config.php.bak")

results = {"PASS": 0, "WARN": 0, "FAIL": 0, "UNVERIFIED": 0}


def report(level, msg):
    results[level] += 1
    print(f"  [{level}] {msg}")


def fetch(url, follow_redirects=True, method="GET"):
    try:
        r = safe_get(url, method=method, follow_redirects=follow_redirects,
                     timeout=TIMEOUT, allow_http=True, read_body=False,
                     headers={"User-Agent": UA, "Accept-Encoding": "gzip, br"})
        final_url = getattr(r, "url", url)
        if (follow_redirects and not
                same_audit_origin(url, final_url, allow_http_upgrade=True)):
            return (None, {"_error": "redirected to unrelated origin %s" %
                           final_url}, [])
        return r.status, dict(
            (k.lower(), v) for k, v in r.headers.items()
        ), r.headers.get_all("Set-Cookie") or []
    except BlockedUrlError as e:
        return None, {"_error": "BLOCKED unsafe target: %s" % e}, []
    except Exception as e:
        return None, {"_error": f"{type(e).__name__}: {e}"}, []


def same_site(host_a, host_b):
    """Same host, or one is the www. variant of the other."""
    def normalize(value):
        try:
            parsed = urlparse(value if "://" in value else "//" + value)
            host = parsed.hostname
            if not host:
                return None
            return host.rstrip(".").encode("idna").decode("ascii").lower()
        except (UnicodeError, ValueError):
            return None

    a, b = normalize(host_a), normalize(host_b)
    if not a or not b:
        return False
    strip = lambda h: h[4:] if h.startswith("www.") else h
    return strip(a) == strip(b)


def same_audit_origin(left, right, allow_http_upgrade=False):
    """Require the same host/effective port, allowing only 80-to-443 upgrade."""
    try:
        a, b = urlparse(left), urlparse(right)
        a_port = a.port or (443 if a.scheme.lower() == "https" else 80)
        b_port = b.port or (443 if b.scheme.lower() == "https" else 80)
    except ValueError:
        return False
    if not same_site(left, right):
        return False
    if a.scheme.lower() == b.scheme.lower():
        return a_port == b_port
    return bool(allow_http_upgrade and a.scheme.lower() == "http" and
                b.scheme.lower() == "https" and a_port == 80 and b_port == 443)


def check_https_redirect(url, max_hops=5):
    p = urlparse(url)
    if p.scheme != "https":
        report("FAIL", f"Target is not HTTPS: {url}")
        return
    expected_host = p.netloc
    current = urlunparse(("http",) + p[1:])
    hops = 0
    while hops < max_hops:
        status, headers, _ = fetch(current, follow_redirects=False)
        if status is None:
            if hops == 0:
                report("WARN", f"Port 80 unreachable ({headers.get('_error')}) — "
                               "fine if HTTP is blocked at the edge")
            else:
                report("FAIL", f"Redirect hop {hops} unreachable "
                               f"({headers.get('_error')}): {current}")
            return
        if status in (301, 302, 307, 308):
            location = headers.get("location", "")
            if not location:
                report("FAIL", f"HTTP redirect hop {hops + 1} has no Location header")
                return
            nxt = urlparse(location)
            if not nxt.scheme:  # relative redirect — resolve against current
                from urllib.parse import urljoin
                location = urljoin(current, location)
                nxt = urlparse(location)
            hops += 1
            # Every hop is bound to a valid expected host and effective port.
            if nxt.scheme == "http" and hops > 1:
                report("FAIL", f"Redirect chain downgrades to http at hop {hops}: {location}")
                return
            if nxt.scheme not in ("http", "https"):
                report("FAIL", f"HTTP redirect hop {hops} has no valid absolute "
                               f"HTTP(S) destination: {location}")
                return
            if nxt.scheme == "http" and not same_audit_origin(current, location):
                report("FAIL", f"HTTP redirects to an UNRELATED origin at hop {hops}: "
                               f"{location} (expected {expected_host}) — not counted "
                               "as an HTTPS upgrade")
                return
            if nxt.scheme == "https" and (
                    not same_audit_origin(current, location,
                                          allow_http_upgrade=True) or
                    not same_audit_origin(url, location)):
                report("FAIL", f"HTTP redirects to an UNRELATED origin at hop {hops}: "
                               f"{location} (expected {url}) — not counted "
                               "as an HTTPS upgrade")
                return
            if status in (302, 307) and hops == 1:
                report("WARN", f"HTTP redirects with {status}; use 301/308 for HTTPS upgrade")
            current = location
            if nxt.scheme == "https":
                if hops == 1 and status in (301, 308):
                    report("PASS", "HTTP redirects permanently to HTTPS (same site)")
                elif status in (301, 308):
                    report("WARN", f"HTTP reaches HTTPS after {hops} hops — collapse to one 301/308")
                return
            continue
        report("FAIL", f"HTTP does not redirect to HTTPS (got {status})")
        return
    report("FAIL", f"HTTP redirect chain exceeded {max_hops} hops without reaching HTTPS")


def validate_hsts(value, is_https=True):
    """Validate one HSTS value as a small public compatibility seam.

    The full header audit performs the same checks in context.  Keeping this
    callable lets fixtures and downstream integrations validate a single value
    without constructing a complete response header map.
    """
    value = (value or "").strip()
    if not value:
        report("FAIL", "HSTS is empty")
        return
    directives = {}
    malformed = False
    for part in value.split(";"):
        part = part.strip()
        if not part:
            report("FAIL", "HSTS contains an empty directive")
            malformed = True
            continue
        name, sep, raw = part.partition("=")
        name = name.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
            report("FAIL", f"HSTS contains a malformed directive: {part!r}")
            malformed = True
            continue
        if name in directives:
            report("FAIL", f"HSTS: duplicate directive '{name}'")
            malformed = True
        directives[name] = raw.strip().strip('"') if sep else ""
    allowed = {"max-age", "includesubdomains", "preload"}
    unknown = set(directives) - allowed
    if unknown:
        report("FAIL", f"HSTS has unknown/malformed directive(s): {sorted(unknown)}")
        malformed = True
    raw_age = directives.get("max-age")
    if raw_age is None or not raw_age.isdigit():
        report("FAIL", "HSTS requires a numeric max-age")
        return
    age = int(raw_age)
    if age == 0:
        report("FAIL", "HSTS max-age=0 disables HSTS")
    elif not is_https:
        report("WARN", "HSTS is ignored on an HTTP response")
    elif age < 15552000:
        report("WARN", f"HSTS max-age is short ({age}s)")
    elif not malformed:
        report("PASS", f"HSTS max-age valid ({age}s)")
    if "preload" in directives and (
        "includesubdomains" not in directives or age < 31536000
    ):
        report("WARN", "HSTS preload requires max-age >= 31536000 and includeSubDomains")


VALID_REFERRER_POLICIES = {
    "no-referrer", "no-referrer-when-downgrade", "origin",
    "origin-when-cross-origin", "same-origin", "strict-origin",
    "strict-origin-when-cross-origin", "unsafe-url"}
KNOWN_CSP_DIRECTIVES = {
    "default-src", "script-src", "script-src-elem", "script-src-attr",
    "style-src", "style-src-elem", "style-src-attr", "img-src", "font-src",
    "connect-src", "media-src", "object-src", "child-src", "frame-src",
    "worker-src", "frame-ancestors", "form-action", "base-uri", "sandbox",
    "report-uri", "report-to", "manifest-src", "prefetch-src",
    "navigate-to", "upgrade-insecure-requests", "block-all-mixed-content",
    "require-trusted-types-for", "trusted-types"}


def validate_csp(value):
    """Return (level, message) for a present CSP value. Presence alone is
    never a pass: garbage, wildcard script sources (`default-src *`),
    and materially incomplete production policies FAIL; unsafe-eval and
    nonce-less unsafe-inline never pass."""
    directives = {}
    duplicates = set()
    for part in value.split(";"):
        part = part.strip()
        if not part:
            continue
        name = part.split(None, 1)[0].lower()
        if name in directives:
            duplicates.add(name)
            continue
        directives[name] = part[len(name):].strip()
    if duplicates:
        return ("FAIL", "content-security-policy has duplicate directive(s) "
                        "%s; browsers honor the first occurrence, so later "
                        "safer-looking values cannot justify a pass" %
                        sorted(duplicates))
    recognized = set(directives) & KNOWN_CSP_DIRECTIVES
    if not recognized:
        return ("FAIL", "content-security-policy present but INVALID - no "
                        "recognized directive in %r" % value[:80])
    unknown = set(directives) - KNOWN_CSP_DIRECTIVES
    if unknown:
        return ("WARN", "content-security-policy has unknown directive(s) "
                        "%s - typos give NO protection" % sorted(unknown)[:5])
    if "default-src" not in directives and "script-src" not in directives:
        return ("FAIL", "CSP is materially incomplete for production: "
                        "neither default-src nor script-src is set, so "
                        "scripts are completely unrestricted")
    # the directive that actually governs script execution
    scripty = directives.get("script-src", directives.get("default-src", ""))
    script_tokens = scripty.split()
    if "*" in script_tokens or any(
            t in ("http:", "https:") for t in script_tokens):
        return ("FAIL", "CSP allows scripts from ANY origin (%r governs "
                        "scripts) - a `default-src *` style policy provides "
                        "no script protection and can never PASS"
                % scripty[:60])
    if "'unsafe-eval'" in script_tokens:
        return ("WARN", "CSP allows 'unsafe-eval' - eval()/Function() XSS "
                        "amplification; remove it or justify it explicitly")
    if "'unsafe-inline'" in scripty and "'nonce-" not in scripty and "'sha256-" not in scripty:
        return ("WARN", "CSP allows 'unsafe-inline' scripts without "
                        "nonces/hashes - XSS protection is largely void")
    return ("PASS", "content-security-policy parses with recognized "
                    "directives (%d) and a restricted script source"
            % len(recognized))


# Permissions-Policy features (W3C permissions registry + common vendor
# features). Unknown names warn; a header with NO valid directive fails.
KNOWN_PP_FEATURES = {
    "accelerometer", "ambient-light-sensor", "attribution-reporting",
    "autoplay", "battery", "bluetooth", "browsing-topics", "camera",
    "ch-ua", "clipboard-read", "clipboard-write", "compute-pressure",
    "cross-origin-isolated", "display-capture", "document-domain",
    "encrypted-media", "execution-while-not-rendered",
    "execution-while-out-of-viewport", "fullscreen", "gamepad",
    "geolocation", "gyroscope", "hid", "identity-credentials-get",
    "idle-detection", "interest-cohort", "join-ad-interest-group",
    "keyboard-map", "local-fonts", "magnetometer", "microphone", "midi",
    "otp-credentials", "payment", "picture-in-picture",
    "publickey-credentials-create", "publickey-credentials-get",
    "run-ad-auction", "screen-wake-lock", "serial", "speaker-selection",
    "storage-access", "sync-xhr", "unload", "usb", "web-share",
    "window-management", "window-placement", "xr-spatial-tracking",
}
_PP_ORIGIN_RE = re.compile(r'^"https?://[^"\s]+"$')
_PP_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def validate_permissions_policy(value):
    """Structured-header-style validation of Permissions-Policy. Each
    comma-separated directive must be `feature=allowlist` where allowlist
    is `*`, `()`, `(self)`, `(src)`, or a parenthesised list of `self`,
    `src`, and quoted origins. A header with no valid directive (e.g.
    `banana`) FAILS - presence is never a pass."""
    valid, invalid_names, invalid_values = [], [], []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            invalid_values.append(part[:40])
            continue
        name, _, allow = part.partition("=")
        name, allow = name.strip().lower(), allow.strip()
        if not _PP_NAME_RE.match(name):
            invalid_values.append(part[:40])
            continue
        ok_value = (allow == "*"
                    or (allow.startswith("(") and allow.endswith(")")
                        and all(tok in ("self", "src")
                                or _PP_ORIGIN_RE.match(tok)
                                for tok in allow[1:-1].split()
                                if tok)))
        if not ok_value:
            invalid_values.append(part[:40])
            continue
        if name not in KNOWN_PP_FEATURES:
            invalid_names.append(name)
            continue
        valid.append(name)
    if not valid:
        return ("FAIL", "permissions-policy present but INVALID - no valid "
                        "`feature=allowlist` directive in %r (a bare token "
                        "like 'banana' is not a policy)" % value[:60])
    if invalid_values:
        return ("FAIL", "permissions-policy has malformed directive(s) %s - "
                        "browsers ignore them, so the header does not do "
                        "what it claims" % invalid_values[:3])
    if invalid_names:
        return ("WARN", "permissions-policy names unknown feature(s) %s - "
                        "typos give NO protection (%d valid directive(s) "
                        "recognized)" % (sorted(set(invalid_names))[:5],
                                         len(valid)))
    return ("PASS", "permissions-policy: %d valid directive(s) (%s%s)"
            % (len(valid), ", ".join(sorted(valid)[:4]),
               "..." if len(valid) > 4 else ""))


def check_security_headers(headers):
    for name, miss_level in SECURITY_HEADERS.items():
        if name not in headers:
            if name == "x-frame-options" and \
                    "frame-ancestors" in headers.get("content-security-policy", ""):
                report("PASS", "frame-ancestors set via CSP (x-frame-options not needed)")
            else:
                report(miss_level, f"Missing header: {name}")
            continue
        value = headers[name].strip()
        # VALUE validation — presence alone is never a pass
        if name == "x-content-type-options":
            if value.lower() == "nosniff":
                report("PASS", "x-content-type-options: nosniff")
            else:
                report("FAIL", f"x-content-type-options present but INVALID: "
                               f"{value[:40]!r} (must be exactly 'nosniff')")
        elif name == "referrer-policy":
            tokens = [t.strip().lower() for t in value.split(",") if t.strip()]
            invalid = [t for t in tokens if t not in VALID_REFERRER_POLICIES]
            if not tokens or invalid:
                report("FAIL", f"referrer-policy present but INVALID token(s) "
                               f"{invalid or [value[:40]]} — browsers ignore "
                               "unknown policies")
            elif "unsafe-url" in tokens:
                report("WARN", "referrer-policy 'unsafe-url' leaks full URLs "
                               "cross-origin")
            else:
                report("PASS", f"referrer-policy: {value[:60]}")
        elif name == "content-security-policy":
            level, msg = validate_csp(value)
            report(level, msg)
        elif name == "permissions-policy":
            level, msg = validate_permissions_policy(value)
            report(level, msg)
        elif name == "x-frame-options":
            v = value.upper()
            if v in ("DENY", "SAMEORIGIN"):
                report("PASS", f"x-frame-options: {v}")
            elif v.startswith("ALLOW-FROM"):
                report("WARN", "x-frame-options ALLOW-FROM is deprecated and "
                               "ignored by modern browsers — use CSP "
                               "frame-ancestors")
            else:
                report("FAIL", f"x-frame-options present but INVALID: "
                               f"{value[:40]!r} (DENY or SAMEORIGIN)")
        elif name == "strict-transport-security":
            report("PASS", f"{name}: {value[:90]}")   # directives audited below
        else:
            report("PASS", f"{name}: {value[:90]}")
    hsts = headers.get("strict-transport-security", "")
    if hsts:
        directives = {}
        malformed = False
        for part in hsts.split(";"):
            part = part.strip()
            if not part:
                continue
            name, _, value = part.partition("=")
            name = name.strip().lower()
            if name in directives:
                report("FAIL", f"HSTS: duplicate directive '{name}' — header is invalid per RFC 6797")
                malformed = True
            directives[name] = value.strip().strip('"')
        if "max-age" not in directives:
            report("FAIL", "HSTS present but has NO max-age directive — header has no effect")
        else:
            raw = directives["max-age"]
            if not raw.isdigit():
                report("FAIL", f"HSTS max-age is not a valid number: '{raw}' — header has no effect")
            else:
                age = int(raw)
                if age == 0:
                    report("FAIL", "HSTS max-age=0 actively DISABLES HSTS for this host")
                elif age < 15552000:
                    report("WARN", f"HSTS max-age is short ({age}s); recommend >= 15552000")
                if not malformed and age >= 15552000:
                    report("PASS", f"HSTS max-age valid ({age}s)")
        unknown = set(directives) - {"max-age", "includesubdomains", "preload"}
        if unknown:
            report("WARN", f"HSTS: unknown directive(s) {sorted(unknown)} — check for typos")
        if "includesubdomains" not in directives:
            report("WARN", "HSTS lacks includeSubDomains — subdomains stay unprotected "
                           "(add once all subdomains serve HTTPS)")
        raw_age = directives.get("max-age", "")
        safe_age = int(raw_age) if raw_age.isdigit() else 0  # malformed -> 0, never crash
        if "preload" in directives and (
                "includesubdomains" not in directives or safe_age < 31536000):
            report("WARN", "HSTS 'preload' requires max-age >= 31536000 AND includeSubDomains")
    for name in LEAKY_HEADERS:
        val = headers.get(name, "")
        if any(ch.isdigit() for ch in val):
            report("WARN", f"Version leakage: {name}: {val}")


def check_caching_and_compression(headers):
    enc = headers.get("content-encoding", "")
    if enc in ("gzip", "br", "zstd"):
        report("PASS", f"Compression enabled ({enc})")
    else:
        report("WARN", "No compression on this response (gzip/brotli)")
    cc = headers.get("cache-control")
    if cc:
        report("PASS", f"cache-control: {cc}")
    else:
        report("WARN", "No cache-control header")


def parse_cookie_attributes(set_cookie):
    """Structural Set-Cookie parse: the FIRST ';'-segment is name=value; the
    remaining segments are attributes (name or name=value). Substring
    matching is wrong — a cookie VALUE containing 'secure' is not a flag."""
    segments = [seg.strip() for seg in set_cookie.split(";")]
    name = segments[0].split("=", 1)[0].strip()
    attrs = {}
    for seg in segments[1:]:
        if not seg:
            continue
        k, _, v = seg.partition("=")
        attrs[k.strip().lower()] = v.strip()
    return name, attrs


def check_cookies(cookies):
    for c in cookies:
        name, attrs = parse_cookie_attributes(c)
        # SameSite VALUE validation comes FIRST — an invalid or insecure
        # value is a FAIL, never softened into a missing-flag warning.
        if "samesite" in attrs:
            ssv = attrs.get("samesite", "").strip().lower()
            if ssv not in ("strict", "lax", "none"):
                report("FAIL", f"Cookie '{name}' has INVALID SameSite="
                               f"{attrs.get('samesite')!r} - browsers treat "
                               "unknown values inconsistently (use Strict, "
                               "Lax, or None)")
                continue
            if ssv == "none" and "secure" not in attrs:
                report("FAIL", f"Cookie '{name}' has SameSite=None WITHOUT "
                               "Secure - rejected by modern browsers")
                continue
        missing = [f for f in ("secure", "httponly", "samesite")
                   if f not in attrs]
        if missing:
            report("WARN", f"Cookie '{name}' missing flags: {', '.join(missing)}")
            continue
        ss = attrs.get("samesite", "").strip().lower()
        if ss not in ("strict", "lax", "none"):
            report("FAIL", f"Cookie '{name}' has INVALID SameSite="
                           f"{attrs.get('samesite')!r} — browsers treat "
                           "unknown values inconsistently (use Strict, Lax, "
                           "or None)")
        elif ss == "none" and "secure" not in attrs:
            report("FAIL", f"Cookie '{name}' has SameSite=None WITHOUT "
                           "Secure — rejected by modern browsers")
        else:
            report("PASS", f"Cookie '{name}' has Secure/HttpOnly/"
                           f"SameSite={ss}")


def check_sensitive_paths(url):
    base = "{0.scheme}://{0.netloc}".format(urlparse(url))
    for path in SENSITIVE_PATHS:
        status, headers, _ = fetch(base + path)
        if status == 200:
            ct = headers.get("content-type", "")
            if "html" in ct and path != "/.env":
                report("WARN", f"{path} returns 200 with HTML — likely a soft-404, verify manually")
            else:
                report("FAIL", f"EXPOSED: {base}{path} returns 200")
        elif status is None:
            report("UNVERIFIED", f"{path} could not be verified "
                                 f"({headers.get('_error', 'connection error')}) — "
                                 "NOT a pass; re-check when reachable")
        elif status in (401, 403, 404):
            report("PASS", f"{path} not exposed ({status})")
        else:
            report("WARN", f"{path} returned {status} — verify manually")


def main(urls):
    exit_code = 0
    for url in urls:
        print(f"\n=== {url} ===")
        try:
            check_url(url, allow_http=True)
        except BlockedUrlError as e:
            print(f"  [BLOCKED] unsafe target: {e}")
            exit_code = max(exit_code, 2)
            continue
        status, headers, cookies = fetch(url)
        if status is None:
            print(f"  [ERROR] Could not connect: {headers.get('_error')}")
            exit_code = max(exit_code, 2)
            continue
        print(f"  Status: {status}")
        if not 200 <= status < 300:
            report("FAIL", f"Target returned HTTP {status}; headers on an "
                   "unsuccessful response do not prove production readiness")
            continue
        check_https_redirect(url)
        check_security_headers(headers)
        check_caching_and_compression(headers)
        check_cookies(cookies)
        check_sensitive_paths(url)
    print(f"\nTotals: {results['PASS']} pass, {results['WARN']} warn, "
          f"{results['FAIL']} fail, {results['UNVERIFIED']} unverified")
    print(f"RESULT: pass={results['PASS']} warn={results['WARN']} "
          f"fail={results['FAIL']} unverified={results['UNVERIFIED']}")
    if results["FAIL"]:
        exit_code = max(exit_code, 1)
    elif results["UNVERIFIED"] and exit_code == 0:
        exit_code = 3
    return exit_code


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
