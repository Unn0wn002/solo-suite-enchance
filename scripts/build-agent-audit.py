#!/usr/bin/env python3
"""Build deterministic agent-platform manifests, locks, notices, and audit reports."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from agent_platform_common import ROOT


AUDIT_PATH = ROOT / "docs" / "agent-audit" / "evidence" / "source-audits.json"
CATALOG_PATH = ROOT / "docs" / "agent-audit" / "evidence" / "reconstructed-catalog.json"
WSHOBSON_PATH = ROOT / "docs" / "agent-audit" / "evidence" / "wshobson-selected.json"
NPM_AUDIT_PATH = ROOT / "docs" / "agent-audit" / "evidence" / "npm-audit-summary.json"
SCANNER_AUDIT_PATH = ROOT / "docs" / "agent-audit" / "evidence" / "security-scanner-summary.json"
SECURITY_TOOL_LOCK_PATH = ROOT / "agent-platform" / "tooling" / "security-tools.lock.json"
HIGH_RISK_REMEDIATION_PATH = ROOT / "agent-platform" / "security" / "high-risk-remediations.json"
REQUESTED_ADDITIONS_PATH = ROOT / "docs" / "agent-audit" / "evidence" / "requested-source-additions.json"

ROLE_ROUTES = {
    "Product Manager": ("product-discovery", "planning", "product-manager"),
    "UI/UX Designer": ("ui-ux-design", "design", "ui-ux-designer"),
    "Software Architect": ("software-architecture", "architecture", "software-architect"),
    "Frontend Developer": ("frontend-development", "frontend", "frontend-developer"),
    "GSAP Animation Developer": ("gsap-animation", "gsap-animation", "gsap-animation-developer"),
    "Backend Developer": ("backend-development", "backend", "backend-developer"),
    "Database Engineer": ("database-engineering", "database", "database-engineer"),
    "QA Engineer": ("qa-verification", "qa", "qa-engineer"),
    "Security Reviewer": ("security-review", "security", "security-reviewer"),
    "DevOps Engineer": ("devops-release", "devops", "devops-engineer"),
    "Technical Writer": ("technical-writing", "documentation", "technical-writer"),
    "Data Analyst": ("data-analysis", "analytics", "data-analyst"),
    "Token Reduction and Repository Intelligence": (
        "repository-intelligence-routing",
        "architecture",
        "software-architect",
    ),
}

SOURCE_FINDINGS = {
    "aider": (
        "The CLI can mutate repositories, execute subprocesses, access home-directory configuration, "
        "send model/API traffic, and collect opt-out analytics. Its documentation includes pipe-to-shell "
        "installers; static source review also found TLS-verification overrides in an explicit flag path."
    ),
    "code-review-graph": (
        "The repository contains MCP configuration and session-start hooks, accepts remote-service "
        "credentials, performs repository analysis, and documents download-and-execute installation. "
        "Its overlapping graph capability is rejected; Graphify is the sole graph route."
    ),
    "context7": (
        "The MCP server sends documentation queries to an external service, accepts API credentials, "
        "has telemetry/configuration surfaces, and includes package cleanup lifecycle scripts. It is not "
        "activated at the repository root."
    ),
    "serena": (
        "The MCP server is intentionally capable of broad workspace reading/editing and subprocess use. "
        "Auxiliary source contains shell and recursive-removal operations; no server was started during audit."
    ),
    "graphify": (
        "The CLI can parse the repository and optionally use MCP, database, network, or model-provider "
        "integrations. Documentation includes a pipe-to-shell installer; this repository uses the audited "
        "CLI version or explicit project-local bootstrap and keeps generated output out of startup context."
    ),
    "repomix": (
        "The CLI reads and exports repository content and offers an MCP mode. Package manifests contain "
        "prepare/build lifecycle scripts, so no package installation was performed; use only filtered snapshots."
    ),
    "wshobson-agents": (
        "The selected Claude plugin set contains commands, agents, skills, and opt-in hook definitions. "
        "Some documentation demonstrates destructive or download-and-execute commands. No hook, command, "
        "or MCP configuration from the source was activated."
    ),
    "qa-orchestra": (
        "The workflow material includes examples for hooks and MCP-backed QA orchestration. It was adapted "
        "as bounded verification guidance rather than copied or activated."
    ),
    "gsap-skills": (
        "The selected skills are instruction-only, MIT-licensed, and contain no selected lifecycle, hook, "
        "MCP, or credential surface. Canonical guidance was independently normalized."
    ),
    "storymap-skill": (
        "The selected skill is instruction-only and MIT-licensed with no selected executable, hook, MCP, "
        "credential, or lifecycle surface. Canonical planning guidance was independently normalized."
    ),
}

HIGH_DECISIONS = {
    "aider": "Rejected; use the active platform client under repository policy.",
    "code-review-graph": "Rejected; Graphify is the sole relationship graph.",
    "context7": "Rejected; use primary official documentation through reviewed host web access.",
    "serena": "Rejected; use Graphify plus bounded native symbol search and client-native editing.",
}

COMPONENT_OVERRIDES = {
    ("wshobson-agents", "plugins/block-no-verify"): {
        "risk_level": "HIGH",
        "decision_status": "REJECTED",
        "primary_classification": "QUARANTINED",
        "recommendation": (
            "Do not copy or activate the settings-mutating hook command. Preserve only the verification-policy "
            "intent in AGENTS.md; any future project-local hook needs adversarial tests and separate approval."
        ),
    },
    ("wshobson-agents", "plugins/protect-mcp"): {
        "risk_level": "CRITICAL",
        "decision_status": "REJECTED",
        "primary_classification": "QUARANTINED",
        "recommendation": (
            "Do not activate, copy, or translate the automatic all-tool npx hook. Promotion requires an "
            "offline-reviewed pinned package, lock, privacy review, and explicit trust decision."
        ),
    },
    ("wshobson-agents", "plugins/cloud-infrastructure"): {
        "risk_level": "HIGH",
        "recommendation": (
            "Adapt instruction concepts only after removing download-and-execute examples; keep disabled by default."
        ),
    },
    ("wshobson-agents", "plugins/python-development"): {
        "risk_level": "HIGH",
        "recommendation": (
            "Adapt instruction concepts only after removing download-and-execute and broad cleanup examples."
        ),
    },
}

REPORT_PATHS = {
    "executive": ROOT / "docs" / "agent-audit" / "EXECUTIVE_SUMMARY.md",
    "inventory": ROOT / "docs" / "agent-audit" / "SOURCE_INVENTORY.md",
    "compatibility": ROOT / "docs" / "agent-audit" / "COMPATIBILITY_MATRIX.md",
    "security": ROOT / "docs" / "agent-audit" / "SECURITY_REPORT.md",
    "license": ROOT / "docs" / "agent-audit" / "LICENSE_REPORT.md",
    "deduplication": ROOT / "docs" / "agent-audit" / "DEDUPLICATION_REPORT.md",
    "installation": ROOT / "docs" / "agent-audit" / "INSTALLATION_GUIDE.md",
    "update": ROOT / "docs" / "agent-audit" / "UPDATE_GUIDE.md",
    "rejected": ROOT / "docs" / "agent-audit" / "REJECTED_AND_QUARANTINED.md",
    "manual": ROOT / "docs" / "agent-audit" / "MANUAL_REVIEW_REQUIRED.md",
    "platform_readme": ROOT / "agent-platform" / "README.md",
    "notices": ROOT / "THIRD_PARTY_NOTICES.md",
    "manifest": ROOT / "agent-platform" / "manifest.yaml",
    "lock": ROOT / "agent-platform" / "agent-extensions.lock.json",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def code(value: Any) -> str:
    return f"`{md(value)}`"


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or "capability"


def source_name(entry: dict[str, Any]) -> str:
    path = entry["subdirectory"]
    return entry["normalized_source_id"] if path == "." else f"{entry['normalized_source_id']}-{slug(path)}"


def component_policy(entry: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    policy = {
        "risk_level": source["risk_level"],
        "decision_status": source["decision_status"],
        "primary_classification": source["primary_classification"],
        "recommendation": source["recommendation"],
        "compatibility": dict(source["compatibility"]),
    }
    override = COMPONENT_OVERRIDES.get(
        (entry["normalized_source_id"], entry["subdirectory"]),
        {},
    )
    policy.update(override)
    if policy["decision_status"] in {"BLOCKED", "QUARANTINED", "REJECTED"}:
        policy["compatibility"] = {
            "chatgpt": "REJECTED",
            "codex": "REJECTED",
            "claude": "REJECTED",
            "antigravity": "REJECTED",
            "antigravity_cli": "REJECTED",
        }
    return policy


def group_entries(entries: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        groups[(entry["normalized_source_id"], entry["subdirectory"])].append(entry)
    return [groups[key] for key in sorted(groups)]


def build_manifest(
    audit: dict[str, Any],
    catalog: dict[str, Any],
    high_risk_remediations: dict[str, Any],
) -> tuple[dict[str, Any], dict[tuple[str, str], str]]:
    sources = {item["source_id"]: item for item in audit["sources"]}
    capabilities: list[dict[str, Any]] = []
    names: set[str] = set()
    group_names: dict[tuple[str, str], str] = {}
    remediation_by_name = {
        item["canonical_name"]: item
        for item in high_risk_remediations.get("findings", [])
        if isinstance(item, dict) and isinstance(item.get("canonical_name"), str)
    }
    for group in group_entries(catalog["entries"]):
        first = group[0]
        source = sources[first["normalized_source_id"]]
        policy = component_policy(first, source)
        name = source_name(first)
        if name in names:
            name = f"{first['normalized_source_id']}-{name}"
        names.add(name)
        key = (first["normalized_source_id"], first["subdirectory"])
        group_names[key] = name
        roles = sorted({entry["role"] for entry in group})
        categories = sorted({entry["category"] for entry in group})
        routes = [ROLE_ROUTES[role] for role in roles]
        skill_names = sorted({route[0] for route in routes})
        profiles = sorted({route[1] for route in routes})
        role_adapters = sorted({route[2] for route in routes})
        external = policy["decision_status"] == "EXTERNAL_TOOL_ONLY"
        rejected = policy["decision_status"] in {"BLOCKED", "QUARANTINED", "REJECTED"}
        primary_skill = (
            "repository-intelligence-routing"
            if external
            else skill_names[0]
        )
        duplicate_note: dict[str, Any] | None = None
        if len(group) > 1:
            duplicate_note = {
                "canonical_entry_id": first["entry_id"],
                "additional_role_assignments": [entry["entry_id"] for entry in group[1:]],
            }
        if source["source_id"] == "code-review-graph":
            duplicate_note = {
                "relationship": "rejected_duplicate_of",
                "canonical_capability": "graphify",
                "activation_constraint": "no activation path",
            }
        capability = {
                "canonical_name": name,
                "description": first["intended_capability"],
                "role_tags": roles,
                "category_tags": categories,
                "source_url": source["source_url"],
                "source_path": first["subdirectory"],
                "pinned_commit_sha": source["commit_sha"],
                "license": source["license"]["spdx"],
                "risk_level": policy["risk_level"],
                "primary_type": policy["primary_classification"],
                "status": policy["decision_status"],
                "integration_kind": (
                    "rejected_evidence"
                    if rejected
                    else "external_reference"
                    if external
                    else "original_adapter"
                ),
                "canonical_skill_path": None if rejected else f".agents/skills/{primary_skill}/SKILL.md",
                "related_canonical_skills": (
                    [] if rejected else [f".agents/skills/{item}/SKILL.md" for item in skill_names]
                ),
                "claude_adapter_path": (
                    None
                    if rejected
                    else f".claude/skills/{primary_skill}/SKILL.md"
                    if not external
                    else ".claude/skills/repository-intelligence-routing/SKILL.md"
                ),
                "antigravity_adapter_path": None if rejected else f".agents/skills/{primary_skill}/SKILL.md",
                "role_adapter_paths": (
                    {"claude": [], "antigravity": []}
                    if rejected
                    else {
                        "claude": [f".claude/agents/{item}.md" for item in role_adapters],
                        "antigravity": [f".agents/agents/{item}.md" for item in role_adapters],
                    }
                ),
                "external_tool_requirement": {
                    "name": source["source_id"] if external and not rejected else None,
                    "required": False,
                },
                "enabled_by_default": False,
                "activation_profile": [] if rejected else profiles,
                "replacement_or_duplicate_relationship": duplicate_note,
                "recommendation": policy["recommendation"],
            }
        remediation = remediation_by_name.get(name)
        if remediation:
            capability.update(
                {
                    "remediation_status": remediation["remediation_status"],
                    "residual_integration_risk": remediation["residual_integration_risk"],
                    "remediation": remediation["remediation"],
                    "safe_replacement": remediation["replacement"],
                }
            )
        capabilities.append(capability)
    manifest = {
        "schema_version": 1,
        "audit_mode": audit["mode"],
        "audit_date": audit["audit_date"],
        "catalog_source_status": catalog["catalog_source_status"],
        "default_profile": "planning",
        "default_profile_rationale": (
            "Planning loads one role and one canonical skill; phase-specific profiles are selected on demand."
        ),
        "capabilities": capabilities,
    }
    return manifest, group_names


def build_lock(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "audit_date": audit["audit_date"],
        "audit_tool_version": audit["audit_tool_version"],
        "mode": audit["mode"],
        "sources": [
            {
                "source": source["source_url"],
                "resolved_url": source["resolved_url"],
                "default_branch": source["default_branch"],
                "commit_sha": source["commit_sha"],
                "latest_release_or_tag": source["latest_release_or_tag"],
                "last_meaningful_update": source["last_meaningful_update"],
                "file_checksums": source["scan"]["file_checksums"],
                "license": source["license"]["spdx"],
                "status": source["decision_status"],
                "risk_level": source["risk_level"],
                "security_decision": source["recommendation"],
                "component_exceptions": (
                    [
                        {
                            "source_path": path,
                            "status": policy.get("decision_status", source["decision_status"]),
                            "risk_level": policy["risk_level"],
                            "decision": policy["recommendation"],
                        }
                        for (source_id, path), policy in sorted(COMPONENT_OVERRIDES.items())
                        if source_id == source["source_id"]
                    ]
                ),
            }
            for source in sorted(audit["sources"], key=lambda item: item["source_url"].lower())
        ],
    }


def decision_counts(
    catalog: dict[str, Any],
    sources: dict[str, dict[str, Any]],
) -> dict[str, int]:
    seen: set[tuple[str, str]] = set()
    counts = defaultdict(int)
    for entry in catalog["entries"]:
        key = (entry["normalized_source_id"], entry["subdirectory"])
        if key in seen:
            counts["DUPLICATE_CAPABILITY"] += 1
        else:
            seen.add(key)
            source = sources[entry["normalized_source_id"]]
            counts[component_policy(entry, source)["decision_status"]] += 1
    return dict(counts)


def build_executive(
    audit: dict[str, Any],
    catalog: dict[str, Any],
    manifest: dict[str, Any],
) -> str:
    sources = {item["source_id"]: item for item in audit["sources"]}
    counts = decision_counts(catalog, sources)
    risk_counts = defaultdict(int)
    for item in manifest["capabilities"]:
        risk_counts[item["risk_level"]] += 1
    residual_high = sum(
        1
        for item in manifest["capabilities"]
        if item.get("residual_integration_risk") in {"HIGH", "CRITICAL"}
    )
    return "\n".join(
        [
            "# Executive Summary",
            "",
            f"Mode: `{audit['mode']}`. Audit date: `{audit['audit_date']}`.",
            "",
            "The requested historical catalog was absent from the worktree, Git history, configured remotes, "
            "Documents, OneDrive, and sibling checkouts. A deterministic 69-row catalog was reconstructed from "
            "the sibling `EC Solo Suite Learns` evidence corpus and adopted as repository-canonical v1. It is "
            "complete against that snapshot and does not claim unknown historical wording.",
            "",
            "## Result",
            "",
            f"- Catalog entries: {catalog['total_catalog_entries']}.",
            f"- Unique repositories: {catalog['unique_sources']}.",
            f"- Unique source paths: {len(manifest['capabilities'])}.",
            f"- Adapted capabilities: {counts.get('ADAPTED', 0)}.",
            f"- External-tool-only capabilities: {counts.get('EXTERNAL_TOOL_ONLY', 0)}.",
            f"- Duplicate role assignments: {counts.get('DUPLICATE_CAPABILITY', 0)}.",
            f"- Blocked: {counts.get('BLOCKED', 0)}; quarantined: {counts.get('QUARANTINED', 0)}; "
            f"rejected: {counts.get('REJECTED', 0)}.",
            f"- Source-audit failures: {len(audit['failures'])}.",
            "",
            "## Risk disposition",
            "",
            f"- Historical source HIGH: {risk_counts['HIGH']} unique paths; every integration remediation is verified.",
            f"- MEDIUM: {risk_counts['MEDIUM']} unique paths; adapted or optional, never auto-activated.",
            f"- LOW: {risk_counts['LOW']} unique paths; normalized into original portable guidance.",
            f"- Historical source CRITICAL: {risk_counts['CRITICAL']} rejected component; no activation path remains.",
            f"- Residual integrated `CRITICAL`/`HIGH` capabilities: {residual_high}.",
            "",
            "No audited catalog source implementation, installer, hook, MCP server, or package lifecycle script "
            "was executed. Separately reviewed security-scanner releases were installed project-locally from "
            "hash-verified artifacts and executed after inspection. Catalog source pins and selected audit-file "
            "checksums are recorded in the lock file.",
            "",
            "## Repository baseline",
            "",
            "- Branch created for this work: `audit/agent-extension-platform`.",
            "- Starting commit: `e6705a979f82deaf95dd692794adba550e1de9f2`.",
            "- Host: Windows x64 with PowerShell 5.1.",
            "- Available: Node.js 24.18.0, npm 11.16.0, pnpm 11.9.0, Python 3.12.10, "
            "Git 2.55.0, Codex 0.144.1, Claude Code 2.1.207, Graphify 0.9.27.",
            "- Project-local security tools: Semgrep 1.171.0, Gitleaks 8.30.1, Trivy 0.72.0, and "
            "pip-audit 2.10.1. Unavailable locally: uv, Antigravity/`agy`, Serena, Context7, Repomix, "
            "Aider, and Make.",
            "",
            "## Verdict",
            "",
            "`READY_WITH_WARNINGS`: deterministic repository and scanner validation can pass, but "
            "Antigravity plus interactive Claude discovery remain `NOT_EXECUTED`.",
            "",
        ]
    )


def build_inventory(audit: dict[str, Any], catalog: dict[str, Any]) -> str:
    lines = [
        "# Source Inventory",
        "",
        "> Status: `RECONSTRUCTED_CANONICAL_V1`. No authoritative historical copy was found locally or "
        "in configured remotes. Entries below preserve all rows from the read-only sibling evidence snapshot.",
        "",
        f"Catalog entries: **{catalog['total_catalog_entries']}**. Normalized repositories: "
        f"**{catalog['unique_sources']}**.",
        "",
        "## Normalized repositories",
        "",
        "| Source | Owner/repository | Default branch | Pinned commit | Release/tag | Updated | License | Audit status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for source in sorted(audit["sources"], key=lambda item: item["source_id"]):
        release = source.get("latest_release_or_tag") or {}
        lines.append(
            "| {id} | {owner}/{repo} | {branch} | {sha} | {tag} | {updated} | {license} | `AUDITED` |".format(
                id=md(source["source_id"]),
                owner=md(source["owner"]),
                repo=md(source["repository"]),
                branch=md(source["default_branch"]),
                sha=code(source["commit_sha"]),
                tag=md(release.get("tag", "none recorded")),
                updated=md(source["last_meaningful_update"]),
                license=md(source["license"]["spdx"]),
            )
        )
    lines.extend(
        [
            "",
            "## Catalog entries",
            "",
            "| # | Role | Category | Capability | Repository | Subdirectory | Intended kind |",
            "| ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for entry in catalog["entries"]:
        lines.append(
            f"| {entry['ordinal']} | {md(entry['role'])} | {md(entry['category'])} | "
            f"{md(entry['display_name'])} | [{md(entry['owner'])}/{md(entry['repository'])}]"
            f"({entry['repository_url']}) | {code(entry['subdirectory'])} | "
            f"`{md(entry['component_kind'])}` |"
        )
    lines.extend(
        [
            "",
            "A source is cloned and locked once even when it serves several roles. Repeated source/path "
            "assignments remain visible here and are marked `DUPLICATE_CAPABILITY` in the compatibility matrix.",
            "",
        ]
    )
    return "\n".join(lines)


def build_compatibility(
    audit: dict[str, Any],
    catalog: dict[str, Any],
    group_names: dict[tuple[str, str], str],
) -> str:
    sources = {item["source_id"]: item for item in audit["sources"]}
    seen: set[tuple[str, str]] = set()
    lines = [
        "# Compatibility Matrix",
        "",
        "Statuses describe the audited integration decision, not whether a local platform runtime was exercised.",
        "",
        "| Role | Category | Capability | Source | Type | Codex | ChatGPT | Claude | Antigravity | Antigravity CLI | Required adapter | Risk | Recommendation |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in catalog["entries"]:
        key = (entry["normalized_source_id"], entry["subdirectory"])
        source = sources[entry["normalized_source_id"]]
        policy = component_policy(entry, source)
        duplicate = key in seen
        seen.add(key)
        item_type = "DUPLICATE_CAPABILITY" if duplicate else policy["primary_classification"]
        recommendation = (
            f"Reuse canonical `{group_names[key]}`; do not copy or activate a second instance."
            if duplicate
            else policy["recommendation"]
        )
        compatibility = policy["compatibility"]
        lines.append(
            f"| {md(entry['role'])} | {md(entry['category'])} | {md(entry['display_name'])} | "
            f"[{md(source['source_id'])}]({source['source_url']}) `{md(entry['subdirectory'])}` | "
            f"`{item_type}` | `{compatibility['codex']}` | `{compatibility['chatgpt']}` | "
            f"`{compatibility['claude']}` | `{compatibility['antigravity']}` | "
            f"`{compatibility['antigravity_cli']}` | "
            f"{md('No adapter; evidence only.' if policy['decision_status'] in {'BLOCKED', 'QUARANTINED', 'REJECTED'} else source['required_adapter'])} | "
            f"`{policy['risk_level']}` | {md(recommendation)} |"
        )
    lines.extend(
        [
            "",
            "ChatGPT/Codex use the canonical skill metadata and on-demand bodies. Claude uses generated "
            "skill and role adapters. Antigravity uses the shared skill/rule/workflow surfaces; runtime "
            "discovery remains `NOT_EXECUTED` until a supported local installation is available.",
            "",
        ]
    )
    return "\n".join(lines)


def build_security(
    audit: dict[str, Any],
    npm_audit: dict[str, Any] | None,
    scanner_audit: dict[str, Any] | None,
    security_tools: dict[str, Any] | None,
    high_risk_remediations: dict[str, Any],
) -> str:
    ordered = sorted(
        audit["sources"],
        key=lambda item: ({"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "UNKNOWN": 4}[item["risk_level"]], item["source_id"]),
    )
    lines = [
        "# Security and Supply-Chain Report",
        "",
        "This was a static, read-only audit. Pattern matches were reviewed as leads, not treated as proof "
        "of malicious intent, and no third-party code or configuration was executed.",
        "",
            "## Highest-risk source findings — remediation verified",
            "",
            "Historical source severity is preserved for audit integrity. It is not the residual risk of the "
            "repository integration. Every item below has a machine-checked remediation record, and no "
            "integrated `HIGH` or `CRITICAL` residual risk remains.",
            "",
            "### wshobson/agents `protect-mcp` — `CRITICAL`, `REJECTED`",
            "",
            "The selected plugin registers `PreToolUse` and `PostToolUse` hooks matching every tool call. "
            "They invoke `npx protect-mcp@0.7.4` before and after each call and pass tool inputs/outputs through "
            "environment variables. Setup documentation also uses an unpinned `@latest`; the npm artifact was "
            "not present, locked, or audited. The hook was not copied, translated, installed, or executed.",
            "",
            "### wshobson/agents `block-no-verify` — `HIGH`, `REJECTED`",
            "",
            "Its policy goal is sound, but its command edits automatic Claude hook settings and offers a global "
            "path outside the repository. No packaged adversarial tests establish resistance to quoting or "
            "command-chain bypasses. Only the verification-policy intent is retained in shared instructions.",
            "",
    ]
    for source in ordered:
        if source["risk_level"] != "HIGH":
            continue
        lines.extend(
            [
                f"### {source['source_id']} — `HIGH`",
                "",
                SOURCE_FINDINGS[source["source_id"]],
                "",
                f"Decision: {HIGH_DECISIONS[source['source_id']]} Pin: `{source['commit_sha']}`.",
                "",
            ]
        )
    lines.extend(
        [
            "## Remediation verification",
            "",
            "| Capability | Source risk | Integration | Remediation | Residual risk | Replacement |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for finding in high_risk_remediations.get("findings", []):
        lines.append(
            f"| `{md(finding.get('canonical_name'))}` | `{md(finding.get('source_risk'))}` | "
            f"`{md(finding.get('integration_status'))}` | `{md(finding.get('remediation_status'))}` | "
            f"`{md(finding.get('residual_integration_risk'))}` | {md(finding.get('replacement'))} |"
        )
    lines.extend(
        [
            "",
            "## Medium- and low-risk findings",
            "",
            "| Source | Risk | Surfaces | Decision |",
            "| --- | --- | --- | --- |",
        ]
    )
    for source in ordered:
        if source["risk_level"] == "HIGH":
            continue
        lines.append(
            f"| [{md(source['source_id'])}]({source['source_url']}) | `{source['risk_level']}` | "
            f"{md(SOURCE_FINDINGS[source['source_id']])} | {md(source['recommendation'])} |"
        )
    lines.extend(
        [
            "",
            "## Controls applied",
            "",
            "- All clones were shallow, filtered, non-recursive, and stored under ignored `.tmp/`.",
            "- Git hooks were neutralized for clone operations; submodules, installers, lifecycle scripts, "
            "MCP servers, agent hooks, and source-provided commands were not executed.",
            "- No root `.mcp.json` or project hook was activated.",
            "- Rejected sources have no canonical skill, adapter, profile, hook, MCP, or installation path.",
            "- Accepted source-driven capabilities are disabled by default and selected only through bounded profiles.",
            "- Canonical skills are original normalized guidance; no third-party implementation code was copied.",
            "- Graphify is the sole relationship graph. `code-review-graph` is rejected rather than co-activated.",
            "- Repository-local validators reject root MCP activation, project hooks, verification bypasses, "
            "and references to rejected external tools in active profiles.",
            "",
            "## Scanner coverage",
            "",
            "- Local deterministic secret and dangerous-command scan: implemented by `scripts/agent-security.py`.",
        ]
    )
    if npm_audit:
        counts = npm_audit["vulnerability_counts"]
        lines.extend(
            [
                f"- npm audit with lifecycle scripts disabled: **{counts.get('total', 0)}** findings "
                f"({counts.get('critical', 0)} critical, {counts.get('high', 0)} high, "
                f"{counts.get('moderate', 0)} moderate, {counts.get('low', 0)} low).",
            ]
        )
        direct_dependencies = npm_audit.get("direct_dependencies", [])
        if direct_dependencies:
            lines.extend(
                [
                    "",
                    "### Remaining application dependency findings",
                    "",
                    "| Direct dependency | Severity | Affected range | npm fix candidate |",
                    "| --- | --- | --- | --- |",
                ]
            )
            for item in direct_dependencies:
                fix = item.get("fix_available")
                if isinstance(fix, dict):
                    fix_text = f"{fix.get('name')} {fix.get('version')} (semver-major={fix.get('isSemVerMajor')})"
                else:
                    fix_text = str(fix)
                lines.append(
                    f"| `{md(item.get('name'))}` | `{md(item.get('severity'))}` | "
                    f"`{md(item.get('affected_range'))}` | {md(fix_text)} |"
                )
        lines.append("")
    else:
        lines.extend(
            [
                "- npm audit: `NOT_EXECUTED`; run `python scripts/agent-security.py --npm-audit --write-evidence`.",
                "",
            ]
        )
    if scanner_audit:
        results = scanner_audit.get("results", {})
        summary = ", ".join(
            f"{name}={result.get('status', 'UNKNOWN')} ({len(result.get('findings', []))} findings)"
            for name, result in sorted(results.items())
        )
        lines.extend(
            [
                f"- Project-local scanner suite: {summary}.",
                "- Raw secret values are never written to evidence. Semgrep metrics and Trivy telemetry/version "
                "checks are disabled; Trivy blocks HIGH/CRITICAL findings.",
            ]
        )
        if security_tools:
            python = security_tools.get("python", {})
            packages = python.get("packages", {})
            native = security_tools.get("native_tools", {})
            lines.extend(
                [
                    "- Reviewed and pinned tools: "
                    f"Semgrep {packages.get('semgrep', {}).get('version', 'unknown')}, "
                    f"pip-audit {packages.get('pip-audit', {}).get('version', 'unknown')}, "
                    f"Gitleaks {native.get('gitleaks', {}).get('version', 'unknown')}, and "
                    f"Trivy {native.get('trivy', {}).get('version', 'unknown')}.",
                    "- pip-audit identified three advisories in Semgrep's original `mcp==1.23.3` dependency; "
                    "the isolated lock uses tested `mcp==1.28.1`, and both Semgrep and pip-audit pass.",
                ]
            )
    else:
        lines.append("- Semgrep, Gitleaks, Trivy, and pip-audit: `NOT_EXECUTED`; scanner evidence is missing.")
    lines.extend(
        [
            "",
            "## Blocked, quarantined, and rejected",
            "",
            "- Historical `CRITICAL`: one source component (`plugins/protect-mcp`); remediation is `VERIFIED` "
            "and residual integration risk is `NONE`.",
            "- `BLOCKED`: none; all ten licenses were identified and all source pins resolved.",
            "- `QUARANTINED`: none.",
            "- `REJECTED`: six unique paths: Aider, Serena, Context7, code-review-graph, "
            "`plugins/protect-mcp`, and `plugins/block-no-verify`.",
            "- The original severity remains recorded as audit evidence. All eight HIGH/CRITICAL capability "
            "records have verified remediations; residual integrated HIGH/CRITICAL count is zero.",
            "",
        ]
    )
    return "\n".join(lines)


def build_license(audit: dict[str, Any]) -> str:
    lines = [
        "# License Report",
        "",
        "No third-party implementation was copied into the canonical skill library. The repository contains "
        "original adapters and references; notices preserve provenance for every audited source.",
        "",
        "| Source | License | Copy | Modify | Redistribute | Notice | Decision |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for source in sorted(audit["sources"], key=lambda item: item["source_id"]):
        license_data = source["license"]
        lines.append(
            f"| [{md(source['source_id'])}]({source['source_url']}) | `{md(license_data['spdx'])}` | "
            f"{'yes' if license_data['copying_permitted'] else 'no'} | "
            f"{'yes' if license_data['modification_permitted'] else 'no'} | "
            f"{'yes' if license_data['redistribution_permitted'] else 'no'} | "
            f"{'required' if license_data['notice_required'] else 'not flagged'} | "
            f"`{source['decision_status']}` |"
        )
    lines.extend(
        [
            "",
            "All audited sources had an identifiable permissive license at the pinned commit. A future update "
            "that produces `UNKNOWN`, `NOASSERTION`, or a missing license must be blocked before synchronization.",
            "",
        ]
    )
    return "\n".join(lines)


def build_deduplication() -> str:
    return """# Capability Deduplication Report

