#!/usr/bin/env python3
"""Canonical source for the shared "evidence-based audit format" block (T-018).

44 command files end with the same output contract. Markdown has no include
mechanism and a Claude command is a PROMPT -- the block has to be physically
present in each file or the model never sees the required shape -- so the
contract cannot be de-duplicated by reference without changing behaviour.

Instead it is canonicalised here and the copies are GENERATED from this one
definition:

    python tools/output_contract.py --check     # fail if any copy has drifted
    python tools/output_contract.py --write     # rewrite every copy

No symlinks and no runtime lookups are involved: the shipped files stay plain,
self-contained Markdown, so packaged plugins and Windows checkouts behave
exactly as before. `tests/test_output_contract.py` runs --check.

This module lives in tools/ deliberately: `release/build_release.py` ALLOW_DIRS
does not include tools/, so it is build-time source, never shipped, and it
creates no cross-plugin runtime dependency between independently installable
plugins.
"""
import argparse
import glob
import io
import os
import sys


HEADING = "## Output — evidence-based audit format"

CANONICAL = '''## Output — evidence-based audit format
Never just "good" or "bad" — every claim names its proof. If nothing was actually inspected for an area, say "not checked", don't guess. End with exactly:

```
## Status
PASS / WARNING / FAIL

## Evidence Checked
- File: …
- Config: …
- Page: …
- Command output: …
- Screenshot: …
- Connector data: …
(only the lines that apply — but at least one; no evidence, no finding)

## Findings
1. …
2. …

## Risk Level
Low / Medium / High / Critical

## Required Fixes
1. …

## Suggested Tasks
→ `.solo/tasks.md` entries with stable T-IDs

## Verification Steps
1. …

## Next Recommended Command
/…
```'''


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def command_files(root=None):
    root = root or repo_root()
    return sorted(
        p.replace(os.sep, "/")
        for p in glob.glob(os.path.join(root, "plugins", "*", "commands",
                                        "*.md")))


def extract(text):
    """Return (start, end) of the contract block, or None.

    The block runs from the heading to the close of the fenced example that
    follows it. The fence contains its own '## ' lines, so a heading-to-heading
    scan would truncate it -- that is exactly the mistake that made the
    animation.md drift look like a false positive.
    """
    start = text.find(HEADING)
    if start < 0:
        return None
    open_fence = text.find("```", start)
    if open_fence < 0:
        return None
    close_fence = text.find("```", open_fence + 3)
    if close_fence < 0:
        return None
    return start, close_fence + 3


def audit(root=None):
    """Return {path: current_block} for every copy that has drifted."""
    drifted = {}
    for path in command_files(root):
        with io.open(path, encoding="utf-8", newline="") as stream:
            text = stream.read()
        span = extract(text)
        if span is None:
            continue
        block = text[span[0]:span[1]]
        if block != CANONICAL:
            drifted[path] = block
    return drifted


def carriers(root=None):
    out = []
    for path in command_files(root):
        with io.open(path, encoding="utf-8", newline="") as stream:
            if extract(stream.read()) is not None:
                out.append(path)
    return out


def write(root=None):
    fixed = []
    for path in sorted(audit(root)):
        with io.open(path, encoding="utf-8", newline="") as stream:
            text = stream.read()
        start, end = extract(text)
        with io.open(path, "w", encoding="utf-8", newline="") as stream:
            stream.write(text[:start] + CANONICAL + text[end:])
        fixed.append(path)
    return fixed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true",
                       help="exit 1 if any copy differs from the canonical")
    group.add_argument("--write", action="store_true",
                       help="rewrite every drifted copy in place")
    args = parser.parse_args(argv)
    if args.write:
        fixed = write()
        for path in fixed:
            print("rewrote", path)
        print("%d file(s) rewritten; %d carry the contract"
              % (len(fixed), len(carriers())))
        return 0
    drifted = audit()
    for path in sorted(drifted):
        print("DRIFTED: %s" % path)
    print("%d carrier(s), %d drifted" % (len(carriers()), len(drifted)))
    return 1 if drifted else 0


if __name__ == "__main__":
    sys.exit(main())
