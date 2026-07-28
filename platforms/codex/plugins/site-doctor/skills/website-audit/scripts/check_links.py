#!/usr/bin/env python3
"""check_links.py — crawl same-domain pages, verify every link and asset,
and flag broken links (status >= 400), mixed content, and long redirect chains.

Stdlib only. Outbound requests go through lib/url_guard.py (SSRF guard) —
private/internal/metadata targets and unsafe redirects are refused with a
BLOCKED result. Usage:
    python3 check_links.py https://example.com [--max-pages 30] [--delay 0.3]
        [--max-urls 500] [--max-requests 750] [--max-total-bytes 33554432]
        [--max-seconds 300] [--max-output-findings 200]
        [--max-redirect-hops 2] [--fail-on-mixed]

Exit code: 0 = clean, 1 = broken links found (or mixed content with
--fail-on-mixed, or redirect chains past --max-redirect-hops), 2 = could
not start crawl. Numeric options must be positive (delay may be 0).

Exit codes: 0 = crawl complete, nothing broken; 1 = broken links / long
redirect chains (or mixed content with --fail-on-mixed); 2 = usage or
blocked start URL; 3 = nothing broken but coverage is UNVERIFIED (crawl
stopped by a page/request/URL/byte/time budget or a truncated response).
"""
import os
import sys
import time
import argparse
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urldefrag
from collections import deque

sys.path.insert(0, os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "lib")))
try:
    from url_guard import safe_get, check_url, BlockedUrlError
except ImportError:
    sys.exit("url_guard.py not found — run from an intact site-doctor plugin")

UA = "site-doctor-linkcheck/1.0"
TIMEOUT = 12
MAX_BYTES = 2 * 1024 * 1024  # per-response read cap


class LinkExtractor(HTMLParser):
    """Collect hrefs (navigable) and asset srcs separately."""

    def __init__(self):
        super().__init__()
        self.links, self.assets = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag in ("img", "script", "iframe", "source", "video", "audio") and a.get("src"):
            self.assets.append(a["src"])
        elif tag == "link" and a.get("href"):
            self.assets.append(a["href"])


def _budget_exhausted(budget):
    if budget is None:
        return None
    if time.monotonic() >= budget["deadline"]:
        return "wall-clock budget reached"
    if budget["requests"] >= budget["max_requests"]:
        return "request budget reached"
    if budget["bytes"] >= budget["max_bytes"]:
        return "response-byte budget reached"
    return budget.get("reason")


def request(url, method="HEAD", budget=None):
    """Return status, URL, hops, type, body, and truncation state.

    A global crawl budget is translated into a per-request timeout and body
    cap.  That keeps one slow or oversized response from silently overrunning
    the aggregate limits.
    """
    exhausted = _budget_exhausted(budget)
    if exhausted:
        if budget is not None:
            budget["reason"] = exhausted
        return f"BUDGET: {exhausted}", url, 0, "", None, False
    timeout = TIMEOUT
    max_bytes = MAX_BYTES
    if budget is not None:
        remaining_seconds = budget["deadline"] - time.monotonic()
        remaining_bytes = budget["max_bytes"] - budget["bytes"]
        if remaining_seconds <= 0:
            budget["reason"] = "wall-clock budget reached"
            return "BUDGET: wall-clock budget reached", url, 0, "", None, False
        if remaining_bytes <= 0:
            budget["reason"] = "response-byte budget reached"
            return "BUDGET: response-byte budget reached", url, 0, "", None, False
        timeout = max(0.001, min(TIMEOUT, remaining_seconds))
        max_bytes = min(MAX_BYTES, remaining_bytes)
        budget["requests"] += 1
    try:
        r = safe_get(url, method=method, timeout=timeout, allow_http=True,
                     max_bytes=max_bytes, headers={"User-Agent": UA})
    except BlockedUrlError as e:
        return f"BLOCKED: {e}", url, 0, "", None, False
    except Exception as e:
        if budget is not None and time.monotonic() >= budget["deadline"]:
            budget["reason"] = "wall-clock budget reached"
            return "BUDGET: wall-clock budget reached", url, 0, "", None, False
        return f"ERR: {type(e).__name__}", url, 0, "", None, False
    if method == "HEAD" and r.status in (403, 405, 501):
        return request(url, "GET", budget)  # some servers reject HEAD
    if budget is not None and r.body:
        budget["bytes"] += len(r.body)
        if r.truncated:
            budget["reason"] = "response body truncated before complete coverage"
        elif budget["bytes"] >= budget["max_bytes"]:
            budget["reason"] = "response-byte budget reached"
    return (r.status, r.url, r.hops, r.headers.get("Content-Type", ""),
            r.body, bool(r.truncated))