One canonical skill is maintained per repository concern. Source components may contribute evidence or role
tags, but are not copied repeatedly.

| Overlap | Default | Optional alternative | Disabled/redundant | Decision |
| --- | --- | --- | --- | --- |
| Architecture and relationship graph | Graphify | Native bounded search | code-review-graph | Graphify is the sole graph engine; the duplicate hook-capable graph is rejected. |
| Symbol navigation and editing | Graphify plus bounded native search | Client-native symbol tools when already available | Serena | Avoid a broad MCP permission surface for targeted symbol work. |
| Current external documentation | Primary official documentation | Reviewed host web lookup | Context7 and copied READMEs | Use current primary sources without activating an extra MCP server. |
| Repository export and handoff | Repomix filtered snapshot | Native file selection | Full permanent dumps | Use occasionally, filter aggressively, and keep output outside startup context. |
| Coding client | Active Codex, Claude, or Antigravity host | None | Aider and simultaneous coding clients | Keep repository mutation and credentials inside the selected host's reviewed boundary. |
| Product planning | `product-discovery` | Source-specific story-map reference | Repeated PM plugins | Story mapping and acceptance criteria share one canonical planning route. |
| UI, architecture, frontend, backend, database, QA, security, DevOps, docs, analytics | One role-named canonical skill each | Profile-scoped optional skills | Repeated role assignments from source plugins | Role tags aggregate; source directories are locked once. |

