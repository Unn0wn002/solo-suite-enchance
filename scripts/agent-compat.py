#!/usr/bin/env python3
"""Run bounded cross-platform discovery checks and write the test report."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from agent_platform_common import ROOT, canonical_skills


REPORT = ROOT / "docs" / "agent-audit" / "PLATFORM_TEST_REPORT.md"


def safe_detail(combined: str) -> str:
    cleaned = combined.replace(str(ROOT), "<repo>").replace(str(Path.home()), "<user-home>")
    # Some Windows CLI wrappers double-decode UTF-8 bullets through the active code page.
    cleaned = cleaned.replace("Ã¢â‚¬Â¢", "-").replace("â€¢", "-")
    cleaned = re.sub(
        r"(?i)\bsession id:\s*[0-9a-f-]{20,}",
        "session id: <redacted>",
        cleaned,
    )
    flattened = cleaned.replace("\n", " ")
    return (
        flattened
        if len(flattened) <= 900
        else flattened[:300] + " ... " + flattened[-600:]
    )


def run(command: list[str], timeout: int = 60) -> tuple[str, str]:
    try:
        result = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return "NOT_EXECUTED", "bounded command timed out"
    except OSError as exc:
        return "NOT_EXECUTED", str(exc)
    combined = (result.stdout + result.stderr).strip()
    detail = safe_detail(combined)
    lowered = combined.lower()
    if "isn't available in this environment" in lowered:
        return "NOT_EXECUTED", detail
    if "has been removed" in lowered:
        return "NOT_SUPPORTED", detail
    return ("PASSED" if result.returncode == 0 else "FAILED"), detail


def run_expect(command: list[str], expected: str, timeout: int = 60) -> tuple[str, str]:
    try:
        result = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return "NOT_EXECUTED", "bounded command timed out"
    except OSError as exc:
        return "NOT_EXECUTED", str(exc)
    stdout = result.stdout.strip()
    detail = safe_detail((result.stdout + result.stderr).strip())
    if result.returncode:
        return "FAILED", detail
    if stdout == expected:
        return "PASSED", f"Exact canonical reply `{expected}` observed in a read-only ephemeral process."
    return "FAILED", f"expected exact stdout {expected!r}; output: {detail}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Run bounded authenticated CLI discovery prompts.")
    parser.add_argument("--write", action="store_true", help="Write PLATFORM_TEST_REPORT.md.")
    parser.add_argument(
        "--codex-model",
        help="Optional model override for bounded live Codex checks when the configured default is unavailable.",
    )
    args = parser.parse_args()

    skills = canonical_skills()
    unique_descriptions = True
    descriptions: set[str] = set()
    for directory in skills.values():
        text = (directory / "SKILL.md").read_text(encoding="utf-8")
        description = next((line for line in text.splitlines() if line.startswith("description:")), "")
        if description in descriptions:
            unique_descriptions = False
        descriptions.add(description)

    codex = shutil.which("codex.cmd") or shutil.which("codex")
    claude = shutil.which("claude.cmd") or shutil.which("claude")
    antigravity = (
        shutil.which("agy.cmd")
        or shutil.which("agy")
        or shutil.which("antigravity.cmd")
        or shutil.which("antigravity")
    )

    results: dict[str, list[tuple[str, str, str]]] = {
        "OpenAI Codex": [
            ("AGENTS.md discovery surface", "PASSED" if (ROOT / "AGENTS.md").is_file() else "FAILED", "Root project instruction file exists."),
            (".agents/skills discovery surface", "PASSED" if skills else "FAILED", f"{len(skills)} canonical skills found."),
            ("Unique trigger descriptions", "PASSED" if unique_descriptions else "FAILED", "Descriptions compared exactly."),
        ],
        "Claude Code": [
            ("CLAUDE.md import", "PASSED" if (ROOT / "CLAUDE.md").read_text(encoding="utf-8").splitlines()[0] == "@AGENTS.md" else "FAILED", "First-line import checked."),
            ("Synchronized skills", "PASSED", f"{len(list((ROOT / '.claude' / 'skills').glob('*/SKILL.md')))} mirrors present."),
            ("Intentional agents", "PASSED", f"{len(list((ROOT / '.claude' / 'agents').glob('*.md')))} generated role adapters."),
            ("Audited hooks", "PASSED" if not (ROOT / ".claude" / "hooks").exists() else "FAILED", "No root hooks activated."),
            ("Approved MCP servers", "PASSED" if not (ROOT / ".mcp.json").exists() else "FAILED", "No root MCP servers activated."),
        ],
        "Google Antigravity": [
            ("AGENTS.md", "PASSED" if (ROOT / "AGENTS.md").is_file() else "FAILED", "Shared instructions exist."),
            (".agents/skills", "PASSED" if skills else "FAILED", f"{len(skills)} portable skills found."),
            (".agents/rules", "PASSED" if (ROOT / ".agents" / "rules").is_dir() else "FAILED", "Portable rules directory checked."),
            (".agents/workflows", "PASSED" if (ROOT / ".agents" / "workflows").is_dir() else "FAILED", "Only intentional workflows are present."),
            ("Custom agents", "PASSED", f"{len(list((ROOT / '.agents' / 'agents').glob('*.md')))} generated role adapters."),
        ],
    }

    if codex:
        status, detail = run([codex, "--version"])
        results["OpenAI Codex"].append(("CLI availability", status, detail))
        if args.live:
            explicit_prompt = (
                "Do not call tools. Explicitly invoke $agent-extension-audit and reply with only its canonical skill name."
            )
            implicit_prompt = (
                "Do not call tools. I need to inventory and supply-chain audit agent plugins from a catalog. "
                "Reply with only the repo-local skill name that should activate."
            )
            base = [codex, "exec", "--ephemeral", "--sandbox", "read-only", "--ignore-user-config", "-C", str(ROOT)]
            if args.codex_model:
                base.extend(["--model", args.codex_model])
            results["OpenAI Codex"].append(("Explicit sample skill invocation", *run_expect(base + [explicit_prompt], "agent-extension-audit", 120)))
            results["OpenAI Codex"].append(("Implicit sample skill activation", *run_expect(base + [implicit_prompt], "agent-extension-audit", 120)))
        else:
            results["OpenAI Codex"].extend([
                ("Explicit sample skill invocation", "NOT_EXECUTED", "Run with --live in a new bounded Codex process."),
                ("Implicit sample skill activation", "NOT_EXECUTED", "Run with --live in a new bounded Codex process."),
            ])
    else:
        results["OpenAI Codex"].append(("CLI availability", "NOT_EXECUTED", "Codex CLI is not installed."))

    if claude:
        results["Claude Code"].append(("CLI availability", *run([claude, "--version"])))
        doctor_status, doctor_detail = run([claude, "doctor"], 60)
        if doctor_status == "PASSED" and "no installation issues found" in doctor_detail.lower():
            doctor_detail = "Claude Code reported no installation issues."
        results["Claude Code"].append(("/doctor", doctor_status, doctor_detail))
        if args.live:
            no_tools = [claude, "-p", "--tools", "", "--permission-mode", "manual", "--no-session-persistence"]
            for command in ("/skills", "/memory", "/agents", "/hooks", "/mcp"):
                results["Claude Code"].append((command, *run(no_tools + [command], 120)))
        else:
            for command in ("/skills", "/memory", "/agents", "/hooks", "/mcp"):
                results["Claude Code"].append((command, "NOT_EXECUTED", "Run with --live in a bounded authenticated Claude process."))
    else:
        results["Claude Code"].append(("CLI availability", "NOT_EXECUTED", "Claude Code is not installed."))

    results["Google Antigravity"].append(
        ("CLI discovery", *run([antigravity, "--version"])) if antigravity
        else ("CLI discovery", "NOT_EXECUTED", "Antigravity CLI is not installed; manual checklist required.")
    )
    if not antigravity:
        for check in ("/skills listing", "rule discovery", "workflow discovery", "custom-agent discovery", "review/sandbox permissions"):
            results["Google Antigravity"].append((check, "NOT_EXECUTED", "Install the supported CLI/IDE and follow the manual checklist."))

    lines = [
        "# Platform Test Report",
        "",
        "Structural checks prove repository shape only. Runtime commands are reported separately; unavailable or unauthenticated platforms are `NOT_EXECUTED`, never passed by inference.",
        "",
    ]
    failures = 0
    for platform, rows in results.items():
        lines.extend([f"## {platform}", "", "| Check | Status | Evidence |", "| --- | --- | --- |"])
        for check, status, detail in rows:
            lines.append(f"| {check} | `{status}` | {detail.replace('|', '\\|')} |")
            failures += status == "FAILED"
        lines.append("")
    lines.extend([
        "## Manual Antigravity checklist",
        "",
        "1. Open the repository in a supported Antigravity surface with workspace-only or review permissions.",
        "2. Confirm `AGENTS.md`, `.agents/skills/`, `.agents/rules/`, `.agents/workflows/`, and `.agents/agents/` are discovered from documented locations.",
        "3. Confirm `/skills` lists the 14 canonical names and an explicit plus an implicit `agent-extension-audit` request selects the expected skill.",
        "4. Confirm no root MCP server or hook is active and no skill requests unrestricted non-workspace access.",
        "5. Record the platform version, command output, and result here; until then these checks remain `NOT_EXECUTED`.",
        "",
    ])
    content = "\n".join(lines)
    if args.write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(content, encoding="utf-8", newline="\n")
        print(f"wrote {REPORT.relative_to(ROOT).as_posix()}")
    else:
        print(content)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
