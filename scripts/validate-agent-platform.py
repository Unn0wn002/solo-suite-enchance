#!/usr/bin/env python3
"""Validate role/profile/adaptor integrity and audited source decisions."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from agent_platform_common import (
    ROOT,
    SHA_RE,
    canonical_skills,
    load_json_yaml,
    relative,
    sha256_text_lf,
)


REQUIRED_PROFILES = {
    "planning", "design", "architecture", "frontend", "gsap-animation", "backend",
    "database", "qa", "security", "devops", "documentation", "analytics", "release", "full-audit",
}
REQUIRED_ROLES = {
    "product-manager", "ui-ux-designer", "software-architect", "frontend-developer",
    "gsap-animation-developer", "backend-developer", "database-engineer", "qa-engineer",
    "security-reviewer", "devops-engineer", "technical-writer", "data-analyst",
}
REJECTED_EXTERNAL_TOOLS = {"aider", "serena", "context7", "code-review-graph"}
REQUIRED_RULES = {"context.md", "security.md", "tool-permissions.md", "verification-integrity.md"}
SECURITY_TOOL_FILES = {
    "scripts/bootstrap-security-tools.py",
    "scripts/run-security-scanners.py",
    "agent-platform/tooling/security-tools.lock.json",
    "agent-platform/tooling/security-python-requirements-win-py312.txt",
    "agent-platform/security/semgrep-rules.yaml",
    ".gitleaks.toml",
    "agent-platform/security/high-risk-remediations.json",
    "scripts/check-high-risk-remediations.py",
}
EXPECTED_SECURITY_RESULTS = {
    "semgrep",
    "gitleaks_worktree",
    "gitleaks_history",
    "trivy",
    "pip_audit_scanners",
    "pip_audit_graphify",
}


def load_required(path: Path, errors: list[str]):
    if not path.is_file():
        errors.append(f"missing {relative(path.parent)}/{path.name}")
        return None
    try:
        return load_json_yaml(path)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{relative(path)}: invalid JSON-compatible YAML/JSON: {exc}")
        return None


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    agents = ROOT / "AGENTS.md"
    claude = ROOT / "CLAUDE.md"
    if not agents.is_file() or not agents.read_text(encoding="utf-8").strip():
        errors.append("AGENTS.md is missing or empty")
    elif agents.stat().st_size > 12_000:
        errors.append("AGENTS.md exceeds the concise 12 KB repository limit")
    if not claude.is_file():
        errors.append("CLAUDE.md is missing")
    elif claude.read_text(encoding="utf-8").splitlines()[0] != "@AGENTS.md":
        errors.append("CLAUDE.md first line must be @AGENTS.md")

    generator = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate-agent-adapters.py"), "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if generator.returncode:
        errors.append("generated role/profile adapters are stale: " + (generator.stdout + generator.stderr).strip())
    remediation_check = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check-high-risk-remediations.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if remediation_check.returncode:
        errors.append(
            "HIGH/CRITICAL remediations are invalid: "
            + (remediation_check.stdout + remediation_check.stderr).strip()
        )

    skills = set(canonical_skills())
    profile_root = ROOT / "agent-platform" / "profiles"
    actual_profiles = {path.stem for path in profile_root.glob("*.yaml")} if profile_root.is_dir() else set()
    missing_profiles = REQUIRED_PROFILES - actual_profiles
    if missing_profiles:
        errors.append(f"missing profiles: {sorted(missing_profiles)}")
    for name in sorted(actual_profiles):
        data = load_required(profile_root / f"{name}.yaml", errors)
        if not isinstance(data, dict):
            continue
        for field in (
            "enabled_roles", "enabled_skills", "optional_skills", "disabled_duplicates",
            "external_tools", "verification_commands", "token_budget_guidance",
        ):
            if field not in data:
                errors.append(f"agent-platform/profiles/{name}.yaml: missing {field}")
        unknown_roles = set(data.get("enabled_roles", [])) - REQUIRED_ROLES
        unknown_skills = (set(data.get("enabled_skills", [])) | set(data.get("optional_skills", []))) - skills
        if unknown_roles:
            errors.append(f"profile {name}: unknown roles {sorted(unknown_roles)}")
        if unknown_skills:
            errors.append(f"profile {name}: unknown skills {sorted(unknown_skills)}")
        for tool in data.get("external_tools", []):
            if not isinstance(tool, dict) or not isinstance(tool.get("name"), str) or not isinstance(tool.get("required"), bool):
                errors.append(f"profile {name}: each external tool must declare name and boolean required")
        active_tools = {tool.get("name") for tool in data.get("external_tools", []) if isinstance(tool, dict)}
        rejected_tools = active_tools & REJECTED_EXTERNAL_TOOLS
        if rejected_tools:
            errors.append(f"profile {name}: rejected external tools are active: {sorted(rejected_tools)}")
        if len(data.get("enabled_skills", [])) > data.get("token_budget_guidance", {}).get("target_max_active_skills", 0):
            errors.append(f"profile {name}: enabled skills exceed token guidance")

    role_root = ROOT / "agent-platform" / "roles"
    actual_roles = {path.stem for path in role_root.glob("*.md")} if role_root.is_dir() else set()
    if REQUIRED_ROLES - actual_roles:
        errors.append(f"missing role definitions: {sorted(REQUIRED_ROLES - actual_roles)}")
    required_sections = [
        "## Responsibilities", "## Inputs", "## Outputs", "## Applicable skills",
        "## Required verification", "## Security boundaries", "## Handoff target", "## Definition of done",
    ]
    for role in sorted(REQUIRED_ROLES & actual_roles):
        text = (role_root / f"{role}.md").read_text(encoding="utf-8")
        for section in required_sections:
            if section not in text:
                errors.append(f"agent-platform/roles/{role}.md: missing {section}")
        for adapter in (ROOT / ".claude" / "agents" / f"{role}.md", ROOT / ".agents" / "agents" / f"{role}.md"):
            if not adapter.is_file():
                errors.append(f"missing role adapter {relative(adapter)}")

    manifest = load_required(ROOT / "agent-platform" / "manifest.yaml", errors)
    lock = load_required(ROOT / "agent-platform" / "agent-extensions.lock.json", errors)
    if isinstance(manifest, dict):
        capabilities = manifest.get("capabilities")
        if not isinstance(capabilities, list):
            errors.append("agent-platform/manifest.yaml: capabilities must be a list")
        else:
            seen: set[tuple[str, str]] = set()
            for item in capabilities:
                if not isinstance(item, dict):
                    errors.append("manifest capability is not an object")
                    continue
                key = (str(item.get("source_url")), str(item.get("source_path")))
                if key in seen:
                    errors.append(f"duplicate manifest source entry: {key}")
                seen.add(key)
                status = item.get("status")
                pin = item.get("pinned_commit_sha")
                if status in {"ACCEPTED", "ADAPTED", "EXTERNAL_TOOL_ONLY"} and not SHA_RE.fullmatch(str(pin or "")):
                    errors.append(f"{item.get('canonical_name')}: accepted source is not pinned")
                skill_path = item.get("canonical_skill_path")
                if skill_path and not (ROOT / skill_path).is_file():
                    errors.append(f"{item.get('canonical_name')}: missing canonical skill path {skill_path}")
                source_slug = str(item.get("source_url", "")).rstrip("/").split("/")[-1].lower()
                if source_slug in REJECTED_EXTERNAL_TOOLS:
                    if status != "REJECTED":
                        errors.append(f"{item.get('canonical_name')}: rejected source status is {status}")
                    for field in ("canonical_skill_path", "claude_adapter_path", "antigravity_adapter_path"):
                        if item.get(field) is not None:
                            errors.append(f"{item.get('canonical_name')}: rejected source exposes {field}")
                    if item.get("activation_profile"):
                        errors.append(f"{item.get('canonical_name')}: rejected source has an activation profile")
    if isinstance(lock, dict):
        sources = lock.get("sources")
        if not isinstance(sources, list):
            errors.append("lock file sources must be a list")
        else:
            seen_urls: set[str] = set()
            for source in sources:
                url = str(source.get("source", ""))
                if url in seen_urls:
                    errors.append(f"duplicate lock source: {url}")
                seen_urls.add(url)
                if source.get("status") not in {"BLOCKED", "QUARANTINED", "REJECTED"} and not SHA_RE.fullmatch(str(source.get("commit_sha", ""))):
                    errors.append(f"lock source is unpinned: {url}")
                checksums = source.get("file_checksums")
                if not isinstance(checksums, dict) or not checksums:
                    errors.append(f"lock source has no audit checksums: {url}")

    if (ROOT / ".mcp.json").exists():
        errors.append("root .mcp.json is prohibited; MCP servers require a separately reviewed, profile-scoped decision")
    for hook_root in (ROOT / ".claude" / "hooks", ROOT / ".agents" / "hooks"):
        if hook_root.is_dir() and any(path.is_file() for path in hook_root.rglob("*")):
            errors.append(f"project hook activation is prohibited: {relative(hook_root)}")
    rule_root = ROOT / ".agents" / "rules"
    actual_rules = {path.name for path in rule_root.glob("*.md")} if rule_root.is_dir() else set()
    if REQUIRED_RULES - actual_rules:
        errors.append(f"missing portable security rules: {sorted(REQUIRED_RULES - actual_rules)}")
    if not (ROOT / "scripts" / "bootstrap-graphify.py").is_file():
        errors.append("missing explicit project-local Graphify bootstrap")
    for required in sorted(SECURITY_TOOL_FILES):
        if not (ROOT / required).is_file():
            errors.append(f"missing security-tool artifact: {required}")
    security_tools = load_required(
        ROOT / "agent-platform" / "tooling" / "security-tools.lock.json",
        errors,
    )
    if isinstance(security_tools, dict):
        python_lock = security_tools.get("python", {})
        requirements = ROOT / str(python_lock.get("requirements", ""))
        if not requirements.is_file():
            errors.append("security Python requirements lock is missing")
        else:
            requirements_bytes = requirements.read_bytes()
            requirements_digest = sha256_text_lf(requirements)
            if requirements_digest != python_lock.get("requirements_sha256"):
                errors.append("security Python requirements checksum does not match security-tools.lock.json")
            requirement_lines = [
                line.strip()
                for line in requirements_bytes.decode("utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
            requirement_re = re.compile(
                r"^[A-Za-z0-9_.-]+==[^=\s]+ --hash=sha256:[0-9a-f]{64}$"
            )
            if any(not requirement_re.fullmatch(line) for line in requirement_lines):
                errors.append("security Python requirements contain an unpinned or unhashed entry")
            required_pins = {"semgrep": "1.171.0", "pip_audit": "2.10.1", "mcp": "1.28.1"}
            normalized = {line.split("==", 1)[0].lower(): line for line in requirement_lines}
            for name, version in required_pins.items():
                if not normalized.get(name, "").startswith(f"{name}=={version} "):
                    errors.append(f"security Python requirements are missing {name}=={version}")
        for native_name in ("gitleaks", "trivy"):
            native = security_tools.get("native_tools", {}).get(native_name)
            if not isinstance(native, dict):
                errors.append(f"security tool lock is missing {native_name}")
                continue
            if not native.get("version") or not re.fullmatch(
                r"[0-9a-f]{64}", str(native.get("checksum_manifest_sha256", ""))
            ):
                errors.append(f"security tool lock has invalid {native_name} version or manifest hash")
            assets = native.get("assets")
            if not isinstance(assets, dict) or not assets:
                errors.append(f"security tool lock has no {native_name} assets")
            elif any(
                not isinstance(asset, dict)
                or not asset.get("name")
                or not re.fullmatch(r"[0-9a-f]{64}", str(asset.get("sha256", "")))
                for asset in assets.values()
            ):
                errors.append(f"security tool lock has an invalid {native_name} asset")
    scanner_evidence = load_required(
        ROOT / "docs" / "agent-audit" / "evidence" / "security-scanner-summary.json",
        errors,
    )
    if isinstance(scanner_evidence, dict):
        results = scanner_evidence.get("results")
        if not isinstance(results, dict):
            errors.append("security scanner evidence results must be an object")
        else:
            if set(results) != EXPECTED_SECURITY_RESULTS:
                errors.append(
                    "security scanner evidence has unexpected result set: "
                    f"{sorted(set(results) ^ EXPECTED_SECURITY_RESULTS)}"
                )
            for name, result in results.items():
                if not isinstance(result, dict) or result.get("status") != "PASSED":
                    errors.append(f"security scanner evidence is not passing: {name}")
                elif result.get("findings"):
                    errors.append(f"security scanner evidence records findings: {name}")
    catalog_comparison = load_required(
        ROOT / "docs" / "agent-audit" / "evidence" / "catalog-authority-comparison.json",
        errors,
    )
    if isinstance(catalog_comparison, dict):
        if catalog_comparison.get("result") != "NO_AUTHORITATIVE_HISTORICAL_COPY_FOUND":
            errors.append("catalog authority comparison has an unexpected result")
        if catalog_comparison.get("decision") != "ADOPT_RECONSTRUCTED_AS_REPOSITORY_CANONICAL_V1":
            errors.append("reconstructed catalog is not recorded as canonical v1")
    core_tools = load_required(ROOT / "core-tooling.json", errors)
    if isinstance(core_tools, dict):
        tool_ids = {str(tool.get("id")) for tool in core_tools.get("tools", []) if isinstance(tool, dict)}
        leaked = tool_ids & REJECTED_EXTERNAL_TOOLS
        if leaked:
            errors.append(f"core-tooling.json exposes rejected tools: {sorted(leaked)}")
        graphify = next(
            (tool for tool in core_tools.get("tools", []) if isinstance(tool, dict) and tool.get("id") == "graphify"),
            None,
        )
        if not graphify:
            errors.append("core-tooling.json is missing Graphify")
        else:
            lock_path = ROOT / str(graphify.get("requirementsLock", ""))
            if not lock_path.is_file():
                errors.append("Graphify requirements lock is missing")
            else:
                digest = sha256_text_lf(lock_path)
                if digest != graphify.get("requirementsSha256"):
                    errors.append("Graphify requirements lock checksum does not match core-tooling.json")
                pins = [
                    line.strip()
                    for line in lock_path.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                ]
                if any(line.count("==") != 1 for line in pins):
                    errors.append("Graphify requirements lock contains a floating dependency")
                if f"graphifyy=={graphify.get('version')}" not in pins:
                    errors.append("Graphify direct package version is absent from its requirements lock")
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Agent platform validation failed with {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"Agent platform validation passed: {len(actual_roles)} roles, {len(actual_profiles)} profiles, {len(skills)} skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
