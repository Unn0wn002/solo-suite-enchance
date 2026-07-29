#!/usr/bin/env python3
"""Clone and statically audit catalog sources without executing source code."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from agent_platform_common import ROOT, is_within


CATALOG = ROOT / "docs" / "agent-audit" / "evidence" / "reconstructed-catalog.json"
OUTPUT = ROOT / "docs" / "agent-audit" / "evidence" / "source-audits.json"
TEMP_ROOT = ROOT / ".tmp" / "agent-extension-audit"
AUDIT_DATE = "2026-07-28"
TOOL_VERSION = "solo-suite-agent-audit/1.0.0"
TEXT_SUFFIXES = {
    ".md", ".mdx", ".txt", ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh",
    ".ps1", ".bat", ".cmd", ".rb", ".go", ".rs", ".java", ".kt", ".cs", ".xml",
}
MANIFEST_NAMES = {
    "package.json", "pyproject.toml", "requirements.txt", "setup.py", "setup.cfg",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
    "server.json", "gemini-extension.json", "plugin.json", "marketplace.json",
}
LOCK_NAMES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock", "poetry.lock",
    "Pipfile.lock", "Cargo.lock", "go.sum",
}
SKIP_DIRS = {
    ".git", "node_modules", ".next", ".venv", "venv", "__pycache__", "dist", "build",
    "coverage", ".pytest_cache", ".mypy_cache", ".ruff_cache", "public", "assets",
}
URL_RE = re.compile(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")
ENV_PATTERNS = [
    re.compile(r"(?:os\.environ(?:\.get)?\(|os\.getenv\(|env::var\()\s*[\"']([A-Z][A-Z0-9_]{2,})"),
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]{2,})"),
    re.compile(r"\$\{([A-Z][A-Z0-9_]{2,})\}"),
]
DESTRUCTIVE_PATTERNS = {
    "recursive deletion": re.compile(r"(?i)\b(?:rm\s+-[^\n]*r[^\n]*f|shutil\.rmtree|Remove-Item[^\n]*-Recurse)"),
    "verification bypass": re.compile(r"(?i)\b(?:--no-verify|skip[_-]?verification|disable[_-]?(?:tests|security))\b"),
    "download and execute": re.compile(r"(?i)\b(?:curl|wget)\b[^\n|]*\|\s*(?:ba|z|fi)?sh\b|\b(?:irm|Invoke-RestMethod)\b[^\n|]*\|\s*(?:iex|Invoke-Expression)\b"),
    "shell execution": re.compile(r"(?i)\b(?:os\.system|subprocess\.[A-Za-z_]+\([^\n]*shell\s*=\s*True|child_process\.exec\()"),
}
PROMPT_PATTERNS = {
    "ignore prior policy": re.compile(r"(?i)\bignore\s+(?:all\s+)?(?:previous|prior|repository|system)\s+(?:instructions?|policy|rules?)\b"),
    "override authority": re.compile(r"(?i)\b(?:override|bypass)\s+(?:system|repository|security|user)\s+(?:instructions?|policy|rules?|controls?)\b"),
    "credential request": re.compile(r"(?i)\b(?:send|upload|print|reveal|provide)\b[^\n]{0,80}\b(?:api key|credential|secret|token|password)\b"),
}
NETWORK_PATTERNS = {
    "HTTP client": re.compile(r"(?i)\b(?:requests\.|httpx\.|aiohttp\.|urllib\.request|fetch\(|axios\.|got\(|undici|reqwest::|net/http)\b"),
    "socket/server": re.compile(r"(?i)\b(?:socket\.|listen\(|createServer\(|websocket|streamable[_ -]?http|stdio_server)\b"),
}
FILESYSTEM_PATTERNS = {
    "home-directory access": re.compile(r"(?i)\b(?:Path\.home\(|expanduser\(|os\.homedir\(|USERPROFILE|HOME)\b"),
    "filesystem mutation": re.compile(r"(?i)\b(?:write_text\(|write_bytes\(|open\([^\n]*[\"'][wax]\+?[\"']|unlink\(|rename\(|replace\(|mkdir\(|copyfile\()"),
    "subprocess": re.compile(r"(?i)\b(?:subprocess\.|child_process\.|Command::new|execFile\(|spawn\()\b"),
}


SOURCE_POLICY = {
    "storymap-skill": {
        "classification": "PORTABLE_AGENT_SKILL", "risk": "LOW", "decision": "ADAPTED",
        "recommendation": "Use the original, pinned skill as reference; keep the canonical product-discovery skill original and concise.",
    },
    "gsap-skills": {
        "classification": "PORTABLE_AGENT_SKILL", "risk": "LOW", "decision": "ADAPTED",
        "recommendation": "Use the official pinned skills as versioned references; activate only the GSAP skill needed for the current implementation.",
    },
    "qa-orchestra": {
        "classification": "COMMAND_OR_WORKFLOW", "risk": "MEDIUM", "decision": "ADAPTED",
        "recommendation": "Adapt schemas and evidence patterns only; keep orchestration scripts disabled unless separately reviewed for the target project.",
    },
    "wshobson-agents": {
        "classification": "CLAUDE_PLUGIN", "risk": "MEDIUM", "decision": "ADAPTED",
        "recommendation": "Use selected plugin trees as pinned references; do not activate bundled hooks or translate them automatically.",
    },
    "graphify": {
        "classification": "LOCAL_CLI_TOOL", "risk": "MEDIUM", "decision": "EXTERNAL_TOOL_ONLY",
        "recommendation": "Primary relationship graph; run project-locally and keep optional network/database exports off unless explicitly requested.",
    },
    "serena": {
        "classification": "MCP_SERVER", "risk": "HIGH", "decision": "REJECTED",
        "recommendation": "Rejected from all activation paths. Use Graphify plus bounded native symbol search and client-native editing instead.",
    },
    "context7": {
        "classification": "MCP_SERVER", "risk": "HIGH", "decision": "REJECTED",
        "recommendation": "Rejected from all activation paths. Use primary official documentation through the active client's reviewed web access.",
    },
    "repomix": {
        "classification": "LOCAL_CLI_TOOL", "risk": "MEDIUM", "decision": "EXTERNAL_TOOL_ONLY",
        "recommendation": "Use filtered snapshots only and keep generated outputs outside permanent context.",
    },
    "aider": {
        "classification": "LOCAL_CLI_TOOL", "risk": "HIGH", "decision": "REJECTED",
        "recommendation": "Rejected from all activation paths. Use the active Codex, Claude, or Antigravity client under repository policy.",
    },
    "code-review-graph": {
        "classification": "LOCAL_CLI_TOOL", "risk": "HIGH", "decision": "REJECTED",
        "recommendation": "Rejected as a duplicate graph and hook surface. Graphify is the sole architecture and relationship graph.",
    },
}


COMPATIBILITY = {
    "PORTABLE_AGENT_SKILL": {
        "chatgpt": "PORTABLE", "codex": "PORTABLE", "claude": "PORTABLE",
        "antigravity": "PORTABLE", "antigravity_cli": "PORTABLE",
        "adapter": "Canonical Agent Skills wrapper plus generated Claude mirror.",
    },
    "CLAUDE_PLUGIN": {
        "chatgpt": "ADAPTER_REQUIRED", "codex": "ADAPTER_REQUIRED", "claude": "NATIVE",
        "antigravity": "ADAPTER_REQUIRED", "antigravity_cli": "ADAPTER_REQUIRED",
        "adapter": "Extract instruction-only skills; keep Claude agents, commands, and hooks platform-specific.",
    },
    "COMMAND_OR_WORKFLOW": {
        "chatgpt": "ADAPTER_REQUIRED", "codex": "ADAPTER_REQUIRED", "claude": "ADAPTER_REQUIRED",
        "antigravity": "ADAPTER_REQUIRED", "antigravity_cli": "ADAPTER_REQUIRED",
        "adapter": "Normalize reusable behavior into a skill and keep structured workflow adapters platform-specific.",
    },
    "MCP_SERVER": {
        "chatgpt": "WRAPPER_REQUIRED", "codex": "EXTERNAL_TOOL_ONLY", "claude": "EXTERNAL_TOOL_ONLY",
        "antigravity": "EXTERNAL_TOOL_ONLY", "antigravity_cli": "EXTERNAL_TOOL_ONLY",
        "adapter": "Client-specific MCP registration, scoped permissions, credentials, and an optional routing skill.",
    },
    "LOCAL_CLI_TOOL": {
        "chatgpt": "EXTERNAL_TOOL_ONLY", "codex": "EXTERNAL_TOOL_ONLY", "claude": "EXTERNAL_TOOL_ONLY",
        "antigravity": "EXTERNAL_TOOL_ONLY", "antigravity_cli": "EXTERNAL_TOOL_ONLY",
        "adapter": "Optional project-local CLI wrapper and capability-routing guidance.",
    },
}


def git_run(git: str, args: list[str], cwd: Path | None = None, timeout: int = 90) -> str:
    result = subprocess.run(
        [git, *args], cwd=cwd or ROOT, text=True, capture_output=True, timeout=timeout, check=False
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()[:500])
    return result.stdout.strip()


def safe_clone(git: str, url: str, destination: Path) -> None:
    if not is_within(destination, TEMP_ROOT) or destination.parent.resolve() != TEMP_ROOT.resolve():
        raise ValueError(f"unsafe clone destination: {destination}")
    if destination.exists():
        remote = git_run(git, ["-C", str(destination), "remote", "get-url", "origin"])
        if remote.removesuffix(".git").lower() != url.removesuffix(".git").lower():
            raise ValueError(f"existing clone has unexpected origin: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    git_run(
        git,
        [
            "-c", "core.hooksPath=NUL", "clone", "--depth", "1", "--filter=blob:none",
            "--no-recurse-submodules", url, str(destination),
        ],
        timeout=240,
    )


def github_metadata(owner: str, repository: str) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repository}"
    request = urllib.request.Request(url, headers={"User-Agent": TOOL_VERSION, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"status": "NOT_VERIFIED", "reason": str(exc)}
    result = {
        "status": "VERIFIED",
        "html_url": data.get("html_url"),
        "default_branch": data.get("default_branch"),
        "archived": data.get("archived"),
        "pushed_at": data.get("pushed_at"),
        "updated_at": data.get("updated_at"),
        "owner": data.get("owner", {}).get("login"),
        "owner_type": data.get("owner", {}).get("type"),
        "license_spdx": (data.get("license") or {}).get("spdx_id"),
    }
    release_url = f"{url}/releases/latest"
    release_request = urllib.request.Request(release_url, headers={"User-Agent": TOOL_VERSION, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(release_request, timeout=20) as response:
            release = json.load(response)
        result["latest_release"] = {
            "tag": release.get("tag_name"),
            "published_at": release.get("published_at"),
            "url": release.get("html_url"),
        }
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        result["latest_release"] = None
    return result


def relevant_roots(clone: Path, subdirectories: list[str]) -> list[Path]:
    roots = [clone]
    if "." not in subdirectories:
        roots = [clone / subdirectory for subdirectory in subdirectories if (clone / subdirectory).exists()]
    return roots


def iter_files(roots: list[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for root in roots:
        if root.is_file():
            candidates = [root]
        else:
            candidates = root.rglob("*")
        for path in candidates:
            if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield path


def text_files(roots: list[Path], limit: int = 25_000) -> tuple[list[tuple[Path, str]], bool]:
    result: list[tuple[Path, str]] = []
    truncated = False
    for path in iter_files(roots):
        if len(result) >= limit:
            truncated = True
            break
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in MANIFEST_NAMES | LOCK_NAMES:
            continue
        try:
            if path.stat().st_size > 1_000_000:
                continue
            result.append((path, path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return result, truncated


def line_samples(files: list[tuple[Path, str]], clone: Path, patterns: dict[str, re.Pattern[str]], limit: int = 20) -> dict[str, Any]:
    counts = collections.Counter()
    samples: list[dict[str, Any]] = []
    for path, text in files:
        for number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in patterns.items():
                if pattern.search(line):
                    counts[label] += 1
                    if len(samples) < limit:
                        samples.append({
                            "kind": label,
                            "file": path.relative_to(clone).as_posix(),
                            "line": number,
                            "excerpt": line.strip()[:240],
                        })
    return {"counts": dict(sorted(counts.items())), "samples": samples}


def detect_license(clone: Path) -> dict[str, Any]:
    files = sorted(
        path for path in clone.iterdir()
        if path.is_file() and re.match(r"(?i)^(LICENSE|COPYING|NOTICE)", path.name)
    )
    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")[:10_000] for path in files
    )
    identifiers = []
    if "Apache License" in combined and "Version 2.0" in combined:
        identifiers.append("Apache-2.0")
    if "MIT License" in combined or (
        "Permission is hereby granted, free of charge" in combined and "THE SOFTWARE IS PROVIDED \"AS IS\"" in combined
    ):
        identifiers.append("MIT")
    spdx = " OR ".join(identifiers) if identifiers else "UNKNOWN"
    allowed = spdx != "UNKNOWN"
    return {
        "spdx": spdx,
        "files": [path.name for path in files],
        "copying_permitted": allowed,
        "modification_permitted": allowed,
        "redistribution_permitted": allowed,
        "notice_required": allowed,
    }


def parse_manifest(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"path": path.name, "kind": path.name}
    try:
        if path.name == "package.json":
            data = json.loads(path.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            lifecycle = {
                key: value for key, value in scripts.items()
                if key in {"preinstall", "install", "postinstall", "prepare", "prepublish", "prepublishOnly"}
            }
            dependencies = {}
            for field in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
                dependencies.update(data.get(field) or {})
            result.update({
                "package_name": data.get("name"),
                "scripts": scripts,
                "lifecycle_scripts": lifecycle,
                "dependency_count": len(dependencies),
                "dependency_samples": sorted(dependencies)[:30],
            })
        elif path.name == "pyproject.toml":
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            project = data.get("project", {})
            dependencies = project.get("dependencies") or []
            result.update({
                "package_name": project.get("name"),
                "scripts": project.get("scripts") or {},
                "lifecycle_scripts": {},
                "dependency_count": len(dependencies),
                "dependency_samples": dependencies[:30],
                "build_backend": data.get("build-system", {}).get("build-backend"),
            })
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        result["parse_error"] = str(exc)
    return result


def component_inventory(clone: Path, subdirectories: list[str]) -> list[dict[str, Any]]:
    rows = []
    for subdirectory in subdirectories:
        root = clone if subdirectory == "." else clone / subdirectory
        if not root.exists():
            rows.append({"path": subdirectory, "status": "MISSING"})
            continue
        paths = [path for path in root.rglob("*") if path.is_file() and ".git" not in path.parts]
        rows.append({
            "path": subdirectory,
            "status": "AUDITED",
            "files": len(paths),
            "skills": sum(path.name == "SKILL.md" for path in paths),
            "commands": sum("commands" in path.parts and path.suffix.lower() == ".md" for path in paths),
            "agents": sum("agents" in path.parts and path.suffix.lower() in {".md", ".yaml", ".yml"} for path in paths),
            "hooks": sum("hook" in path.name.lower() or "hooks" in path.parts for path in paths),
            "mcp_definitions": sum(path.name == ".mcp.json" or "mcp" in path.name.lower() for path in paths),
            "tests": sum("test" in part.lower() for path in paths for part in path.parts[-3:]),
        })
    return rows


def audit_source(git: str, source_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = rows[0]
    url = first["repository_url"]
    clone = TEMP_ROOT / source_id
    safe_clone(git, url, clone)
    commit = git_run(git, ["-C", str(clone), "rev-parse", "HEAD"])
    branch = git_run(git, ["-C", str(clone), "branch", "--show-current"])
    resolved = git_run(git, ["-C", str(clone), "remote", "get-url", "origin"]).removesuffix(".git")
    last_commit = git_run(git, ["-C", str(clone), "show", "-s", "--format=%cI", "HEAD"])
    metadata = github_metadata(first["owner"], first["repository"])
    subdirectories = sorted({row["subdirectory"] for row in rows})
    roots = relevant_roots(clone, subdirectories)
    files, truncated = text_files(roots)

    manifests = sorted({
        path for path, _ in files
        if path.name in MANIFEST_NAMES or (path.name == "plugin.json" and ".claude-plugin" in path.parts)
    })
    lock_files = sorted({path for path, _ in files if path.name in LOCK_NAMES})
    parsed_manifests = []
    lifecycle = []
    dependency_count = 0
    dependency_samples: set[str] = set()
    for path in manifests:
        parsed = parse_manifest(path)
        parsed["path"] = path.relative_to(clone).as_posix()
        parsed_manifests.append(parsed)
        dependency_count += int(parsed.get("dependency_count") or 0)
        dependency_samples.update(str(value) for value in parsed.get("dependency_samples", []))
        for name, command in (parsed.get("lifecycle_scripts") or {}).items():
            lifecycle.append({"manifest": parsed["path"], "name": name, "command": command})

    executable = []
    for path, text in files:
        if (
            path.suffix.lower() in {".sh", ".ps1", ".bat", ".cmd", ".py"}
            and ("scripts" in path.parts or text.startswith("#!"))
        ):
            executable.append(path.relative_to(clone).as_posix())
    git_hooks = sorted({
        path.relative_to(clone).as_posix() for path, _ in files
        if ".git" not in path.parts and ("hooks" in path.parts or path.name.lower().endswith("hook"))
    })
    agent_hooks = sorted({
        path.relative_to(clone).as_posix() for path, text in files
        if ("hooks" in path.parts or path.name.lower() in {"hooks.json", "settings.json"}) and "hook" in text.lower()
    })
    mcp_defs = sorted({
        path.relative_to(clone).as_posix() for path, text in files
        if path.name in {".mcp.json", "server.json"} or "mcpservers" in text.lower() or "fastmcp" in text.lower()
    })
    permission_files = sorted({
        path.relative_to(clone).as_posix() for path, text in files
        if re.search(r"(?i)\b(?:allowedTools|disallowedTools|permissionMode|permissions:|sandbox)\b", text)
    })

    env_names: set[str] = set()
    urls: set[str] = set()
    telemetry_files: set[str] = set()
    credential_names: set[str] = set()
    for path, text in files:
        for pattern in ENV_PATTERNS:
            env_names.update(pattern.findall(text))
        urls.update(url.rstrip(".,);]>'\"") for url in URL_RE.findall(text))
        if re.search(r"(?i)\b(?:telemetry|sentry|posthog|analytics|opentelemetry)\b", text):
            telemetry_files.add(path.relative_to(clone).as_posix())
    for name in env_names:
        if re.search(r"(?i)(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH)", name):
            credential_names.add(name)

    network = line_samples(files, clone, NETWORK_PATTERNS)
    filesystem = line_samples(files, clone, FILESYSTEM_PATTERNS)
    destructive = line_samples(files, clone, DESTRUCTIVE_PATTERNS)
    prompt_risks = line_samples(
        [(path, text) for path, text in files if path.suffix.lower() in {".md", ".mdx", ".txt"}],
        clone,
        PROMPT_PATTERNS,
    )
    tests = sorted({
        path.relative_to(clone).as_posix() for path, _ in files
        if any(part.lower() in {"test", "tests", "__tests__"} for part in path.parts)
        or path.name.lower().startswith("test_")
        or path.name.lower().endswith((".test.ts", ".test.js", ".spec.ts", ".spec.js"))
    })
    docs = sorted({
        path.relative_to(clone).as_posix() for path, _ in files
        if path.name.lower() in {"readme.md", "architecture.md", "security.md", "contributing.md"}
        or "docs" in path.parts
    })
    policy = SOURCE_POLICY[source_id]
    compatibility = dict(COMPATIBILITY[policy["classification"]])
    compatibility.pop("adapter", None)
    adapter = COMPATIBILITY[policy["classification"]]["adapter"]
    if policy["decision"] in {"BLOCKED", "QUARANTINED", "REJECTED"}:
        compatibility = {
            "chatgpt": "REJECTED",
            "codex": "REJECTED",
            "claude": "REJECTED",
            "antigravity": "REJECTED",
            "antigravity_cli": "REJECTED",
        }
        adapter = "None; the audited source is retained as evidence only."
    generated_behavior = (
        "NONDETERMINISTIC_EXTERNAL_MODEL" if credential_names or source_id in {"aider", "context7"}
        else "DETERMINISTIC_WITH_PINNED_INPUTS" if source_id in {"repomix", "graphify", "code-review-graph"}
        else "INSTRUCTION_OR_WORKFLOW_DEPENDENT"
    )

    checksums = {}
    important = [
        path for path, _ in files
        if path.name in {"SKILL.md", "package.json", "pyproject.toml", ".mcp.json", "server.json", "plugin.json", "hooks.json"}
        or path in manifests or path in lock_files or re.match(r"(?i)^(LICENSE|NOTICE|COPYING)", path.name)
    ]
    for path in sorted(set(important))[:500]:
        checksums[path.relative_to(clone).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not checksums:
        for path in sorted(path for path in clone.iterdir() if path.is_file())[:10]:
            checksums[path.relative_to(clone).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()

    installation_methods = []
    if any(path.name == "package.json" for path in manifests):
        installation_methods.append("Node package manager; lifecycle scripts were not executed")
    if any(path.name == "pyproject.toml" for path in manifests):
        installation_methods.append("Python package/tool manager; build backend and installers were not executed")
    if any(path.name in {".mcp.json", "server.json"} for path, _ in files):
        installation_methods.append("Client-specific MCP configuration")
    if any(path.name == "SKILL.md" for path, _ in files):
        installation_methods.append("Agent Skill directory or plugin packaging")

    return {
        "source_id": source_id,
        "source_url": url,
        "resolved_url": resolved,
        "owner": first["owner"],
        "repository": first["repository"],
        "catalog_entry_count": len(rows),
        "catalog_subdirectories": subdirectories,
        "default_branch": metadata.get("default_branch") or branch,
        "clone_branch": branch,
        "commit_sha": commit,
        "catalog_snapshot_sha": first["repository_commit"],
        "latest_release_or_tag": metadata.get("latest_release"),
        "last_meaningful_update": last_commit,
        "license": detect_license(clone),
        "maintainer": {
            "owner": metadata.get("owner") or first["owner"],
            "owner_type": metadata.get("owner_type"),
            "archived": metadata.get("archived"),
            "metadata_status": metadata.get("status"),
        },
        "suspicious_ownership_changes": {
            "status": "NOT_VERIFIED",
            "reason": "A shallow static audit cannot establish ownership-transfer history; human review of repository events is required.",
        },
        "component_inventory": component_inventory(clone, subdirectories),
        "package_manifests": parsed_manifests,
        "lock_files": [path.relative_to(clone).as_posix() for path in lock_files],
        "installation_methods": installation_methods,
        "dependencies": {
            "declared_count_across_manifests": dependency_count,
            "samples": sorted(dependency_samples)[:60],
            "unpinned_review": "See package manifests and lock-file list; ranges and missing locks require per-package review.",
        },
        "executable_scripts": {"count": len(executable), "samples": executable[:60]},
        "package_lifecycle_scripts": lifecycle,
        "git_hooks": git_hooks[:100],
        "agent_hooks": agent_hooks[:100],
        "network_behavior": network,
        "filesystem_access": filesystem,
        "mcp_server_definitions": mcp_defs[:100],
        "tool_permission_definitions": permission_files[:100],
        "environment_variables": sorted(env_names),
        "credential_requirements": sorted(credential_names),
        "telemetry": {
            "status": "PRESENT_OR_DOCUMENTED" if telemetry_files else "NOT_DETECTED",
            "files": sorted(telemetry_files)[:100],
        },
        "external_services": sorted(urls)[:100],
        "destructive_command_risks": destructive,
        "prompt_injection_risks": prompt_risks,
        "generated_code_determinism": generated_behavior,
        "tests": {"present": bool(tests), "count": len(tests), "samples": tests[:60]},
        "documentation_matches_implementation": {
            "status": "PARTIALLY_VERIFIED",
            "reason": "Documentation, manifests, implementation, and test presence were compared statically; runtime claims were not executed.",
            "documentation_samples": docs[:40],
        },
        "primary_classification": policy["classification"],
        "compatibility": compatibility,
        "required_adapter": adapter,
        "risk_level": policy["risk"],
        "recommendation": policy["recommendation"],
        "decision_status": policy["decision"],
        "enabled_by_default": False,
        "scan": {
            "text_files_inspected": len(files),
            "truncated": truncated,
            "file_checksums": checksums,
        },
    }


def build(refresh: bool) -> dict[str, Any]:
    if not CATALOG.is_file():
        raise FileNotFoundError("reconstructed catalog evidence is missing")
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in data["entries"]:
        grouped[row["normalized_source_id"]].append(row)
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git is not installed")
    if refresh and TEMP_ROOT.exists():
        # Refresh means fresh ignored clones. Deletion is delegated to the exact safe cleanup script.
        cleanup = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "agent-clean-temp.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if cleanup.returncode:
            raise RuntimeError(cleanup.stderr or cleanup.stdout)
    sources = []
    failures = []
    for source_id in sorted(grouped):
        try:
            sources.append(audit_source(git, source_id, grouped[source_id]))
            print(f"audited {source_id}", file=sys.stderr)
        except Exception as exc:  # Continue by design; record source-level block.
            first = grouped[source_id][0]
            policy = SOURCE_POLICY[source_id]
            failures.append({"source_id": source_id, "reason": str(exc)})
            sources.append({
                "source_id": source_id,
                "source_url": first["repository_url"],
                "resolved_url": None,
                "owner": first["owner"],
                "repository": first["repository"],
                "catalog_entry_count": len(grouped[source_id]),
                "catalog_subdirectories": sorted({row["subdirectory"] for row in grouped[source_id]}),
                "commit_sha": first.get("repository_commit"),
                "catalog_snapshot_sha": first.get("repository_commit"),
                "license": {"spdx": "UNKNOWN", "copying_permitted": False, "modification_permitted": False, "redistribution_permitted": False},
                "primary_classification": "BLOCKED",
                "compatibility": {platform: "REJECTED" for platform in ("chatgpt", "codex", "claude", "antigravity", "antigravity_cli")},
                "required_adapter": "None until source audit succeeds.",
                "risk_level": "UNKNOWN",
                "recommendation": f"BLOCKED: {exc}",
                "decision_status": "BLOCKED",
                "enabled_by_default": False,
                "scan": {"text_files_inspected": 0, "truncated": False, "file_checksums": {}},
            })
    return {
        "schema_version": 1,
        "audit_date": AUDIT_DATE,
        "audit_tool_version": TOOL_VERSION,
        "mode": "FULL_AUDIT_AND_IMPLEMENTATION",
        "safety": {
            "source_code_executed": False,
            "lifecycle_scripts_executed": False,
            "hooks_activated": False,
            "mcp_servers_activated": False,
            "clone_mode": "depth=1, blob-filtered, non-recursive submodules, hooks path disabled",
        },
        "catalog_entries": len(data["entries"]),
        "unique_sources": len(grouped),
        "failures": failures,
        "sources": sources,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Validate existing evidence without network or writes.")
    mode.add_argument("--dry-run", action="store_true", help="List planned source audits without cloning.")
    mode.add_argument("--refresh", action="store_true", help="Discard only isolated clones and perform fresh audits.")
    args = parser.parse_args()
    if args.check:
        if not OUTPUT.is_file():
            print("ERROR: source audit evidence is missing", file=sys.stderr)
            return 1
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
        errors = []
        if data.get("catalog_entries") != 69:
            errors.append("source audit does not cover 69 catalog entries")
        if data.get("unique_sources") != 10 or len(data.get("sources", [])) != 10:
            errors.append("source audit does not cover 10 unique sources")
        for source in data.get("sources", []):
            if not source.get("commit_sha"):
                errors.append(f"{source.get('source_id')}: missing commit SHA")
            if source.get("decision_status") != "BLOCKED" and not source.get("scan", {}).get("file_checksums"):
                errors.append(f"{source.get('source_id')}: no audited file checksums")
        for error in errors:
            print(f"ERROR: {error}")
        if not errors:
            print("Source audit evidence covers 69 catalog entries and 10 sources")
        return 1 if errors else 0
    if args.dry_run:
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
        for source in sorted({row["repository_url"] for row in data["entries"]}):
            print(f"would shallow-clone and statically inspect {source}")
        return 0
    try:
        result = build(args.refresh)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT.relative_to(ROOT).as_posix()}")
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
