#!/usr/bin/env python3
"""Guard capability parity between the Claude and Antigravity distributions.

Antigravity is intentionally a near-identical mirror of Claude for the plugin
capability surface. The only reviewed capability-content difference is the
project capability-routing skill. Antigravity also duplicates each plugin's
`.claude-plugin/plugin.json` at the plugin root for its loader.

This validator compares every regular file below `plugins/`, so new skills,
commands, helper libraries, manifests, or other plugin runtime files cannot
drift silently. Platform-specific top-level documentation and generated parity
artifacts are outside this capability-surface check.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / "platforms" / "claude" / "plugins"
ANTIGRAVITY = ROOT / "platforms" / "antigravity" / "plugins"

# Reviewed 2026-08-07 and documented in platforms/antigravity/parity/README.md.
ALLOWED_CONTENT_DIFFERENCES = {
    Path("project/skills/capability-routing/SKILL.md"):
        "Antigravity intentionally carries a condensed platform-specific routing skill",
}

IGNORE_NAMES = {"__pycache__"}
IGNORE_SUFFIXES = {".pyc", ".pyo"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root: Path) -> dict[Path, Path]:
    result: dict[Path, Path] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in IGNORE_NAMES for part in relative.parts):
            continue
        if path.suffix.lower() in IGNORE_SUFFIXES:
            continue
        result[relative] = path
    return result


def main() -> int:
    if not CLAUDE.is_dir() or not ANTIGRAVITY.is_dir():
        print("ERROR: Claude and Antigravity plugin roots must both exist", file=sys.stderr)
        return 1

    claude = files(CLAUDE)
    antigravity = files(ANTIGRAVITY)
    errors: list[str] = []

    # Antigravity's loader requires one root plugin.json per plugin. It must be
    # an exact duplicate of the canonical .claude-plugin/plugin.json.
    allowed_extras: set[Path] = set()
    for manifest in sorted(CLAUDE.glob("*/.claude-plugin/plugin.json")):
        plugin = manifest.parent.parent.name
        extra = Path(plugin) / "plugin.json"
        allowed_extras.add(extra)
        target = ANTIGRAVITY / extra
        if not target.is_file():
            errors.append(f"missing Antigravity loader manifest: plugins/{extra.as_posix()}")
        elif digest(target) != digest(manifest):
            errors.append(
                f"Antigravity loader manifest differs from canonical manifest: "
                f"plugins/{extra.as_posix()}"
            )

    claude_names = set(claude)
    antigravity_names = set(antigravity)

    for relative in sorted(claude_names - antigravity_names):
        errors.append(f"missing from Antigravity plugins: {relative.as_posix()}")

    unexplained_extras = antigravity_names - claude_names - allowed_extras
    for relative in sorted(unexplained_extras):
        errors.append(f"undeclared Antigravity-only plugin file: {relative.as_posix()}")

    for relative in sorted(claude_names & antigravity_names):
        if digest(claude[relative]) == digest(antigravity[relative]):
            continue
        if relative in ALLOWED_CONTENT_DIFFERENCES:
            continue
        errors.append(f"Claude/Antigravity plugin content drift: {relative.as_posix()}")

    # An allowlist entry should fail closed if the files disappear or converge;
    # otherwise stale exceptions can mask future changes.
    for relative in sorted(ALLOWED_CONTENT_DIFFERENCES):
        source = claude.get(relative)
        target = antigravity.get(relative)
        if source is None or target is None:
            errors.append(f"stale parity exception references missing file: {relative.as_posix()}")
        elif digest(source) == digest(target):
            errors.append(
                f"stale parity exception is no longer different: {relative.as_posix()} — "
                "remove it from ALLOWED_CONTENT_DIFFERENCES"
            )

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Distribution parity validation failed with {len(errors)} error(s)", file=sys.stderr)
        return 1

    mirrored = len(claude_names & antigravity_names) - len(ALLOWED_CONTENT_DIFFERENCES)
    print(
        "Claude/Antigravity distribution parity passed: "
        f"{mirrored} byte-identical plugin file(s), "
        f"{len(ALLOWED_CONTENT_DIFFERENCES)} reviewed content exception(s), "
        f"{len(allowed_extras)} verified Antigravity loader manifest duplicate(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