def _sleep_with_budget(delay, budget):
    """Sleep no longer than the remaining crawl time; return whether usable."""
    if delay <= 0:
        return True
    remaining = budget["deadline"] - time.monotonic()
    if remaining <= 0:
        budget["reason"] = "wall-clock budget reached"
        return False
    time.sleep(min(delay, remaining))
    if delay >= remaining or time.monotonic() >= budget["deadline"]:
        budget["reason"] = "wall-clock budget reached"
        return False
    return True


def skippable(url):
    return url.startswith(("mailto:", "tel:", "javascript:", "data:", "#"))


def positive_int(value):
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return n


def non_negative_float(value):
    import math
    f = float(value)
    if not math.isfinite(f) or f < 0:
        raise argparse.ArgumentTypeError(
            "must be a finite number >= 0 (got %r)" % value)
    return f


def positive_float(value):
    f = non_negative_float(value)
    if f <= 0:
        raise argparse.ArgumentTypeError("must be a finite number > 0")
    return f


def parse_args(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("start_url")
    ap.add_argument("--max-pages", type=positive_int, default=30)
    ap.add_argument("--max-urls", type=positive_int, default=500,
                    help="maximum unique URLs admitted to the crawl")
    ap.add_argument("--max-requests", type=positive_int, default=750,
                    help="maximum HTTP attempts, including HEAD-to-GET fallbacks")
    ap.add_argument("--max-total-bytes", type=positive_int,
                    default=32 * 1024 * 1024,
                    help="maximum aggregate response-body bytes")
    ap.add_argument("--max-seconds", type=positive_float, default=300.0,
                    help="maximum total wall-clock runtime")
    ap.add_argument("--max-output-findings", type=positive_int, default=200,
                    help="maximum detailed findings printed per category")
    ap.add_argument("--delay", type=non_negative_float, default=0.3)
    ap.add_argument("--max-redirect-hops", type=positive_int, default=2,
                    help="redirect chains longer than this are reported "
                         "(and fail the run)")
    ap.add_argument("--max-redirects", dest="max_redirect_hops",
                    type=positive_int, default=argparse.SUPPRESS,
                    help=argparse.SUPPRESS)
    ap.add_argument("--fail-on-mixed", action="store_true",
                    help="exit non-zero when mixed content is found")
    ap.add_argument("--mixed-content", choices=("warn", "fail"),
                    help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.mixed_content == "fail":
        args.fail_on_mixed = True
    return args


def _request_result(value):
    """Normalize the legacy five-field request seam to the current six."""
    if len(value) == 5:
        return (*value, False)
    return value


def main(argv=None):
    args = parse_args(argv)

    start = args.start_url.rstrip("/")
    host = urlparse(start).netloc
    if not host:
        print("Invalid URL"); return 2
    try:
        check_url(start, allow_http=True)
    except BlockedUrlError as e:
        print(f"BLOCKED unsafe target: {e}"); return 2

    queue = deque([start])
    discovered = {start}
    seen_pages, checked, broken, mixed, long_chains = set(), {}, [], [], []
    budget = {
        "deadline": time.monotonic() + args.max_seconds,
        "requests": 0,
        "max_requests": args.max_requests,
        "bytes": 0,
        "max_bytes": args.max_total_bytes,
        "reason": None,
    }

    while queue and len(seen_pages) < args.max_pages:
        if _budget_exhausted(budget):
            budget["reason"] = _budget_exhausted(budget)
            break
        page = queue.popleft()
        if page in seen_pages:
            continue
        seen_pages.add(page)
        status, final, page_hops, ctype, body, truncated = _request_result(
            request(page, "GET", budget))
        print(f"[crawl {len(seen_pages)}/{args.max_pages}] {status} {page}")
        if isinstance(status, int) and page_hops > args.max_redirect_hops:
            long_chains.append((page, page_hops, final or page))
        if truncated or (isinstance(status, str) and
                         status.startswith("BUDGET:")):
            break
        if not isinstance(status, int) or status >= 400 or body is None:
            broken.append((page, status, "(crawled page)"))
            continue
        if "html" not in ctype:
            continue

        parser = LinkExtractor()
        try:
            parser.feed(body.decode("utf-8", errors="replace"))
        except Exception:
            continue

        page_https = urlparse(final).scheme == "https"
        for raw in parser.links + parser.assets:
            if skippable(raw):
                continue
            url = urldefrag(urljoin(final, raw))[0]
            scheme = urlparse(url).scheme
            if scheme not in ("http", "https"):
                continue
            if page_https and scheme == "http":
                mixed.append((final, url))
            if url not in discovered:
                if len(discovered) >= args.max_urls:
                    budget["reason"] = "unique-URL budget reached"
                    break
                discovered.add(url)
            if url not in checked:
                if _budget_exhausted(budget):
                    budget["reason"] = _budget_exhausted(budget)
                    break
                if not _sleep_with_budget(args.delay, budget):
                    break
                st, _, hops, _, _, truncated = _request_result(
                    request(url, "HEAD", budget))
                if truncated or (isinstance(st, str) and
                                 st.startswith("BUDGET:")):
                    break
                checked[url] = st
                if not isinstance(st, int) or st >= 400:
                    broken.append((final, st, url))
                elif hops > args.max_redirect_hops:
                    long_chains.append((final, hops, url))
            # enqueue same-host pages found via <a>
            if raw in parser.links and urlparse(url).netloc == host \
                    and url not in seen_pages and url not in queue:
                queue.append(url)
        if budget.get("reason"):
            break

    print(f"\n=== Link check summary for {start} ===")
    print(f"Pages crawled: {len(seen_pages)}   Unique URLs checked: {len(checked)}")
    if broken:
        print(f"\nBROKEN ({len(broken)}):")
        for src, st, url in broken[:args.max_output_findings]:
            print(f"  [{st}] {url}\n         found on: {src}")
        if len(broken) > args.max_output_findings:
            print(f"  ... {len(broken) - args.max_output_findings} omitted by output budget")
    if mixed:
        print(f"\nMIXED CONTENT ({len(mixed)}){' [configured as FAILURE]' if args.fail_on_mixed else ''}:")
        for src, url in mixed[:args.max_output_findings]:
            print(f"  {url}\n         loaded by: {src}")
        if len(mixed) > args.max_output_findings:
            print(f"  ... {len(mixed) - args.max_output_findings} omitted by output budget")
    if long_chains:
        print(f"\nREDIRECT CHAINS over {args.max_redirect_hops} hop(s) ({len(long_chains)}):")
        for src, hops, url in long_chains[:args.max_output_findings]:
            print(f"  [{hops} hops] {url}\n         found on: {src}")
        if len(long_chains) > args.max_output_findings:
            print(f"  ... {len(long_chains) - args.max_output_findings} omitted by output budget")
    if not broken and not mixed and not long_chains:
        print("No broken links, mixed content, or long redirect chains found.")
    failed = bool(broken) or bool(long_chains) or (args.fail_on_mixed and bool(mixed))
    unverified = 0
    if budget.get("reason"):
        unverified = 1
        print(f"[UNVERIFIED] crawl stopped: {budget['reason']} "
              f"(requests={budget['requests']}, bytes={budget['bytes']}, "
              f"urls={len(discovered)})")
    if len(seen_pages) >= args.max_pages and queue:
        unverified = 1
        print(f"[UNVERIFIED] crawl stopped at --max-pages {args.max_pages} "
              f"with {len(queue)} page(s) still queued - link coverage "
              "incomplete")
    ok = max(len(checked) - len(broken) - len(long_chains), 0)
    mixed_fail = len(mixed) if args.fail_on_mixed else 0
    print(f"RESULT: pass={ok} warn={len(mixed) - mixed_fail} "
          f"fail={len(broken) + len(long_chains) + mixed_fail} "
          f"unverified={unverified}")
    if failed:
        return 1
    if unverified:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
