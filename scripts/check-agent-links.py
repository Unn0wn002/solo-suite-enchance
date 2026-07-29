#!/usr/bin/env python3
"""Check local Markdown links and optionally verify external HTTP targets."""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse

from agent_platform_common import ROOT, is_within, relative


LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
DOC_ROOTS = [ROOT / "docs" / "agent-audit", ROOT / "agent-platform", ROOT / ".agents", ROOT / ".claude"]
DOC_FILES = [ROOT / "AGENTS.md", ROOT / "CLAUDE.md", ROOT / "THIRD_PARTY_NOTICES.md"]


def markdown_files() -> list[Path]:
    files = [path for path in DOC_FILES if path.is_file()]
    for root in DOC_ROOTS:
        if root.is_dir():
            files.extend(root.rglob("*.md"))
    return sorted(set(files))


def external_status(url: str, timeout: float) -> tuple[bool, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "solo-suite-agent-audit/1.0"}, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 400, str(response.status)
    except urllib.error.HTTPError as exc:
        if exc.code in {405, 429}:
            request = urllib.request.Request(url, headers={"User-Agent": "solo-suite-agent-audit/1.0"})
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    return 200 <= response.status < 400, str(response.status)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as retry:
                return False, str(retry)
        return False, str(exc.code)
    except (urllib.error.URLError, TimeoutError) as exc:
        return False, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--external", action="store_true", help="Verify HTTP(S) links over the network.")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    errors: list[str] = []
    external: set[str] = set()
    for file in markdown_files():
        text = file.read_text(encoding="utf-8")
        for raw in LINK_RE.findall(text):
            target = raw.strip().split(maxsplit=1)[0].strip("<>")
            parsed = urlparse(target)
            if parsed.scheme in {"http", "https"}:
                external.add(target)
                continue
            if parsed.scheme or target.startswith("#"):
                continue
            local = (file.parent / unquote(parsed.path)).resolve()
            if not is_within(local, ROOT):
                errors.append(f"{relative(file)}: link escapes repository: {target}")
            elif not local.exists():
                errors.append(f"{relative(file)}: missing local link target: {target}")

    if args.external:
        for url in sorted(external):
            ok, status = external_status(url, args.timeout)
            print(f"{'OK' if ok else 'BROKEN'} {status} {url}")
            if not ok:
                errors.append(f"external link failed ({status}): {url}")
    else:
        print(f"External links NOT_EXECUTED: {len(external)} URL(s); pass --external to verify")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Agent link validation passed: {len(markdown_files())} Markdown files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
