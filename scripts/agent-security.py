#!/usr/bin/env python3
"""Read-only security checks for the local agent platform."""

from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from agent_platform_common import ROOT, relative


SCAN_ROOTS = [
    ROOT / ".agents",
    ROOT / ".claude",
    ROOT / "agent-platform",
    ROOT / "docs" / "agent-audit",
]
SCAN_FILES = [ROOT / "AGENTS.md", ROOT / "CLAUDE.md", ROOT / "Makefile", ROOT / "package.json"]
NPM_AUDIT_EVIDENCE = ROOT / "docs" / "agent-audit" / "evidence" / "npm-audit-summary.json"
SECURITY_TOOL_ROOT = ROOT / ".tools" / "security"
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".py", ".ps1", ".sh", ".toml", ".txt"}
SECRET_PATTERNS = {
    "OpenAI-style secret": re.compile(r"\bsk-(?!example|redacted)[A-Za-z0-9_-]{20,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "assigned credential": re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*[\"'](?!REDACTED|EXAMPLE|CHANGEME)[^\"']{10,}[\"']"
    ),
}
EXECUTABLE_RISK_PATTERNS = {
    "download and execute": re.compile(r"(?i)\b(?:curl|wget)\b[^\n|]*\|\s*(?:ba|z|fi)?sh\b"),
    "PowerShell download and execute": re.compile(r"(?i)\b(?:irm|Invoke-RestMethod)\b[^\n|]*\|\s*(?:iex|Invoke-Expression)\b"),
    "verification bypass": re.compile(r"(?i)(?<![\"'])\b(?:git\s+[^\n]*--no-verify|--no-verify\s+(?:commit|push))\b"),
    "shell execution API": re.compile(r"(?i)\b(?:shell\s*=\s*True|os\.system\s*\(|Invoke-Expression\s+)"),
}


def files_to_scan() -> list[Path]:
    files = [path for path in SCAN_FILES if path.is_file()]
    for root in SCAN_ROOTS:
        if root.is_dir():
            files.extend(
                path
                for path in root.rglob("*")
                if path.is_file() and (path.suffix.lower() in TEXT_SUFFIXES or path.name in {"SKILL.md", "Makefile"})
            )
    return sorted(set(files))


def local_scan() -> list[str]:
    findings: list[str] = []
    for path in files_to_scan():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"{relative(path)}: unexpected binary content in agent platform text surface")
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{relative(path)}: {label}")
        if path.suffix.lower() in {".py", ".ps1", ".sh"}:
            for label, pattern in EXECUTABLE_RISK_PATTERNS.items():
                if pattern.search(text):
                    findings.append(f"{relative(path)}: {label}")
    if (ROOT / ".mcp.json").exists():
        findings.append(".mcp.json: root MCP activation requires an approved manifest decision")
    for hook_root in (ROOT / ".claude" / "hooks", ROOT / ".agents" / "hooks"):
        hooks = list(hook_root.glob("**/*")) if hook_root.is_dir() else []
        if any(path.is_file() for path in hooks):
            findings.append(f"{relative(hook_root)}: project hooks are prohibited")
    return findings


