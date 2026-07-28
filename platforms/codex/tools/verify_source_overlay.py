#!/usr/bin/env python3
"""Verify the exact base-to-canonical Claude source overlay.

This verifier is deliberately independent of build_canonical_source.py.  It
compares the two archives directly, requires the complete changed-file set and
both sides of every changed-file digest to match the published manifest, and
can then run the digest-pinned parity checker against a Codex target checkout.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
from http.client import IncompleteRead
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import ssl
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "parity/source-overlay-manifest.json"
# Archive names are later joined to a temporary directory in networked mode.
# Keep this an intentionally small, cross-platform allow-list: a manifest is
# data, not a path-authorisation mechanism.  In particular, reject separators,
# drive-qualified names, dot-segments, control characters, and names that are
# ambiguous on Windows (trailing spaces/dots).
PLAIN_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DOWNLOAD_RETRY_DELAYS = (1.0, 2.0)
ALLOWED_DOWNLOAD_HOSTS = frozenset({
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
})
TRANSIENT_HTTP_STATUSES = {408, 425, 429, 500, 502, 503, 504}
TRANSIENT_ERRNOS = frozenset(
    value
    for value in (
        getattr(errno, "ETIMEDOUT", None),
        getattr(errno, "ECONNRESET", None),
        getattr(errno, "ECONNABORTED", None),
        getattr(errno, "ECONNREFUSED", None),
        getattr(errno, "EHOSTUNREACH", None),
        getattr(errno, "ENETUNREACH", None),
    )
    if value is not None
)


class VerificationError(RuntimeError):
    """Raised when an archive or overlay violates the published contract."""


def _validate_download_url(url: str, label: str) -> None:
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise VerificationError(f"{label} is malformed: {url}") from exc
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_DOWNLOAD_HOSTS:
        raise VerificationError(f"{label} left the permitted GitHub hosts: {url}")


class _PinnedRedirectHandler(HTTPRedirectHandler):
    """Reject every redirect hop that leaves the pinned GitHub host set."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_download_url(newurl, "public-source redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _is_transient_download_error(exc: BaseException) -> bool:
    if isinstance(exc, HTTPError):
        return exc.code in TRANSIENT_HTTP_STATUSES
    if isinstance(exc, IncompleteRead):
        return True
    if isinstance(exc, ssl.SSLError):
        return False
    if isinstance(exc, URLError):
        reason = exc.reason
        return reason is not exc and isinstance(reason, BaseException) and (
            _is_transient_download_error(reason)
        )
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    return isinstance(exc, OSError) and exc.errno in TRANSIENT_ERRNOS


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_safe_plain_filename(value: object) -> bool:
    """Return whether *value* is safe to append to a directory path.

    This deliberately accepts only ordinary archive-style names.  It is used
    for the manifest's ``base_archive`` before any temporary-path join, so a
    malicious manifest cannot turn the download destination into a traversal
    or an absolute path.
    """

    if (
        not isinstance(value, str)
        or PLAIN_FILENAME_RE.fullmatch(value) is None
        or value in {".", ".."}
        or value.endswith((".", " "))
    ):
        return False
    # ``PureWindowsPath.is_reserved`` covers CON/PRN/AUX/NUL, COM/LPT
    # device names (including extension-bearing forms), and superscript
    # variants that are special on Windows even though they look like files.
    return not PureWindowsPath(value).is_reserved()


def _download_pinned(
    url: str,
    limit: int = 64 * 1024 * 1024,
    *,
    opener=None,
    sleeper=time.sleep,
) -> bytes:
    _validate_download_url(url, "public-source URL")
    if opener is None:
        opener = build_opener(_PinnedRedirectHandler()).open
    delays = DOWNLOAD_RETRY_DELAYS
    for attempt in range(len(delays) + 1):
        request = Request(
            url, headers={"User-Agent": "solo-suite-overlay-verifier/1"}
        )
        try:
            with opener(request, timeout=90) as response:
                _validate_download_url(response.geturl(), "public-source redirect")
                data = response.read(limit + 1)
            if len(data) > limit:
                raise VerificationError("public source material exceeds the download limit")
            return data
        except VerificationError:
            raise
        except (OSError, IncompleteRead) as exc:
            retry = _is_transient_download_error(exc)
            if isinstance(exc, HTTPError):
                exc.close()
            if not retry:
                raise VerificationError(
                    f"could not download public source material: {exc}"
                ) from exc
            if attempt == len(delays):
                raise VerificationError(
                    "could not download public source material after "
                    f"{attempt + 1} attempts: {exc}"
                ) from exc
            sleeper(delays[attempt])
    raise AssertionError("download retry loop exhausted unexpectedly")


