#!/usr/bin/env python3
"""Fail closed when a HIGH/CRITICAL source finding regains an activation path."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "agent-platform" / "manifest.yaml"
REMEDIATIONS = ROOT / "agent-platform" / "security" / "high-risk-remediations.json"
REJECTED_STATUSES = {"BLOCKED", "QUARANTINED", "REJECTED"}
PROHIBITED_ADAPTER_PATTERNS = {
    "download-and-execute shell pipeline": re.compile(
        r"(?i)\b(?:curl|wget)\b[^\n|]*\|\s*(?:ba|z|fi)?sh\b"
    ),
    "download-and-execute PowerShell pipeline": re.compile(
        r"(?i)\b(?:irm|Invoke-RestMethod)\b[^\n|]*\|\s*(?:iex|Invoke-Expression)\b"
    ),
    "verification bypass": re.compile(r"(?i)\b--no-verify\b"),
    "protect-mcp execution": re.compile(r"(?i)\bnpx(?:\.cmd)?\s+protect-mcp\b"),
    "broad recursive deletion": re.compile(
        r"(?i)\b(?:rm\s+-[^\n]*r[^\n]*f|Remove-Item\b[^\n]*-Recurse)"
    ),
}


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_lf_normalized(path: Path) -> str:
    """Hash text controls consistently across Git checkout line endings."""
    content = path.read_bytes()
    if b"\0" in content:
        raise ValueError(f"control artifact is not text: {path}")
    normalized = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def main() -> int:
    errors: list[str] = []
    try:
        manifest = load_json(MANIFEST)
        ledger = load_json(REMEDIATIONS)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot load remediation evidence: {exc}", file=sys.stderr)
        return 1

    capabilities = manifest.get("capabilities")
    findings = ledger.get("findings")
    if not isinstance(capabilities, list) or not isinstance(findings, list):
        print("ERROR: manifest capabilities and remediation findings must be arrays", file=sys.stderr)
        return 1

    high_capabilities = {
        str(item.get("canonical_name")): item
        for item in capabilities
        if isinstance(item, dict) and item.get("risk_level") in {"HIGH", "CRITICAL"}
    }
    finding_map: dict[str, dict[str, object]] = {}
    for finding in findings:
        if not isinstance(finding, dict):
            errors.append("remediation finding is not an object")
            continue
        name = str(finding.get("canonical_name", ""))
        if not name or name in finding_map:
            errors.append(f"missing or duplicate remediation finding name: {name!r}")
            continue
        finding_map[name] = finding

    missing = set(high_capabilities) - set(finding_map)
    extra = set(finding_map) - set(high_capabilities)
    if missing:
        errors.append(f"HIGH/CRITICAL capabilities without remediation evidence: {sorted(missing)}")
    if extra:
        errors.append(f"remediation evidence without a HIGH/CRITICAL capability: {sorted(extra)}")

    allowed_residual = set(ledger.get("policy", {}).get("allowed_residual_risk", []))
    for name in sorted(set(high_capabilities) & set(finding_map)):
        capability = high_capabilities[name]
        finding = finding_map[name]
        if finding.get("source_risk") != capability.get("risk_level"):
            errors.append(f"{name}: source risk differs between manifest and remediation evidence")
        if finding.get("integration_status") != capability.get("status"):
            errors.append(f"{name}: integration status differs between manifest and remediation evidence")
        if finding.get("remediation_status") != "VERIFIED":
            errors.append(f"{name}: remediation is not VERIFIED")
        residual = finding.get("residual_integration_risk")
        if residual not in allowed_residual:
            errors.append(f"{name}: residual integration risk is not allowed: {residual}")
        for field in ("remediation", "replacement"):
            if not str(finding.get(field, "")).strip():
                errors.append(f"{name}: remediation evidence is missing {field}")
        if capability.get("enabled_by_default") is not False:
            errors.append(f"{name}: HIGH/CRITICAL capability is enabled by default")
        if capability.get("remediation_status") != finding.get("remediation_status"):
            errors.append(f"{name}: generated manifest remediation status is stale")
        if capability.get("residual_integration_risk") != residual:
            errors.append(f"{name}: generated manifest residual risk is stale")

        if capability.get("status") in REJECTED_STATUSES:
            for field in ("canonical_skill_path", "claude_adapter_path", "antigravity_adapter_path"):
                if capability.get(field) is not None:
                    errors.append(f"{name}: rejected capability exposes {field}")
            if capability.get("activation_profile"):
                errors.append(f"{name}: rejected capability has an activation profile")
            if capability.get("related_canonical_skills"):
                errors.append(f"{name}: rejected capability exposes related canonical skills")
            role_paths = capability.get("role_adapter_paths", {})
            if not isinstance(role_paths, dict) or any(role_paths.get(platform) for platform in ("claude", "antigravity")):
                errors.append(f"{name}: rejected capability exposes role adapters")
            external = capability.get("external_tool_requirement", {})
            if not isinstance(external, dict) or external.get("name") is not None or external.get("required") is not False:
                errors.append(f"{name}: rejected capability exposes an external tool requirement")
        elif capability.get("status") == "ADAPTED":
            skill_path = str(capability.get("canonical_skill_path", ""))
            if skill_path != finding.get("replacement"):
                errors.append(f"{name}: adapted skill does not match the verified replacement")
                continue
            skill = ROOT / skill_path
            if not skill.is_file():
                errors.append(f"{name}: adapted skill is missing: {skill_path}")
                continue
            text = skill.read_text(encoding="utf-8")
            for label, pattern in PROHIBITED_ADAPTER_PATTERNS.items():
                if pattern.search(text):
                    errors.append(f"{name}: adapted skill contains {label}")
        else:
            errors.append(f"{name}: HIGH/CRITICAL capability has unsupported status {capability.get('status')}")

    policy = ledger.get("policy", {})
    if policy.get("control_artifact_hash_mode") != "sha256-lf-normalized":
        errors.append("remediation ledger control hash mode is not sha256-lf-normalized")

    artifacts = ledger.get("control_artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        errors.append("remediation ledger has no control artifact checksums")
    else:
        for relative, expected in sorted(artifacts.items()):
            path = ROOT / str(relative)
            if not path.is_file():
                errors.append(f"missing remediation control artifact: {relative}")
            elif not re.fullmatch(r"[0-9a-f]{64}", str(expected)):
                errors.append(f"invalid remediation checksum: {relative}")
            else:
                try:
                    actual = sha256_lf_normalized(path)
                except ValueError as exc:
                    errors.append(str(exc))
                    continue
                if actual != expected:
                    errors.append(f"remediation control artifact drifted: {relative}")

    if (ROOT / ".mcp.json").exists():
        errors.append("root .mcp.json reintroduces an MCP activation path")
    for hook_root in (ROOT / ".agents" / "hooks", ROOT / ".claude" / "hooks"):
        if hook_root.is_dir() and any(path.is_file() for path in hook_root.rglob("*")):
            errors.append(f"project hook activation reintroduced under {hook_root.relative_to(ROOT)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"HIGH/CRITICAL remediation validation failed with {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(
        "HIGH/CRITICAL remediation validation passed: "
        f"{len(high_capabilities)} source finding(s), 0 residual HIGH/CRITICAL integration risks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