The 69 catalog rows normalize to 57 unique source paths. The remaining 12 rows are role assignments marked
`DUPLICATE_CAPABILITY` in the compatibility matrix, not extra installed copies.
"""


def build_installation() -> str:
    return """# Agent Platform Installation Guide

No administrator access, global install, symlink, hook, or root MCP activation is required for project-scoped use.

## ChatGPT and Codex

1. Open the repository root so `AGENTS.md` and `.agents/skills/` are in project scope.
2. Run `python scripts/validate-agent-skills.py` and `python scripts/validate-agent-platform.py`.
3. Select one phase profile from `agent-platform/profiles/`; start with `planning.yaml`.
4. Invoke a skill by name when deterministic routing matters. Skill bodies and references load on demand.

## Claude Code

1. Run `python scripts/sync-agent-skills.py`.
2. Confirm `CLAUDE.md` starts with `@AGENTS.md`.
3. Run `python scripts/sync-agent-skills.py --check`.
4. In an interactive Claude session, inspect `/skills`, `/memory`, `/agents`, `/hooks`, and `/mcp`.
5. Keep source-provided hooks and MCP servers disabled unless separately approved.

## Google Antigravity and Antigravity CLI

1. Open the repository with review or workspace-only permissions.
2. Confirm discovery of `AGENTS.md`, `.agents/skills/`, `.agents/rules/`, `.agents/workflows/`,
   `.agents/agents/`, and `.agents/agents.md`.
