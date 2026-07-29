#!/usr/bin/env python3
"""Run the pinned project-local security scanners and write redacted evidence."""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools" / "security"
BIN = TOOLS / "bin"
PY_BIN = TOOLS / "python" / ("Scripts" if os.name == "nt" else "bin")
SUFFIX = ".exe" if os.name == "nt" else ""
EVIDENCE = ROOT / "docs" / "agent-audit" / "evidence" / "security-scanner-summary.json"


def executable(group: str, name: str) -> Path:
    base = PY_BIN if group == "python" else BIN
    return base / f"{name}{SUFFIX}"


def run(command: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def parse_json_output(result: subprocess.CompletedProcess[str]) -> object:
    text = result.stdout.strip()
    if not text:
        return {}
    return json.loads(text)


def semgrep_scan() -> dict[str, object]:
    tool = executable("python", "semgrep")
    command = [
        str(tool),
        "scan",
        "--config",
        "agent-platform/security/semgrep-rules.yaml",
        "--metrics=off",
        "--disable-version-check",
        "--error",
        "--json",
    ]
    for excluded in (".git", ".tools", ".tmp", "node_modules", "graphify-out", "dist", "coverage"):
        command.extend(["--exclude", excluded])
    command.extend(["app", "scripts", "tests", "platforms"])
    result = run(command)
    payload = parse_json_output(result)
    findings = [
        {
            "rule": item.get("check_id"),
            "path": item.get("path"),
            "line": item.get("start", {}).get("line"),
            "severity": item.get("extra", {}).get("severity"),
            "message": item.get("extra", {}).get("message"),
        }
        for item in payload.get("results", [])
    ]
    return {
        "status": "PASSED" if result.returncode == 0 and not findings else "FAILED",
        "exit_code": result.returncode,
        "findings": findings,
        "errors": payload.get("errors", []),
    }


def gitleaks_scan(temp: Path, mode: str) -> dict[str, object]:
    tool = executable("native", "gitleaks")
    report = temp / f"gitleaks-{mode}.json"
    command = [
        str(tool),
        mode,
        ".",
        "--config",
        ".gitleaks.toml",
        "--no-banner",
        "--no-color",
        "--redact=100",
        "--log-level",
        "warn",
        "--report-format",
        "json",
        "--report-path",
        str(report),
        "--exit-code",
        "1",
        "--timeout",
        "300",
    ]
    if mode == "dir":
        command.extend(["--max-target-megabytes", "5"])
    result = run(command)
    payload = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else []
    findings = [
        {
            "rule": item.get("RuleID"),
            "path": item.get("File"),
            "line": item.get("StartLine"),
            "commit": item.get("Commit") or None,
        }
        for item in payload
    ]
    return {
        "status": "PASSED" if result.returncode == 0 and not findings else "FAILED",
        "exit_code": result.returncode,
        "findings": findings,
    }


def trivy_scan(temp: Path) -> dict[str, object]:
    tool = executable("native", "trivy")
    report = temp / "trivy.json"
    command = [
        str(tool),
        "fs",
        ".",
        "--cache-dir",
        str(TOOLS / "trivy-cache"),
        "--disable-telemetry",
        "--skip-version-check",
        "--no-progress",
        "--include-dev-deps",
        "--scanners",
        "vuln,misconfig,secret",
        "--severity",
        "HIGH,CRITICAL",
        "--exit-code",
        "1",
        "--format",
        "json",
        "--output",
        str(report),
        "--timeout",
        "10m",
    ]
    for excluded in (".git", ".tools", ".tmp", "node_modules", "graphify-out", "dist", "coverage"):
        command.extend(["--skip-dirs", excluded])
    result = run(command, timeout=720)
    payload = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    findings: list[dict[str, object]] = []
    for target in payload.get("Results", []):
        for item in target.get("Vulnerabilities") or []:
            findings.append(
                {
                    "kind": "vulnerability",
                    "target": target.get("Target"),
                    "id": item.get("VulnerabilityID"),
                    "package": item.get("PkgName"),
                    "installed": item.get("InstalledVersion"),
                    "fixed": item.get("FixedVersion"),
                    "severity": item.get("Severity"),
                }
            )
        for item in target.get("Misconfigurations") or []:
            findings.append(
                {
                    "kind": "misconfiguration",
                    "target": target.get("Target"),
                    "id": item.get("ID"),
                    "title": item.get("Title"),
                    "severity": item.get("Severity"),
                }
            )
        for item in target.get("Secrets") or []:
            findings.append(
                {
                    "kind": "secret",
                    "target": target.get("Target"),
                    "rule": item.get("RuleID"),
                    "line": item.get("StartLine"),
                    "severity": item.get("Severity"),
                }
            )
    return {
        "status": "PASSED" if result.returncode == 0 and not findings else "FAILED",
        "exit_code": result.returncode,
        "findings": findings,
    }


def pip_audit(arguments: list[str], label: str) -> dict[str, object]:
    tool = executable("python", "pip-audit")
    result = run([str(tool), *arguments, "--format", "json", "--progress-spinner", "off"])
    payload = parse_json_output(result)
    findings = [
        {
            "package": dependency.get("name"),
            "version": dependency.get("version"),
            "id": vulnerability.get("id"),
            "fix_versions": vulnerability.get("fix_versions", []),
            "aliases": vulnerability.get("aliases", []),
        }
        for dependency in payload.get("dependencies", [])
        for vulnerability in dependency.get("vulns", [])
    ]
    return {
        "target": label,
        "status": "PASSED" if result.returncode == 0 and not findings else "FAILED",
        "exit_code": result.returncode,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-evidence", action="store_true", help="Write a redacted normalized summary.")
    args = parser.parse_args()
    required = [
        executable("python", "semgrep"),
        executable("python", "pip-audit"),
        executable("native", "gitleaks"),
        executable("native", "trivy"),
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        print("ERROR: scanner bootstrap is incomplete: " + ", ".join(missing), file=sys.stderr)
        return 2

    (ROOT / ".tmp").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="agent-security-", dir=ROOT / ".tmp") as directory:
        temp = Path(directory)
        results = {
            "semgrep": semgrep_scan(),
            "gitleaks_worktree": gitleaks_scan(temp, "dir"),
            "gitleaks_history": gitleaks_scan(temp, "git"),
            "trivy": trivy_scan(temp),
            "pip_audit_scanners": pip_audit(["--local"], "scanner environment"),
            "pip_audit_graphify": pip_audit(
                [
                    "--no-deps",
                    "--disable-pip",
                    "--requirement",
                    "agent-platform/tooling/graphify-requirements.txt",
                ],
                "Graphify requirements",
            ),
        }

    failed = False
    for name, result in results.items():
        count = len(result.get("findings", []))
        print(f"{name}: {result['status']} ({count} finding(s))")
        failed = failed or result["status"] != "PASSED"

    evidence = {
        "schema_version": 1,
        "audit_date": datetime.date.today().isoformat(),
        "policy": {
            "secret_values_recorded": False,
            "semgrep_metrics": False,
            "trivy_telemetry": False,
            "trivy_severity_gate": ["HIGH", "CRITICAL"],
        },
        "results": results,
    }
    if args.write_evidence:
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {EVIDENCE.relative_to(ROOT).as_posix()}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
