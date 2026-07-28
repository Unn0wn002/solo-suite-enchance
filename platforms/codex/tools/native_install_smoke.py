#!/usr/bin/env python3
"""Smoke-test a Solo Suite marketplace through the native Codex CLI.

The check is deliberately isolated from the caller's Codex profile.  A user
can still ask for ``--check-current`` to detect duplicate configured
marketplaces before installing: Codex resolves the first matching marketplace
name, so a stale same-name entry can otherwise install an older tree without a
clear error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]


def _normal_path(value: str | Path) -> str:
    """Return a case-insensitive comparable absolute Windows/POSIX path."""

    text = str(value).strip()
    if text.startswith("\\\\?\\"):
        text = text[4:]
    try:
        return os.path.normcase(str(Path(text).expanduser().resolve()))
    except (OSError, RuntimeError):
        return os.path.normcase(os.path.abspath(text))


def _parse_json_output(raw: str) -> Any:
    """Parse JSON even when a CLI prepends a warning line."""

    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as first:
        starts = [index for index, character in enumerate(text) if character == "{"]
        for index in starts:
            try:
                return json.loads(text[index:])
            except json.JSONDecodeError:
                continue
        raise ValueError("Codex did not return JSON: %s" % first) from first


def _file_hashes(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _run(
    executable: str,
    args: Iterable[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [executable, *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _resolve_codex(requested: str | None) -> str | None:
    if requested:
        path = Path(requested).expanduser()
        return str(path) if path.is_file() else None
    for name in ("codex", "codex.cmd", "codex.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _marketplace(suite_root: Path) -> tuple[str, list[dict[str, Any]]]:
    path = suite_root / ".agents" / "plugins" / "marketplace.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("name"), str):
        raise ValueError("marketplace.json has no string name")
    entries = payload.get("plugins")
    if not isinstance(entries, list) or not entries:
        raise ValueError("marketplace.json has no plugin entries")
    if any(not isinstance(item, dict) or not isinstance(item.get("name"), str)
           for item in entries):
        raise ValueError("marketplace plugin entries are malformed")
    return payload["name"], entries


def _current_collision(
    executable: str, suite_root: Path, marketplace_name: str
) -> str | None:
    """Return a remediation message for duplicate/wrong current entries."""

    env = dict(os.environ)
    result = _run(
        executable, ("plugin", "marketplace", "list", "--json"),
        cwd=suite_root, env=env,
    )
    if result.returncode:
        return None  # The CLI may be present but too old to expose this query.
    try:
        payload = _parse_json_output(result.stdout)
    except ValueError:
        return None
    entries = payload.get("marketplaces") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return None
    matches = [
        item for item in entries
        if isinstance(item, dict) and item.get("name") == marketplace_name
    ]
    expected = _normal_path(suite_root)
    roots = [_normal_path(item.get("root", "")) for item in matches]
    if len(matches) > 1:
        return (
            "duplicate configured marketplace name %r resolves to %s; "
            "remove every stale entry and re-add the intended root %s"
            % (marketplace_name, ", ".join(roots), expected)
        )
    if matches and roots[0] != expected:
        return (
            "configured marketplace %r points to %s, expected %s; "
            "remove the stale entry and re-add the intended root"
            % (marketplace_name, roots[0], expected)
        )
    return None


def _unavailable(reason: str, report_path: Path | None, *, exit_code: int) -> int:
    payload = {
        "schema": "solo-suite/native-install-report-v1",
        "status": "unavailable",
        "reason": reason,
    }
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_bytes(
            (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
    print("UNVERIFIED native Codex install smoke: %s" % reason)
    return exit_code


def smoke(
    suite_root: Path,
    executable: str,
    *,
    check_current: bool = False,
    self_check: bool = True,
) -> dict[str, Any]:
    suite_root = suite_root.resolve()
    marketplace_name, entries = _marketplace(suite_root)
    release = json.loads((suite_root / "RELEASE.json").read_text(encoding="utf-8"))
    expected_version = release.get("version")
    if not isinstance(expected_version, str):
        raise ValueError("RELEASE.json has no version")
    collision = (
        _current_collision(executable, suite_root, marketplace_name)
        if check_current else None
    )
    if collision:
        raise RuntimeError(collision)

    with tempfile.TemporaryDirectory(prefix="solo-suite-native-") as temp:
        isolated = Path(temp)
        codex_home = isolated / ".codex"
        codex_home.mkdir()
        env = dict(os.environ)
        # Codex merges profile-level marketplace state when USERPROFILE/HOME
        # points at the real user.  Isolate all three roots for a deterministic
        # smoke and to prevent stale same-name entries from masking this tree.
        env.update({
            "CODEX_HOME": str(codex_home),
            "USERPROFILE": str(isolated),
            "HOME": str(isolated),
        })
        added = _run(
            executable,
            ("plugin", "marketplace", "add", str(suite_root), "--json"),
            cwd=suite_root,
            env=env,
        )
        if added.returncode:
            raise RuntimeError("marketplace add failed: " + (added.stdout + added.stderr).strip())
        added_payload = _parse_json_output(added.stdout)
        if added_payload.get("marketplaceName") != marketplace_name:
            raise RuntimeError("Codex registered an unexpected marketplace name")
        if _normal_path(added_payload.get("installedRoot", "")) != _normal_path(suite_root):
            raise RuntimeError("Codex registered an unexpected marketplace root")

        installed: list[dict[str, Any]] = []
        for entry in entries:
            name = entry["name"]
            result = _run(
                executable,
                ("plugin", "add", f"{name}@{marketplace_name}", "--json"),
                cwd=suite_root,
                env=env,
            )
            if result.returncode:
                raise RuntimeError(
                    f"{name} install failed: {(result.stdout + result.stderr).strip()}"
                )
            payload = _parse_json_output(result.stdout)
            installed_path = Path(str(payload.get("installedPath", "")))
            if not installed_path.is_dir():
                raise RuntimeError(f"{name} install returned no cache directory")
            source = suite_root / "plugins" / name
            source_hashes = _file_hashes(source)
            installed_hashes = _file_hashes(installed_path)
            if source_hashes != installed_hashes:
                missing = sorted(set(source_hashes) - set(installed_hashes))
                extra = sorted(set(installed_hashes) - set(source_hashes))
                changed = sorted(
                    key for key in set(source_hashes) & set(installed_hashes)
                    if source_hashes[key] != installed_hashes[key]
                )
                raise RuntimeError(
                    f"{name} installed tree differs (missing={missing}, "
                    f"extra={extra}, changed={changed})"
                )
            manifest = json.loads(
                (installed_path / ".codex-plugin" / "plugin.json").read_text(
                    encoding="utf-8"
                )
            )
            if manifest.get("version") != expected_version:
                raise RuntimeError(
                    f"{name} installed version {manifest.get('version')!r} "
                    f"does not match {expected_version!r}"
                )
            check_status = "not_requested"
            if self_check:
                check = _run(
                    sys.executable,
                    (
                        str(suite_root / "plugins/solo/skills/suite-integrity/scripts/self_check.py"),
                        str(installed_path),
                        "-",
                    ),
                    cwd=suite_root,
                    env=env,
                )
                if check.returncode:
                    raise RuntimeError(
                        f"{name} installed-plugin self-check failed: "
                        f"{(check.stdout + check.stderr).strip()}"
                    )
                check_status = "pass_with_warning" if "WARN  " in check.stdout else "pass"
            installed.append({
                "name": name,
                "version": manifest["version"],
                "file_count": len(source_hashes),
                "self_check": check_status,
            })
        return {
            "schema": "solo-suite/native-install-report-v1",
            "status": "pass",
            "marketplace": marketplace_name,
            "version": expected_version,
            "plugin_count": len(installed),
            "plugins": installed,
            "isolation": "CODEX_HOME+USERPROFILE+HOME",
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-root", type=Path, default=ROOT)
    parser.add_argument("--codex", help="path to codex/codex.cmd/codex.exe")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--if-available", action="store_true")
    parser.add_argument("--check-current", action="store_true")
    parser.add_argument("--no-self-check", action="store_true")
    args = parser.parse_args(argv)
    executable = _resolve_codex(args.codex)
    if executable is None:
        return _unavailable(
            "codex executable is unavailable", args.report,
            exit_code=0 if args.if_available else 2,
        )
    try:
        probe = subprocess.run(
            [executable, "plugin", "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _unavailable(
            f"unable to query codex plugin help: {exc}", args.report,
            exit_code=0 if args.if_available else 2,
        )
    if probe.returncode or "marketplace" not in (probe.stdout + probe.stderr).lower():
        return _unavailable(
            "installed Codex CLI has no plugin marketplace commands", args.report,
            exit_code=0 if args.if_available else 2,
        )
    try:
        payload = smoke(
            args.suite_root,
            executable,
            check_current=args.check_current,
            self_check=not args.no_self_check,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        payload = {
            "schema": "solo-suite/native-install-report-v1",
            "status": "fail",
            "reason": str(exc),
        }
        print("FAIL native Codex install smoke: %s" % exc)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_bytes(
                (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
            )
        return 1
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_bytes(
            (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
    print(
        "PASS native Codex install smoke: %d plugin(s), exact installed trees"
        % payload["plugin_count"]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