3. Use `/skills` in `agy` when a supported CLI is installed.
4. Follow the manual checklist in `PLATFORM_TEST_REPORT.md`; this host has no Antigravity runtime.

## Optional audited global promotion

When the user explicitly requests availability across every local project, preview and run the reviewed installer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-global-agent-platforms.ps1 -WhatIf
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-global-agent-platforms.ps1
```

The installer writes only below the current user's `.codex`, `.claude`, `.gemini/config`, and
`.solo-suite-global-backups` directories. It installs exact reviewed copies, registers the local Codex and Claude
marketplaces, enables their 19 plugin trees, and backs up existing destinations before replacement. Restart all
three hosts after installation. It does not globally install Graphify, GSAP, package managers, hooks, or MCP
servers.

To promote only the reviewed Graphify host adapters after the audited `graphify==0.9.32` CLI is available, use:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-global-agent-platforms.ps1 -GraphifyOnly -WhatIf
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-global-agent-platforms.ps1 -GraphifyOnly
```

This adds `$graphify` to Codex, `/graphify` to Claude, and `/graphify` to Antigravity without running Graphify's
own platform installers or enabling hooks, MCP, network ingestion, databases, LLM labeling, or global graphs.

## Optional repository-intelligence tools

- Graphify: relationship and architecture graphs only; output remains outside startup context.
- Repomix: occasional filtered repository snapshots and handoffs.

