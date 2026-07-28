#!/usr/bin/env python3
"""animation_check.py — static scan of a project's source tree for GSAP
animation usage and common correctness/performance/accessibility gaps.

Stdlib only, local filesystem only (no network — there is nothing here for
url_guard to guard). Scans .js/.jsx/.ts/.tsx/.vue files under the given
project root for:

  - GSAP presence (import, require, or CDN <script> tag) and whether it's
    also declared in package.json (flags duplicate-load risk)
  - layout-triggering properties passed directly to gsap.to/from/fromTo/set
    (width/height/top/left/margin/padding) where a transform equivalent
    usually exists
  - cleanup signals: gsap.context/.revert(), useGSAP, ScrollTrigger.kill(),
    .kill() on stored tween/timeline refs, gsap.killTweensOf(), or an
    overwrite:true/'auto' tween option — vs. tween/timeline creation with
    none of these anywhere in the same file
  - prefers-reduced-motion handling: matchMedia("(prefers-reduced-motion"
    or gsap.matchMedia() anywhere in the scanned tree
  - ScrollTrigger usage without any refresh/cleanup awareness

This is a heuristic source-grep, not a real AST/control-flow analysis —
false positives/negatives are expected on unusual code shapes. Treat its
output as a prioritized starting point for manual review, not a verdict.

Usage:
    python3 animation_check.py /path/to/project

Exit codes: 0 = GSAP found, no heuristic gaps flagged; 1 = gaps flagged;
2 = usage error; 3 = no GSAP usage detected in the scanned tree.
"""
import os
import re
import sys
import json

SOURCE_EXT = (".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte")
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt",
             ".svelte-kit", "out", "coverage", "__pycache__", ".cache"}
MAX_FILES = 4000
MAX_FILE_BYTES = 1_000_000

GSAP_IMPORT_RE = re.compile(r'''(?:from\s+["']gsap|require\(["']gsap|import\s+gsap|<script[^>]+gsap[^>]*cdn)''', re.IGNORECASE)
GSAP_CDN_RE = re.compile(r'<script[^>]+src=["\'][^"\']*gsap[^"\']*["\']', re.IGNORECASE)
TWEEN_CALL_RE = re.compile(r'gsap\.(to|from|fromTo|set|timeline)\s*\(')
SCROLLTRIGGER_CREATE_RE = re.compile(r'ScrollTrigger\.create\s*\(')
LAYOUT_PROP_RE = re.compile(
    r'(?:^|[,{\s])(width|height|top|left|right|bottom|margin(?:Top|Bottom|Left|Right)?|padding(?:Top|Bottom|Left|Right)?)\s*:',
    re.MULTILINE)
CLEANUP_SIGNAL_RE = re.compile(
    r'gsap\.context\s*\(|\.revert\(\)|useGSAP\s*\(|ScrollTrigger\.kill\s*\(|'
    r'ScrollTrigger\.getAll\s*\(|\.kill\(\)|gsap\.killTweensOf\s*\(|'
    r'overwrite\s*:\s*(?:true|["\']auto["\'])')
REDUCED_MOTION_RE = re.compile(
    r'prefers-reduced-motion|gsap\.matchMedia\s*\(')
SCROLLTRIGGER_ANY_RE = re.compile(r'ScrollTrigger\b')
SCROLLTRIGGER_REFRESH_RE = re.compile(r'ScrollTrigger\.refresh\s*\(')


def iter_source_files(root):
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(SOURCE_EXT):
                count += 1
                if count > MAX_FILES:
                    return
                yield os.path.join(dirpath, fn)


