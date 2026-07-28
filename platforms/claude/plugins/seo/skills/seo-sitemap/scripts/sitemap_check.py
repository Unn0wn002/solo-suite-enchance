#!/usr/bin/env python3
"""sitemap_check.py — discover and validate a site's XML sitemap(s).

Stdlib only. Outbound requests go through lib/url_guard.py (SSRF guard) —
private/internal/metadata targets and unsafe redirects are refused with a
BLOCKED result.

Discovery order: every ``Sitemap:`` line in robots.txt, then the
conventional ``/sitemap.xml`` and ``/sitemap_index.xml`` paths as a
fallback. Each candidate that resolves to valid XML is parsed and checked
against the sitemaps.org protocol limits (50,000 URLs / 50MB uncompressed
per file) plus a handful of quality checks: HTTPS-only entries, sane
<lastmod> dates, and duplicate <loc> entries.

Usage:
    python3 sitemap_check.py https://example.com [--max-urls-preview 10]

Exit codes: 0 = a valid sitemap was found with no protocol violations;
1 = a discovered sitemap has protocol violations (over the URL/size cap,
non-HTTPS entries mixed with HTTPS); 2 = usage/blocked; 3 = no sitemap
could be found or parsed at all.
"""
import os
import re
import sys
import argparse
import datetime
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

sys.path.insert(0, os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "lib")))
try:
    from url_guard import safe_get, check_url, BlockedUrlError
except ImportError:
    sys.exit("url_guard.py not found — run from an intact seo plugin")

UA = "solo-suite-seo/1.0"
TIMEOUT = 15
MAX_BYTES = 55 * 1024 * 1024  # a little over the 50MB sitemap cap, to still
                               # be able to report "this file is over limit"
SITEMAP_URL_CAP = 50_000
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
NEWS_URL_CAP = 1_000


def fetch_text(url):
    try:
        r = safe_get(url, timeout=TIMEOUT, allow_http=True, max_bytes=MAX_BYTES,
                     headers={"User-Agent": UA})
    except BlockedUrlError as e:
        return None, "BLOCKED: %s" % e
    except Exception as e:
        return None, "request failed: %s" % e
    if not 200 <= r.status < 300:
        return None, "HTTP %s" % r.status
    body = r.body or b""
    if not body.strip():
        return None, "empty response body"
    try:
        return body.decode("utf-8", "strict"), None
    except UnicodeDecodeError:
        return body.decode("utf-8", "replace"), "body was not valid UTF-8 (replaced invalid bytes)"


def discover_candidates(base_url):
    """Return an ordered, deduplicated list of candidate sitemap URLs."""
    candidates = []
    robots_url = urljoin(base_url, "/robots.txt")
    text, err = fetch_text(robots_url)
    if text:
        for line in text.splitlines():
            m = re.match(r"(?i)^\s*sitemap:\s*(\S+)", line)
            if m:
                candidates.append(m.group(1).strip())
    for fallback in ("/sitemap.xml", "/sitemap_index.xml"):
        u = urljoin(base_url, fallback)
        if u not in candidates:
            candidates.append(u)
    seen, ordered = set(), []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def is_sitemap_index(root):
    return root.tag == SITEMAP_NS + "sitemapindex"


def parse_sitemap(xml_text):
    """Return (kind, entries, error) where kind is 'urlset', 'sitemapindex',
    or None on parse failure. entries is a list of dicts with loc/lastmod."""
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as e:
        return None, [], "XML parse error: %s" % e
    is_news = any("news" in child.tag.lower() for child in root.iter())
    if is_sitemap_index(root):
        entries = []
        for sm in root.findall(SITEMAP_NS + "sitemap"):
            loc = sm.findtext(SITEMAP_NS + "loc")
            lastmod = sm.findtext(SITEMAP_NS + "lastmod")
            entries.append({"loc": loc, "lastmod": lastmod})
        return "sitemapindex", entries, None
    entries = []
    for u in root.findall(SITEMAP_NS + "url"):
        loc = u.findtext(SITEMAP_NS + "loc")
        lastmod = u.findtext(SITEMAP_NS + "lastmod")
        entries.append({"loc": loc, "lastmod": lastmod})
    return ("newsurlset" if is_news else "urlset"), entries, None