Use `python scripts/bootstrap-graphify.py --check` to detect Graphify. A missing installation can be provisioned
explicitly and project-locally with `python scripts/bootstrap-graphify.py --install`; the bootstrap never runs
from package lifecycle hooks, uses the exact wheel-only requirements lock under `agent-platform/tooling/`, and
never changes global agent configuration. Serena, Context7, Aider, and code-review-graph are rejected
evidence-only sources and have no installation or activation path.

## Project-local security scanners

1. Review `agent-platform/tooling/security-tools.lock.json` and its exact source URLs and SHA-256 hashes.
2. Preview with `python scripts/bootstrap-security-tools.py --dry-run`.
3. Install only into ignored `.tools/security/` with `python scripts/bootstrap-security-tools.py --install`.
4. Verify the pinned install with `python scripts/bootstrap-security-tools.py --check`.
5. Verify every historical HIGH/CRITICAL source decision with
   `python scripts/check-high-risk-remediations.py`.
6. Run all scanners and refresh redacted evidence with
   `python scripts/agent-security.py --npm-audit --full-scanners --write-evidence`.

The Python wheel closure is fail-closed to Windows amd64 with Python 3.12. Native Gitleaks and Trivy assets are
locked for the audited Windows, Linux, and macOS architectures. No global install, package lifecycle hook, MCP
server, credential login, or container socket is used.

## Profiles and capability control

- Activate only the phase profile that owns the next deliverable.
- To disable a capability, remove it from a profile's `enabled_skills` and `optional_skills`, set its manifest
  decision to disabled, regenerate adapters, and validate.
- There is intentionally no default profile that loads every skill.

## Update, verify, and roll back

- Check upstream movement: `python scripts/agent-update-check.py`.
- Refresh isolated audit evidence only after review: `python scripts/audit-agent-sources.py --refresh`.
- Rebuild locks/reports: `python scripts/build-agent-audit.py --write`.
- Verify mirrors: `python scripts/sync-agent-skills.py --check`.
- Roll back by reverting the reviewed project commit or restoring the prior manifest and lock together; do not
  mix adapters from one lock with source decisions from another.
"""


def build_update() -> str:
    return """# Agent Extension Update Guide

Updates are audit events, not installs.

1. Run `python scripts/agent-update-check.py` to compare pinned commits and releases without changing the lock.
2. Review upstream ownership, license, release notes, default branch, and exact diff from the pinned commit.
3. Run `python scripts/audit-agent-sources.py --dry-run` to inspect clone targets and safety policy.
4. Refresh in the isolated ignored directory with `python scripts/audit-agent-sources.py --refresh`. This clones
   source only; it does not execute source code, hooks, submodules, installers, or lifecycle scripts.
5. Review `docs/agent-audit/evidence/source-audits.json` and any focused evidence files.
6. Rebuild deterministically with `python scripts/build-agent-audit.py --write`.
7. Synchronize generated adapters with `python scripts/sync-agent-skills.py`.
8. Run `make agent-validate` or the Python equivalents in `agent-platform/README.md`.
9. Review the Git diff for license changes, permissions, credentials, hooks, MCP activation, binaries, caches,
   secrets, and unpinned references.
10. Remove isolated clones with `python scripts/agent-clean-temp.py --dry-run`, then run it without `--dry-run`.
11. Update Graphify incrementally only after the final source state is stable.

Never update a pin to floating `main`, `master`, or `latest`. Unknown licenses are blocked, and high-risk
capabilities stay disabled until a human approves the new permission and trust boundary.
"""


def build_rejected() -> str:
    return """# Rejected and Quarantined Items

## Current decision totals

- `BLOCKED`: 0
- `QUARANTINED`: 0
- `REJECTED`: 6 unique paths
- Historical `CRITICAL`: 1 source component finding
- Residual integrated `CRITICAL`/`HIGH`: 0

`plugins/protect-mcp` is rejected because it automatically invokes an unaudited npm package around every
tool call. `plugins/block-no-verify` is rejected as an installable hook command because it mutates automatic
hook configuration and offers a global out-of-repository target; only their policy intent was retained in
repository-local rules and deterministic validation.

The four `HIGH`-risk sources—Aider, code-review-graph, Context7, and Serena—are rejected and retained only as
audit evidence. Graphify, bounded native repository search, primary official documentation, and the active
coding host replace their intended functions without adding another MCP server, hook, or credential boundary.

The two HIGH-risk Wshobson source paths that contributed useful concepts use independently written,
instruction-only `devops-release` and `backend-development` skills. No source installer, hook, agent, command,
download pipeline, or cleanup script was copied. `agent-platform/security/high-risk-remediations.json` and
`scripts/check-high-risk-remediations.py` fail closed if any of the eight records regains an unsafe path.

Any future source with an unknown license, unresolved pin, confirmed credential collection, exfiltration,
verification bypass, destructive default, or hidden automatic execution must move to `BLOCKED` or
`QUARANTINED`; its evidence stays documented while its files remain outside the canonical library.
"""


def build_manual() -> str:
    return """# Manual Review Required

Only the following items need human or unavailable-platform action:

