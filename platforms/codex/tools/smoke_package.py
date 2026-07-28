#!/usr/bin/env python3
"""Smoke-test a packaged Solo Suite ZIP from disposable external paths."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile


EXPECTED_FOLDER = "solo-suite-codex-v1.0.27"
HISTORICAL_SOURCE_NAME = "solo-suite-plugin-v1.0.26.zip"
HISTORICAL_SOURCE_SHA256 = (
    "b691905f8ade4c2fb7e0084a46f537c9be8d7b2bf0f4d160c38c5e930aed1d43"
)
CANONICAL_SOURCE_NAME = (
    "solo-suite-plugin-v1.0.27-codex-v1.0.27-parity-source.zip"
)
CANONICAL_SOURCE_SHA256 = (
    "7dde7bbe44e7534e3f1890ddb1c5feba5554d60127c4dd7ef2095b31cafb03aa"
)
CANONICAL_SOURCE_FOLDER = "solo-suite-plugin-v1.0.27"
CANONICAL_CAPABILITIES_SHA256 = (
    "3f03cfe3cb25cff447dcfcba028df832288e9212c0fe816b9f702b7a1038f5ec"
)
WORKING_TREE_CAPABILITIES_SHA256 = (
    "7d0fd32bbb6de7f357f1642595c729c2e8b48f39c96184c4c76ce0f046a6b7bd"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(
    command: list[str],
    cwd: Path,
    accepted_returncodes: tuple[int, ...] = (0,),
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=180,
    )
    if result.returncode not in accepted_returncodes:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"{result.stdout}{result.stderr}"
        )
    return result


def safe_members(archive: zipfile.ZipFile) -> list[str]:
    names = archive.namelist()
    if not names:
        raise RuntimeError("package is empty")
    top = {PurePosixPath(name).parts[0] for name in names}
    if top != {EXPECTED_FOLDER}:
        raise RuntimeError(f"package must contain exactly {EXPECTED_FOLDER!r}: {top}")
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "" in path.parts:
            raise RuntimeError(f"unsafe archive member: {name}")
        if any(part in {".venv", "__pycache__", ".docx-qa", ".git"} for part in path.parts):
            raise RuntimeError(f"development artifact leaked into package: {name}")
    return names


def extract_canonical_source(archive_path: Path, destination: Path) -> Path:
    if not archive_path.is_file():
        raise RuntimeError(f"canonical source archive does not exist: {archive_path}")
    if sha256(archive_path) != CANONICAL_SOURCE_SHA256:
        raise RuntimeError("canonical source archive digest does not match the release pin")
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if not members:
            raise RuntimeError("canonical source archive is empty")
        seen: set[str] = set()
        for info in members:
            name = info.filename
            relative = PurePosixPath(name)
            if (
                relative.is_absolute()
                or "\\" in name
                or not relative.parts
                or any(part in {"", ".", ".."} for part in relative.parts)
                or relative.parts[0] != CANONICAL_SOURCE_FOLDER
            ):
                raise RuntimeError(f"unsafe canonical source member: {name!r}")
            key = relative.as_posix()
            if key in seen:
                raise RuntimeError(f"duplicate canonical source member: {name!r}")
            seen.add(key)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise RuntimeError(f"canonical source contains a symbolic link: {name}")
            target = destination.joinpath(*relative.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
    source = destination / CANONICAL_SOURCE_FOLDER
    manifest = source / "parity/capabilities.json"
    if not manifest.is_file() or sha256(manifest) != CANONICAL_CAPABILITIES_SHA256:
        raise RuntimeError("canonical source capabilities manifest is invalid")
    metadata = json.loads((source / "PARITY-SOURCE.json").read_text(encoding="utf-8"))
    if (
        metadata.get("target_version") != "1.0.27"
        or metadata.get("capabilities_sha256") != CANONICAL_CAPABILITIES_SHA256
    ):
        raise RuntimeError("canonical source provenance is invalid")
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--canonical-source-archive", type=Path, required=True)
    args = parser.parse_args()
    archive_path = args.archive.resolve()
    canonical_source_path = args.canonical_source_archive.resolve()
    adjacent = archive_path.with_suffix(archive_path.suffix + ".sha256")
    if adjacent.is_file():
        expected = adjacent.read_text(encoding="utf-8").split()[0]
        if sha256(archive_path) != expected:
            raise RuntimeError("adjacent ZIP SHA-256 does not match")
    with tempfile.TemporaryDirectory(prefix="solo-suite-package-") as temp:
        temp_root = Path(temp)
        extract_root = temp_root / "installed"
        source_extract_root = temp_root / "canonical-source"
        outside = temp_root / "disposable-project"
        outside.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            names = safe_members(archive)
            archive.extractall(extract_root)
        suite = extract_root / EXPECTED_FOLDER
        nested_release_assets = [
            name for name in names
            if name.startswith(f"{EXPECTED_FOLDER}/parity/artifacts/")
            and (name.endswith(".zip") or name.endswith(".sha256"))
        ]
        if nested_release_assets:
            raise RuntimeError(
                "install ZIP must not duplicate separately attested parity assets"
            )
        canonical_source = extract_canonical_source(
            canonical_source_path, source_extract_root
        )
        checksum_path = suite / "RELEASE-CHECKSUMS.txt"
        declared = {}
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            digest, relative = line.split("  ", 1)
            target = (suite / relative).resolve()
            try:
                target.relative_to(suite.resolve())
            except ValueError as exc:
                raise RuntimeError(f"checksum path escapes package: {relative}") from exc
            if not target.is_file() or sha256(target) != digest:
                raise RuntimeError(f"content checksum mismatch: {relative}")
            declared[relative] = digest
        actual = {
            path.relative_to(suite).as_posix()
            for path in suite.rglob("*")
            if path.is_file() and path != checksum_path
        }
        if set(declared) != actual:
            raise RuntimeError(
                "content checksum inventory mismatch: "
                f"missing={sorted(actual-set(declared))}, extra={sorted(set(declared)-actual)}"
            )
        release = json.loads((suite / "RELEASE.json").read_text(encoding="utf-8"))
        if release["version"] != "1.0.27":
            raise RuntimeError("packaged release version mismatch")
        if release.get("source_archive") != CANONICAL_SOURCE_NAME:
            raise RuntimeError("release does not identify the canonical parity source")
        if release.get("source_archive_sha256") != CANONICAL_SOURCE_SHA256:
            raise RuntimeError("canonical source archive digest is not pinned")
        if release.get("source_archive_required_for_build") is not False:
            raise RuntimeError("canonical source is incorrectly marked as a build input")
        if release.get("source_archive_required_for_validation") is not True:
            raise RuntimeError("canonical source is not required for validation")
        if release.get("historical_source_archive_sha256") != HISTORICAL_SOURCE_SHA256:
            raise RuntimeError("historical source reference digest is not pinned")

        provenance = json.loads(
            (suite / "RELEASE-PROVENANCE.json").read_text(encoding="utf-8")
        )
        if provenance.get("record_kind") != "generated-build-provenance":
            raise RuntimeError("package contains unbound or unknown provenance")
        source_commands = provenance.get("source_checkout_validation_commands")
        package_commands = provenance.get("installed_package_validation_commands")
        if not isinstance(source_commands, list) or not isinstance(package_commands, list):
            raise RuntimeError("package provenance does not separate validation profiles")
        if not any("unittest discover" in command for command in source_commands):
            raise RuntimeError("source-checkout test command is missing from provenance")
        if any("unittest discover" in command for command in package_commands):
            raise RuntimeError("installed-package commands incorrectly require source tests")
        if not any("smoke_package.py" in command for command in package_commands):
            raise RuntimeError("installed-package smoke command is missing from provenance")
        if provenance.get("validation_commands") != package_commands:
            raise RuntimeError("legacy validation commands are not package-safe")
        if provenance.get("build_type") != "reproducible-zip-from-git-tree":
            raise RuntimeError("package provenance does not identify the reproducible build")
        materials = provenance.get("materials", [])
        if not isinstance(materials, list):
            raise RuntimeError("package provenance materials must be a list")
        canonical = next(
            (
                item for item in materials
                if isinstance(item, dict)
                and item.get("uri") == CANONICAL_SOURCE_NAME
            ),
            None,
        )
        canonical_digest = canonical.get("digest") if canonical else None
        if not (
            isinstance(canonical_digest, dict)
            and canonical_digest.get("sha256") == CANONICAL_SOURCE_SHA256
        ):
            raise RuntimeError("package provenance lacks the pinned canonical source")
        if canonical.get("required_for_validation") is not True:
            raise RuntimeError("canonical source is not a required validation material")
        historical = next(
            (
                item for item in materials
                if isinstance(item, dict)
                and item.get("uri") == HISTORICAL_SOURCE_NAME
            ),
            None,
        )
        historical_digest = historical.get("digest") if historical else None
        if not (
            isinstance(historical_digest, dict)
            and historical_digest.get("sha256") == HISTORICAL_SOURCE_SHA256
        ):
            raise RuntimeError("package provenance lacks the historical base reference")
        if provenance.get("validation_state") in {"validated", "ci"}:
            commit = provenance.get("source_git_commit", "")
            if not (
                isinstance(commit, str)
                and len(commit) in {40, 64}
                and all(character in "0123456789abcdef" for character in commit)
            ):
                raise RuntimeError("validated package lacks a full Git source commit")
            if provenance.get("source_git_dirty") is not False:
                raise RuntimeError("validated package provenance identifies a dirty source")
            git_materials = [
                item for item in materials
                if isinstance(item, dict)
                and isinstance(item.get("digest"), dict)
                and item["digest"].get("gitCommit") == commit
            ]
            if len(git_materials) != 1:
                raise RuntimeError("validated package lacks its Git material identity")

        readme = (suite / "README.md").read_text(encoding="utf-8")
        parity_readme = (suite / "parity/README.md").read_text(encoding="utf-8")
        if "Full contributor test suite (source checkout only)" not in readme:
            raise RuntimeError("README does not identify source-checkout-only tests")
        if "Extracted release package validation" not in readme:
            raise RuntimeError("README does not document installed-package validation")
        if "From the release root:" in readme:
            raise RuntimeError("README retains the ambiguous release-root validation claim")
        if "intentionally omits nested archives" not in parity_readme:
            raise RuntimeError("parity docs do not disclose the install-ZIP asset boundary")

        python = sys.executable
        package_capabilities = suite / "parity/capabilities.json"
        package_capabilities_digest = sha256(package_capabilities)
        if package_capabilities_digest == CANONICAL_CAPABILITIES_SHA256:
            parity = run(
                [
                    python,
                    str(canonical_source / "tools/parity.py"),
                    "check",
                    "--source",
                    str(canonical_source),
                    "--target",
                    str(suite),
                ],
                outside,
            )
        elif package_capabilities_digest == WORKING_TREE_CAPABILITIES_SHA256:
            parity = None
        else:
            raise RuntimeError(
                "installed package parity manifest is neither the historical "
                "canonical digest nor the declared working-tree digest"
            )
        run([python, str(suite / "tools/validate_plugins.py")], outside)
        self_check = suite / "plugins/solo/skills/suite-integrity/scripts/self_check.py"
        run([python, str(self_check), str(suite), "-"], outside)
        rooms = suite / "plugins/ai/skills/agent-room-templates/scripts/validate_rooms.py"
        run([python, str(rooms), "--suite", str(suite)], outside)

        cache_plugin = temp_root / "codex-cache/site-doctor/1.0.27"
        shutil.copytree(suite / "plugins/site-doctor", cache_plugin)
        run([python, str(self_check), str(cache_plugin), "-"], outside)

        fixture = outside / "package.json"
        fixture.write_text('{"dependencies":{"demo":"1.2.3"}}\n', encoding="utf-8")
        launcher = cache_plugin / "scripts/run_helper.py"
        helper = run(
            [python, str(launcher), "dependency-audit/check-deps", str(outside)],
            outside,
            accepted_returncodes=(3,),
        )
        if "Node / npm" not in helper.stdout:
            raise RuntimeError("installed helper did not inspect disposable project")
        print(f"PASS one top-level folder with {len(names)} file(s)")
        print("PASS adjacent ZIP digest and internal content checksums")
        if parity is not None:
            print(parity.stdout.strip())
        else:
            print(
                "PASS historical canonical archive attested; "
                "working-tree parity was validated before packaging"
            )
        print("PASS pinned canonical Claude source archive")
        print("PASS source-checkout and installed-package validation profiles")
        print("PASS source-checkout and installed-cache self-checks")
        print("PASS helper executed from disposable external working directory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
