#!/usr/bin/env python3
"""Generate release metadata and a reproducible one-folder ZIP.

Validated builds are created from the committed Git tree in a disposable staging
directory.  The working tree is never rewritten, and a validated/CI package is
refused unless the repository is clean and has a resolvable HEAD commit.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Mapping, Optional
import unicodedata
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.27"
FOLDER = f"solo-suite-codex-v{VERSION}"
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
    "f41023ad95262dfe5585d9d64873c5281dd4b186ae83d025bb0b9ef00efdb1fa"
)
STRICT_VALIDATION_STATES = {"validated", "ci"}
VALIDATION_STATES = {"pending", "preflight", *STRICT_VALIDATION_STATES}
EXCLUDED_PARTS = {
    ".git", ".venv", ".docx-qa", ".solo", "dist", "__pycache__", "htmlcov",
}
EXCLUDED_PREFIXES = {
    "artifacts/runs",
    "worktrees/runs",
}
EXCLUDED_NAMES = {".coverage", "coverage.xml"}
COMMIT_PATTERN = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
DEPENDENCY_LICENSES = {
    "pyyaml": "MIT",
    "coverage": "Apache-2.0",
    "jsonschema": "MIT",
    "attrs": "MIT",
    "jsonschema-specifications": "MIT",
    "referencing": "MIT",
    "rpds-py": "MIT",
    "typing-extensions": "PSF-2.0",
    "pip": "MIT",
    "pip-audit": "Apache-2.0",
}
REQUIREMENT_INPUTS = {
    "requirements-dev.txt": "release-validation",
    "requirements-audit.txt": "vulnerability-audit",
}
REGULAR_GIT_MODES = {"100644", "100755"}
WINDOWS_RESERVED_NAMES = {
    "aux", "con", "nul", "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


@dataclass(frozen=True)
class BuildContext:
    """Immutable source identity used by every generated release document."""

    commit: Optional[str]
    dirty: bool
    epoch: int
    timestamp: str
    zip_time: tuple[int, int, int, int, int, int]
    git_root: Optional[Path]


@dataclass(frozen=True)
class BuildResult:
    output: Path
    digest: str
    files: int
    context: BuildContext


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_text_lf(path: Path, content: str) -> None:
    """Write UTF-8 text with stable LF endings on every supported host."""

    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def dump_json(path: Path, payload: object) -> None:
    write_text_lf(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def git_environment() -> dict[str, str]:
    """Return a Git environment immune to repository-local replacement refs."""

    environ = os.environ.copy()
    environ["GIT_NO_REPLACE_OBJECTS"] = "1"
    return environ


def run_git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=git_environment(),
            timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        if check:
            raise RuntimeError(f"unable to inspect Git source: {exc}") from exc
        return subprocess.CompletedProcess(["git"], 1, "", str(exc))
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Git command failed: {detail or arguments}")
    return result


def _source_epoch(root: Path, environ: Mapping[str, str], commit: Optional[str]) -> int:
    supplied = environ.get("SOURCE_DATE_EPOCH")
    if supplied is not None:
        try:
            epoch = int(supplied, 10)
        except ValueError as exc:
            raise RuntimeError("SOURCE_DATE_EPOCH must be an integer Unix timestamp") from exc
        if epoch < 0:
            raise RuntimeError("SOURCE_DATE_EPOCH must not be negative")
        return epoch
    if commit:
        value = run_git(root, "show", "-s", "--format=%ct", commit).stdout.strip()
        try:
            return int(value, 10)
        except ValueError as exc:
            raise RuntimeError("Git HEAD did not provide a valid commit timestamp") from exc
    raise RuntimeError(
        "a deterministic timestamp requires Git HEAD or SOURCE_DATE_EPOCH"
    )


def _time_values(epoch: int) -> tuple[str, tuple[int, int, int, int, int, int]]:
    try:
        instant = datetime.fromtimestamp(epoch, timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise RuntimeError("source timestamp is outside the supported range") from exc
    if not 1980 <= instant.year <= 2107:
        raise RuntimeError("source timestamp must be between 1980 and 2107 for ZIP")
    timestamp = instant.isoformat(timespec="seconds").replace("+00:00", "Z")
    return timestamp, (
        instant.year, instant.month, instant.day,
        instant.hour, instant.minute, instant.second - (instant.second % 2),
    )


def resolve_build_context(
    root: Path,
    validation_state: str,
    environ: Optional[Mapping[str, str]] = None,
) -> BuildContext:
    """Resolve Git identity and fail closed for publication-grade builds."""

    if validation_state not in VALIDATION_STATES:
        raise RuntimeError(
            f"unsupported validation state {validation_state!r}; "
            f"expected one of {sorted(VALIDATION_STATES)}"
        )
    root = root.resolve()
    environ = os.environ if environ is None else environ
    probe = run_git(root, "rev-parse", "--show-toplevel", check=False)
    git_root: Optional[Path] = None
    commit: Optional[str] = None
    dirty = False
    if probe.returncode == 0:
        git_root = Path(probe.stdout.strip()).resolve()
        try:
            same_root = git_root.samefile(root)
        except OSError:
            same_root = git_root == root
        if not same_root:
            raise RuntimeError(
                f"release root must be the Git repository root: {git_root}"
            )
        commit_result = run_git(root, "rev-parse", "--verify", "HEAD", check=False)
        candidate = commit_result.stdout.strip().lower()
        if commit_result.returncode == 0 and COMMIT_PATTERN.fullmatch(candidate):
            commit = candidate
        status = run_git(
            root, "status", "--porcelain=v1", "--untracked-files=all", check=False
        )
        if status.returncode:
            raise RuntimeError("unable to determine whether the Git working tree is clean")
        dirty = bool(status.stdout.strip())

    if validation_state in STRICT_VALIDATION_STATES:
        if not git_root or not commit:
            raise RuntimeError(
                f"{validation_state} release requires a Git checkout with a HEAD commit"
            )
        if dirty:
            raise RuntimeError(
                f"{validation_state} release requires a clean Git working tree"
            )

    epoch = _source_epoch(root, environ, commit)
    timestamp, zip_time = _time_values(epoch)
    return BuildContext(commit, dirty, epoch, timestamp, zip_time, git_root)


def verify_historical_archive(path: Path) -> None:
    """Optionally verify the legacy input without making it a build dependency."""

    path = path.resolve()
    if not path.is_file():
        raise RuntimeError(f"historical source archive does not exist: {path}")
    actual = sha256(path)
    if actual != HISTORICAL_SOURCE_SHA256:
        raise RuntimeError(
            "historical source archive digest mismatch: "
            f"expected {HISTORICAL_SOURCE_SHA256}, got {actual}"
        )


def _extract_canonical_source(path: Path, destination: Path) -> Path:
    """Extract the pinned source archive without trusting ZIP member paths."""

    with zipfile.ZipFile(path) as archive:
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
                raise RuntimeError(f"unsafe canonical source archive member: {name!r}")
            key = relative.as_posix()
            if key in seen:
                raise RuntimeError(f"duplicate canonical source archive member: {name!r}")
            seen.add(key)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise RuntimeError(
                    f"canonical source archive contains a symbolic link: {name}"
                )
            target = destination.joinpath(*relative.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
    source = destination / CANONICAL_SOURCE_FOLDER
    if not source.is_dir():
        raise RuntimeError(
            f"canonical source archive lacks {CANONICAL_SOURCE_FOLDER!r}"
        )
    return source


def verify_canonical_source_archive(path: Path, target: Path | None = ROOT) -> None:
    """Verify the historical source artifact and reconcile target parity modes."""

    path = path.resolve()
    if target is not None:
        target = target.resolve()
    if not path.is_file():
        raise RuntimeError(f"canonical source archive does not exist: {path}")
    actual = sha256(path)
    if actual != CANONICAL_SOURCE_SHA256:
        raise RuntimeError(
            "canonical source archive digest mismatch: "
            f"expected {CANONICAL_SOURCE_SHA256}, got {actual}"
        )
    try:
        with tempfile.TemporaryDirectory(prefix="solo-suite-parity-source-") as temp:
            source = _extract_canonical_source(path, Path(temp))
            manifest = source / "parity/capabilities.json"
            if not manifest.is_file() or sha256(manifest) != CANONICAL_CAPABILITIES_SHA256:
                raise RuntimeError(
                    "canonical source archive has an invalid capabilities manifest"
                )
            metadata = json.loads(
                (source / "PARITY-SOURCE.json").read_text(encoding="utf-8")
            )
            if (
                metadata.get("target_version") != VERSION
                or metadata.get("capabilities_sha256")
                != CANONICAL_CAPABILITIES_SHA256
            ):
                raise RuntimeError("canonical source provenance does not match this release")
            if target is not None:
                target_manifest = target / "parity/capabilities.json"
                target_digest = (
                    sha256(target_manifest) if target_manifest.is_file() else None
                )
                if target_digest == CANONICAL_CAPABILITIES_SHA256:
                    checker = source / "tools/parity.py"
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(checker),
                            "check",
                            "--source",
                            str(source),
                            "--target",
                            str(target),
                        ],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=180,
                    )
                    if result.returncode:
                        raise RuntimeError(
                            "canonical source/target parity check failed:\n"
                            f"{result.stdout}{result.stderr}"
                        )
                elif target_digest != WORKING_TREE_CAPABILITIES_SHA256:
                    raise RuntimeError(
                        "target parity manifest is neither the historical "
                        "canonical digest nor the declared working-tree digest"
                    )
    except (json.JSONDecodeError, KeyError, OSError, zipfile.BadZipFile) as exc:
        raise RuntimeError(f"invalid canonical source archive: {exc}") from exc


def counts(root: Path = ROOT) -> dict[str, int]:
    return {
        "plugins": len(list(root.glob("plugins/*/.codex-plugin/plugin.json"))),
        "skills": len(list(root.glob("plugins/*/skills/*/SKILL.md"))),
        "commands": len(
            json.loads((root / "command-map.json").read_text(encoding="utf-8"))
        ),
        "scripts": len([
            path for path in root.glob("plugins/**/*.py")
            if "__pycache__" not in path.parts
        ]),
    }


def requirements(root: Path = ROOT) -> list[tuple[str, str, str]]:
    """Read direct, exact validation-tool pins without resolving a new graph."""

    result: dict[str, tuple[str, str, set[str]]] = {}
    for filename, role in REQUIREMENT_INPUTS.items():
        path = root / filename
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s]+)", line)
            if match is None:
                raise RuntimeError(f"{filename} contains a non-exact pin: {line}")
            name, version = match.groups()
            normalized = name.lower().replace("_", "-")
            existing = result.get(normalized)
            if existing is not None and existing[1] != version:
                raise RuntimeError(
                    f"conflicting direct dependency pins for {normalized}: "
                    f"{existing[1]} and {version}"
                )
            if existing is None:
                result[normalized] = (name, version, {role})
            else:
                existing[2].add(role)
    return [
        (name, version, "+".join(sorted(roles)))
        for name, version, roles in (
            result[key] for key in sorted(result)
        )
    ]


def write_release(root: Path, validation_state: str) -> None:
    dump_json(root / "RELEASE.json", {
        "name": "solo-suite-codex",
        "version": VERSION,
        "previous_version": "1.0.12",
        "source_archive": CANONICAL_SOURCE_NAME,
        "source_archive_sha256": CANONICAL_SOURCE_SHA256,
        "source_archive_required_for_build": False,
        "source_archive_required_for_validation": True,
        "historical_source_archive": HISTORICAL_SOURCE_NAME,
        "historical_source_archive_sha256": HISTORICAL_SOURCE_SHA256,
        "counts": counts(root),
        "format": "codex-plugin-marketplace",
        "top_level_folder": FOLDER,
        "validation_state": validation_state,
    })


def write_sbom(root: Path, context: BuildContext) -> None:
    source_identity = context.commit or f"source-date-epoch-{context.epoch}"
    plugin_packages = []
    relationships = []
    for manifest_path in sorted(root.glob("plugins/*/.codex-plugin/plugin.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        spdx_id = "SPDXRef-Plugin-" + manifest["name"].replace("-", "-")
        plugin_packages.append({
            "SPDXID": spdx_id,
            "name": manifest["name"],
            "versionInfo": manifest["version"],
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": manifest.get("license", "NOASSERTION"),
            "licenseDeclared": manifest.get("license", "NOASSERTION"),
            "copyrightText": "Copyright 2026 Sakura Yukihira",
            "primaryPackagePurpose": "APPLICATION",
        })
        relationships.append({
            "spdxElementId": "SPDXRef-Package",
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": spdx_id,
        })
    dependency_packages = []
    for name, version, dependency_role in requirements(root):
        spdx_id = "SPDXRef-Python-" + re_safe(name)
        runtime = name.lower() == "pyyaml"
        normalized_name = name.lower().replace("_", "-")
        declared_license = DEPENDENCY_LICENSES.get(normalized_name, "NOASSERTION")
        comment = (
            "Runtime dependency of the structural self-check."
            if runtime else
            "Pinned vulnerability-audit tooling dependency."
            if "vulnerability-audit" in dependency_role else
            "Pinned development and release-validation dependency."
        )
        dependency_packages.append({
            "SPDXID": spdx_id,
            "name": name,
            "versionInfo": version,
            "downloadLocation": f"https://pypi.org/project/{name}/{version}/",
            "filesAnalyzed": False,
            "licenseConcluded": declared_license,
            "licenseDeclared": declared_license,
            "copyrightText": "NOASSERTION",
            "primaryPackagePurpose": "LIBRARY",
            "comment": comment,
        })
        relationships.append(
            {
                "spdxElementId": "SPDXRef-Package",
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": spdx_id,
            }
            if runtime else
            {
                "spdxElementId": spdx_id,
                "relationshipType": "DEV_DEPENDENCY_OF",
                "relatedSpdxElement": "SPDXRef-Package",
            }
        )
    dump_json(root / "SBOM.spdx.json", {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": FOLDER,
        "documentNamespace": f"urn:solo-suite:spdx:{VERSION}:{source_identity}",
        "creationInfo": {
            "created": context.timestamp,
            "creators": ["Tool: solo-suite/tools/package_release.py"],
        },
        "documentDescribes": ["SPDXRef-Package"],
        "packages": [{
            "SPDXID": "SPDXRef-Package",
            "name": "solo-suite-codex",
            "versionInfo": VERSION,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "MIT",
            "licenseDeclared": "MIT",
            "copyrightText": "Copyright 2026 Sakura Yukihira",
            "primaryPackagePurpose": "APPLICATION",
        }, *plugin_packages, *dependency_packages],
        "relationships": relationships,
    })


def re_safe(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value)


def write_provenance(
    root: Path, validation_state: str, context: BuildContext
) -> None:
    if validation_state in STRICT_VALIDATION_STATES and (
        not context.commit or context.dirty
    ):
        raise RuntimeError(
            "validated package provenance requires an exact clean Git commit"
        )
    source_commit = context.commit
    materials = [{
        "uri": CANONICAL_SOURCE_NAME,
        "digest": {"sha256": CANONICAL_SOURCE_SHA256},
        "role": "canonical-parity-source",
        "required_for_build": False,
        "required_for_validation": True,
    }, {
        "uri": HISTORICAL_SOURCE_NAME,
        "digest": {"sha256": HISTORICAL_SOURCE_SHA256},
        "role": "historical-source-reference",
        "required_for_build": False,
        "required_for_validation": False,
    }]
    if context.commit:
        materials.append({
            "uri": "git+source#HEAD",
            "digest": {"gitCommit": context.commit},
            "role": "release-source",
            "required_for_build": True,
            "required_for_validation": True,
        })
    dump_json(root / "RELEASE-PROVENANCE.json", {
        "schema": "solo-suite/release-provenance-v1",
        "record_kind": "generated-build-provenance",
        "subject": {"name": f"{FOLDER}.zip", "version": VERSION},
        "builder": {
            "id": "local-codex-workspace",
            "tool": "tools/package_release.py",
        },
        "build_type": (
            "reproducible-zip-from-git-tree"
            if context.commit and not context.dirty
            else "preflight-zip-from-working-tree"
        ),
        "build_timestamp": context.timestamp,
        "source_date_epoch": context.epoch,
        "materials": materials,
        "source_git_commit": source_commit,
        "source_git_dirty": context.dirty if context.git_root else None,
        "source_identity_note": (
            "Resolved from the clean committed Git tree."
            if context.commit and not context.dirty else
            "A Git commit is identified, but this preflight includes working-tree changes."
            if context.commit else
            "No Git commit is asserted for this non-publication preflight snapshot."
        ),
        "publisher": "Sakura Yukihira (Ayaya)",
        "validation_state": validation_state,
        "validation_commands": [
            "python plugins/solo/skills/suite-integrity/scripts/self_check.py . -",
            "python plugins/ai/skills/agent-room-templates/scripts/validate_rooms.py --suite .",
            "python tools/validate_plugins.py --official-if-available",
            "python tools/smoke_package.py <release.zip> --canonical-source-archive "
            f"<{CANONICAL_SOURCE_NAME}>",
        ],
        "source_checkout_validation_commands": [
            "python -m unittest discover -s tests -t . -v",
            "python tools/verify_source_overlay.py --canonical-only "
            f"--canonical-source-archive parity/artifacts/{CANONICAL_SOURCE_NAME} "
            "--target .",
            "git diff --exit-code",
            "git status --short --untracked-files=all",
        ],
        "installed_package_validation_commands": [
            "python plugins/solo/skills/suite-integrity/scripts/self_check.py . -",
            "python plugins/ai/skills/agent-room-templates/scripts/validate_rooms.py --suite .",
            "python tools/validate_plugins.py --official-if-available",
            "python tools/smoke_package.py <release.zip> --canonical-source-archive "
            f"<{CANONICAL_SOURCE_NAME}>",
        ],
        "artifact_digest_note": (
            "The ZIP SHA-256 is stored beside the ZIP and in the outer release handoff; "
            "embedding it in this file would create a circular digest."
        ),
    })


def included_files(root: Path = ROOT) -> list[Path]:
    root = root.resolve()
    files = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"refusing to package symbolic link: {path}")
        if not path.is_file():
            continue
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise RuntimeError(f"refusing file outside release root: {path}") from exc
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        relative_posix = relative.as_posix()
        if any(
            relative_posix == prefix or relative_posix.startswith(prefix + "/")
            for prefix in EXCLUDED_PREFIXES
        ):
            continue
        if path.name in EXCLUDED_NAMES or path.suffix in {".pyc", ".zip", ".sha256"}:
            continue
        files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def write_checksums(root: Path) -> None:
    root = root.resolve()
    lines = []
    for path in included_files(root):
        if path.name == "RELEASE-CHECKSUMS.txt":
            continue
        lines.append(f"{sha256(path)}  {path.relative_to(root).as_posix()}")
    write_text_lf(root / "RELEASE-CHECKSUMS.txt", "\n".join(lines) + "\n")


def _portable_git_path(raw_path: bytes, seen: set[str]) -> PurePosixPath:
    """Decode one committed path and reject ambiguous or unsafe ZIP names."""

    try:
        decoded = raw_path.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise RuntimeError("committed paths must be valid UTF-8") from exc
    relative = PurePosixPath(decoded)
    if (
        not decoded
        or relative.is_absolute()
        or "\\" in decoded
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise RuntimeError(f"unsafe committed path: {decoded!r}")
    invalid = set('<>:"\\|?*')
    for part in relative.parts:
        if (
            part.endswith((".", " "))
            or any(ord(character) < 32 or character in invalid for character in part)
            or part.split(".", 1)[0].casefold() in WINDOWS_RESERVED_NAMES
        ):
            raise RuntimeError(f"committed path is not portable: {decoded!r}")
    collision_key = "/".join(
        unicodedata.normalize("NFC", part).casefold() for part in relative.parts
    )
    if collision_key in seen:
        raise RuntimeError(f"case-insensitive committed path collision: {decoded!r}")
    seen.add(collision_key)
    return relative


def _committed_entries(root: Path, commit: str) -> list[tuple[str, PurePosixPath]]:
    """Read the exact committed tree without filters or export attributes."""

    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "-r", "-z", "--full-tree", commit],
            capture_output=True,
            env=git_environment(),
            timeout=120,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"unable to enumerate committed source: {exc}") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"unable to enumerate committed source: {detail}")

    entries: list[tuple[str, PurePosixPath]] = []
    seen: set[str] = set()
    for raw_entry in result.stdout.split(b"\0"):
        if not raw_entry:
            continue
        try:
            metadata, raw_path = raw_entry.split(b"\t", 1)
            mode, object_type, raw_oid = metadata.split(b" ", 2)
            oid = raw_oid.decode("ascii")
        except (ValueError, UnicodeDecodeError) as exc:
            raise RuntimeError("Git returned a malformed committed-tree entry") from exc
        mode_text = mode.decode("ascii", errors="replace")
        if object_type != b"blob" or mode_text not in REGULAR_GIT_MODES:
            path_label = raw_path.decode("utf-8", errors="replace")
            raise RuntimeError(
                f"unsupported committed entry {path_label!r}: "
                f"mode={mode_text}, type={object_type.decode('ascii', errors='replace')}"
            )
        if not COMMIT_PATTERN.fullmatch(oid):
            raise RuntimeError("Git returned an invalid committed blob identifier")
        entries.append((oid, _portable_git_path(raw_path, seen)))
    return entries


def _extract_committed_tree(root: Path, destination: Path, commit: str) -> None:
    entries = _committed_entries(root, commit)
    request = "".join(f"{oid}\n" for oid, _ in entries).encode("ascii")
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "cat-file", "--batch"],
            input=request,
            capture_output=True,
            env=git_environment(),
            timeout=120,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"unable to read committed source blobs: {exc}") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"unable to read committed source blobs: {detail}")

    stream = io.BytesIO(result.stdout)
    for expected_oid, relative in entries:
        header = stream.readline().rstrip(b"\n")
        fields = header.split(b" ")
        if len(fields) != 3:
            raise RuntimeError(f"Git could not read committed blob for {relative}")
        raw_oid, object_type, raw_size = fields
        try:
            oid = raw_oid.decode("ascii")
            size = int(raw_size, 10)
        except (UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError(f"Git returned malformed blob data for {relative}") from exc
        if oid != expected_oid or object_type != b"blob" or size < 0:
            raise RuntimeError(f"Git returned the wrong committed object for {relative}")
        content = stream.read(size)
        if len(content) != size or stream.read(1) != b"\n":
            raise RuntimeError(f"Git returned truncated blob data for {relative}")
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    if stream.read(1):
        raise RuntimeError("Git returned unexpected trailing committed-blob data")


def _copy_working_snapshot(root: Path, destination: Path) -> None:
    for source in included_files(root):
        relative = source.relative_to(root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def stage_source(root: Path, destination: Path, context: BuildContext) -> None:
    """Create an immutable input snapshot without changing the source checkout."""

    destination.mkdir(parents=True, exist_ok=True)
    if context.commit and not context.dirty:
        _extract_committed_tree(root, destination, context.commit)
    else:
        _copy_working_snapshot(root, destination)


def generate_metadata(
    root: Path, validation_state: str, context: BuildContext
) -> None:
    write_release(root, validation_state)
    write_sbom(root, context)
    write_provenance(root, validation_state, context)
    write_checksums(root)


def build_zip(root: Path, output: Path, zip_time: tuple[int, int, int, int, int, int]) -> str:
    # ``included_files`` returns paths beneath its resolved root. Resolve the
    # caller's root here as well so Windows 8.3 aliases (for example
    # RUNNER~1 versus runneradmin on GitHub-hosted runners) cannot make
    # ``relative_to`` compare two lexical spellings of the same directory.
    root = root.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    # Stored entries avoid zlib-version differences across clean build hosts.
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in included_files(root):
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(f"{FOLDER}/{relative}", zip_time)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    digest = sha256(output)
    write_text_lf(
        output.with_suffix(output.suffix + ".sha256"),
        f"{digest}  {output.name}\n",
    )
    return digest


def build_release(
    output: Path,
    validation_state: str,
    *,
    root: Path = ROOT,
    canonical_source_archive: Optional[Path] = None,
    verify_source_archive: Optional[Path] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> BuildResult:
    root = root.resolve()
    output = output.resolve()
    if output.suffix.lower() != ".zip":
        raise RuntimeError("release output must use a .zip suffix")
    sidecar = output.with_suffix(output.suffix + ".sha256")
    for candidate in (output, sidecar):
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            continue
        if not relative.parts or relative.parts[0] != "dist":
            raise RuntimeError(
                "release output must be outside the source root or under ignored dist/"
            )
        tracked = run_git(
            root, "ls-files", "--error-unmatch", "--", relative.as_posix(),
            check=False,
        )
        if tracked.returncode == 0:
            raise RuntimeError(f"release output must not overwrite tracked source: {relative}")
    context = resolve_build_context(root, validation_state, environ)
    if validation_state in STRICT_VALIDATION_STATES and canonical_source_archive is None:
        raise RuntimeError(
            f"{validation_state} release requires --canonical-source-archive"
        )
    if canonical_source_archive is not None:
        verify_canonical_source_archive(canonical_source_archive, root)
    if verify_source_archive is not None:
        verify_historical_archive(verify_source_archive)
    with tempfile.TemporaryDirectory(prefix="solo-suite-release-") as temp:
        stage = Path(temp) / FOLDER
        stage_source(root, stage, context)
        generate_metadata(stage, validation_state, context)
        file_count = len(included_files(stage))
        digest = build_zip(stage, output, context.zip_time)
    return BuildResult(output, digest, file_count, context)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path,
        default=ROOT.parent / f"{FOLDER}.zip",
    )
    parser.add_argument(
        "--validation-state", choices=sorted(VALIDATION_STATES), default="pending"
    )
    parser.add_argument(
        "--canonical-source-archive",
        type=Path,
        help=(
            "pinned reconstructed Claude baseline required for validated/CI builds; its "
            "digest and source/target parity are checked before packaging"
        ),
    )
    parser.add_argument(
        "--verify-source-archive",
        type=Path,
        help=(
            "optionally verify the historical Claude v1.0.26 archive; its presence and "
            "path never affect package contents"
        ),
    )
    args = parser.parse_args()
    try:
        result = build_release(
            args.output,
            args.validation_state,
            canonical_source_archive=args.canonical_source_archive,
            verify_source_archive=args.verify_source_archive,
        )
    except RuntimeError as exc:
        parser.error(str(exc))
    print(f"PACKAGE {result.output}")
    print(f"SHA256 {result.digest}")
    print(f"FILES {result.files}")
    print(f"SOURCE_COMMIT {result.context.commit or 'NONE (preflight only)'}")
    print(f"SOURCE_DATE_EPOCH {result.context.epoch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