def read_text(path):
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return None
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def main():
    if len(sys.argv) != 2:
        print("usage: animation_check.py /path/to/project")
        return 2
    root = sys.argv[1]
    if not os.path.isdir(root):
        print(f"not a directory: {root}")
        return 2

    files_with_gsap = []
    files_with_layout_anim = []
    files_with_tweens_no_cleanup = []
    scrolltrigger_files = []
    scrolltrigger_files_no_refresh_awareness = []
    reduced_motion_hits = 0
    cdn_hits = []
    total_scanned = 0

    for path in iter_source_files(root):
        text = read_text(path)
        if text is None:
            continue
        total_scanned += 1
        rel = os.path.relpath(path, root)

        has_gsap = bool(GSAP_IMPORT_RE.search(text)) or bool(TWEEN_CALL_RE.search(text))
        if not has_gsap:
            continue
        files_with_gsap.append(rel)

        if GSAP_CDN_RE.search(text):
            cdn_hits.append(rel)

        tween_calls = TWEEN_CALL_RE.findall(text)
        if tween_calls:
            # crude property-block scope: look at the ~300 chars following
            # each gsap.to(/from(/fromTo( call for layout properties
            for m in TWEEN_CALL_RE.finditer(text):
                window = text[m.end():m.end() + 300]
                if LAYOUT_PROP_RE.search(window):
                    files_with_layout_anim.append(rel)
                    break
            if not CLEANUP_SIGNAL_RE.search(text):
                files_with_tweens_no_cleanup.append(rel)

        if SCROLLTRIGGER_ANY_RE.search(text):
            scrolltrigger_files.append(rel)
            if not SCROLLTRIGGER_REFRESH_RE.search(text) and not CLEANUP_SIGNAL_RE.search(text):
                scrolltrigger_files_no_refresh_awareness.append(rel)

        if REDUCED_MOTION_RE.search(text):
            reduced_motion_hits += 1

    # package.json cross-check for CDN+npm duplicate-load risk
    pkg_path = os.path.join(root, "package.json")
    gsap_in_package = False
    if os.path.isfile(pkg_path):
        try:
            with open(pkg_path, encoding="utf-8") as f:
                pkg = json.load(f)
            deps = {}
            deps.update(pkg.get("dependencies", {}))
            deps.update(pkg.get("devDependencies", {}))
            gsap_in_package = "gsap" in deps
        except (OSError, json.JSONDecodeError):
            pass

    print(f"=== Animation (GSAP) scan: {root} ===\n")
    print(f"Scanned {total_scanned} source file(s) under {root}.")
    print(f"Files using GSAP: {len(files_with_gsap)}")

    if not files_with_gsap:
        print("\n[UNVERIFIED] no GSAP usage detected in the scanned tree — "
              "nothing to audit here (or the project uses a different "
              "animation approach entirely).")
        return 3

    fails = warns = 0

    if cdn_hits and gsap_in_package:
        warns += 1
        print(f"\n[WARN] GSAP is loaded via both a CDN <script> tag AND the "
              f"npm package in {len(cdn_hits)} file(s) — e.g. {cdn_hits[0]}. "
              f"Loading it twice risks duplicate global state and version "
              f"drift; pick one.")

    if files_with_layout_anim:
        warns += 1
        print(f"\n[WARN] {len(files_with_layout_anim)} file(s) appear to "
              f"animate layout-triggering properties (width/height/top/"
              f"left/margin/padding) directly, e.g. {files_with_layout_anim[0]}. "
              f"A transform equivalent (x/y/scale) usually achieves the "
              f"same visual result without forcing layout — see the "
              f"gsap-performance skill.")

    if files_with_tweens_no_cleanup:
        fails += 1
        print(f"\n[FAIL] {len(files_with_tweens_no_cleanup)} file(s) create "
              f"tweens/timelines with no cleanup signal anywhere in the "
              f"file (no gsap.context, .revert(), useGSAP, or .kill()), "
              f"e.g. {files_with_tweens_no_cleanup[0]}. In a component that "
              f"mounts/unmounts repeatedly (SPA route changes, React/Vue "
              f"component lifecycle) this leaks running animations bound "
              f"to removed DOM nodes.")

    if scrolltrigger_files_no_refresh_awareness:
        warns += 1
        print(f"\n[WARN] {len(scrolltrigger_files_no_refresh_awareness)} "
              f"file(s) use ScrollTrigger with no refresh/kill awareness "
              f"nearby, e.g. {scrolltrigger_files_no_refresh_awareness[0]}. "
              f"Dynamic layout changes (images loading, content toggling) "
              f"need an explicit ScrollTrigger.refresh() or the trigger "
              f"positions go stale.")

    if reduced_motion_hits == 0:
        warns += 1
        print(f"\n[WARN] no `prefers-reduced-motion` handling detected "
              f"anywhere in the scanned tree. Motion-sensitive users have "
              f"no way to opt out; wrap non-essential animation in "
              f"gsap.matchMedia() or a prefers-reduced-motion check.")
    else:
        print(f"\n[OK] prefers-reduced-motion handling detected in "
              f"{reduced_motion_hits} location(s).")

    print(f"\nRESULT: files_with_gsap={len(files_with_gsap)} "
          f"scrolltrigger_files={len(scrolltrigger_files)} "
          f"fail={fails} warn={warns}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
