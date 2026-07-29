#!/usr/bin/env python3
"""Check or explicitly provision the audited Graphify CLI project-locally.

This script is never invoked by a package lifecycle hook. Installation requires
the caller to pass --install and is confined to .tools/graphify/venv.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_ROOT = (ROOT / ".tools" / "graphify").resolve()
VENV_ROOT = TOOL_ROOT / "venv"
PACKAGE = "graphifyy"
VERSION = "0.9.27"
REQUIREMENTS = ROOT / "agent-platform" / "tooling" / "graphify-requirements.txt"


def project_executable() -> Path:
    relative = Path("Scripts/graphify.exe") if os.name == "nt" else Path("bin/graphify")
    return VENV_ROOT / relative


def project_python() -> Path:
    relative = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    return VENV_ROOT / relative


def detected_executable() -> str | None:
    local = project_executable()
    if local.is_file():
        return str(local)
    return shutil.which("graphify")


def read_version(executable: str) -> str | None:
    result = subprocess.run(
        [executable, "--version"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    if result.returncode:
        return None
    output = (result.stdout or result.stderr).strip()
    return output.rsplit(" ", 1)[-1] if output else None


def print_plan() -> None:
    print(f"Would create project-local environment: {VENV_ROOT}")
    print(f"Would install exact audited pins from: {REQUIREMENTS}")
    print(f"Would require the direct package pin: {PACKAGE}=={VERSION}")
    print("Would not install hooks, MCP servers, or global agent configuration.")


def install() -> int:
    if TOOL_ROOT != (ROOT / ".tools" / "graphify").resolve() or ROOT not in TOOL_ROOT.parents:
        print("ERROR: unsafe project-local Graphify target", file=sys.stderr)
        return 2
    if not REQUIREMENTS.is_file():
        print("ERROR: audited Graphify requirements lock is missing", file=sys.stderr)
        return 2
    pins = [
        line.strip()
        for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if f"{PACKAGE}=={VERSION}" not in pins or any(line.count("==") != 1 for line in pins):
        print("ERROR: Graphify requirements must contain exact audited pins", file=sys.stderr)
        return 2
    TOOL_ROOT.mkdir(parents=True, exist_ok=True)
    if not project_python().is_file():
        venv.EnvBuilder(with_pip=True, clear=False, symlinks=False).create(VENV_ROOT)

    environment = os.environ.copy()
    environment.update(
        {
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INPUT": "1",
            "PYTHONNOUSERSITE": "1",
        }
    )
    command = [
        str(project_python()),
        "-m",
        "pip",
        "install",
        "--no-input",
        "--no-cache-dir",
        "--only-binary=:all:",
        "--requirement",
        str(REQUIREMENTS),
    ]
    result = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    if result.returncode:
        print("ERROR: project-local Graphify installation failed", file=sys.stderr)
        return result.returncode
    version = read_version(str(project_executable()))
    if version != VERSION:
        print(
            f"ERROR: installed Graphify version {version or 'UNKNOWN'}; expected {VERSION}",
            file=sys.stderr,
        )
        return 1
    print(f"PASS Graphify {version}: {project_executable()}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Check the pinned CLI without changing files.")
    mode.add_argument("--dry-run", action="store_true", help="Show the project-local install plan.")
    mode.add_argument("--install", action="store_true", help="Explicitly install the pinned CLI under .tools/.")
    args = parser.parse_args()

    if args.dry_run:
        print_plan()
        return 0
    executable = detected_executable()
    if executable:
        version = read_version(executable)
        if version == VERSION:
            print(f"PASS Graphify {version}: {executable}")
            return 0
        if not args.install:
            print(
                f"ERROR: Graphify {version or 'UNKNOWN'} found; audited version is {VERSION}",
                file=sys.stderr,
            )
            return 1
    if args.install:
        return install()
    print(
        "MISSING Graphify. Run `python scripts/bootstrap-graphify.py --dry-run`, "
        "then explicitly opt in with `--install`.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
