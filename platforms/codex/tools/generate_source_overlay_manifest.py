#!/usr/bin/env python3
"""Generate the checked-in, exact-delta manifest for the Claude overlay.

The manifest is derived from the two immutable archives rather than copied
from a hand-maintained list.  The generator fails closed if a changed path is
not one of the reviewed Codex adapter overlays.  This keeps a new source drift
from becoming an accidental, undocumented waiver.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from build_canonical_source import (
    BASE_ASSET_URL,
    BASE_ARCHIVE_NAME,
    BASE_ARCHIVE_SHA256,
    BASE_GIT_COMMIT,
    BASE_PROVENANCE_URL,
    BASE_PROVENANCE_SHA256,
    BASE_TAG,
    BASE_TAG_OBJECT,
    BASE_TAG_SIGNED,
    BASE_TREE_OID,
    SOURCE_FOLDER,
    TARGET_VERSION,
    TARGET_SYNC_COMMIT,
)
from verify_source_overlay import (
    _actual_changes,
    _verify_embedded_provenance,
    is_safe_plain_filename,
    read_archive,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = ROOT / "parity/artifacts/solo-suite-plugin-v1.0.27.zip"
DEFAULT_CANONICAL = ROOT / (
    "parity/artifacts/solo-suite-plugin-v1.0.27-codex-v1.0.27-parity-source.zip"
)
DEFAULT_OUTPUT = ROOT / "parity/source-overlay-manifest.json"

OVERLAY_METADATA: dict[str, tuple[str, str, str | None]] = {
    "plugins/full-team/commands/verify.md": (
        "reviewed-command-source",
        "reviewed-adapter-command-source",
        "parity/canonical-source-overrides/plugins/full-team/commands/verify.md",
    ),
    "plugins/gate/lib/gate_policy.py": (
        "synchronized-gate-policy",
        "synchronized-gate-policy-source",
        "parity/canonical-source-overrides/plugins/gate/lib/gate_policy.py",
    ),
    "plugins/gate/skills/production-readiness-reviewer/SKILL.md": (
        "synchronized-gate-policy",
        "synchronized-gate-policy-source",
        "parity/canonical-source-overrides/plugins/gate/skills/production-readiness-reviewer/SKILL.md",
    ),
    "plugins/gate/skills/production-readiness-reviewer/scripts/check_evidence.py": (
        "synchronized-gate-policy",
        "synchronized-gate-policy-source",
        "parity/canonical-source-overrides/plugins/gate/skills/production-readiness-reviewer/scripts/check_evidence.py",
    ),
    "plugins/release/commands/deploy-plan.md": (
        "reviewed-command-source",
        "reviewed-adapter-command-source",
        "parity/canonical-source-overrides/plugins/release/commands/deploy-plan.md",
    ),
    "plugins/release/commands/rollback-plan.md": (
        "reviewed-command-source",
        "reviewed-adapter-command-source",
        "parity/canonical-source-overrides/plugins/release/commands/rollback-plan.md",
    ),
    "plugins/solo/commands/full-team-dev.md": (
        "reviewed-command-source",
        "reviewed-adapter-command-source",
        "parity/canonical-source-overrides/plugins/solo/commands/full-team-dev.md",
    ),
    "parity/capabilities.json": (
        "generated-parity-manifest",
        "",
        None,
    ),
    "tools/parity.py": (
        "generated-verifier",
        "canonical-parity-checker",
        None,
    ),
    "PARITY-SOURCE.json": ("generated-provenance", "", None),
}


def _top_level(path: Path) -> str:
    with ZipFile(path) as archive:
        roots = {
            name.split("/", 1)[0]
            for name in archive.namelist()
            if name and not name.endswith("/")
        }
    if roots != {SOURCE_FOLDER}:
        raise RuntimeError(
            f"archive must contain exactly {SOURCE_FOLDER!r}, found {sorted(roots)}"
        )
    return SOURCE_FOLDER


def _validate_base_archive(path: Path) -> str:
    """Verify the generator is operating on the pinned public base asset."""

    if not is_safe_plain_filename(path.name):
        raise RuntimeError(f"base archive must have a safe plain filename: {path.name!r}")
    if path.name != BASE_ARCHIVE_NAME:
        raise RuntimeError(
            "base archive filename does not match the pinned release asset: "
            f"expected {BASE_ARCHIVE_NAME!r}, got {path.name!r}"
        )
    if not path.is_file():
        raise RuntimeError(f"base archive does not exist: {path}")
    digest = sha256_file(path)
    if digest != BASE_ARCHIVE_SHA256:
        raise RuntimeError(
            "base archive digest does not match the pinned release asset: "
            f"expected {BASE_ARCHIVE_SHA256}, got {digest}"
        )
    return digest


def _validate_base_provenance(path: Path, base_digest: str) -> str:
    """Verify the exact public provenance record paired with the base asset."""

    if not is_safe_plain_filename(path.name):
        raise RuntimeError(
            f"base provenance must have a safe plain filename: {path.name!r}"
        )
    if not path.is_file():
        raise RuntimeError(f"base provenance does not exist: {path}")
    digest = sha256_file(path)
    if digest != BASE_PROVENANCE_SHA256:
        raise RuntimeError(
            "base provenance digest does not match the pinned public record: "
            f"expected {BASE_PROVENANCE_SHA256}, got {digest}"
        )
    if base_digest != BASE_ARCHIVE_SHA256:
        raise RuntimeError(
            "base archive digest does not match the pinned release asset: "
            f"expected {BASE_ARCHIVE_SHA256}, got {base_digest}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"base provenance is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("base provenance must be a JSON object")
    expected = {
        "artifact": BASE_ARCHIVE_NAME,
        "artifact_sha256": BASE_ARCHIVE_SHA256,
        "version": TARGET_VERSION,
        "source_commit": BASE_GIT_COMMIT,
        "source_tree_oid": BASE_TREE_OID,
        "worktree_head_commit": BASE_GIT_COMMIT,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise RuntimeError(f"base provenance {key} does not match pinned source")
    if payload.get("source_dirty") is not False:
        raise RuntimeError("base provenance is not bound to a clean source tree")
    return digest


def generate(
    base_archive: Path,
    canonical_archive: Path,
    base_provenance: Path,
    output: Path,
    *,
    target_sync_commit: str = TARGET_SYNC_COMMIT,
    capabilities_sha256: str,
    working_tree_capabilities_sha256: str | None = None,
    working_tree_parity_sha256: str | None = None,
) -> dict:
    # Check identity before comparing archive contents.  Without these pins a
    # caller could substitute a different archive and matching provenance
    # record that happened to produce the same reviewed path delta.
    base_digest = _validate_base_archive(base_archive)
    provenance_digest = _validate_base_provenance(base_provenance, base_digest)
    top = _top_level(base_archive)
    if _top_level(canonical_archive) != top:
        raise RuntimeError("base and canonical archive top-level folders differ")
    canonical_digest = sha256_file(canonical_archive)
    base = read_archive(base_archive, base_digest, top)
    canonical = read_archive(canonical_archive, canonical_digest, top)
    actual = _actual_changes(base, canonical)
    unknown = sorted(set(actual) - set(OVERLAY_METADATA))
    missing = sorted(set(OVERLAY_METADATA) - set(actual))
    if unknown or missing:
        raise RuntimeError(
            f"archive delta is not the reviewed overlay: unknown={unknown}, missing={missing}"
        )

    changes: list[dict] = []
    for path, (before, after, change) in actual.items():
        category, role, origin = OVERLAY_METADATA[path]
        item = {
            "path": path,
            "change": change,
            "category": category,
            "base_sha256": before,
            "result_sha256": after,
        }
        if origin is not None:
            origin_path = ROOT / Path(*origin.split("/"))
            if not origin_path.is_file():
                raise RuntimeError(f"overlay origin is missing: {origin}")
            if sha256_file(origin_path) != after:
                raise RuntimeError(f"overlay origin digest mismatch: {origin}")
            item["origin"] = origin
            if role:
                item["provenance_role"] = role
        else:
            item["origin"] = None
            if role:
                item["provenance_role"] = role
                item["provenance_origin"] = path
        changes.append(item)

    manifest = {
        "schema": "solo-suite/source-overlay-manifest-v1",
        "target_release": "solo-suite-codex-v1.0.27",
        "top_level_folder": top,
        "base_archive": base_archive.name,
        "base_archive_sha256": base_digest,
        "base_git_commit": BASE_GIT_COMMIT,
        "base_git_commit_authenticated": True,
        "base_tag": BASE_TAG,
        "base_tag_object": BASE_TAG_OBJECT,
        "base_tag_signed": BASE_TAG_SIGNED,
        "base_tree_oid": BASE_TREE_OID,
        "base_repository": "https://github.com/Unn0wn002/solo-suite",
        "base_release_url": f"https://github.com/Unn0wn002/solo-suite/releases/tag/{BASE_TAG}",
        "base_asset_url": BASE_ASSET_URL,
        "base_provenance_url": BASE_PROVENANCE_URL,
        "base_provenance_sha256": provenance_digest,
        "overlay_source_commits": {
            "canonical_tag_commit": BASE_GIT_COMMIT,
            "codex_target_sync": target_sync_commit,
        },
        "canonical_archive": canonical_archive.name,
        "canonical_archive_sha256": canonical_digest,
        "target_sync_commit": target_sync_commit,
        "capabilities_sha256": capabilities_sha256,
        **(
            {"working_tree_capabilities_sha256": working_tree_capabilities_sha256}
            if working_tree_capabilities_sha256
            else {}
        ),
        **(
            {"working_tree_parity_sha256": working_tree_parity_sha256}
            if working_tree_parity_sha256
            else {}
        ),
        "provenance_status": "authenticated-tag-reproducible-overlay",
        "provenance_caveat": (
            "The Claude v1.0.27 annotated tag, commit, tree, and public release "
            "asset are pinned; the checked-in provenance JSON is the exact public "
            "release CI record and is digest-pinned rather than locally rebuilt. "
            "The tag is not cryptographically signed (base_tag_signed=false). "
            "The Codex result differs from that base only at the ten paths declared "
            "here; those are reviewed adapter or generated-verifier overlays, not "
            "an assertion of byte identity with the unmodified Claude archive."
        ),
        "changes": changes,
        "verification": [
            "python tools/verify_source_overlay.py --base-archive "
            "parity/artifacts/solo-suite-plugin-v1.0.27.zip "
            "--base-provenance parity/artifacts/solo-suite-plugin-v1.0.27.provenance.json "
            "--canonical-source-archive parity/artifacts/solo-suite-plugin-v1.0.27-codex-v1.0.27-parity-source.zip",
            "python tools/verify_source_overlay.py --canonical-only "
            "--canonical-source-archive parity/artifacts/solo-suite-plugin-v1.0.27-codex-v1.0.27-parity-source.zip",
            "python tools/parity.py check --source <current-claude-source> --target .",
        ],
    }
    # Confirm the archive's embedded PARITY-SOURCE record before publishing the
    # manifest; this catches a stale target-sync or capability digest early.
    _verify_embedded_provenance(manifest, canonical)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-archive", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--canonical-source-archive", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--base-provenance", type=Path, default=ROOT / "parity/artifacts/solo-suite-plugin-v1.0.27.provenance.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-sync-commit", default=TARGET_SYNC_COMMIT)
    parser.add_argument("--capabilities-sha256", required=True)
    parser.add_argument("--working-tree-capabilities-sha256")
    parser.add_argument("--working-tree-parity-sha256")
    args = parser.parse_args()
    manifest = generate(
        args.base_archive.resolve(),
        args.canonical_source_archive.resolve(),
        args.base_provenance.resolve(),
        args.output.resolve(),
        target_sync_commit=args.target_sync_commit,
        capabilities_sha256=args.capabilities_sha256,
        working_tree_capabilities_sha256=args.working_tree_capabilities_sha256,
        working_tree_parity_sha256=args.working_tree_parity_sha256,
    )
    print(f"MANIFEST {args.output.resolve()}")
    print(f"CHANGES {len(manifest['changes'])}")
    print(f"SHA256 {hashlib.sha256(args.output.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