1. Install or open a supported Google Antigravity/`agy` environment, then execute the checklist in
   `PLATFORM_TEST_REPORT.md`; all current Antigravity runtime checks are `NOT_EXECUTED`.
2. In an interactive Claude Code terminal, verify `/skills`, `/memory`, `/agents`, `/hooks`, and `/mcp`.
   Noninteractive print mode does not expose all interactive slash commands.
3. If a future proposal attempts to restore Aider, Serena, Context7, code-review-graph, `protect-mcp`, or
   `block-no-verify`, perform a new audit and explicit trust decision; the current repository has no enablement path.
4. Review repository ownership-transfer history. A shallow source snapshot cannot establish historical
   ownership changes.

No current item requires license approval: all ten audited pins expose a recognized permissive license, and no
third-party implementation code was copied.
"""


def build_platform_readme() -> str:
    return """# Agent Extension Platform

This directory coordinates a portable, profile-scoped extension system.

- Canonical skills: `.agents/skills/`
- Generated Claude mirrors: `.claude/skills/`
- Shared role definitions: `agent-platform/roles/`
- Generated role adapters: `.claude/agents/` and `.agents/agents/`
- Phase profiles: `agent-platform/profiles/`
- Provenance and decisions: `manifest.yaml` and `agent-extensions.lock.json`
- Audit evidence and reports: `docs/agent-audit/`

Start with `planning`; switch to the smallest phase profile that owns the next artifact. `full-audit` is for
extension maintenance only and still caps active skills. Graphify is optional and installed only through the
explicit project-local bootstrap; rejected tools are never installed or activated.

## Commands without Make

```powershell
python scripts/sync-agent-skills.py
python scripts/validate-agent-skills.py
python scripts/validate-agent-platform.py
python scripts/check-agent-licenses.py
python scripts/check-agent-links.py
python scripts/bootstrap-security-tools.py --check
python scripts/check-high-risk-remediations.py
python scripts/agent-security.py --npm-audit --full-scanners --write-evidence
python scripts/agent-compat.py --write
python scripts/agent-token-report.py --write
python scripts/agent-update-check.py
python scripts/bootstrap-graphify.py --check
```

Every generator supports `--check`, `--dry-run`, or both where mutation is possible. Read the installation and
update guides before changing source pins.
"""


def build_notices(audit: dict[str, Any], security_tools: dict[str, Any] | None) -> str:
    lines = [
        "# Third-Party Notices",
        "",
        "The agent platform uses original adapters and references to the audited sources below; it does not "
        "vendor their implementation code. Source names and URLs are retained for attribution and provenance.",
        "",
        "| Source | Pinned commit | License | Integration |",
        "| --- | --- | --- | --- |",
    ]
    for source in sorted(audit["sources"], key=lambda item: item["source_id"]):
        lines.append(
            f"| [{md(source['owner'])}/{md(source['repository'])}]({source['source_url']}) | "
            f"`{source['commit_sha']}` | `{md(source['license']['spdx'])}` | "
            f"`{source['decision_status']}` reference/original adapter |"
        )
    if security_tools:
        python = security_tools.get("python", {}).get("packages", {})
        native = security_tools.get("native_tools", {})
        for name, item in (
            ("Semgrep", python.get("semgrep", {})),
            ("pip-audit", python.get("pip-audit", {})),
            ("Gitleaks", native.get("gitleaks", {})),
            ("Trivy", native.get("trivy", {})),
        ):
            lines.append(
                f"| [{name}]({item.get('source', '')}) | `{item.get('version', '')}` | "
                f"`{item.get('license', 'UNKNOWN')}` | project-local security scanner |"
            )
    lines.extend(
        [
            "",
            "License files were inspected at the pinned commits. If implementation code is copied in a future "
            "change, the applicable full license text, copyright notice, and source-specific obligations must "
            "be added before promotion.",
            "",
        ]
    )
    return "\n".join(lines)


def requested_sources() -> dict[str, dict[str, Any]]:
    if not REQUESTED_ADDITIONS_PATH.is_file():
        return {}
    data = load_json(REQUESTED_ADDITIONS_PATH)
    sources = data.get("sources")
    if not isinstance(sources, list):
        raise ValueError("requested source additions must contain a sources array")
    result = {str(item.get("id")): item for item in sources if isinstance(item, dict)}
    required = {"addyosmani-agent-skills", "graphify", "greensock-gsap"}
    if set(result) != required:
        raise ValueError(f"requested source additions differ from required set: {sorted(set(result) ^ required)}")
    return result


def addy_skill_names(source: dict[str, Any]) -> list[str]:
    checksums = source.get("file_checksums")
    if not isinstance(checksums, dict):
        raise ValueError("Addy source evidence has no file checksums")
    names = sorted({
        path.split("/")[1]
        for path in checksums
        if re.fullmatch(r"skills/[^/]+/SKILL\.md", str(path))
    })
    if len(names) != 24:
        raise ValueError(f"Addy source evidence must identify 24 skills, found {len(names)}")
    return names


def augment_manifest(manifest: dict[str, Any], requested: dict[str, dict[str, Any]]) -> dict[str, Any]:
    graphify = requested["graphify"]
    addy = requested["addyosmani-agent-skills"]
    gsap = requested["greensock-gsap"]
    manifest["audit_date"] = "2026-08-02"
    for capability in manifest["capabilities"]:
        if capability.get("source_url") == graphify["source"]:
            capability["pinned_commit_sha"] = graphify["commit_sha"]
            capability["integration_kind"] = "audited_cli_skill_and_global_adapters"
            capability["canonical_skill_path"] = ".agents/skills/graphify/SKILL.md"
            capability["related_canonical_skills"] = [
                ".agents/skills/repository-intelligence-routing/SKILL.md"
            ]
            capability["claude_adapter_path"] = ".claude/skills/graphify/SKILL.md"
            capability["antigravity_adapter_path"] = ".agents/skills/graphify/SKILL.md"
            capability["recommendation"] = graphify["decision"]
    names = addy_skill_names(addy)
    manifest["capabilities"].extend([
        {
            "canonical_name": "addyosmani-agent-skills",
            "description": "Audited lifecycle skills and command adapters from addyosmani/agent-skills.",
            "role_tags": ["Product Manager", "Software Architect", "Frontend Developer", "Backend Developer", "QA Engineer", "Security Reviewer", "DevOps Engineer", "Technical Writer"],
            "category_tags": ["specification", "planning", "implementation", "testing", "review", "shipping"],
            "source_url": addy["source"],
            "source_path": ".",
            "pinned_commit_sha": addy["commit_sha"],
            "license": addy["license"],
            "risk_level": addy["risk"],
            "primary_type": addy["classification"],
            "status": addy["status"],
            "integration_kind": "safety_adapted_project_install",
            "canonical_skill_path": ".agents/skills/using-agent-skills/SKILL.md",
            "related_canonical_skills": [f".agents/skills/{name}/SKILL.md" for name in names],
            "claude_adapter_path": ".claude/skills/using-agent-skills/SKILL.md",
            "antigravity_adapter_path": ".agents/skills/using-agent-skills/SKILL.md",
            "role_adapter_paths": {"claude": [], "antigravity": []},
            "external_tool_requirement": {"name": None, "required": False},
            "enabled_by_default": False,
            "activation_profile": [],
            "replacement_or_duplicate_relationship": {
                "relationship": "supplements_existing_role_skills",
                "activation_constraint": "load only the narrow skill needed for the current task",
            },
            "recommendation": addy["decision"],
        },
        {
            "canonical_name": "greensock-gsap-runtime",
            "description": "Exact GSAP runtime dependency shared by all agent platforms working in this repository.",
            "role_tags": ["GSAP Animation Developer", "Frontend Developer"],
            "category_tags": ["animation", "runtime-library"],
            "source_url": gsap["source"],
            "source_path": ".",
            "pinned_commit_sha": gsap["commit_sha"],
            "license": gsap["license"],
            "risk_level": gsap["risk"],
            "primary_type": gsap["classification"],
            "status": gsap["status"],
            "integration_kind": "exact_project_dependency",
            "canonical_skill_path": ".agents/skills/gsap-animation/SKILL.md",
            "related_canonical_skills": [".agents/skills/frontend-development/SKILL.md"],
            "claude_adapter_path": ".claude/skills/gsap-animation/SKILL.md",
            "antigravity_adapter_path": ".agents/skills/gsap-animation/SKILL.md",
            "role_adapter_paths": {
                "claude": [".claude/agents/gsap-animation-developer.md"],
                "antigravity": [".agents/agents/gsap-animation-developer.md"],
            },
            "external_tool_requirement": {"name": None, "required": False},
            "enabled_by_default": False,
            "activation_profile": ["frontend", "gsap-animation"],
            "replacement_or_duplicate_relationship": {
                "relationship": "runtime_for",
                "canonical_capability": "gsap-animation",
            },
            "recommendation": gsap["decision"],
        },
    ])
    return manifest


def augment_lock(lock: dict[str, Any], requested: dict[str, dict[str, Any]]) -> dict[str, Any]:
    lock["audit_date"] = "2026-08-01"
    by_url = {source["source"]: source for source in lock["sources"]}
    graphify = requested["graphify"]
    graph_entry = by_url[graphify["source"]]
    graph_entry.update({
        "default_branch": graphify["branch"],
        "commit_sha": graphify["commit_sha"],
        "latest_release_or_tag": {
            "tag": graphify["tag"],
            "published_at": "2026-08-01T14:36:23Z",
            "url": f"{graphify['source']}/releases/tag/{graphify['tag']}",
        },
        "last_meaningful_update": graphify["last_update"],
        "file_checksums": graphify["file_checksums"],
        "license": graphify["license"],
        "status": graphify["status"],
        "risk_level": graphify["risk"],
        "security_decision": graphify["decision"],
    })
    for source_id in ("addyosmani-agent-skills", "greensock-gsap"):
        source = requested[source_id]
        lock["sources"].append({
            "source": source["source"],
            "resolved_url": source["source"],
            "default_branch": source["branch"],
            "commit_sha": source["commit_sha"],
            "latest_release_or_tag": (
                {
                    "tag": source["tag"],
                    "published_at": source["last_update"],
                    "url": f"{source['source']}/tree/{source['tag']}",
                }
                if source.get("tag") else None
            ),
            "last_meaningful_update": source["last_update"],
            "file_checksums": source["file_checksums"],
            "license": source["license"],
            "status": source["status"],
            "risk_level": source["risk"],
            "security_decision": source["decision"],
            "component_exceptions": [],
        })
    lock["sources"].sort(key=lambda item: item["source"].lower())
    return lock


def insert_after_h1(text: str, section: str) -> str:
    marker = "\n\n"
    index = text.find(marker)
    if index < 0:
        raise ValueError("generated Markdown has no H1 boundary")
    return text[: index + len(marker)] + section.rstrip() + "\n\n" + text[index + len(marker):]


def augment_reports(
    generated: dict[Path, str],
    requested: dict[str, dict[str, Any]],
) -> dict[Path, str]:
    addy = requested["addyosmani-agent-skills"]
    graphify = requested["graphify"]
    gsap = requested["greensock-gsap"]

    generated[REPORT_PATHS["executive"]] = generated[REPORT_PATHS["executive"]].replace(
        "- Available: Node.js 24.18.0, npm 11.16.0, pnpm 11.9.0, Python 3.12.10, "
        "Git 2.55.0, Codex 0.144.1, Claude Code 2.1.207, Graphify 0.9.27.",
        "- Requested-source update (2026-08-01): bundled Node.js 24.14.0, pnpm 11.9.0, "
        "Python 3.13.14, the Codex desktop host, and Graphify 0.9.32 were available. Claude Code "
        "and Antigravity CLIs were not available for interactive validation.",
    )

    inventory_section = f"""## Requested installation additions (2026-08-01)

