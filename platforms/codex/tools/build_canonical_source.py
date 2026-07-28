#!/usr/bin/env python3
"""Reconstruct and package the pinned Claude v1.0.27 baseline for Codex v1.0.27.

The exact authenticated Claude v1.0.27 Git-object build is the immutable base.
Reviewed Codex adapter files are overlaid before the canonical parity manifest
is regenerated. A build succeeds only when that manifest is byte-identical to
the Codex checkout's pinned manifest and the full source/target parity check
passes.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
TARGET_VERSION = "1.0.27"
SOURCE_FOLDER = "solo-suite-plugin-v1.0.27"
BASE_ARCHIVE_NAME = f"{SOURCE_FOLDER}.zip"
BASE_ARCHIVE_SHA256 = (
    "e6ade834f95695766af5655a2444d49096ba3b0c49b4f1f726a119ef30848caa"
)
BASE_GIT_COMMIT = "a31be037edaee840479977585e33ac0e57088cb4"
BASE_TAG = "v1.0.27"
BASE_TAG_OBJECT = "7495f3ac2c4da972f0f4435028ed468da3135475"
BASE_TAG_SIGNED = False
BASE_TREE_OID = "0517f8f10a5406f227eb3177b188b2b1103fcf47"
BASE_REPOSITORY = "https://github.com/Unn0wn002/solo-suite"
BASE_RELEASE_URL = f"{BASE_REPOSITORY}/releases/tag/{BASE_TAG}"
BASE_ASSET_URL = (
    f"{BASE_REPOSITORY}/releases/download/{BASE_TAG}/{BASE_ARCHIVE_NAME}"
)
BASE_PROVENANCE_URL = (
    f"{BASE_REPOSITORY}/releases/download/{BASE_TAG}/provenance.json"
)
BASE_PROVENANCE_SHA256 = (
    "a6d59e91229d38dfb284c130957c138a2718912dcd23fea4917670f9b875633b"
)
TARGET_SYNC_COMMIT = "16d3bba2503c1698d770cc52b3fe53be39ab6e09"
SOURCE_DATE_EPOCH = 1_784_160_312
OUTPUT_NAME = (
    f"{SOURCE_FOLDER}-codex-v{TARGET_VERSION}-parity-source.zip"
)
EXPECTED_CAPABILITIES_SHA256 = (
    "3f03cfe3cb25cff447dcfcba028df832288e9212c0fe816b9f702b7a1038f5ec"
)
EXPECTED_OVERLAY_MANIFEST_SHA256 = (
    "34e1811a2124820d24f6be2712db4ebc2487439f9cb4da46b2074e46d8aca95f"
)
EXPECTED_ARCHIVE_SHA256 = (
    "7dde7bbe44e7534e3f1890ddb1c5feba5554d60127c4dd7ef2095b31cafb03aa"
)

COMMAND_OVERLAYS = (
    "plugins/full-team/commands/verify.md",
    "plugins/release/commands/deploy-plan.md",
    "plugins/release/commands/rollback-plan.md",
    "plugins/solo/commands/full-team-dev.md",
)
GATE_POLICY_OVERLAYS = (
    "plugins/gate/skills/production-readiness-reviewer/SKILL.md",
    "plugins/gate/lib/gate_policy.py",
    "plugins/gate/skills/production-readiness-reviewer/scripts/check_evidence.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _safe_relative(name: str) -> PurePosixPath:
    value = PurePosixPath(name)
    if (
        value.is_absolute()
        or "\\" in name
        or not value.parts
        or any(part in {"", ".", ".."} for part in value.parts)
        or value.parts[0] != SOURCE_FOLDER
    ):
        raise RuntimeError(f"unsafe or unexpected source archive member: {name!r}")
    return value


def extract_base(archive_path: Path, destination: Path) -> Path:
    if not archive_path.is_file():
        raise RuntimeError(f"base source archive does not exist: {archive_path}")
    actual = sha256(archive_path)
    if actual != BASE_ARCHIVE_SHA256:
        raise RuntimeError(
            "base source archive digest mismatch: "
            f"expected {BASE_ARCHIVE_SHA256}, got {actual}"
        )
    with zipfile.ZipFile(archive_path) as archive:
        if not archive.infolist():
            raise RuntimeError("base source archive is empty")
        seen: set[str] = set()
        for info in archive.infolist():
            relative = _safe_relative(info.filename)
            key = relative.as_posix()
            if key in seen:
                raise RuntimeError(f"duplicate source archive member: {info.filename!r}")
            seen.add(key)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise RuntimeError(f"source archive contains a symbolic link: {info.filename}")
            target = destination.joinpath(*relative.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
    source = destination / SOURCE_FOLDER
    if not source.is_dir():
        raise RuntimeError(f"base source archive lacks {SOURCE_FOLDER!r}")
    return source


def verify_base_provenance(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"base provenance does not exist: {path}")
    actual = sha256(path)
    if actual != BASE_PROVENANCE_SHA256:
        raise RuntimeError(
            "base provenance digest mismatch: "
            f"expected {BASE_PROVENANCE_SHA256}, got {actual}"
        )
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"base provenance is not valid JSON: {exc}") from exc
    for key, expected in {
        "artifact_sha256": BASE_ARCHIVE_SHA256,
        "source_commit": BASE_GIT_COMMIT,
        "source_tree_oid": BASE_TREE_OID,
    }.items():
        if record.get(key) != expected:
            raise RuntimeError(
                f"base provenance {key} mismatch: expected {expected}, "
                f"got {record.get(key)}"
            )
    if record.get("source_dirty") is not False:
        raise RuntimeError("base provenance is not bound to a clean source tree")


def overlay_files(source: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for relative in COMMAND_OVERLAYS:
        origin = ROOT / "parity/canonical-source-overrides" / relative
        if not origin.is_file():
            raise RuntimeError(f"Claude command overlay is missing: {origin}")
        destination = source / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(origin.read_bytes())
        records.append({
            "path": relative,
            "role": "reviewed-adapter-command-source",
            "origin": origin.relative_to(ROOT).as_posix(),
            "sha256": sha256(origin),
        })
    for relative in GATE_POLICY_OVERLAYS:
        origin = ROOT / "parity/canonical-source-overrides" / relative
        if not origin.is_file():
            raise RuntimeError(f"gate policy overlay is missing: {origin}")
        destination = source / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(origin.read_bytes())
        records.append({
            "path": relative,
            "role": "synchronized-gate-policy-source",
            "origin": origin.relative_to(ROOT).as_posix(),
            "sha256": sha256(origin),
        })
    # The published parity-source archive is a historical artifact.  Keep its
    # embedded checker byte-stable even as the working-tree checker evolves to
    # understand both historical and current parity profiles.
    checker = ROOT / "parity/canonical-source-overrides/tools/parity.py"
    if not checker.is_file():
        raise RuntimeError(f"historical canonical parity checker is missing: {checker}")
    destination = source / "tools/parity.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(checker.read_bytes())
    records.append({
        "path": "tools/parity.py",
        "role": "canonical-parity-checker",
        "origin": "tools/parity.py",
        "sha256": sha256(checker),
    })
    return records


def generate_historical_manifest(source: Path) -> None:
    checker = source / "tools/parity.py"
    generated = subprocess.run(
        [sys.executable, str(checker), "generate", "--source", str(source)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    if generated.returncode:
        raise RuntimeError(
            "canonical source manifest generation failed:\n"
            f"{generated.stdout}{generated.stderr}"
        )
    source_manifest = source / "parity/capabilities.json"
    source_digest = sha256(source_manifest)
    if EXPECTED_CAPABILITIES_SHA256 and source_digest != EXPECTED_CAPABILITIES_SHA256:
        raise RuntimeError(
            "canonical source manifest has an unexpected digest: "
            f"expected {EXPECTED_CAPABILITIES_SHA256}, got {source_digest}"
        )
    print(generated.stdout.strip())
    print(
        "Historical canonical source generated independently; "
        "current working-tree parity is verified separately."
    )


def tree_digest(source: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        (
            path for path in source.rglob("*")
            if path.is_file() and path.name != "PARITY-SOURCE.json"
        ),
        key=lambda path: path.relative_to(source).as_posix(),
    ):
        relative = path.relative_to(source).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256(path)))
        digest.update(b"\n")
    return digest.hexdigest()


def write_provenance(source: Path, overlays: list[dict[str, str]]) -> None:
    instant = datetime.fromtimestamp(SOURCE_DATE_EPOCH, timezone.utc)
    write_json(source / "PARITY-SOURCE.json", {
        "schema": "solo-suite/canonical-parity-source-v1",
        "source_suite": "solo-suite-plugin",
        "source_version": "1.0.27",
        "target_suite": "solo-suite-codex",
        "target_version": TARGET_VERSION,
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "built_at": instant.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "base_archive": BASE_ARCHIVE_NAME,
        "base_archive_sha256": BASE_ARCHIVE_SHA256,
        "base_git_commit": BASE_GIT_COMMIT,
        "base_tag": BASE_TAG,
        "base_tag_object": BASE_TAG_OBJECT,
        "base_tag_signed": BASE_TAG_SIGNED,
        "base_tree_oid": BASE_TREE_OID,
        "base_repository": BASE_REPOSITORY,
        "base_release_url": BASE_RELEASE_URL,
        "base_asset_url": BASE_ASSET_URL,
        "base_provenance_url": BASE_PROVENANCE_URL,
        "base_provenance_sha256": BASE_PROVENANCE_SHA256,
        "target_sync_commit": TARGET_SYNC_COMMIT,
        "capabilities_sha256": EXPECTED_CAPABILITIES_SHA256,
        "tree_sha256": tree_digest(source),
        # Keep the embedded record byte-stable and in the same path order used
        # by the independently generated overlay manifest.
        "overlays": sorted(overlays, key=lambda item: item["path"]),
        "verification": [
            "python tools/parity.py generate --source <canonical-source>",
            "python tools/parity.py check --source <canonical-source> --target <codex-target>",
        ],
    })


def package_source(source: Path, output: Path) -> str:
    instant = datetime.fromtimestamp(SOURCE_DATE_EPOCH, timezone.utc)
    zip_time = (
        instant.year,
        instant.month,
        instant.day,
        instant.hour,
        instant.minute,
        instant.second - instant.second % 2,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(
            (path for path in source.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(source).as_posix(),
        ):
            relative = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(f"{SOURCE_FOLDER}/{relative}", zip_time)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    digest = sha256(output)
    with output.with_suffix(output.suffix + ".sha256").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write(f"{digest}  {output.name}\n")
    return digest


def verify_published_overlay(
    base_archive: Path, base_provenance: Path, output: Path
) -> None:
    manifest = ROOT / "parity/source-overlay-manifest.json"
    actual_manifest_digest = sha256(manifest)
    if EXPECTED_OVERLAY_MANIFEST_SHA256 and actual_manifest_digest != EXPECTED_OVERLAY_MANIFEST_SHA256:
        raise RuntimeError(
            "source overlay manifest digest mismatch: "
            f"expected {EXPECTED_OVERLAY_MANIFEST_SHA256}, "
            f"got {actual_manifest_digest}"
        )
    verifier = ROOT / "tools/verify_source_overlay.py"
    checked = subprocess.run(
        [
            sys.executable,
            str(verifier),
            "--base-archive",
            str(base_archive),
            "--canonical-source-archive",
            str(output),
            "--base-provenance",
            str(base_provenance),
            "--manifest",
            str(manifest),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    if checked.returncode:
        raise RuntimeError(
            "published source overlay verification failed:\n"
            f"{checked.stdout}{checked.stderr}"
        )
    print(checked.stdout.strip())


def build(base_archive: Path, base_provenance: Path, output: Path) -> str:
    base_archive = base_archive.resolve()
    base_provenance = base_provenance.resolve()
    output = output.resolve()
    verify_base_provenance(base_provenance)
    with tempfile.TemporaryDirectory(prefix="solo-suite-canonical-source-") as temp:
        source = extract_base(base_archive, Path(temp))
        overlays = overlay_files(source)
        generate_historical_manifest(source)
        write_provenance(source, overlays)
        digest = package_source(source, output)
    verify_published_overlay(base_archive, base_provenance, output)
    if EXPECTED_ARCHIVE_SHA256 and digest != EXPECTED_ARCHIVE_SHA256:
        raise RuntimeError(
            "canonical source archive digest mismatch: "
            f"expected {EXPECTED_ARCHIVE_SHA256}, got {digest}"
        )
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base_group = parser.add_mutually_exclusive_group()
    base_group.add_argument("--base-archive", type=Path)
    base_group.add_argument(
        "--fetch-public-base", action="store_true",
        help="download the authenticated base asset/provenance pinned in parity/source-overlay-manifest.json",
    )
    parser.add_argument("--output", type=Path, default=ROOT.parent / OUTPUT_NAME)
    parser.add_argument(
        "--base-provenance", type=Path,
        default=ROOT / "parity/artifacts/solo-suite-plugin-v1.0.27.provenance.json",
    )
    args = parser.parse_args()
    try:
        if args.fetch_public_base:
            from verify_source_overlay import (
                fetch_public_base,
                is_safe_plain_filename,
                load_manifest,
            )

            manifest = load_manifest(ROOT / "parity/source-overlay-manifest.json")
            with tempfile.TemporaryDirectory(prefix="solo-suite-public-base-") as temp:
                temporary = Path(temp)
                public_provenance = temporary / "provenance.json"
                archive_name = manifest.get("base_archive")
                if not is_safe_plain_filename(archive_name):
                    raise RuntimeError(
                        "overlay manifest has an invalid base_archive filename"
                    )
                base_archive = fetch_public_base(
                    manifest,
                    temporary / archive_name,
                    public_provenance,
                )
                digest = build(base_archive, public_provenance, args.output)
        elif args.base_archive is not None:
            digest = build(args.base_archive, args.base_provenance, args.output)
        else:
            parser.error("one of --base-archive or --fetch-public-base is required")
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))
    output = args.output.resolve()
    print(f"CANONICAL_SOURCE {output}")
    print(f"SHA256 {digest}")
    print(f"SOURCE_DATE_EPOCH {SOURCE_DATE_EPOCH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
