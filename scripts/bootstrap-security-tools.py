#!/usr/bin/env python3
"""Provision audited security scanners under .tools/security.

Installation is explicit, project-local, hash-verified, and never connected to
package lifecycle hooks. Native archives are inspected before one executable is
extracted. The Python scanner environment is fully hashed for Windows x86-64
with Python 3.12 and fails closed on other Python targets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import venv
import zipfile
from pathlib import Path, PurePosixPath

from agent_platform_common import sha256_text_lf


ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = (ROOT / ".tools" / "security").resolve()
BIN_ROOT = TOOLS_ROOT / "bin"
PYTHON_VENV = TOOLS_ROOT / "python"
LOCK_PATH = ROOT / "agent-platform" / "tooling" / "security-tools.lock.json"
TEMP_ROOT = ROOT / ".tmp"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_lock() -> dict[str, object]:
    data = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    requirements = ROOT / str(data["python"]["requirements"])
    expected = str(data["python"]["requirements_sha256"])
    if not requirements.is_file() or sha256_text_lf(requirements) != expected:
        raise RuntimeError("security Python requirements lock is missing or has drifted")
    return data


def platform_key() -> str:
    system = platform.system().lower()
    system = "darwin" if system == "darwin" else system
    machine = platform.machine().lower()
    architecture = {
        "amd64": "amd64",
        "x86_64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }.get(machine)
    if system not in {"windows", "linux", "darwin"} or not architecture:
        raise RuntimeError(f"unsupported native-tool platform: {system}-{machine}")
    return f"{system}-{architecture}"


def python_executable() -> Path:
    relative = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    return PYTHON_VENV / relative


def python_tool(name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    relative = Path("Scripts") if os.name == "nt" else Path("bin")
    return PYTHON_VENV / relative / f"{name}{suffix}"


def native_tool(name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return BIN_ROOT / f"{name}{suffix}"


def run_version(path: Path, arguments: list[str], expected: str) -> tuple[bool, str]:
    if not path.is_file():
        return False, "MISSING"
    result = subprocess.run(
        [str(path), *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    return result.returncode == 0 and expected in output, output.splitlines()[0] if output else "UNKNOWN"


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "EC-Solo-Suite-Security-Bootstrap/1"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def safe_member(name: str) -> bool:
    member = PurePosixPath(name.replace("\\", "/"))
    return not member.is_absolute() and ".." not in member.parts


def extract_executable(archive: Path, executable: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload: bytes | None = None
    if archive.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                if not safe_member(member.filename):
                    raise RuntimeError(f"unsafe archive path: {member.filename}")
                unix_mode = (member.external_attr >> 16) & 0o170000
                if unix_mode == 0o120000:
                    raise RuntimeError(f"archive symlink rejected: {member.filename}")
                if PurePosixPath(member.filename).name.lower() == executable.lower():
                    payload = bundle.read(member)
    else:
        with tarfile.open(archive, mode="r:gz") as bundle:
            for member in bundle.getmembers():
                if not safe_member(member.name) or member.issym() or member.islnk():
                    raise RuntimeError(f"unsafe archive member: {member.name}")
                if PurePosixPath(member.name).name.lower() == executable.lower():
                    extracted = bundle.extractfile(member)
                    payload = extracted.read() if extracted else None
    if payload is None:
        raise RuntimeError(f"{executable} was not found in {archive.name}")
    destination.write_bytes(payload)
    if os.name != "nt":
        destination.chmod(0o755)


def install_native(name: str, item: dict[str, object], target_key: str, temp: Path) -> None:
    assets = item["assets"]
    if target_key not in assets:
        raise RuntimeError(f"{name} has no audited asset for {target_key}")
    asset = assets[target_key]
    filename = str(asset["name"])
    version = str(item["version"])
    archive = temp / filename
    url = f"https://github.com/{'gitleaks/gitleaks' if name == 'gitleaks' else 'aquasecurity/trivy'}/releases/download/v{version}/{filename}"
    download(url, archive)
    actual = sha256(archive)
    if actual != str(asset["sha256"]):
        raise RuntimeError(f"{name} archive hash mismatch: {actual}")
    executable_name = f"{name}.exe" if target_key.startswith("windows-") else name
    extract_executable(archive, executable_name, native_tool(name))


def install_python(data: dict[str, object]) -> None:
    expected_lock = str(data["python"]["platform_lock"])
    actual_lock = f"{platform_key()}-python-{sys.version_info.major}.{sys.version_info.minor}"
    if actual_lock != expected_lock:
        raise RuntimeError(
            f"fully hashed Python scanner lock targets {expected_lock}; current target is {actual_lock}"
        )
    if not python_executable().is_file():
        PYTHON_VENV.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True, clear=False, symlinks=False).create(PYTHON_VENV)
    requirements = ROOT / str(data["python"]["requirements"])
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
        str(python_executable()),
        "-m",
        "pip",
        "install",
        "--no-input",
        "--no-cache-dir",
        "--only-binary=:all:",
        "--require-hashes",
        "--no-deps",
        "--requirement",
        str(requirements),
    ]
    result = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    if result.returncode:
        raise RuntimeError(f"hashed Python scanner installation exited {result.returncode}")


def check(data: dict[str, object]) -> int:
    checks = [
        ("semgrep", python_tool("semgrep"), ["--version"], str(data["python"]["packages"]["semgrep"]["version"])),
        (
            "pip-audit",
            python_tool("pip-audit"),
            ["--version"],
            str(data["python"]["packages"]["pip-audit"]["version"]),
        ),
        ("gitleaks", native_tool("gitleaks"), ["version"], str(data["native_tools"]["gitleaks"]["version"])),
        ("trivy", native_tool("trivy"), ["--version"], str(data["native_tools"]["trivy"]["version"])),
    ]
    failed = False
    for name, path, arguments, expected in checks:
        passed, output = run_version(path, arguments, expected)
        print(f"{'PASS' if passed else 'MISSING'} {name} {expected}: {path} ({output})")
        failed = failed or not passed
    return 1 if failed else 0


def print_plan(data: dict[str, object]) -> None:
    target = platform_key()
    print(f"Target: {target}; install root: {TOOLS_ROOT}")
    print(
        "Python: Semgrep "
        f"{data['python']['packages']['semgrep']['version']} and pip-audit "
        f"{data['python']['packages']['pip-audit']['version']} from the fully hashed wheel lock."
    )
    for name in ("gitleaks", "trivy"):
        item = data["native_tools"][name]
        asset = item["assets"].get(target)
        print(f"Native: {name} {item['version']} -> {asset['name'] if asset else 'UNSUPPORTED'}")
    print("No hooks, MCP servers, login, container socket, global install, or lifecycle script will be used.")


def install(data: dict[str, object]) -> int:
    expected = (ROOT / ".tools" / "security").resolve()
    if TOOLS_ROOT != expected or ROOT not in TOOLS_ROOT.parents:
        raise RuntimeError("unsafe security-tool installation target")
    target = platform_key()
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    install_python(data)
    with tempfile.TemporaryDirectory(prefix="security-tool-bootstrap-", dir=TEMP_ROOT) as directory:
        temp = Path(directory)
        for name in ("gitleaks", "trivy"):
            install_native(name, data["native_tools"][name], target, temp)
    return check(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Verify project-local scanner versions.")
    mode.add_argument("--dry-run", action="store_true", help="Show the audited installation plan.")
    mode.add_argument("--install", action="store_true", help="Install scanners under .tools/security.")
    args = parser.parse_args()
    try:
        data = load_lock()
        if args.dry_run:
            print_plan(data)
            return 0
        if args.install:
            return install(data)
        return check(data)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