These records supplement the historical reconstructed catalog. Detailed static evidence is in
`evidence/requested-source-additions.json`.

| Source | Pinned commit | Release/version | License | Decision |
| --- | --- | --- | --- | --- |
| [addyosmani/agent-skills]({addy['source']}) | `{addy['commit_sha']}` | plugin 1.0.0 | MIT | `ADAPTED` project skills and commands; hooks excluded |
| [Graphify-Labs/graphify]({graphify['source']}) | `{graphify['commit_sha']}` | {graphify['tag']} | Apache-2.0 OR MIT | `EXTERNAL_TOOL_ONLY` exact CLI |
| [greensock/GSAP]({gsap['source']}) | `{gsap['commit_sha']}` | {gsap['version']} | GSAP Standard No-Charge | `ACCEPTED_PROJECT_DEPENDENCY` |"""
    generated[REPORT_PATHS["inventory"]] = insert_after_h1(
        generated[REPORT_PATHS["inventory"]], inventory_section
    )

    compatibility_section = f"""## Requested installation additions

| Source | Type | Codex/ChatGPT | Claude | Antigravity | Adapter | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| [addyosmani/agent-skills]({addy['source']}) | `PORTABLE_SKILL_PLUGIN` | 24 project skills | 24 generated mirrors + 8 commands | 24 project skills + 8 workflows | Safety-adapted; hook and installer surfaces excluded | `MEDIUM` |
| [Graphify-Labs/graphify]({graphify['source']}) | `LOCAL_CLI_TOOL` | Shared CLI {graphify['version']} | Shared CLI {graphify['version']} | Shared CLI {graphify['version']} | Existing repository-routing skill; no platform installer | `MEDIUM` |
| [greensock/GSAP]({gsap['source']}) | `PROJECT_JAVASCRIPT_LIBRARY` | Shared project dependency | Shared project dependency | Shared project dependency | Existing `gsap-animation` skill | `LOW` |"""
    generated[REPORT_PATHS["compatibility"]] = insert_after_h1(
        generated[REPORT_PATHS["compatibility"]], compatibility_section
    )

    security_section = f"""## Requested installation source findings

