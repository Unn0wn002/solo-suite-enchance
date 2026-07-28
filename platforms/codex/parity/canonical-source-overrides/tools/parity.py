#!/usr/bin/env python3
"""Check the Claude source and Codex adapter for capability parity.

The checker intentionally uses only Python's standard library.  The Claude
checkout is the canonical source of commands, specialist skills, and shared
helpers; the Codex checkout is an adapter and is allowed only the small set of
runtime differences declared below.  ``generate`` records a deterministic
manifest in the canonical checkout.  ``check`` compares both checkouts to
that manifest and reports every mismatch before returning a non-zero status.

Examples::

    python tools/parity.py generate --source C:/src/solo-suite-v1.0.27-work
    python tools/parity.py --check --source C:/src/solo-suite-v1.0.27-work \
        --target C:/src/solo-suite-codex-v1.0.27

``--generate`` is accepted as an alias for the ``generate`` subcommand.  The
manifest deliberately contains relative paths and hashes only; no workstation
paths or timestamps are written, so it can be reviewed and committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable, Iterator


SCHEMA = "solo-suite/capability-parity-v1"
EXPECTED_PLUGIN_COUNT = 18
EXPECTED_COMMAND_COUNT = 102
EXPECTED_SPECIALIST_COUNT = 56
EXPECTED_TARGET_SKILL_COUNT = 159

# Codex requires one standardized user-facing footer on every skill.  It is a
# platform output contract, not content migrated from any individual Claude
# command/skill, so normalized parity removes only this exact terminal block.
# The older generated one-line footer is likewise ignored only on an exact
# match (before or after the declared terminology translation); detailed
# output sections remain part of the parity hash.
STANDARDIZED_OUTPUT_CONTRACT = """## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation)."""
LEGACY_OUTPUT_CONTRACTS = {
    "End with the 7-part contract: **Summary · Findings/Work done · Risks · "
    "Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) "
    "**· Verification · Next command** (exact slash command).",
    "End with the 7-part contract: **Summary · Findings/Work done · Risks · "
    "Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) "
    "**· Verification · Next skill** (exact skill invocation).",
}

COMMAND_TITLE_ACRONYMS = {
    "a11y": "A11y",
    "ai": "AI",
    "api": "API",
    "authz": "AuthZ",
    "ci": "CI",
    "db": "DB",
    "e2e": "E2E",
    "prd": "PRD",
    "qa": "QA",
    "rls": "RLS",
    "seo": "SEO",
    "ui": "UI",
    "ux": "UX",
}

# These are genuine platform adapters, not missing capabilities.  Their
# canonical Claude files are retained byte-for-byte under parity/claude-rooms
# (AgentRooms) or are implemented by the Codex self-checker (suite-integrity).
WAIVER_SKILLS = {
    "ai:agent-room-templates": "codex-native AgentRoom runtime and trust journal",
    "solo:suite-integrity": "Codex source-checkout/installed-plugin integrity checker",
}

# Codex ships one orchestration skill which has no Claude command equivalent.
ALLOWED_EXTRA_SKILLS = {"full-team:full-team-orchestrator"}

# These six files are deliberately Codex-native gate runtime support.  They
# are not silently ignored: their exact relative paths are recorded in the
# manifest and the target inventory must contain no other unexplained extras.
ALLOWED_NATIVE_FILES = {
    "plugins/gate/skills/production-readiness-reviewer/references/gate-evidence-v1.schema.json",
    "plugins/gate/skills/production-readiness-reviewer/references/project-profile-v1.schema.json",
    "plugins/gate/skills/production-readiness-reviewer/references/score-evidence-v1.schema.json",
    "plugins/gate/skills/production-readiness-reviewer/scripts/validate_gate_evidence.py",
    "plugins/gate/skills/quality-gatekeeper/references/phase-gate-evidence-v1.schema.json",
    "plugins/gate/skills/quality-gatekeeper/scripts/validate_phase_gate_evidence.py",
}

# Shared helper libraries are part of the capability surface even though they
# live one level above a skill directory.
SHARED_ROOTS = (
    "plugins/gate/lib",
    "plugins/site-doctor/lib",
)

IGNORE_NAMES = {"__pycache__"}
IGNORE_SUFFIXES = {".pyc", ".pyo"}


class ParityError(RuntimeError):
    """A source or target parity invariant failed."""


def normal_path(path: Path) -> str:
    """Return a stable, POSIX-style relative path for a manifest entry."""

    return path.as_posix()


def sha256(path: Path) -> str:
    if path.is_symlink():
        raise ParityError(f"symlink is not an acceptable parity file: {path}")
    try:
        data = path.read_bytes()
    except OSError as exc:  # pragma: no cover - exercised by filesystem errors
        raise ParityError(f"cannot read {path}: {exc}") from exc
    return hashlib.sha256(data).hexdigest()


