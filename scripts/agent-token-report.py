#!/usr/bin/env python3
"""Measure startup-context surfaces and generate the context report."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from agent_platform_common import ROOT, canonical_skills, parse_frontmatter


REPORT = ROOT / "docs" / "agent-audit" / "TOKEN_AND_CONTEXT_REPORT.md"


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def build_report() -> str:
    startup_files = [ROOT / "AGENTS.md", ROOT / "CLAUDE.md"]
    skill_rows = []
    descriptions: list[str] = []
    large_files: list[tuple[int, str, int]] = []
    for name, directory in canonical_skills().items():
        fields, body = parse_frontmatter(directory / "SKILL.md")
        description = fields.get("description", "")
        descriptions.append(description.lower())
        skill_rows.append((name, len(description), word_count(body)))
        for path in directory.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                large_files.append((path.stat().st_size, path.relative_to(ROOT).as_posix(), word_count(text)))
    duplicate_descriptions = [description for description, count in Counter(descriptions).items() if count > 1]

    profile_rows = []
    for path in sorted((ROOT / "agent-platform" / "profiles").glob("*.yaml")):
        data = json.loads(path.read_text(encoding="utf-8"))
        profile_rows.append(
            (
                data["name"],
                len(data.get("enabled_roles", [])),
                len(data.get("enabled_skills", [])),
                len(data.get("optional_skills", [])),
                len(data.get("external_tools", [])),
                data.get("token_budget_guidance", {}).get("target_max_active_skills", ""),
            )
        )

    mcp_files = [
        path for path in ROOT.rglob("*")
        if path.is_file()
        and "node_modules" not in path.parts
        and ".tmp" not in path.parts
        and (path.name == ".mcp.json" or "mcp" in path.name.lower())
    ]
    root_mcp = int((ROOT / ".mcp.json").exists())
    largest = sorted(large_files, reverse=True)[:10]

    lines = [
        "# Token and Context Report",
        "",
        "Generated from measured file sizes, word counts, metadata counts, and profile composition. These are context-pressure indicators, not exact model-token savings.",
        "",
        "## Estimated startup-context sources",
        "",
        "| Source | Bytes | Words | Loading behavior |",
        "| --- | ---: | ---: | --- |",
    ]
    for path in startup_files:
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            lines.append(f"| `{path.name}` | {path.stat().st_size} | {word_count(text)} | Startup instruction surface |")
    lines.append(f"| Canonical skill metadata | {sum(row[1] for row in skill_rows)} description characters | {len(skill_rows)} skills | Metadata first; bodies on demand |")
    lines.extend([
        "",
        "## Duplicate descriptions",
        "",
        f"- Exact duplicate canonical descriptions: {len(duplicate_descriptions)}.",
        "- Cross-platform mirrors are generated copies and should not be loaded together by one platform.",
        "",
        "## Large instruction and reference files",
        "",
        "| File | Bytes | Words |",
        "| --- | ---: | ---: |",
    ])
    for size, name, words in largest:
        lines.append(f"| `{name}` | {size} | {words} |")
    lines.extend([
        "",
        "## Large generated files",
        "",
        "- `graphify-out/`, dependencies, build output, coverage, media, caches, and repository dumps are excluded through `.graphifyignore`, `.repomixignore`, and `.claudeignore`.",
        "- Generated Graphify and Repomix output is not a startup instruction source.",
        "",
        "## MCP tool-count risks",
        "",
        f"- Root MCP activation files: {root_mcp}.",
        f"- Repository files with MCP in the filename outside dependencies/temp: {len(mcp_files)}; most belong to isolated platform distributions or audit documentation.",
        "- Exposing multiple broad MCP servers increases metadata, permission, and prompt-injection surface. Profiles therefore name external tools but do not activate servers.",
        "",
        "## Recommended active profile sizes",
        "",
        "| Profile | Roles | Enabled skills | Optional skills | External tools | Target max active skills |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in profile_rows:
        lines.append(f"| `{row[0]}` | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} |")
    lines.extend([
        "",
        "## Suggested token-reduction actions",
        "",
        "- Start with `planning` for new work, then switch to the single phase profile that owns the next artifact.",
        "- Load role definitions, complete skill bodies, and references only after metadata routing selects them.",
        "- Keep Graphify for relationships, bounded native search for symbols, primary official sources for current docs, and Repomix for bounded exports.",
        "- Keep Aider, Serena, Context7, and code-review-graph out of profiles and activation surfaces; their audit records remain evidence-only.",
        "- Do not place copied READMEs, full repository maps, source clones, or broad MCP inventories in startup instructions.",
        "- Re-run this measured report after adding skills or profiles; do not claim exact token savings without tokenizer-based measurement for the actual host/model.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    content = build_report()
    current = REPORT.read_text(encoding="utf-8") if REPORT.is_file() else None
    if args.check:
        if current != content:
            print("TOKEN_AND_CONTEXT_REPORT.md is stale", file=sys.stderr)
            return 1
        print("Token and context report is current")
        return 0
    if args.dry_run:
        print(content)
        return 0
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(content, encoding="utf-8", newline="\n")
    print(f"wrote {REPORT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
