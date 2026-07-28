#!/usr/bin/env python3
"""schema_check.py — extract and sanity-check Schema.org JSON-LD blocks on a page.

Stdlib only. Outbound requests go through lib/url_guard.py (SSRF guard) —
private/internal/metadata targets and unsafe redirects are refused with a
BLOCKED result.

Parses every ``<script type="application/ld+json">`` block, reports each
detected @type, flags structural problems (missing @context/@type, invalid
JSON, relative URLs where an absolute one is expected), and flags a small
set of types Google no longer surfaces as rich results. The deprecated/
no-rich-result list below is a snapshot — verify against current Google
documentation before treating it as authoritative in a report.

Usage:
    python3 schema_check.py https://example.com/page

Exit codes: 0 = valid JSON-LD found, no structural problems; 1 = structural
problems found (broken JSON, missing required keys); 2 = usage/blocked;
3 = no JSON-LD detected at all.
"""
import os
import re
import sys
import json
import argparse
from urllib.parse import urlparse

sys.path.insert(0, os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "lib")))
try:
    from url_guard import safe_get, check_url, BlockedUrlError
except ImportError:
    sys.exit("url_guard.py not found — run from an intact seo plugin")

UA = "solo-suite-seo/1.0"
TIMEOUT = 15
MAX_BYTES = 3 * 1024 * 1024

JSONLD_BLOCK_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL)

# Snapshot only — re-verify against Google's current schema documentation
# before citing a specific date in a report.
NO_RICH_RESULT = {
    "FAQPage": "Google retired FAQ rich results suite-wide; keep existing "
               "markup as informational, don't add new FAQPage for a SERP "
               "payoff — use QAPage for genuine user Q&A instead.",
}
DEPRECATED = {
    "HowTo": "rich results removed; do not recommend",
}
REQUIRED_HINTS = {
    "Article": ("headline", "author"),
    "BlogPosting": ("headline", "author"),
    "NewsArticle": ("headline", "author", "datePublished"),
    "Product": ("name",),
    "LocalBusiness": ("name", "address"),
    "Organization": ("name", "url"),
    "Event": ("name", "startDate", "location"),
    "Review": ("itemReviewed", "reviewRating"),
    "BreadcrumbList": ("itemListElement",),
}


def fetch_html(url):
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
    return body.decode("utf-8", "replace"), None


def flatten_nodes(data):
    """Yield every dict node in a JSON-LD payload, including @graph members."""
    if isinstance(data, list):
        for item in data:
            yield from flatten_nodes(item)
    elif isinstance(data, dict):
        if "@graph" in data and isinstance(data["@graph"], list):
            for item in data["@graph"]:
                yield from flatten_nodes(item)
        else:
            yield data


def check_absolute(value, label, path, issues):
    if isinstance(value, str) and value and not urlparse(value).scheme:
        issues.append(f"{path}: {label} {value!r} looks relative — Google "
                       f"expects an absolute URL")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    args = ap.parse_args()

    try:
        check_url(args.url, allow_http=True)
    except BlockedUrlError as e:
        print(f"BLOCKED unsafe target: {e}")
        return 2

    html, err = fetch_html(args.url)
    if html is None:
        print(f"[error] {args.url} — {err}")
        return 2

    blocks = JSONLD_BLOCK_RE.findall(html)
    print(f"=== Schema (JSON-LD) check for {args.url} ===\n")
    print(f"Found {len(blocks)} <script type=\"application/ld+json\"> block(s).")

    if not blocks:
        has_microdata = bool(re.search(r'itemscope', html, re.IGNORECASE))
        has_rdfa = bool(re.search(r'\btypeof=', html, re.IGNORECASE))
        if has_microdata:
            print("[INFO] Microdata (itemscope) detected instead — Google "
                  "prefers JSON-LD; consider migrating.")
        if has_rdfa:
            print("[INFO] RDFa (typeof=) detected instead — Google prefers "
                  "JSON-LD; consider migrating.")
        if not has_microdata and not has_rdfa:
            print("[UNVERIFIED] no structured data of any format detected.")
        return 3

    fails = warns = 0
    seen_types = []
    for i, raw in enumerate(blocks):
        label = f"block {i + 1}"
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError as e:
            fails += 1
            print(f"\n[FAIL] {label}: invalid JSON — {e}")
            continue

        for node in flatten_nodes(data):
            if not isinstance(node, dict):
                continue
            node_type = node.get("@type", "(missing)")
            seen_types.append(node_type if isinstance(node_type, str) else str(node_type))
            path = f"{label} ({node_type})"

            if "@context" not in node and "@context" not in (data if isinstance(data, dict) else {}):
                warns += 1
                print(f"[WARN] {path}: no @context on this node "
                      f"(may be inherited from a parent — verify)")
            if node_type == "(missing)":
                fails += 1
                print(f"[FAIL] {path}: no @type present")
                continue

            if node_type in DEPRECATED:
                fails += 1
                print(f"[FAIL] {path}: @type {node_type!r} is deprecated — "
                      f"{DEPRECATED[node_type]}")
            elif node_type in NO_RICH_RESULT:
                print(f"[INFO] {path}: @type {node_type!r} — "
                      f"{NO_RICH_RESULT[node_type]}")

            required = REQUIRED_HINTS.get(node_type, ())
            missing = [k for k in required if k not in node]
            if missing:
                warns += 1
                print(f"[WARN] {path}: missing commonly-required "
                      f"propert{'y' if len(missing) == 1 else 'ies'}: "
                      f"{', '.join(missing)}")

            for key in ("url", "logo", "image"):
                val = node.get(key)
                if isinstance(val, str):
                    check_absolute(val, key, path, [])
                    if val and not urlparse(val).scheme:
                        warns += 1
                        print(f"[WARN] {path}: {key} {val!r} looks relative "
                              f"— use an absolute URL")

    print(f"\nTypes detected: {', '.join(sorted(set(seen_types))) or '(none)'}")
    print(f"\nRESULT: blocks={len(blocks)} fail={fails} warn={warns}")
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