def fetch_public_base(
    manifest: dict,
    destination: Path,
    provenance_destination: Path | None = None,
) -> Path:
    # Validate this even for direct callers that bypass ``load_manifest``.
    # ``main`` subsequently joins this value to a temporary directory.
    if not is_safe_plain_filename(manifest.get("base_archive")):
        raise VerificationError(
            "overlay manifest has an invalid base_archive filename"
        )
    asset_url = manifest.get("base_asset_url")
    provenance_url = manifest.get("base_provenance_url")
    expected_provenance = manifest.get("base_provenance_sha256")
    if not all(isinstance(value, str) and value for value in (
        asset_url, provenance_url, expected_provenance,
    )):
        raise VerificationError(
            "overlay manifest lacks authenticated public base asset/provenance URLs"
        )
    asset = _download_pinned(asset_url)
    digest = sha256_bytes(asset)
    if digest != manifest["base_archive_sha256"]:
        raise VerificationError(
            "downloaded public base digest mismatch: "
            f"expected {manifest['base_archive_sha256']}, got {digest}"
        )
    provenance = _download_pinned(provenance_url, limit=4 * 1024 * 1024)
    provenance_digest = sha256_bytes(provenance)
    if provenance_digest != expected_provenance:
        raise VerificationError(
            "downloaded public provenance digest mismatch: "
            f"expected {expected_provenance}, got {provenance_digest}"
        )
    try:
        record = json.loads(provenance.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"public provenance is not valid JSON: {exc}") from exc
    if not isinstance(record, dict):
        raise VerificationError("public provenance must be a JSON object")
    if (
        record.get("artifact_sha256") != manifest.get("base_archive_sha256")
        or record.get("source_commit") != manifest.get("base_git_commit")
        or record.get("source_tree_oid") != manifest.get("base_tree_oid")
        or record.get("source_dirty") is not False
    ):
        raise VerificationError(
            "public provenance does not bind the downloaded archive to the "
            "pinned clean source commit/tree"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(asset)
    if provenance_destination is not None:
        provenance_destination.parent.mkdir(parents=True, exist_ok=True)
        provenance_destination.write_bytes(provenance)
    return destination


def load_manifest(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read overlay manifest {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise VerificationError("overlay manifest must be a JSON object")
    if payload.get("schema") != "solo-suite/source-overlay-manifest-v1":
        raise VerificationError("overlay manifest has an unsupported schema")
    if not is_safe_plain_filename(payload.get("base_archive")):
        raise VerificationError(
            "overlay manifest has an invalid base_archive filename"
        )
    for key in ("base_archive_sha256", "canonical_archive_sha256"):
        if not SHA256_RE.fullmatch(str(payload.get(key, ""))):
            raise VerificationError(f"overlay manifest has an invalid {key}")
    top = payload.get("top_level_folder")
    if not isinstance(top, str) or not top or "/" in top or "\\" in top:
        raise VerificationError("overlay manifest has an invalid top_level_folder")
    changes = payload.get("changes")
    if not isinstance(changes, list) or not changes:
        raise VerificationError("overlay manifest must declare changed files")
    seen: set[str] = set()
    for item in changes:
        if not isinstance(item, dict):
            raise VerificationError("overlay manifest change entries must be objects")
        changed_path = item.get("path")
        if not isinstance(changed_path, str) or not _safe_relative(changed_path):
            raise VerificationError(f"unsafe overlay path: {changed_path!r}")
        if changed_path in seen:
            raise VerificationError(f"duplicate overlay path: {changed_path}")
        seen.add(changed_path)
        change = item.get("change")
        if change not in {"add", "replace", "delete"}:
            raise VerificationError(f"invalid change kind for {changed_path}: {change!r}")
        before = item.get("base_sha256")
        after = item.get("result_sha256")
        if change == "add":
            valid = before is None and SHA256_RE.fullmatch(str(after or ""))
        elif change == "delete":
            valid = SHA256_RE.fullmatch(str(before or "")) and after is None
        else:
            valid = (
                SHA256_RE.fullmatch(str(before or ""))
                and SHA256_RE.fullmatch(str(after or ""))
            )
        if not valid:
            raise VerificationError(f"invalid before/after digests for {changed_path}")
        origin = item.get("origin")
        if origin is not None and (
            not isinstance(origin, str) or not _safe_relative(origin)
        ):
            raise VerificationError(f"unsafe overlay origin for {changed_path}")
    return payload


def verify_base_provenance(path: Path, manifest: dict) -> dict:
    """Verify the source builder record bound to the pinned base archive."""
    expected = manifest.get("base_provenance_sha256")
    if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
        raise VerificationError("overlay manifest has an invalid base_provenance_sha256")
    if not path.is_file():
        raise VerificationError(f"base provenance does not exist: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise VerificationError(
            "base provenance digest mismatch: "
            f"expected {expected}, got {actual}"
        )
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"base provenance is not valid JSON: {exc}") from exc
    if not isinstance(record, dict):
        raise VerificationError("base provenance must be a JSON object")
    checks = {
        "artifact_sha256": manifest.get("base_archive_sha256"),
        "source_commit": manifest.get("base_git_commit"),
        "source_tree_oid": manifest.get("base_tree_oid"),
    }
    for key, value in checks.items():
        if record.get(key) != value:
            raise VerificationError(
                f"base provenance {key} does not match the overlay manifest"
            )
    if record.get("source_dirty") is not False:
        raise VerificationError("base provenance is not bound to a clean source tree")
    return record


def _safe_relative(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        bool(value)
        and not path.is_absolute()
        and "\\" not in value
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def read_archive(path: Path, expected_digest: str, top_level: str) -> dict[str, bytes]:
    if not path.is_file():
        raise VerificationError(f"archive does not exist: {path}")
    actual_digest = sha256_file(path)
    if actual_digest != expected_digest:
        raise VerificationError(
            f"archive digest mismatch for {path.name}: "
            f"expected {expected_digest}, got {actual_digest}"
        )
    files: dict[str, bytes] = {}
    prefix = f"{top_level}/"
    try:
        with zipfile.ZipFile(path) as archive:
            if not archive.infolist():
                raise VerificationError(f"archive is empty: {path}")
            seen_members: set[str] = set()
            for info in archive.infolist():
                name = info.filename
                member = PurePosixPath(name)
                if (
                    member.is_absolute()
                    or "\\" in name
                    or any(part in {"", ".", ".."} for part in member.parts)
                    or not name.startswith(prefix)
                ):
                    raise VerificationError(f"unsafe archive member: {name!r}")
                if name in seen_members:
                    raise VerificationError(f"duplicate archive member: {name!r}")
                seen_members.add(name)
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise VerificationError(f"archive contains a symbolic link: {name}")
                if info.is_dir():
                    continue
                relative = name[len(prefix):]
                if not _safe_relative(relative):
                    raise VerificationError(f"unsafe archive member: {name!r}")
                if relative in files:
                    raise VerificationError(f"duplicate relative archive member: {relative}")
                files[relative] = archive.read(info)
    except zipfile.BadZipFile as exc:
        raise VerificationError(f"invalid ZIP archive {path}: {exc}") from exc
    return files


def _digest(value: bytes | None) -> str | None:
    return None if value is None else sha256_bytes(value)


def _actual_changes(
    base: dict[str, bytes], canonical: dict[str, bytes]
) -> dict[str, tuple[str | None, str | None, str]]:
    result: dict[str, tuple[str | None, str | None, str]] = {}
    for path in sorted(set(base) | set(canonical)):
        before = base.get(path)
        after = canonical.get(path)
        if before == after:
            continue
        if before is None:
            kind = "add"
        elif after is None:
            kind = "delete"
        else:
            kind = "replace"
        result[path] = (_digest(before), _digest(after), kind)
    return result


def _verify_embedded_provenance(manifest: dict, canonical: dict[str, bytes]) -> None:
    try:
        provenance = json.loads(canonical["PARITY-SOURCE.json"].decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"canonical PARITY-SOURCE.json is invalid: {exc}") from exc
    if not isinstance(provenance, dict):
        raise VerificationError("canonical PARITY-SOURCE.json must be a JSON object")
    for manifest_key, provenance_key in (
        ("base_archive_sha256", "base_archive_sha256"),
        ("base_provenance_sha256", "base_provenance_sha256"),
        ("base_git_commit", "base_git_commit"),
        ("base_tree_oid", "base_tree_oid"),
        ("base_tag_object", "base_tag_object"),
        ("base_tag_signed", "base_tag_signed"),
        ("target_sync_commit", "target_sync_commit"),
        ("capabilities_sha256", "capabilities_sha256"),
    ):
        if provenance.get(provenance_key) != manifest.get(manifest_key):
            raise VerificationError(
                f"embedded provenance {provenance_key} does not match overlay manifest"
            )
    expected_overlays = []
    for item in manifest["changes"]:
        role = item.get("provenance_role")
        if role is None:
            continue
        expected_overlays.append({
            "path": item["path"],
            "role": role,
            "origin": item.get("provenance_origin", item["origin"]),
            "sha256": item["result_sha256"],
        })
    if provenance.get("overlays") != expected_overlays:
        raise VerificationError(
            "embedded provenance overlay list does not match overlay manifest"
        )


def _verify_origins(manifest: dict, target: Path) -> None:
    root = target.resolve()
    for item in manifest["changes"]:
        origin = item.get("origin")
        if origin is None:
            continue
        candidate = (root / Path(*PurePosixPath(origin).parts)).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise VerificationError(f"overlay origin escapes target: {origin}") from exc
        if not candidate.is_file():
            raise VerificationError(f"overlay origin does not exist: {origin}")
        actual = sha256_file(candidate)
        if actual != item["result_sha256"]:
            if (
                item["path"] == "parity/capabilities.json"
                and actual == manifest.get("working_tree_capabilities_sha256")
            ):
                continue
            if (
                item["path"] == "tools/parity.py"
                and actual == manifest.get("working_tree_parity_sha256")
            ):
                continue
            raise VerificationError(
                f"overlay origin digest mismatch for {origin}: "
                f"expected {item['result_sha256']}, got {actual}"
            )


def _target_parity_output(
    manifest: dict, canonical: dict[str, bytes], top_level: str, target: Path
) -> str:
    """Run historical parity only for a matching target; otherwise record the
    declared working-tree parity mode without claiming archive parity."""

    target_manifest = target.resolve() / "parity/capabilities.json"
    target_digest = sha256_file(target_manifest) if target_manifest.is_file() else None
    historical_digest = manifest.get("capabilities_sha256")
    working_tree_digest = manifest.get("working_tree_capabilities_sha256")
    if target_digest == historical_digest:
        return _run_parity(canonical, top_level, target)
    if target_digest == working_tree_digest:
        return (
            "WORKING-TREE PARITY DEFERRED: target uses the declared "
            "working-tree capabilities manifest; historical archive parity "
            "is attested independently."
        )
    raise VerificationError(
        "target parity manifest is neither the historical canonical digest "
        "nor the declared working-tree digest"
    )


def _run_parity(canonical: dict[str, bytes], top_level: str, target: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="solo-suite-overlay-verify-") as temp:
        source = Path(temp) / top_level
        for relative, content in canonical.items():
            destination = source.joinpath(*PurePosixPath(relative).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        checker = source / "tools/parity.py"
        result = subprocess.run(
            [
                sys.executable,
                str(checker),
                "check",
                "--source",
                str(source),
                "--target",
                str(target.resolve()),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        if result.returncode:
            raise VerificationError(
                "canonical source/target parity failed:\n"
                f"{result.stdout}{result.stderr}"
            )
        return result.stdout.strip()


def verify(
    base_archive: Path,
    canonical_archive: Path,
    manifest_path: Path,
    target: Path | None = None,
    base_provenance: Path | None = None,
    *,
    provenance_already_verified: bool = False,
) -> tuple[int, str | None]:
    manifest = load_manifest(manifest_path)
    if base_provenance is not None:
        verify_base_provenance(base_provenance.resolve(), manifest)
    elif manifest.get("base_provenance_sha256") and not provenance_already_verified:
        raise VerificationError(
            "full overlay verification requires the pinned base provenance record"
        )
    top_level = manifest["top_level_folder"]
    base = read_archive(
        base_archive.resolve(), manifest["base_archive_sha256"], top_level
    )
    canonical = read_archive(
        canonical_archive.resolve(), manifest["canonical_archive_sha256"], top_level
    )
    expected = {
        item["path"]: (
            item["base_sha256"],
            item["result_sha256"],
            item["change"],
        )
        for item in manifest["changes"]
    }
    actual = _actual_changes(base, canonical)
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        mismatched = sorted(
            path for path in set(expected) & set(actual)
            if expected[path] != actual[path]
        )
        raise VerificationError(
            "archive delta does not match overlay manifest: "
            f"missing={missing}, unexpected={unexpected}, mismatched={mismatched}"
        )
    _verify_embedded_provenance(manifest, canonical)
    parity_output = None
    if target is not None:
        _verify_origins(manifest, target)
        parity_output = _target_parity_output(manifest, canonical, top_level, target)
    return len(actual), parity_output


def verify_canonical_only(
    canonical_archive: Path,
    manifest_path: Path,
    target: Path | None = None,
) -> tuple[int, str | None]:
    """Verify the checked-in canonical archive without downloading the base.

    The archive digest pins every member, so this mode can prove that the
    checked-in result has not changed while deliberately leaving the
    public-base provenance check to the networked mode.  This is useful for
    offline CI/review and is reported separately so it cannot be mistaken for
    full source provenance.
    """

    manifest = load_manifest(manifest_path)
    canonical = read_archive(
        canonical_archive.resolve(),
        manifest["canonical_archive_sha256"],
        manifest["top_level_folder"],
    )
    _verify_embedded_provenance(manifest, canonical)
    for item in manifest["changes"]:
        path = item["path"]
        content = canonical.get(path)
        if item["change"] == "delete":
            if content is not None:
                raise VerificationError(
                    f"canonical archive retains declared deleted path: {path}"
                )
            continue
        if content is None:
            raise VerificationError(
                f"canonical archive lacks declared result path: {path}"
            )
        actual = sha256_bytes(content)
        if actual != item["result_sha256"]:
            raise VerificationError(
                f"canonical result digest mismatch for {path}: "
                f"expected {item['result_sha256']}, got {actual}"
            )
    parity_output = None
    if target is not None:
        _verify_origins(manifest, target)
        parity_output = _target_parity_output(
            manifest, canonical, manifest["top_level_folder"], target
        )
    return len(manifest["changes"]), parity_output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base_group = parser.add_mutually_exclusive_group()
    base_group.add_argument("--base-archive", type=Path)
    base_group.add_argument(
        "--fetch-public-base", action="store_true",
        help="download and authenticate the base asset/provenance URLs pinned in the manifest",
    )
    base_group.add_argument(
        "--canonical-only", action="store_true",
        help="verify the checked-in canonical archive and embedded provenance without downloading the base",
    )
    parser.add_argument("--canonical-source-archive", type=Path, required=True)
    parser.add_argument(
        "--base-provenance", type=Path,
        help="source builder provenance paired with --base-archive",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--target", type=Path)
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest)
        if args.fetch_public_base:
            with tempfile.TemporaryDirectory(prefix="solo-suite-public-base-") as temp:
                # ``load_manifest`` and ``fetch_public_base`` both validate the
                # name; retain the explicit guard at the sink so this remains
                # safe if this path is refactored to receive a different
                # manifest object later.
                archive_name = manifest.get("base_archive")
                if not is_safe_plain_filename(archive_name):
                    raise VerificationError(
                        "overlay manifest has an invalid base_archive filename"
                    )
                base_archive = fetch_public_base(manifest, Path(temp) / archive_name)
                count, parity_output = verify(
                    base_archive,
                    args.canonical_source_archive,
                    args.manifest,
                    args.target,
                    provenance_already_verified=True,
                )
        elif args.base_archive is not None:
            count, parity_output = verify(
                args.base_archive,
                args.canonical_source_archive,
                args.manifest,
                args.target,
                args.base_provenance,
            )
        elif args.canonical_only:
            count, parity_output = verify_canonical_only(
                args.canonical_source_archive,
                args.manifest,
                args.target,
            )
        else:
            parser.error(
                "one of --base-archive, --fetch-public-base, or --canonical-only is required"
            )
    except (OSError, VerificationError) as exc:
        parser.error(str(exc))
    if args.fetch_public_base:
        print("PUBLIC BASE PASS: authenticated pinned asset and provenance record")
    elif args.canonical_only:
        print(
            "OFFLINE CANONICAL PASS: checked-in archive digest and embedded "
            "provenance verified (public base not downloaded)"
        )
    print(f"OVERLAY PASS: {count} exact archive differences verified")
    if parity_output:
        print(parity_output)
    caveat = load_manifest(args.manifest)["provenance_caveat"]
    print(f"PROVENANCE CAVEAT: {caveat}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