def npm_audit() -> tuple[str, int, dict[str, object] | None]:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    lock = ROOT / "package-lock.json"
    if not npm or not lock.is_file():
        return "NOT_EXECUTED: npm or package-lock.json unavailable", 0, None
    result = subprocess.run(
        [npm, "audit", "--ignore-scripts", "--audit-level=high", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    try:
        payload = json.loads(result.stdout)
        vulnerabilities = payload.get("metadata", {}).get("vulnerabilities", {})
        summary = ", ".join(f"{key}={value}" for key, value in vulnerabilities.items()) or "no counts returned"
        vulnerable_packages = payload.get("vulnerabilities", {})
        package_summary = ", ".join(
            f"{name}({item.get('severity')}, range={item.get('range')}, fix={item.get('fixAvailable')})"
            for name, item in sorted(vulnerable_packages.items())
            if isinstance(item, dict)
        )
        if package_summary:
            summary = f"{summary}; packages={package_summary}"
        direct = []
        for name, item in sorted(vulnerable_packages.items()):
            if not isinstance(item, dict) or not item.get("isDirect"):
                continue
            direct.append(
                {
                    "name": name,
                    "severity": item.get("severity"),
                    "affected_range": item.get("range"),
                    "fix_available": item.get("fixAvailable"),
                }
            )
        evidence: dict[str, object] | None = {
            "schema_version": 1,
            "audit_date": datetime.date.today().isoformat(),
            "command_policy": "npm audit --ignore-scripts --audit-level=high --json",
            "lifecycle_scripts_executed": False,
            "vulnerability_counts": vulnerabilities,
            "direct_dependencies": direct,
            "exit_code": result.returncode,
        }
    except json.JSONDecodeError:
        summary = (result.stderr or result.stdout).strip()[:500] or "no npm audit output"
        evidence = None
    return f"npm audit: {summary}", result.returncode, evidence


def scanner_path(name: str) -> Path | None:
    suffix = ".exe" if sys.platform == "win32" else ""
    group = "python" if name in {"semgrep", "pip-audit"} else "bin"
    if group == "python":
        directory = Path("Scripts") if sys.platform == "win32" else Path("bin")
        candidate = SECURITY_TOOL_ROOT / "python" / directory / f"{name}{suffix}"
    else:
        candidate = SECURITY_TOOL_ROOT / "bin" / f"{name}{suffix}"
    if candidate.is_file():
        return candidate
    detected = shutil.which(name)
    return Path(detected) if detected else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--npm-audit", action="store_true", help="Also run npm audit with lifecycle scripts disabled.")
    parser.add_argument(
        "--full-scanners",
        action="store_true",
        help="Run the pinned project-local Semgrep, Gitleaks, Trivy, and pip-audit suite.",
    )
    parser.add_argument(
        "--write-evidence",
        action="store_true",
        help="Write a normalized npm-audit summary; requires --npm-audit.",
    )
    args = parser.parse_args()
    if args.write_evidence and not args.npm_audit:
        parser.error("--write-evidence requires --npm-audit")

    findings = local_scan()
    for finding in findings:
        print(f"ERROR: {finding}")

    exit_code = 1 if findings else 0
    if args.npm_audit:
        try:
            summary, code, evidence = npm_audit()
        except subprocess.TimeoutExpired:
            summary, code, evidence = "NOT_EXECUTED: npm audit exceeded 120 seconds", 0, None
        print(summary)
        if args.write_evidence and evidence is not None:
            NPM_AUDIT_EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
            NPM_AUDIT_EVIDENCE.write_text(
                json.dumps(evidence, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            print(f"wrote {NPM_AUDIT_EVIDENCE.relative_to(ROOT).as_posix()}")
        if code:
            exit_code = 1
    else:
        print("npm audit: NOT_EXECUTED (pass --npm-audit to enable network-backed package audit)")

    remediation_result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check-high-risk-remediations.py")],
        cwd=ROOT,
        check=False,
    )
    if remediation_result.returncode:
        exit_code = 1

    optional = ["semgrep", "gitleaks", "trivy", "pip-audit"]
    for scanner in optional:
        path = scanner_path(scanner)
        print(f"{scanner}: {f'AVAILABLE ({path})' if path else 'NOT_INSTALLED'}")
    if args.full_scanners:
        command = [sys.executable, str(ROOT / "scripts" / "run-security-scanners.py")]
        if args.write_evidence:
            command.append("--write-evidence")
        scanner_result = subprocess.run(command, cwd=ROOT, check=False)
        if scanner_result.returncode:
            exit_code = 1
    if exit_code:
        print("Agent security checks failed", file=sys.stderr)
    else:
        print("Agent security checks passed")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