def iter_files(root: Path) -> Iterator[Path]:
    """Yield regular files below *root*, excluding generated Python caches."""

    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in IGNORE_NAMES for part in path.parts):
            continue
        if path.suffix.lower() in IGNORE_SUFFIXES:
            continue
        yield path


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ParityError(f"invalid JSON {path}: {exc}") from exc


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys and a final newline make the file reproducible across hosts.
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    # ``Path.write_text`` has no ``newline`` parameter on Python 3.9.
    path.write_bytes(text.encode("utf-8"))


def parse_frontmatter(text: str) -> tuple[dict[str, str], str] | None:
    """Parse the small YAML frontmatter dialect used by Solo Suite markdown."""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    header_text = text[4:end]
    # A closing marker must occupy the complete line.  This avoids treating a
    # horizontal rule in a description as frontmatter.
    marker_end = end + len("\n---")
    if marker_end < len(text) and text[marker_end] not in {"\n", ""}:
        return None
    body = text[marker_end + (1 if marker_end < len(text) else 0) :]
    fields: dict[str, str] = {}
    for line in header_text.split("\n"):
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            # Preserve malformed metadata as a field so the normalizer cannot
            # accidentally make an invalid document look equivalent.
            fields[f"__invalid__{len(fields)}"] = line
            continue
        key, value = match.groups()
        if key in fields:
            fields[f"__duplicate__{key}"] = value
        else:
            fields[key] = value
    return fields, body


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            parsed = json.loads(value)
            if isinstance(parsed, str):
                return parsed
        except json.JSONDecodeError:
            pass
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def _translate_skill_text(text: str, plugin: str, skill: str) -> str:
    """Apply the same portable wording transform as the Codex adapter.

    This is intentionally narrow.  It does not perform broad prose rewriting;
    it only translates platform syntax that cannot be identical between Claude
    and Codex installations.
    """

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    def helper_path(match: re.Match[str]) -> str:
        helper = match.group(1)
        if helper == skill:
            return "<skill-root>/"
        return f"<skill-root>/../{helper}/"

    text = re.sub(
        r"\$\{CLAUDE_PLUGIN_ROOT\}/skills/([a-z0-9-]+)/",
        helper_path,
        text,
        flags=re.IGNORECASE,
    )
    text = text.replace(
        "${CLAUDE_PLUGIN_ROOT}/lib/", "<skill-root>/../../lib/"
    )
    text = text.replace("${CLAUDE_PLUGIN_ROOT}", "<resolved-plugin-root>")
    text = re.sub(
        r"(?<![A-Za-z0-9])/(?!/)([a-z0-9-]+):([a-z0-9*-]+)",
        lambda match: f"${match.group(1).lower()}-{match.group(2).lower()}",
        text,
        flags=re.IGNORECASE,
    )
    text = text.replace("CLAUDE.md", "AGENTS.md")
    text = text.replace("Claude Code", "Codex")
    text = re.sub(r"slash commands", "skill invocations", text, flags=re.IGNORECASE)
    text = re.sub(r"slash command", "skill invocation", text, flags=re.IGNORECASE)
    text = text.replace("Next Recommended Command", "Next Recommended Skill")
    text = re.sub(
        r"\bnext command\b",
        lambda match: "Next skill" if match.group(0)[0].isupper() else "next skill",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _canonical_document(text: str) -> str:
    """Normalize frontmatter, line endings, and harmless trailing whitespace."""

    parsed = parse_frontmatter(text)
    if parsed is None:
        body = text
        header = None
    else:
        fields, body = parsed
        # Claude's disable-model-invocation field has no Codex equivalent.  It
        # is intentionally removed only here, not arbitrary metadata.
        fields = {
            key.lower(): value.strip()
            for key, value in fields.items()
            if key.lower() != "disable-model-invocation"
        }
        header = tuple(sorted((key, _unquote(value)) for key, value in fields.items()))

    lines = [line.rstrip() for line in body.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    # A document's final newline is formatting, not capability.  Interior
    # blank lines remain significant and are not collapsed.
    while lines and lines[-1] == "":
        lines.pop()
    body_value = "\n".join(lines)
    if header is None:
        return body_value
    header_value = "\n".join(f"{key}: {value}" for key, value in header)
    return f"---\n{header_value}\n---\n{body_value}"


def _strip_output_contract_adapters(text: str) -> str:
    """Remove only suite-owned output-contract wrappers from parity text."""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    stripped = text.rstrip()
    if stripped.endswith(STANDARDIZED_OUTPUT_CONTRACT):
        stripped = stripped[: -len(STANDARDIZED_OUTPUT_CONTRACT)].rstrip()
    lines = [line for line in stripped.split("\n") if line not in LEGACY_OUTPUT_CONTRACTS]
    return "\n".join(lines).rstrip()


def _normalized_adapter_document(text: str) -> str:
    return _canonical_document(_strip_output_contract_adapters(text))


def normalized_specialist(text: str, plugin: str, skill: str, *, source: bool) -> str:
    if source:
        text = _translate_skill_text(text, plugin, skill)
    return _normalized_adapter_document(text)


def _command_title(value: str) -> str:
    return " ".join(
        COMMAND_TITLE_ACRONYMS.get(word, word[:1].upper() + word[1:])
        for word in value.split("-")
    )


def _command_native_description(description: str) -> str:
    text = re.sub(
        r"/([a-z0-9-]+):([a-z0-9*-]+)",
        lambda match: f"${match.group(1).lower()}-{match.group(2).lower()}",
        description,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"slash commands", "skill invocations", text, flags=re.IGNORECASE)
    return re.sub(r"slash command", "skill invocation", text, flags=re.IGNORECASE)


def _transform_command_body(body: str, dependency_skill_names: Iterable[str]) -> str:
    """Mirror the deterministic body transform in convert_commands_to_skills.mjs."""

    transformed = body.rstrip()
    transformed = transformed.replace(
        'python3 "${CLAUDE_PLUGIN_ROOT}/skills/suite-integrity/scripts/self_check.py"',
        'python "<skill-root>/../suite-integrity/scripts/self_check.py"',
        1,
    )
    transformed = transformed.replace(
        "First run the mechanical checker and treat its report as the evidence:",
        "First resolve `<skill-root>` to the directory containing this `SKILL.md`. "
        "Then run the mechanical checker and treat its report as the evidence:",
        1,
    )
    transformed = re.sub(
        r"for:\s*\$ARGUMENTS",
        "for the user's supplied arguments and surrounding request.",
        transformed,
    )
    transformed = re.sub(
        r"on:\s*\$ARGUMENTS",
        "on the user's supplied arguments and surrounding request.",
        transformed,
    )
    transformed = re.sub(
        r"of:\s*\$ARGUMENTS",
        "of the user's supplied arguments and surrounding request.",
        transformed,
    )
    transformed = re.sub(
        r"audit:\s*\$ARGUMENTS",
        "audit the user's supplied arguments and surrounding request.",
        transformed,
    )
    transformed = re.sub(
        r"\.\s*\$ARGUMENTS",
        ". Apply it to the user's supplied arguments and surrounding request.",
        transformed,
    )
    transformed = re.sub(
        r"Debug this problem:\s*\$ARGUMENTS",
        "Debug the problem described in the user's supplied arguments and surrounding request.",
        transformed,
    )
    transformed = transformed.replace(
        "$ARGUMENTS", "the user's supplied arguments and surrounding request"
    )
    transformed = re.sub(
        r"/([a-z0-9-]+):([a-z0-9*-]+)",
        lambda match: f"${match.group(1).lower()}-{match.group(2).lower()}",
        transformed,
        flags=re.IGNORECASE,
    )

    for name in dependency_skill_names:
        escaped = re.escape(name)
        replacement = f"Use ${name}"
        transformed = re.sub(
            rf"Use the \*\*{escaped}\*\* skill",
            lambda _match, value=replacement: value,
            transformed,
            flags=re.IGNORECASE,
        )
        transformed = re.sub(
            rf"Use the {escaped} skill",
            lambda _match, value=replacement: value,
            transformed,
            flags=re.IGNORECASE,
        )
        transformed = re.sub(
            rf"Use {escaped} skill",
            lambda _match, value=replacement: value,
            transformed,
            flags=re.IGNORECASE,
        )
        transformed = transformed.replace(f"**{name}**", f"${name}")

    replacements = (
        (r"slash commands", "skill invocations", re.IGNORECASE),
        (r"slash command", "skill invocation", re.IGNORECASE),
        (r"skills?/commands?", "skills", re.IGNORECASE),
        (r"commands it runs", "skills it invokes", re.IGNORECASE),
        (r"which command to run", "which skill to invoke", re.IGNORECASE),
        (r"which command to use", "which skill to invoke", re.IGNORECASE),
        (r"Next Recommended Command", "Next Recommended Skill", 0),
        (r"Next command", "Next skill", 0),
        (r"next command", "next skill", 0),
        (r"fix commands", "fix invocations", re.IGNORECASE),
        (r"fix command", "fix invocation", re.IGNORECASE),
    )
    for pattern, replacement, flags in replacements:
        transformed = re.sub(pattern, replacement, transformed, flags=flags)
    return re.sub(
        r"^/…$",
        "No follow-up skill is implied here; choose the next validated skill "
        "for the current workflow.",
        transformed,
        flags=re.MULTILINE,
    )


def source_skill_names(source: Path) -> list[str]:
    names = {
        path.parent.name
        for path in (source / "plugins").glob("*/skills/*/SKILL.md")
    }
    return sorted(names, key=lambda value: (-len(value), value))


def normalized_command_skill(
    source_text: str,
    plugin: str,
    command: str,
    dependency_skill_names: Iterable[str],
) -> str:
    """Return the expected normalized Codex SKILL.md for a Claude command."""

    parsed = parse_frontmatter(source_text)
    if parsed is None:
        raise ParityError(f"command has no frontmatter: {plugin}:{command}")
    metadata, body = parsed
    raw_description = metadata.get("description")
    if raw_description is None:
        raise ParityError(f"command has no description: {plugin}:{command}")
    skill_name = f"{plugin}-{command}"
    display_name = f"{_command_title(plugin)} {_command_title(command)}"
    # The converter treats the command frontmatter value as literal text
    # rather than a general YAML scalar, so parity intentionally does too.
    native_description = _command_native_description(raw_description)
    description = (
        f"{native_description} Use when the user explicitly invokes ${skill_name} "
        f"or asks for this {plugin} {command} workflow."
    )
    converted_body = _transform_command_body(body, dependency_skill_names)
    expected = "\n".join(
        (
            "---",
            f"name: {skill_name}",
            f"description: {json.dumps(description, ensure_ascii=False)}",
            "---",
            "",
            f"# {display_name}",
            "",
            "Follow this workflow using the user's supplied context. Preserve stated "
            "gates, evidence requirements, safety constraints, and output contracts.",
            "",
            converted_body,
            "",
        )
    )
    expected = _translate_skill_text(expected, plugin, skill_name)
    return _normalized_adapter_document(expected)


def normalized_command_target(text: str) -> str:
    return _normalized_adapter_document(text)


def parse_plugin_name(path: Path) -> str:
    value = load_json(path)
    if not isinstance(value, dict) or not isinstance(value.get("name"), str):
        raise ParityError(f"plugin manifest has no string name: {path}")
    return value["name"]


def source_plugins(source: Path) -> list[tuple[str, Path]]:
    root = source / "plugins"
    if not root.is_dir():
        raise ParityError(f"missing plugins directory: {root}")
    result: list[tuple[str, Path]] = []
    for directory in sorted(root.iterdir(), key=lambda item: item.name):
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        manifest = directory / ".claude-plugin" / "plugin.json"
        if not manifest.is_file():
            raise ParityError(f"missing Claude plugin manifest: {manifest}")
        name = parse_plugin_name(manifest)
        if name != directory.name:
            raise ParityError(f"plugin directory/name mismatch: {directory.name} != {name}")
        result.append((name, manifest))
    if len(result) != EXPECTED_PLUGIN_COUNT:
        raise ParityError(
            f"expected {EXPECTED_PLUGIN_COUNT} source plugins, found {len(result)}"
        )
    if len({name for name, _ in result}) != len(result):
        raise ParityError("duplicate source plugin names")
    return result


def source_commands(source: Path) -> list[dict[str, object]]:
    commands: list[dict[str, object]] = []
    dependency_skill_names = source_skill_names(source)
    for plugin in sorted(path.name for path in (source / "plugins").iterdir() if path.is_dir()):
        command_root = source / "plugins" / plugin / "commands"
        if not command_root.is_dir():
            continue
        for path in sorted(command_root.iterdir(), key=lambda item: item.name):
            if not path.is_file() or path.suffix.lower() != ".md":
                continue
            command = path.stem
            skill_name = f"{plugin}-{command}"
            source_text = path.read_text(encoding="utf-8")
            commands.append(
                {
                    "id": f"{plugin}:{command}",
                    "legacy_invocation": f"/{plugin}:{command}",
                    "skill_invocation": f"${skill_name}",
                    "codex_invocation": f"${skill_name}",
                    "plugin": plugin,
                    "command": command,
                    "skill_name": skill_name,
                    "source_path": normal_path(path.relative_to(source)),
                    "target_path": f"plugins/{plugin}/skills/{skill_name}/SKILL.md",
                    "source_sha256": sha256(path),
                    "normalized_sha256": hashlib.sha256(
                        normalized_command_skill(
                            source_text,
                            plugin,
                            command,
                            dependency_skill_names,
                        ).encode("utf-8")
                    ).hexdigest(),
                    "allow_implicit_invocation": False,
                }
            )
    if len(commands) != EXPECTED_COMMAND_COUNT:
        raise ParityError(
            f"expected {EXPECTED_COMMAND_COUNT} source commands, found {len(commands)}"
        )
    ids = [str(item["id"]) for item in commands]
    if len(ids) != len(set(ids)):
        raise ParityError("duplicate source command IDs")
    return commands


def source_specialists(source: Path) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for path in sorted((source / "plugins").glob("*/skills/*/SKILL.md")):
        relative = path.relative_to(source)
        plugin, _, skill = relative.parts[1:4]
        skill_id = f"{plugin}:{skill}"
        text = path.read_text(encoding="utf-8")
        parsed = parse_frontmatter(text)
        if parsed is None:
            raise ParityError(f"specialist skill has no frontmatter: {path}")
        fields, _ = parsed
        if _unquote(fields.get("name", "")) != skill:
            raise ParityError(f"skill frontmatter name mismatch: {path}")
        item: dict[str, object] = {
            "id": skill_id,
            "plugin": plugin,
            "skill": skill,
            "source_path": normal_path(relative),
            "target_path": normal_path(relative),
            "source_sha256": sha256(path),
            "normalized_sha256": hashlib.sha256(
                normalized_specialist(text, plugin, skill, source=True).encode("utf-8")
            ).hexdigest(),
        }
        if skill_id in WAIVER_SKILLS:
            item["adapter_waiver"] = WAIVER_SKILLS[skill_id]
        result.append(item)
    if len(result) != EXPECTED_SPECIALIST_COUNT:
        raise ParityError(
            f"expected {EXPECTED_SPECIALIST_COUNT} source specialist skills, found {len(result)}"
        )
    ids = [str(item["id"]) for item in result]
    if len(ids) != len(set(ids)):
        raise ParityError("duplicate source specialist skill IDs")
    actual_waivers = {item for item in ids if item in WAIVER_SKILLS}
    if actual_waivers != set(WAIVER_SKILLS):
        raise ParityError(
            f"adapter waiver set mismatch: expected {sorted(WAIVER_SKILLS)}, "
            f"found {sorted(actual_waivers)}"
        )
    return result


def _skill_companion_files(source: Path, specialists: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for item in specialists:
        skill_id = str(item["id"])
        if skill_id in WAIVER_SKILLS:
            continue
        root = source / str(item["source_path"]).replace("/SKILL.md", "")
        for path in iter_files(root):
            relative = path.relative_to(source)
            # openai.yaml is a target-only interface file; the Claude source
            # normally has none, but excluding it keeps the contract explicit.
            if relative.name == "openai.yaml" or relative.name == "SKILL.md":
                continue
            result.append(
                {
                    "path": normal_path(relative),
                    "sha256": sha256(path),
                    "kind": "skill-companion",
                }
            )
    return result


def _shared_files(source: Path) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for root_name in SHARED_ROOTS:
        root = source / root_name
        if not root.is_dir():
            raise ParityError(f"missing shared helper root: {root}")
        for path in iter_files(root):
            result.append(
                {
                    "path": normal_path(path.relative_to(source)),
                    "sha256": sha256(path),
                    "kind": "shared-helper",
                }
            )
    return result


def _room_archive(source: Path) -> list[dict[str, object]]:
    root = source / "plugins" / "ai" / "skills" / "agent-room-templates"
    if not root.is_dir():
        raise ParityError(f"missing canonical AgentRoom skill: {root}")
    result: list[dict[str, object]] = []
    for path in iter_files(root):
        relative = path.relative_to(root)
        # The archive is a Claude source snapshot.  If a future source starts
        # shipping an interface file, it should not become an accidental
        # second Codex policy; keep the archive's source files only.
        if relative.parts[:1] == ("agents",) and relative.name == "openai.yaml":
            continue
        result.append(
            {
                "source_path": normal_path(Path("plugins/ai/skills/agent-room-templates") / relative),
                "archive_path": normal_path(Path("parity/claude-rooms") / relative),
                "sha256": sha256(path),
            }
        )
    if not result:
        raise ParityError("canonical AgentRoom archive is empty")
    return result


def build_manifest(source: Path) -> dict[str, object]:
    source = source.resolve()
    plugins = source_plugins(source)
    commands = source_commands(source)
    specialists = source_specialists(source)
    companions = _skill_companion_files(source, specialists) + _shared_files(source)
    companions.sort(key=lambda item: str(item["path"]))
    archive = _room_archive(source)
    archive.sort(key=lambda item: str(item["archive_path"]))

    plugin_records: list[dict[str, object]] = []
    for name, manifest in plugins:
        parsed = load_json(manifest)
        version = parsed.get("version") if isinstance(parsed, dict) else None
        plugin_records.append(
            {
                "id": name,
                "source_path": normal_path(manifest.relative_to(source)),
                "source_sha256": sha256(manifest),
                "source_version": version if isinstance(version, str) else None,
            }
        )

    return {
        "schema": SCHEMA,
        "normalization": [
            "Claude/Codex frontmatter (disable-model-invocation is adapter metadata)",
            "Claude command frontmatter/body to the deterministic Codex skill wrapper",
            "slash command invocations to $plugin-command skill invocations",
            "CLAUDE.md and Claude Code to AGENTS.md and Codex",
            "${CLAUDE_PLUGIN_ROOT} helper paths to <skill-root> portable paths",
            "narrow slash-command/skill-invocation wording only",
            "legacy one-line and exact standardized Codex output-contract wrappers excluded",
        ],
        "counts": {
            "plugins": EXPECTED_PLUGIN_COUNT,
            "source_commands": EXPECTED_COMMAND_COUNT,
            "source_specialist_skills": EXPECTED_SPECIALIST_COUNT,
            "target_skills": EXPECTED_TARGET_SKILL_COUNT,
        },
        "plugins": plugin_records,
        "commands": commands,
        "specialist_skills": specialists,
        "companion_files": companions,
        "agentroom_archive": archive,
        "adapter": {
            "skill_waivers": [
                {"id": key, "reason": WAIVER_SKILLS[key]}
                for key in sorted(WAIVER_SKILLS)
            ],
            "allowed_extra_skills": sorted(ALLOWED_EXTRA_SKILLS),
            "allowed_native_files": sorted(ALLOWED_NATIVE_FILES),
        },
    }


def manifest_path(source: Path) -> Path:
    return source / "parity" / "capabilities.json"


def _record_error(errors: list[str], message: str) -> None:
    errors.append(message)


def _check_file_hash(path: Path, expected: str, errors: list[str], label: str) -> None:
    if not path.is_file():
        _record_error(errors, f"{label}: missing {path}")
        return
    try:
        actual = sha256(path)
    except ParityError as exc:
        _record_error(errors, str(exc))
        return
    if actual != expected:
        _record_error(errors, f"{label}: hash mismatch {path} (expected {expected}, got {actual})")


def _target_skill_ids(target: Path) -> set[str]:
    ids: set[str] = set()
    for path in target.glob("plugins/*/skills/*/SKILL.md"):
        relative = path.relative_to(target)
        if len(relative.parts) >= 4:
            ids.add(f"{relative.parts[1]}:{relative.parts[3]}")
    return ids


def _target_policy_ok(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    matches = re.findall(
        r"(?m)^\s*allow_implicit_invocation\s*:\s*(true|false)\s*(?:#.*)?$",
        text,
    )
    return matches == ["false"]


def _target_frontmatter_name(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    parsed = parse_frontmatter(text)
    if parsed is None:
        return None
    fields, _ = parsed
    value = fields.get("name")
    return _unquote(value) if value is not None else None


def _relative_file_set(root: Path) -> set[str]:
    if not root.is_dir():
        return set()
    return {normal_path(path.relative_to(root)) for path in iter_files(root)}


def _check_command_skills(
    source: Path,
    target: Path,
    commands: Iterable[object],
    dependency_skill_names: Iterable[str],
    errors: list[str],
) -> None:
    """Verify each mapped command-derived skill against its canonical body."""

    for item in commands:
        if not isinstance(item, dict):
            continue
        plugin = str(item["plugin"])
        command = str(item["command"])
        skill = str(item["skill_name"])
        skill_id = f"{plugin}:{skill}"
        source_path = source / str(item["source_path"])
        target_path = target / str(item["target_path"])
        if not source_path.is_file():
            _record_error(errors, f"canonical command missing: {source_path}")
            continue
        _check_file_hash(
            source_path,
            str(item["source_sha256"]),
            errors,
            "canonical command",
        )
        if _target_frontmatter_name(target_path) != skill:
            _record_error(errors, f"command target frontmatter name mismatch: {target_path}")
        if not target_path.is_file():
            _record_error(errors, f"command-derived skill target missing: {target_path}")
            continue
        try:
            expected = normalized_command_skill(
                source_path.read_text(encoding="utf-8"),
                plugin,
                command,
                dependency_skill_names,
            )
            actual = normalized_command_target(target_path.read_text(encoding="utf-8"))
            expected_hash = hashlib.sha256(expected.encode("utf-8")).hexdigest()
            manifest_hash = item.get("normalized_sha256")
            if expected_hash != manifest_hash:
                _record_error(
                    errors,
                    f"stale command normalization hash in manifest: {skill_id} (${skill})",
                )
            if expected != actual:
                _record_error(
                    errors,
                    f"normalized command-derived skill body mismatch: "
                    f"{skill_id} (${skill})",
                )
        except (OSError, UnicodeError, ParityError) as exc:
            _record_error(errors, f"cannot compare command-derived skill {skill_id}: {exc}")


def check_target(source: Path, target: Path, manifest: dict[str, object]) -> list[str]:
    errors: list[str] = []
    counts = manifest.get("counts", {})
    commands = manifest.get("commands", [])
    specialists = manifest.get("specialist_skills", [])
    plugins = manifest.get("plugins", [])
    companions = manifest.get("companion_files", [])
    archive = manifest.get("agentroom_archive", [])
    adapter = manifest.get("adapter", {})

    if not isinstance(counts, dict) or not isinstance(commands, list) or not isinstance(specialists, list):
        return ["manifest has invalid capability sections"]

    # Plugin inventory and Codex manifests.
    expected_plugins = {str(item["id"]) for item in plugins if isinstance(item, dict) and "id" in item}
    target_plugin_dirs = {
        path.name
        for path in (target / "plugins").iterdir()
        if path.is_dir() and not path.name.startswith(".")
    } if (target / "plugins").is_dir() else set()
    if target_plugin_dirs != expected_plugins:
        _record_error(
            errors,
            f"target plugin inventory mismatch (expected {sorted(expected_plugins)}, got {sorted(target_plugin_dirs)})",
        )
    for plugin in sorted(expected_plugins):
        path = target / "plugins" / plugin / ".codex-plugin" / "plugin.json"
        if not path.is_file():
            _record_error(errors, f"missing Codex plugin manifest: {path}")
            continue
        try:
            data = load_json(path)
            if not isinstance(data, dict) or data.get("name") != plugin:
                _record_error(errors, f"Codex plugin manifest name mismatch: {path}")
        except ParityError as exc:
            _record_error(errors, str(exc))

    # Command map is an exact migration contract.  We compare the complete
    # entry objects, including paths, invocation IDs, and explicit-only policy.
    map_path = target / "command-map.json"
    try:
        actual_map = load_json(map_path)
    except ParityError as exc:
        _record_error(errors, str(exc))
        actual_map = None
    expected_map = []
    for item in commands:
        if not isinstance(item, dict):
            continue
        expected_map.append(
            {
                key: item[key]
                for key in (
                    "legacy_invocation",
                    "skill_invocation",
                    "codex_invocation",
                    "plugin",
                    "command",
                    "skill_name",
                    "source_path",
                    "target_path",
                    "allow_implicit_invocation",
                )
            }
        )
    if actual_map != expected_map:
        _record_error(errors, "command-map.json does not exactly match the canonical 102-command map")

    expected_command_skill_ids: set[str] = set()
    for item in commands:
        if not isinstance(item, dict):
            continue
        plugin = str(item["plugin"])
        skill = str(item["skill_name"])
        expected_command_skill_ids.add(f"{plugin}:{skill}")
    _check_command_skills(
        source,
        target,
        commands,
        source_skill_names(source),
        errors,
    )

    # Specialist set and normalized body comparison.  The two declared adapter
    # skills are checked for presence/policy but intentionally not body-equal.
    expected_specialist_ids: set[str] = set()
    for item in specialists:
        if not isinstance(item, dict):
            continue
        skill_id = str(item["id"])
        plugin = str(item["plugin"])
        skill = str(item["skill"])
        expected_specialist_ids.add(skill_id)
        source_path = source / str(item["source_path"])
        target_path = target / str(item["target_path"])
        if not source_path.is_file():
            _record_error(errors, f"canonical specialist missing: {source_path}")
            continue
        _check_file_hash(source_path, str(item["source_sha256"]), errors, "canonical specialist")
        if _target_frontmatter_name(target_path) != skill:
            _record_error(errors, f"specialist target frontmatter name mismatch: {target_path}")
        if skill_id not in WAIVER_SKILLS:
            if not target_path.is_file():
                _record_error(errors, f"specialist target missing: {target_path}")
            else:
                try:
                    expected = normalized_specialist(
                        source_path.read_text(encoding="utf-8"), plugin, skill, source=True
                    )
                    actual = normalized_specialist(
                        target_path.read_text(encoding="utf-8"), plugin, skill, source=False
                    )
                    if expected != actual:
                        _record_error(errors, f"normalized specialist body mismatch: {skill_id}")
                    expected_hash = hashlib.sha256(expected.encode("utf-8")).hexdigest()
                    if expected_hash != str(item["normalized_sha256"]):
                        _record_error(errors, f"stale specialist normalization hash in manifest: {skill_id}")
                except (OSError, UnicodeError) as exc:
                    _record_error(errors, f"cannot compare specialist {skill_id}: {exc}")

    # Exactly the canonical 158 skills plus the one declared Codex extra.
    allowed_extra_ids = set(str(value) for value in adapter.get("allowed_extra_skills", []) if isinstance(value, str)) if isinstance(adapter, dict) else set()
    expected_skill_ids = expected_command_skill_ids | expected_specialist_ids | allowed_extra_ids
    actual_skill_ids = _target_skill_ids(target)
    if actual_skill_ids != expected_skill_ids:
        _record_error(
            errors,
            f"target skill inventory mismatch (expected {len(expected_skill_ids)}, got {len(actual_skill_ids)}; "
            f"missing={sorted(expected_skill_ids - actual_skill_ids)}, extra={sorted(actual_skill_ids - expected_skill_ids)})",
        )
    if len(actual_skill_ids) != EXPECTED_TARGET_SKILL_COUNT:
        _record_error(errors, f"expected {EXPECTED_TARGET_SKILL_COUNT} target skills, found {len(actual_skill_ids)}")

    # Every target skill has exactly one explicit-only policy.  This also
    # catches an adapter waiver accidentally becoming implicitly invokable.
    policy_paths = list(target.glob("plugins/*/skills/*/agents/openai.yaml"))
    if len(policy_paths) != EXPECTED_TARGET_SKILL_COUNT:
        _record_error(errors, f"expected {EXPECTED_TARGET_SKILL_COUNT} openai.yaml policies, found {len(policy_paths)}")
    for path in sorted(policy_paths):
        if not _target_policy_ok(path):
            _record_error(errors, f"policy is not exactly allow_implicit_invocation: false: {path}")

    # Companion files: source skill helpers and shared libraries must be exact
    # byte-for-byte copies.  The target inventory is closed except for the six
    # listed Codex gate runtime files.
    expected_companion_paths = {str(item["path"]) for item in companions if isinstance(item, dict)}
    for item in companions:
        if not isinstance(item, dict):
            continue
        path = target / str(item["path"])
        _check_file_hash(path, str(item["sha256"]), errors, "companion")

    actual_companion_paths: set[str] = set()
    for item in specialists:
        if not isinstance(item, dict) or str(item["id"]) in WAIVER_SKILLS:
            continue
        root = target / str(item["target_path"]).replace("/SKILL.md", "")
        for path in iter_files(root):
            relative = normal_path(path.relative_to(target))
            if relative.endswith("/SKILL.md") or relative.endswith("/agents/openai.yaml"):
                continue
            actual_companion_paths.add(relative)
    for root_name in SHARED_ROOTS:
        actual_companion_paths.update(
            normal_path(path.relative_to(target)) for path in iter_files(target / root_name)
        )
    allowed_native_paths = set(str(value) for value in adapter.get("allowed_native_files", []) if isinstance(value, str)) if isinstance(adapter, dict) else set()
    expected_target_companion_paths = expected_companion_paths | allowed_native_paths
    if actual_companion_paths != expected_target_companion_paths:
        _record_error(
            errors,
            "target companion inventory mismatch: "
            f"missing={sorted(expected_target_companion_paths - actual_companion_paths)}, "
            f"extra={sorted(actual_companion_paths - expected_target_companion_paths)}",
        )
    for path in sorted(allowed_native_paths):
        if not (target / path).is_file():
            _record_error(errors, f"missing allowed Codex-native runtime file: {target / path}")

    # Canonical AgentRoom files are archived in the target so the adapter can
    # be reviewed without pretending that its runtime is byte-identical.
    expected_archive_paths = {str(item["archive_path"]) for item in archive if isinstance(item, dict)}
    archive_root = target / "parity" / "claude-rooms"
    actual_archive_paths = {
        normal_path(path.relative_to(target))
        for path in iter_files(archive_root)
    }
    if actual_archive_paths != expected_archive_paths:
        _record_error(
            errors,
            "canonical AgentRoom archive inventory mismatch: "
            f"missing={sorted(expected_archive_paths - actual_archive_paths)}, "
            f"extra={sorted(actual_archive_paths - expected_archive_paths)}",
        )
    for item in archive:
        if not isinstance(item, dict):
            continue
        _check_file_hash(
            target / str(item["archive_path"]),
            str(item["sha256"]),
            errors,
            "AgentRoom archive",
        )

    # Keep the copied parity artifacts themselves synchronized.  A target that
    # was checked with a stale checker/manifest is not a valid parity result.
    source_manifest = manifest_path(source)
    target_manifest = target / "parity" / "capabilities.json"
    if not target_manifest.is_file():
        _record_error(errors, f"target parity manifest missing: {target_manifest}")
    elif source_manifest.is_file() and source_manifest.read_bytes() != target_manifest.read_bytes():
        _record_error(errors, "target parity/capabilities.json is not an exact copy of the canonical manifest")
    source_tool = source / "tools" / "parity.py"
    target_tool = target / "tools" / "parity.py"
    if source_tool.is_file() and target_tool.is_file() and sha256(source_tool) != sha256(target_tool):
        _record_error(errors, "target tools/parity.py is not an exact copy of the canonical checker")
    if not target_tool.is_file():
        _record_error(errors, f"target parity checker missing: {target_tool}")

    return errors


def generate(source: Path) -> Path:
    source = source.resolve()
    value = build_manifest(source)
    destination = manifest_path(source)
    write_json(destination, value)
    print(
        f"Generated {destination} ({EXPECTED_PLUGIN_COUNT} plugins, "
        f"{EXPECTED_COMMAND_COUNT} commands, {EXPECTED_SPECIALIST_COUNT} specialist skills)"
    )
    return destination


def check(source: Path, target: Path) -> int:
    source = source.resolve()
    target = target.resolve()
    if source == target:
        print("ERROR source and target must be distinct checkouts", file=sys.stderr)
        return 1
    try:
        expected = build_manifest(source)
        path = manifest_path(source)
        if not path.is_file():
            raise ParityError(f"canonical manifest missing: {path}; run parity.py generate first")
        actual = load_json(path)
        if actual != expected:
            raise ParityError("canonical parity/capabilities.json is stale; run parity.py generate")
        errors = check_target(source, target, expected)
    except ParityError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if errors:
        print("FAIL capability parity")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "PASS capability parity: "
        f"{EXPECTED_PLUGIN_COUNT} plugins, {EXPECTED_COMMAND_COUNT} commands, "
        f"{EXPECTED_SPECIALIST_COUNT} specialist skills, {EXPECTED_TARGET_SKILL_COUNT} target skills, "
        f"{len(expected['companion_files'])} exact companions, "
        f"{len(expected['agentroom_archive'])} archived AgentRoom files"
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        nargs="?",
        choices=("generate", "check"),
        help="generate the canonical manifest or check source/target parity",
    )
    parser.add_argument("--generate", action="store_true", help="alias for the generate action")
    parser.add_argument("--check", action="store_true", help="alias for the check action")
    parser.add_argument("--source", type=Path, help="canonical Claude checkout")
    parser.add_argument("--target", type=Path, help="Codex adapter checkout (required for check)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    actions = [name for name, present in (("generate", args.generate), ("check", args.check)) if present]
    if args.action:
        actions.append(args.action)
    if len(set(actions)) != 1:
        parser.error("choose exactly one action: generate/--generate or check/--check")
    action = actions[0]
    source = (args.source or Path(__file__).resolve().parents[1]).resolve()
    if action == "generate":
        try:
            generate(source)
        except ParityError as exc:
            print(f"FAIL {exc}", file=sys.stderr)
            return 1
        return 0
    if args.target is None:
        parser.error("--target is required for check")
    return check(source, args.target)


if __name__ == "__main__":
    raise SystemExit(main())
