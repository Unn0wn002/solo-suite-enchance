#!/usr/bin/env python3
"""Build Codex manifests from the synchronized Claude source tree.

The source defaults to the checked-out v1.0.27 Claude tree next to this
repository.  ``SOLO_SUITE_SOURCE_ROOT`` is intentionally supported for CI or
release workspaces that keep the source at a different absolute path.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_source_setting = os.environ.get("SOLO_SUITE_SOURCE_ROOT")
SOURCE = Path(
    _source_setting or (ROOT.parent / "solo-suite-v1.0.27-work")
).expanduser().resolve()
VERSION = "1.0.27"
AUTHOR = "Sakura Yukihira (Ayaya)"

DISPLAY = {
    "ai": "Solo AI",
    "browser": "Solo Browser QA",
    "design": "Solo Design",
    "dev": "Solo Development",
    "docs": "Solo Documentation",
    "gate": "Solo Quality Gates",
    "git": "Solo Git Workflow",
    "growth": "Solo Growth",
    "project": "Solo Project Planning",
    "release": "Solo Release",
    "repo": "Solo Repository Intelligence",
    "security": "Solo Security",
    "seo": "Solo SEO",
    "site-doctor": "Site Doctor",
    "solo": "Solo Suite Core",
    "spec": "Solo Specifications",
    "stack": "Solo Stack Audits",
    "test": "Solo Testing",
    "full-team": "Solo Suite Full Team",
}

CATEGORY = {
    "ai": "AI",
    "browser": "Testing",
    "design": "Design",
    "dev": "Development",
    "docs": "Documentation",
    "gate": "Quality",
    "git": "Development",
    "growth": "Productivity",
    "project": "Productivity",
    "release": "Development",
    "repo": "Development",
    "security": "Security",
    "seo": "Development",
    "site-doctor": "Development",
    "solo": "Productivity",
    "spec": "Productivity",
    "stack": "Development",
    "test": "Testing",
    "full-team": "Productivity",
}

SHORT = {
    "ai": "Review and coordinate AI coding work",
    "browser": "Run safety-first browser quality checks",
    "design": "Review UX, UI, and component systems",
    "dev": "Implement, debug, refactor, and review code",
    "docs": "Create accurate engineering documentation",
    "gate": "Run evidence-based engineering quality gates",
    "git": "Plan safe Git, pull request, and release work",
    "growth": "Audit conversion journeys and activation",
    "project": "Turn product ideas into executable plans",
    "release": "Plan secure releases and recoverable deploys",
    "repo": "Map and understand unfamiliar repositories",
    "security": "Threat-model and test authorization controls",
    "seo": "Run technical, content, and vertical SEO audits",
    "site-doctor": "Audit websites, services, and databases",
    "solo": "Coordinate project memory and team workflows",
    "spec": "Define testable product and API contracts",
    "stack": "Audit configured cloud and SaaS providers",
    "test": "Design unit, integration, and end-to-end tests",
    "full-team": "Coordinate all Solo Suite engineering roles",
}

DEFAULT_PROMPT = {
    name: [f"Use {DISPLAY[name]} to help with this project."] for name in DISPLAY
}

READ_ONLY = {"repo"}

BASE_DESCRIPTION = {
    "ai": "Review AI output, improve prompts, validate handoffs, and prepare declarative AgentRooms plans.",
    "browser": "Run safety-first browser QA for console, visual, mobile, smoke, and form workflows.",
    "design": "Design UX flows and component systems, then review the implemented interface.",
    "dev": "Implement features, diagnose bugs, refactor code, and perform evidence-based code review.",
    "docs": "Create and maintain accurate API, setup, runbook, and repository documentation.",
    "full-team": "Coordinate all 18 Solo Suite component plugins through a profile-aware, evidence-gated workflow.",
    "gate": "Run before-code, before-merge, before-deploy, project-scoring, and 14-category production-readiness gates.",
    "git": "Plan safe branches, commits, pull requests, release notes, and issue synchronization.",
    "growth": "Audit conversion journeys and activation only when the project profile makes growth review relevant.",
    "project": "Turn product ideas into a PRD, architecture, and executable task breakdown.",
    "release": "Prepare CI, release preflight, recoverable deployment plans, and rollback plans.",
    "repo": "Map repository structure, dependencies, risks, dead code, and onboarding context without mutation.",
    "security": "Threat-model systems and review authorization, RLS, secrets, and abuse cases.",
    "seo": "Audit technical SEO, content quality, structured data, search experience, AI-search readiness, local, ecommerce, and international visibility.",
    "site-doctor": "Audit websites, services, databases, infrastructure, security, performance, SEO, and operations.",
    "solo": "Manage shared project memory, session handoffs, synchronization, integrity checks, and orchestration.",
    "spec": "Define feature briefs, acceptance criteria, API contracts, data contracts, and environment contracts.",
    "stack": "Record the active stack, verify connector access, and run only applicable provider audits.",
    "test": "Design and evaluate unit, integration, end-to-end, and edge-case tests.",
}


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def source_metadata(name: str) -> dict:
    if name == "full-team":
        return {
            "description": (
                "Meta-plugin that coordinates every Solo Suite role, verifies that all "
                "18 component plugins are available, and runs profile-aware full-team "
                "delivery with evidence-based gates."
            ),
            "keywords": ["solo", "full-team", "orchestration", "codex", "quality-gates"],
        }
    source = SOURCE / "plugins" / name / ".claude-plugin" / "plugin.json"
    data = load_json(source)
    return {"description": BASE_DESCRIPTION[name], "keywords": data.get("keywords", [])}


def migrated_invocations(name: str) -> list[str]:
    mapping = load_json(ROOT / "command-map.json")
    return [
        entry["codex_invocation"] for entry in mapping
        if entry.get("plugin") == name
    ]


def build_manifest(name: str) -> dict:
    meta = source_metadata(name)
    description = meta["description"].strip()
    invocations = migrated_invocations(name)
    if invocations:
        description += " Migrated workflows: " + ", ".join(invocations) + "."
    long_description = (
        f"{description} This Codex-native edition packages explicit workflows as "
        "skills, records sensitive actions as explicit-only, and uses portable "
        "installed-skill paths."
    )
    return {
        "name": name,
        "version": VERSION,
        "description": description,
        "author": {"name": AUTHOR},
        "license": "MIT",
        "keywords": sorted(set(meta["keywords"] + ["codex", "solo-suite"])),
        "skills": "./skills/",
        "interface": {
            "displayName": DISPLAY[name],
            "shortDescription": SHORT[name],
            "longDescription": long_description,
            "developerName": AUTHOR,
            "category": CATEGORY[name],
            "capabilities": ["Read"] if name in READ_ONLY else ["Read", "Write"],
            "defaultPrompt": DEFAULT_PROMPT[name],
            "brandColor": "#7C3AED",
        },
    }


def main() -> None:
    plugins = ROOT / "plugins"
    names = sorted(path.name for path in plugins.iterdir() if path.is_dir())
    expected = set(DISPLAY)
    if set(names) != expected:
        raise SystemExit(
            f"plugin set mismatch: missing={sorted(expected-set(names))}, "
            f"extra={sorted(set(names)-expected)}"
        )
    for name in names:
        dump_json(plugins / name / ".codex-plugin" / "plugin.json",
                  build_manifest(name))

    market_path = ROOT / ".agents" / "plugins" / "marketplace.json"
    market = load_json(market_path)
    market["name"] = "solo-suite-codex"
    market["interface"] = {"displayName": "Solo Suite Codex"}
    for entry in market["plugins"]:
        entry["category"] = CATEGORY[entry["name"]]
    dump_json(market_path, market)
    print(f"Updated {len(names)} Codex manifests and marketplace metadata")


if __name__ == "__main__":
    main()
