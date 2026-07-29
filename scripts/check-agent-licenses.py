#!/usr/bin/env python3
"""Validate source license decisions and third-party attribution."""

from __future__ import annotations

import json
import sys

from agent_platform_common import ROOT, load_json_yaml


UNKNOWN = {"", "UNKNOWN", "NOASSERTION", "NONE", None}


def main() -> int:
    manifest_path = ROOT / "agent-platform" / "manifest.yaml"
    lock_path = ROOT / "agent-platform" / "agent-extensions.lock.json"
    notices_path = ROOT / "THIRD_PARTY_NOTICES.md"
    errors: list[str] = []
    if not manifest_path.is_file() or not lock_path.is_file() or not notices_path.is_file():
        for path in (manifest_path, lock_path, notices_path):
            if not path.is_file():
                errors.append(f"missing {path.relative_to(ROOT).as_posix()}")
    else:
        try:
            manifest = load_json_yaml(manifest_path)
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot parse license inputs: {exc}")
        else:
            notices = notices_path.read_text(encoding="utf-8")
            lock_by_source = {item.get("source"): item for item in lock.get("sources", [])}
            for capability in manifest.get("capabilities", []):
                status = capability.get("status")
                license_id = capability.get("license")
                copied = capability.get("integration_kind") == "copied_component"
                if copied and license_id in UNKNOWN:
                    errors.append(f"{capability.get('canonical_name')}: unknown-license source is marked copied")
                if status in {"ACCEPTED", "ADAPTED", "EXTERNAL_TOOL_ONLY"}:
                    source = capability.get("source_url")
                    if source not in lock_by_source:
                        errors.append(f"{capability.get('canonical_name')}: source missing from lock")
                    if source and source not in notices:
                        errors.append(f"{capability.get('canonical_name')}: source URL missing from THIRD_PARTY_NOTICES.md")
            for source in lock.get("sources", []):
                if source.get("license") in UNKNOWN and source.get("status") not in {"BLOCKED", "QUARANTINED", "REJECTED"}:
                    errors.append(f"{source.get('source')}: unknown license must be blocked or quarantined")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Agent license and attribution validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