| Source | Risk | Surfaces | Decision |
| --- | --- | --- | --- |
| [addyosmani-agent-skills]({addy['source']}) | `MEDIUM` | 24 skills, 8 commands, 4 personas, executable helpers, and an automatic Claude session hook; one skill documented an unpinned MCP install. | Install safety-adapted project skills and commands only; exclude hooks, installers, unpinned MCP/package setup, and direct persona activation. |
| [Graphify]({graphify['source']}) | `MEDIUM` | CLI plus optional MCP, hooks, model/network integrations, and repository analysis. | Accept the exact {graphify['version']} CLI only; do not activate platform installers, hooks, MCP, or model integrations. |
| [greensock-GSAP]({gsap['source']}) | `LOW` | Browser animation runtime with no package lifecycle scripts, agent hooks, MCP definitions, credentials, or detected telemetry. | Install exact `gsap@{gsap['version']}` with lifecycle scripts disabled and route usage through the portable GSAP skill. |
"""
    security = generated[REPORT_PATHS["security"]]
    security = security.replace("## Controls applied\n", security_section + "\n## Controls applied\n")
    security = security.replace(
        "- Canonical skills are original normalized guidance; no third-party implementation code was copied.",
        "- Imported lifecycle skills carry a repository safety overlay and local references; automatic hooks "
        "and installer instructions were not copied. GSAP is an exact package dependency, not startup agent context.",
    )
    security = security.replace(
        "## Scanner coverage\n",
        "## Scanner coverage\n\nRequested-source update note (2026-08-01): the repository-local policy/remediation "
        "scan passed. A fresh npm audit was `NOT_EXECUTED` because npm is unavailable and pnpm cannot audit an "
        "npm lockfile. The installed full scanner suite was attempted, but Windows Application Control blocked "
        "Semgrep before scanning; the prior scanner evidence below remains historical and was not represented as "
        "a fresh pass.\n",
    )
    generated[REPORT_PATHS["security"]] = security

    license_report = generated[REPORT_PATHS["license"]].replace(
        "No third-party implementation was copied into the canonical skill library. The repository contains "
        "original adapters and references; notices preserve provenance for every audited source.",
        "The canonical library includes safety-adapted MIT-licensed instruction files from "
        "`addyosmani/agent-skills`; the full MIT notice is retained under `agent-platform/licenses/`. "
        "GSAP is installed as an exact package dependency under its declared standard no-charge license.",
    )
    license_rows = (
        f"| [addyosmani-agent-skills]({addy['source']}) | `MIT` | yes | yes | yes | required, retained | `ADAPTED` |\n"
        f"| [greensock-gsap]({gsap['source']}) | `LicenseRef-GSAP-Standard-No-Charge` | package use | not claimed | not claimed | license URL retained | `ACCEPTED_PROJECT_DEPENDENCY` |\n"
    )
    license_report = license_report.replace(
        "| --- | --- | --- | --- | --- | --- | --- |\n",
        "| --- | --- | --- | --- | --- | --- | --- |\n" + license_rows,
        1,
    )
    generated[REPORT_PATHS["license"]] = license_report

    installation = generated[REPORT_PATHS["installation"]]
    installation = installation.replace(
        "4. Invoke a skill by name when deterministic routing matters. Skill bodies and references load on demand.\n",
        "4. Invoke a skill by name when deterministic routing matters. Skill bodies and references load on demand.\n\n"
        "The 24 audited `addyosmani/agent-skills` workflows are installed project-locally under "
        "`.agents/skills/` by default. Codex/ChatGPT invoke the underlying skill directly. An explicitly requested "
        "run of `scripts/install-global-agent-platforms.ps1` promotes the safety-adapted copies into the supported "
        "user-level skill roots without activating the excluded upstream hook.\n",
    )
    installation = installation.replace(
        "5. Keep source-provided hooks and MCP servers disabled unless separately approved.\n",
        "5. Keep source-provided hooks and MCP servers disabled unless separately approved.\n\n"
        "Eight lifecycle commands are installed under `.claude/commands/`: `/spec`, `/plan`, `/build`, `/test`, "
        "`/review`, `/webperf`, `/code-simplify`, and `/ship`. They include the repository safety overlay. The "
        "upstream session-start hook is intentionally absent. The reviewed global installer copies these commands "
        "to `~/.claude/commands/` and registers the validated plugin distribution at user scope.\n",
    )
    installation = installation.replace(
        "4. Follow the manual checklist in `PLATFORM_TEST_REPORT.md`; this host has no Antigravity runtime.\n",
        "4. Follow the manual checklist in `PLATFORM_TEST_REPORT.md`; this host has no Antigravity runtime.\n\n"
        "Eight equivalent workflows are installed under `.agents/workflows/`; Antigravity uses `/planning` rather "
        "than `/plan` to avoid the platform-reserved plan command. Runtime discovery remains `NOT_EXECUTED` on "
        "this host. The reviewed global installer copies them to `~/.gemini/config/global_workflows/` and installs "
        "the audited Antigravity plugin and skill trees under `~/.gemini/config/`.\n\n## GSAP runtime\n\n"
        "`greensock/GSAP` is installed once as the exact project dependency "
        "`gsap@3.15.0`, locked by registry integrity in `package-lock.json`. Agents on every platform use that "
        "same dependency through the portable `gsap-animation` skill. No global package, CDN fallback, or package "
        "lifecycle script is used.\n",
    )
    generated[REPORT_PATHS["installation"]] = installation

    generated[REPORT_PATHS["manual"]] = generated[REPORT_PATHS["manual"]].replace(
        "No current item requires license approval: all ten audited pins expose a recognized permissive license, "
        "and no\nthird-party implementation code was copied.",
        "The historical ten-source catalog requires no license approval. The requested GSAP dependency uses its "
        "declared\nstandard no-charge license rather than a permissive SPDX license; product use must remain within "
        "those terms.\nOnly MIT-licensed instruction material was adapted; no upstream executable helper, hook, "
        "or installer was copied.",
    )

    notices = generated[REPORT_PATHS["notices"]]
    notices = notices.replace(
        "The agent platform uses original adapters and references to the audited sources below; it does not "
        "vendor their implementation code. Source names and URLs are retained for attribution and provenance.",
        "The agent platform uses original adapters, audited references, and the safety-adapted instruction files "
        "listed below. Source names and URLs are retained for attribution and provenance; no upstream hooks or "
        "installers are vendored or activated.",
    )
    notices = notices.replace(
        "| --- | --- | --- | --- |\n",
        "| --- | --- | --- | --- |\n"
        f"| [addyosmani/agent-skills]({addy['source']}) | `{addy['commit_sha']}` | `MIT` | `ADAPTED` 24 project skills and 8 commands/workflows; hooks excluded |\n"
        f"| [greensock/GSAP]({gsap['source']}) | `{gsap['commit_sha']}` | `LicenseRef-GSAP-Standard-No-Charge` | exact project dependency `gsap@{gsap['version']}` |\n",
        1,
    )
    historical_graph = next(
        line for line in notices.splitlines() if "Graphify-Labs/graphify" in line
    )
    notices = notices.replace(
        historical_graph,
        f"| [Graphify-Labs/graphify]({graphify['source']}) | `{graphify['commit_sha']}` | `Apache-2.0 OR MIT` | `EXTERNAL_TOOL_ONLY` exact CLI {graphify['tag']} |",
    )
    notices = notices.replace(
        "License files were inspected at the pinned commits. If implementation code is copied in a future change, "
        "the applicable full license text, copyright notice, and source-specific obligations must be added before "
        "promotion.",
        "License files and package declarations were inspected at the pinned commits. The Addy Osmani MIT text is "
        "retained under `agent-platform/licenses/`; GSAP remains governed by the license URL declared in its package "
        "metadata. Future copied implementation must retain all applicable notices and obligations.",
    )
    generated[REPORT_PATHS["notices"]] = notices
    return generated


def outputs() -> dict[Path, str]:
    audit = load_json(AUDIT_PATH)
    catalog = load_json(CATALOG_PATH)
    npm_audit = load_json(NPM_AUDIT_PATH) if NPM_AUDIT_PATH.is_file() else None
    scanner_audit = load_json(SCANNER_AUDIT_PATH) if SCANNER_AUDIT_PATH.is_file() else None
    security_tools = load_json(SECURITY_TOOL_LOCK_PATH) if SECURITY_TOOL_LOCK_PATH.is_file() else None
    high_risk_remediations = load_json(HIGH_RISK_REMEDIATION_PATH)
    requested = requested_sources()
    if audit["catalog_entries"] != catalog["total_catalog_entries"]:
        raise ValueError("catalog and source-audit entry counts differ")
    manifest, group_names = build_manifest(audit, catalog, high_risk_remediations)
    lock = build_lock(audit)
    if requested:
        manifest = augment_manifest(manifest, requested)
        lock = augment_lock(lock, requested)
    generated = {
        REPORT_PATHS["executive"]: build_executive(audit, catalog, manifest),
        REPORT_PATHS["inventory"]: build_inventory(audit, catalog),
        REPORT_PATHS["compatibility"]: build_compatibility(audit, catalog, group_names),
        REPORT_PATHS["security"]: build_security(
            audit,
            npm_audit,
            scanner_audit,
            security_tools,
            high_risk_remediations,
        ),
        REPORT_PATHS["license"]: build_license(audit),
        REPORT_PATHS["deduplication"]: build_deduplication(),
        REPORT_PATHS["installation"]: build_installation(),
        REPORT_PATHS["update"]: build_update(),
        REPORT_PATHS["rejected"]: build_rejected(),
        REPORT_PATHS["manual"]: build_manual(),
        REPORT_PATHS["platform_readme"]: build_platform_readme(),
        REPORT_PATHS["notices"]: build_notices(audit, security_tools),
        REPORT_PATHS["manifest"]: json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        REPORT_PATHS["lock"]: json.dumps(lock, indent=2, ensure_ascii=False) + "\n",
    }
    return augment_reports(generated, requested) if requested else generated


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Fail if generated artifacts are stale.")
    mode.add_argument("--dry-run", action="store_true", help="Print the paths and sizes without writing.")
    mode.add_argument("--write", action="store_true", help="Write generated artifacts.")
    args = parser.parse_args()
    try:
        generated = outputs()
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"ERROR: cannot build audit artifacts: {exc}", file=sys.stderr)
        return 1
    if args.check:
        stale = []
        for path, content in generated.items():
            current = path.read_text(encoding="utf-8") if path.is_file() else None
            if current != content:
                stale.append(path.relative_to(ROOT).as_posix())
        if stale:
            for path in stale:
                print(f"STALE: {path}")
            return 1
        print(f"Agent audit artifacts are current: {len(generated)} files")
        return 0
    if args.dry_run:
        for path, content in generated.items():
            print(f"WOULD_WRITE {path.relative_to(ROOT).as_posix()} ({len(content.encode('utf-8'))} bytes)")
        return 0
    for path, content in generated.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
