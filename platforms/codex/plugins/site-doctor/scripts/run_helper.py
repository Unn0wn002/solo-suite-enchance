#!/usr/bin/env python3
"""Run a bundled site-doctor helper without depending on the caller's CWD.

The launcher resolves helpers from its own installed plugin directory and only
accepts identifiers in the allowlist below.  Invoke this file with the first
available Python command on the host (``python3``, ``python``, or ``py -3``),
then pass the helper identifier followed by its normal arguments.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HELPERS = {
    "website-audit/check-headers":
        "skills/website-audit/scripts/check_headers.py",
    "website-audit/check-links":
        "skills/website-audit/scripts/check_links.py",
    "compliance-check/scan-trackers":
        "skills/compliance-check/scripts/scan_trackers.py",
    "dependency-audit/check-deps":
        "skills/dependency-audit/scripts/check_deps.py",
    "email-deliverability/check-email-dns":
        "skills/email-deliverability/scripts/check_email_dns.py",
    "mobile-audit/check-mobile":
        "skills/mobile-audit/scripts/check_mobile.py",
    "security-review/scan-secrets":
        "skills/security-review/scripts/scan_secrets.py",
    "seo-optimization/extract-meta":
        "skills/seo-optimization/scripts/extract_meta.py",
}


def resolve_helper(identifier: str) -> Path:
    """Return an allowlisted helper path confined to this plugin root."""
    relative = HELPERS.get(identifier)
    if relative is None:
        raise ValueError("unknown helper identifier")
    candidate = (PLUGIN_ROOT / relative).resolve()
    try:
        candidate.relative_to(PLUGIN_ROOT)
    except ValueError as exc:  # defense in depth if the map is edited badly
        raise ValueError("helper path escapes the plugin root") from exc
    if not candidate.is_file():
        raise FileNotFoundError("bundled helper is missing")
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an allowlisted site-doctor helper from its installed root"
    )
    parser.add_argument("helper", choices=sorted(HELPERS))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    try:
        helper = resolve_helper(args.helper)
    except (ValueError, FileNotFoundError) as exc:
        parser.error(str(exc))
    completed = subprocess.run(
        [sys.executable, str(helper), *args.arguments],
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
