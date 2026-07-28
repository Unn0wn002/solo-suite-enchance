#!/usr/bin/env python3
"""check_mobile.py — fetch a page and check mobile-readiness signals:
viewport meta tag, web app manifest + theme-color, responsive image hints,
and fixed-width/px-heavy layout signals.

Stdlib only. Outbound requests go through lib/url_guard.py (SSRF guard) —
private/internal/metadata targets and unsafe redirects are refused with a
BLOCKED result. Usage:
    python3 check_mobile.py https://example.com

Layout/interaction quality still needs a real browser at multiple widths;
this checks the machine-detectable signals. Exit 0 always (informational).
"""
import os
import sys
import re
from html.parser import HTMLParser

sys.path.insert(0, os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "lib")))
try:
    from url_guard import safe_get, BlockedUrlError
except ImportError:
    sys.exit("url_guard.py not found — run from an intact site-doctor plugin")

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) site-doctor-mobile/1.0"
TIMEOUT = 15
MAX_BYTES = 2 * 1024 * 1024  # response read cap


class MobileParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.viewport = None
        self.has_manifest = False
        self.theme_color = None
        self.apple_touch_icon = False
        self.imgs = 0
        self.imgs_with_srcset = 0
        self.pictures = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            name = (a.get("name") or "").lower()
            if name == "viewport":
                self.viewport = a.get("content", "")
            elif name == "theme-color":
                self.theme_color = a.get("content", "")
        elif tag == "link":
            rel = (a.get("rel") or "").lower()
            if rel == "manifest":
                self.has_manifest = True
            if "apple-touch-icon" in rel:
                self.apple_touch_icon = True
        elif tag == "img":
            self.imgs += 1
            if a.get("srcset"):
                self.imgs_with_srcset += 1
        elif tag == "picture":
            self.pictures += 1


def fetch(url):
    try:
        r = safe_get(url, timeout=TIMEOUT, allow_http=True, max_bytes=MAX_BYTES,
                     headers={"User-Agent": UA})
        if r.status >= 400:
            return r.status, ""
        return r.status, (r.body or b"").decode("utf-8", "replace")
    except BlockedUrlError as e:
        print(f"BLOCKED unsafe target: {e}")
        return None, ""
    except Exception as e:
        print(f"Could not fetch {url}: {e}")
        return None, ""


def check(label, ok, detail, warn=False):
    mark = "PASS" if ok else ("WARN" if warn else "FAIL")
    print(f"  [{mark}] {label}: {detail}")
    return ok


def main(url):
    status, html = fetch(url)
    if status is None:
        return 2
    print(f"=== Mobile readiness: {url} (status {status}) ===\n")
    p = MobileParser()
    try:
        p.feed(html)
    except Exception:
        pass

    print("Viewport:")
    if not p.viewport:
        check("viewport meta tag", False,
              "MISSING — page will render at desktop width on phones")
    else:
        v = p.viewport.lower()
        check("viewport meta tag", True, p.viewport)
        if "width=device-width" not in v:
            check("width=device-width", False,
                  "not set — responsive layout won't work correctly")
        if "user-scalable=no" in v or "maximum-scale=1" in v:
            check("zoom allowed", False,
                  "zoom is disabled — hurts accessibility, avoid this", warn=True)
    print()

    print("Responsive images:")
    if p.imgs == 0:
        print("  (no <img> tags found in initial HTML)")
    else:
        ratio = p.imgs_with_srcset / p.imgs if p.imgs else 0
        check(f"srcset usage ({p.imgs_with_srcset}/{p.imgs} imgs)",
              ratio >= 0.5,
              f"{round(ratio*100)}% of images use srcset "
              f"(+{p.pictures} <picture> elements)",
              warn=(0 < ratio < 0.5))
        if ratio == 0 and p.pictures == 0:
            print("        -> no responsive image hints; phones may download "
                  "full-size desktop images")
    print()

    print("PWA / installability signals:")
    check("web app manifest", p.has_manifest,
          "present" if p.has_manifest else "no <link rel=manifest> "
          "(only needed if you want install/offline)", warn=not p.has_manifest)
    check("theme-color", bool(p.theme_color),
          p.theme_color or "not set (styles the mobile browser chrome)",
          warn=not p.theme_color)
    check("apple-touch-icon", p.apple_touch_icon,
          "present" if p.apple_touch_icon else "not set (iOS home-screen icon)",
          warn=not p.apple_touch_icon)
    print()

    print("Fixed-width / px-heavy layout signals (heuristic):")
    fixed_px = len(re.findall(r"width\s*:\s*\d{3,}px", html))
    viewport_fixed = len(re.findall(r'width=["\']?\d{3,}', html))
    if fixed_px > 5:
        print(f"  [WARN] {fixed_px} 'width: NNNpx' declarations found — check "
              "these don't force horizontal scroll on narrow screens")
    else:
        print(f"  [ok] few hard-coded pixel widths in inline styles ({fixed_px})")
    if viewport_fixed > 3:
        print(f"  [WARN] {viewport_fixed} fixed-width HTML attributes found")
    print()

    print("NOTE: layout breaks, tap-target sizing, and touch interactions need")
    print("a real browser tested at 320px / 375px / 768px widths — this checks")
    print("only the machine-detectable signals.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
