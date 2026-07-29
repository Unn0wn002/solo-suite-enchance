#!/usr/bin/env python3
"""Reconstruct the missing catalog from the preserved learning-corpus snapshot."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from agent_platform_common import ROOT


EVIDENCE = ROOT / "docs" / "agent-audit" / "evidence" / "reconstructed-catalog.json"
CATALOG = ROOT / "docs" / "agent-extension-catalog.md"


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def component_kind(repository: str, subdirectory: str) -> str:
    if repository in {"storymap-skill", "gsap-skills"}:
        return "PORTABLE_AGENT_SKILL"
    if repository == "wshobson-agents":
        return "CLAUDE_PLUGIN"
    if repository == "qa-orchestra":
        return "COMMAND_OR_WORKFLOW"
    if repository in {"serena", "context7"}:
        return "MCP_SERVER"
    if repository in {"graphify", "repomix", "aider", "code-review-graph"}:
        return "LOCAL_CLI_TOOL"
    return "REFERENCE_LIBRARY"


def parse_source(source_root: Path) -> dict[str, object]:
    role_path = source_root / "ROLE_CATALOG.md"
    repositories_path = source_root / "REPOSITORIES.json"
    if not role_path.is_file() or not repositories_path.is_file():
        raise FileNotFoundError("ROLE_CATALOG.md or REPOSITORIES.json is missing from the source root")
    repository_data = json.loads(repositories_path.read_text(encoding="utf-8"))
    repositories = {item["name"]: item for item in repository_data["repositories"]}

    role = None
    role_index = None
    rows = []
    for line_number, line in enumerate(role_path.read_text(encoding="utf-8").splitlines(), start=1):
        heading = re.match(r"^##\s+(\d+)\.\s+(.+?)\s*$", line)
        if heading:
            role_index = int(heading.group(1))
            role = heading.group(2)
            continue
        bullet = re.match(r"^-\s+([^:]+):\s+`repositories/([^/]+)(?:/(.+))?`\s*$", line)
        if not bullet or role is None or role_index is None:
            continue
        display_name = bullet.group(1).strip()
        repository_alias = bullet.group(2)
        subdirectory = bullet.group(3) or "."
        repository = repositories.get(repository_alias)
        if not repository:
            raise ValueError(f"unmapped repository alias on source line {line_number}: {repository_alias}")
        url = repository["upstream"].removesuffix(".git")
        parsed = re.match(r"^https://github\.com/([^/]+)/([^/]+)$", url)
        if not parsed:
            raise ValueError(f"unsupported repository URL: {url}")
        owner, repo_name = parsed.groups()
        capability = f"{display_name} capability for the {role} role."
        rows.append({
            "entry_id": f"{slug(role)}::{repository_alias}::{slug(subdirectory)}",
            "ordinal": len(rows) + 1,
            "source_line": line_number,
            "role": role,
            "role_index": role_index,
            "category": display_name,
            "display_name": display_name,
            "catalog_path": f"repositories/{repository_alias}/{subdirectory}" if subdirectory != "." else f"repositories/{repository_alias}",
            "repository_url": url,
            "normalized_source_id": repository_alias,
            "owner": owner,
            "repository": repo_name,
            "repository_alias": repository_alias,
            "repository_commit": repository["commit"],
            "subdirectory": subdirectory,
            "intended_capability": capability,
            "component_kind": component_kind(repository_alias, subdirectory),
        })
    if len(rows) != 69:
        raise ValueError(f"expected 69 role-catalog bullets, found {len(rows)}")
    return {
        "schema_version": 1,
        "catalog_source_status": "RECONSTRUCTED_CANONICAL_V1",
        "reconstruction_date": repository_data["capturedAt"],
        "source_documents": [
            "../EC Solo Suite Learns/ROLE_CATALOG.md",
            "../EC Solo Suite Learns/REPOSITORIES.json",
            "capability-inventory.json",
        ],
        "source_snapshot": {
            "captured_at": repository_data["capturedAt"],
            "clone_mode": repository_data["cloneMode"],
        },
        "reconstruction_notes": [
            "The requested docs/agent-extension-catalog.md did not exist in the repository or its Git history at audit start.",
            "No authoritative historical copy was found in configured remotes, Downloads, Documents, OneDrive, or sibling checkouts on 2026-07-29.",
            "The reconstructed result is adopted as repository-canonical v1 while preserving its reconstructed provenance.",
            "All 69 role rows are preserved; repeated paths remain separate catalog entries and are deduplicated only at source-audit time.",
            "Category and display name preserve the ROLE_CATALOG bullet label because no separate category field existed.",
        ],
        "total_catalog_entries": len(rows),
        "unique_sources": len({row["repository_url"] for row in rows}),
        "entries": rows,
    }


def render_markdown(data: dict[str, object]) -> str:
    rows = data["entries"]
    lines = [
        "# Agent Extension Catalog",
        "",
        "> Status: `RECONSTRUCTED_CANONICAL_V1`. No authoritative historical copy was found in the working tree, Git history, configured remotes, user document roots, or sibling checkouts. This snapshot was recovered from the read-only learning corpus documents named below and is now the repository canonical catalog; it preserves every role assignment but does not claim unknown historical wording.",
        "",
        "## Provenance",
        "",
        f"- Catalog entries: {data['total_catalog_entries']}",
        f"- Unique repositories: {data['unique_sources']}",
        f"- Snapshot date: {data['reconstruction_date']}",
        "- Sources: `../EC Solo Suite Learns/ROLE_CATALOG.md`, `../EC Solo Suite Learns/REPOSITORIES.json`, and `capability-inventory.json`.",
        "",
        "Repeated rows intentionally preserve role assignments. Source cloning and audit storage are normalized by repository URL.",
        "",
        "## Entries",
        "",
        "| # | Team role | Category | Display name | Repository URL | Owner | Repository | Subdirectory | Intended capability | Component kind |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        values = [
            str(row["ordinal"]),
            row["role"],
            row["category"],
            row["display_name"],
            row["repository_url"],
            row["owner"],
            row["repository"],
            f"`{row['subdirectory']}`",
            row["intended_capability"],
            f"`{row['component_kind']}`",
        ]
        lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in values) + " |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT.parent / "EC Solo Suite Learns",
        help="Read-only source folder containing ROLE_CATALOG.md and REPOSITORIES.json.",
    )
    parser.add_argument("--from-evidence", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.from_evidence or args.check:
        if not EVIDENCE.is_file():
            print("ERROR: reconstructed catalog evidence is missing", file=sys.stderr)
            return 2
        data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    else:
        try:
            data = parse_source(args.source_root.resolve())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
    markdown = render_markdown(data)

    if args.check:
        errors = []
        if data.get("total_catalog_entries") != 69 or len(data.get("entries", [])) != 69:
            errors.append("reconstructed evidence does not contain 69 entries")
        if not CATALOG.is_file() or CATALOG.read_text(encoding="utf-8") != markdown:
            errors.append("docs/agent-extension-catalog.md is stale")
        for error in errors:
            print(f"ERROR: {error}")
        return 1 if errors else 0
    if args.dry_run:
        print(markdown)
        return 0
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    CATALOG.write_text(markdown, encoding="utf-8", newline="\n")
    print(f"wrote {EVIDENCE.relative_to(ROOT).as_posix()} and {CATALOG.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