def validate_lastmod(value):
    if not value:
        return None
    v = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            datetime.datetime.strptime(v.replace("Z", "+0000"), fmt)
            return True
        except ValueError:
            continue
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base_url")
    ap.add_argument("--max-urls-preview", type=int, default=10)
    args = ap.parse_args()

    base = args.base_url.strip()
    try:
        check_url(base, allow_http=True)
    except BlockedUrlError as e:
        print(f"BLOCKED unsafe target: {e}")
        return 2

    candidates = discover_candidates(base)
    print(f"=== Sitemap discovery for {base} ===\n")
    print(f"Checked {len(candidates)} candidate location(s):")

    found = None
    for c in candidates:
        text, err = fetch_text(c)
        if not text:
            print(f"  [skip] {c} — {err}")
            continue
        kind, entries, perr = parse_sitemap(text)
        if perr:
            print(f"  [skip] {c} — {perr}")
            continue
        print(f"  [found] {c} — {kind}, {len(entries)} entries")
        found = (c, kind, entries, len(text.encode('utf-8')))
        break

    if not found:
        print("\n[UNVERIFIED] no candidate resolved to a parseable sitemap — "
              "nothing was found in robots.txt or the conventional paths")
        return 3

    url, kind, entries, byte_size = found
    fails, warns = 0, 0

    if kind == "sitemapindex":
        print(f"\nThis is a sitemap index with {len(entries)} child sitemap(s):")
        for e in entries[:args.max_urls_preview]:
            print(f"  - {e['loc']}  (lastmod: {e['lastmod'] or 'none'})")
        if len(entries) > args.max_urls_preview:
            print(f"  ... and {len(entries) - args.max_urls_preview} more")
    else:
        cap = NEWS_URL_CAP if kind == "newsurlset" else SITEMAP_URL_CAP
        cap_label = "news sitemap 1,000-URL" if kind == "newsurlset" else "50,000-URL"
        if len(entries) > cap:
            fails += 1
            print(f"\n[FAIL] {len(entries)} URLs exceeds the {cap_label} cap "
                  f"— split with a sitemap index")
        if byte_size > 50 * 1024 * 1024:
            fails += 1
            print(f"[FAIL] file is {byte_size / 1024 / 1024:.1f}MB uncompressed "
                  f"— exceeds the 50MB cap, split with a sitemap index")

        non_https = [e["loc"] for e in entries if e["loc"] and
                     urlparse(e["loc"]).scheme != "https"]
        if non_https:
            warns += 1
            print(f"[WARN] {len(non_https)} entries are not HTTPS "
                  f"(e.g. {non_https[0]})")

        locs = [e["loc"] for e in entries if e["loc"]]
        dupes = {u for u in locs if locs.count(u) > 1}
        if dupes:
            warns += 1
            print(f"[WARN] {len(dupes)} duplicate <loc> entries "
                  f"(e.g. {next(iter(dupes))})")

        bad_lastmod = [e for e in entries if e["lastmod"] and
                       validate_lastmod(e["lastmod"]) is False]
        if bad_lastmod:
            warns += 1
            print(f"[WARN] {len(bad_lastmod)} entries have an unparseable "
                  f"<lastmod> value (e.g. {bad_lastmod[0]['lastmod']!r})")

        lastmods = [e["lastmod"] for e in entries if e["lastmod"]]
        if lastmods and len(set(lastmods)) == 1 and len(lastmods) > 5:
            warns += 1
            print(f"[WARN] every entry shares the identical <lastmod> "
                  f"{lastmods[0]!r} — Google only trusts <lastmod> when it "
                  f"reflects real per-page changes")

        print(f"\nPreview ({min(len(entries), args.max_urls_preview)} of "
              f"{len(entries)} URLs):")
        for e in entries[:args.max_urls_preview]:
            print(f"  - {e['loc']}  (lastmod: {e['lastmod'] or 'none'})")

    print(f"\nRESULT: sitemap={url} kind={kind} entries={len(entries)} "
          f"fail={fails} warn={warns}")
    return 1 if fails else 0


def _harden_streams():
    """Never abort a report on a character the console cannot encode.

    Claude Code captures helper stdout through a pipe, so on Windows the
    stream encoding is the ANSI codepage (cp1252) rather than UTF-8. A CJK
    path, an emoji, or a "→" in captured content then raises
    UnicodeEncodeError mid-write -- the tool announces a finding and dies
    before printing where it is. Escaping instead of raising keeps ASCII
    output byte-identical while making that class of crash impossible.

    Called from __main__ only: importing this module (as the tests do) must
    never mutate the importing process's streams.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError, OSError):
            pass


if __name__ == "__main__":
    _harden_streams()
    sys.exit(main())
