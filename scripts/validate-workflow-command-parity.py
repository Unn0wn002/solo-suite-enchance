#!/usr/bin/env python3
"""Validate that .claude/commands/ and .agents/workflows/ stay in parity.

Claude's slash commands and Antigravity's workflows are meant to carry the
same content under matching filenames (the 2026-08-07 audit found 9 of 11
pairs byte-identical, one intentional rename, and two workflow-only files).
Skills have sync-agent-skills.py + validate-agent-skills.py; roles/agents have
generate-agent-adapters.py; commands/workflows had no equivalent script,
which is exactly why that drift went undetected. This validator closes that
gap for *new* drift without breaking on the currently-known, explicitly
reviewed exceptions below — do not add to the allowlists silently; each entry
must be justified.
"""

from __future__ import annotations

import sys
from pathlib import Path

from agent_platform_common import ROOT, relative

COMMANDS_DIR = ROOT / ".claude" / "commands"
WORKFLOWS_DIR = ROOT / ".agents" / "workflows"

# workflow filename -> command filename, when content is identical but names
# differ. Reviewed 2026-08-07.
ALLOWED_RENAMES: dict[str, str] = {
    "planning.md": "plan.md",  # predates the command being named plan.md
}

# Workflow-only files with no .claude/commands/ counterpart, and why.
# Reviewed 2026-08-07.
ALLOWED_ORPHAN_WORKFLOWS: dict[str, str] = {
    "full-audit.md": "Uses the agent-extension-audit skill under the full-audit "
    "profile; no Claude slash-command wrapper has been authored for it.",
    "role-handoff.md": "Generic role/profile handoff ritual; no Claude "
    "slash-command wrapper has been authored for it.",
}

# Command-only files with no .agents/workflows/ counterpart, and why.
ALLOWED_ORPHAN_COMMANDS: dict[str, str] = {}

# Matching-filename pairs allowed to differ in content, and why. Found by
# this validator itself on 2026-08-07 (not previously documented): a
# genuinely new, reviewed exception, not silent drift.
ALLOWED_CONTENT_DIFFERENCES: dict[str, str] = {
    "graphify.md": "Claude's version uses $ARGUMENTS (Claude's slash-command "
    "templating syntax); Antigravity's workflow uses plain-English phrasing "
    "since $ARGUMENTS is Claude-specific and doesn't apply there.",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    if not COMMANDS_DIR.is_dir() or not WORKFLOWS_DIR.is_dir():
        print(
            f"ERROR: expected both {relative(COMMANDS_DIR)} and {relative(WORKFLOWS_DIR)} to exist",
            file=sys.stderr,
        )
        return 1

    commands = {p.name: p for p in COMMANDS_DIR.glob("*.md")}
    workflows = {p.name: p for p in WORKFLOWS_DIR.glob("*.md")}
    errors: list[str] = []

    # 1. Matching filenames must carry identical content, unless explicitly
    #    documented above.
    for name in sorted(set(commands) & set(workflows)):
        if name in ALLOWED_CONTENT_DIFFERENCES:
            continue
        if read(commands[name]) != read(workflows[name]):
            errors.append(
                f"{relative(commands[name])} and {relative(workflows[name])} "
                "share a filename but differ in content — add to "
                "ALLOWED_CONTENT_DIFFERENCES if intentional"
            )

    # 2. Workflow-only names: must be a documented orphan, a documented
    #    rename with matching content, or it's new/undeclared drift.
    for name in sorted(set(workflows) - set(commands)):
        if name in ALLOWED_ORPHAN_WORKFLOWS:
            continue
        workflow_text = read(workflows[name])
        renamed_to = ALLOWED_RENAMES.get(name)
        if renamed_to and renamed_to in commands and read(commands[renamed_to]) == workflow_text:
            continue
        match = next((c for c, p in commands.items() if read(p) == workflow_text), None)
        if match:
            errors.append(
                f".agents/workflows/{name} matches .claude/commands/{match}'s content under "
                "an undeclared different name — add it to ALLOWED_RENAMES if intentional, "
                "or rename one file to match the other"
            )
        else:
            errors.append(
                f".agents/workflows/{name} has no .claude/commands/ counterpart and is not "
                "in ALLOWED_ORPHAN_WORKFLOWS — add a Claude command wrapper, or document why "
                "it stays workflow-only"
            )

    # 3. Command-only names: the symmetric check. Also consult
    #    ALLOWED_RENAMES in reverse (it's keyed workflow -> command).
    renames_by_command = {command: workflow for workflow, command in ALLOWED_RENAMES.items()}
    for name in sorted(set(commands) - set(workflows)):
        if name in ALLOWED_ORPHAN_COMMANDS:
            continue
        command_text = read(commands[name])
        renamed_from = renames_by_command.get(name)
        if renamed_from and renamed_from in workflows and read(workflows[renamed_from]) == command_text:
            continue
        match = next((w for w, p in workflows.items() if read(p) == command_text), None)
        if match:
            errors.append(
                f".claude/commands/{name} matches .agents/workflows/{match}'s content under "
                "an undeclared different name — add it to ALLOWED_RENAMES if intentional, "
                "or rename one file to match the other"
            )
        else:
            errors.append(
                f".claude/commands/{name} has no .agents/workflows/ counterpart and is not "
                "in ALLOWED_ORPHAN_COMMANDS — add an Antigravity workflow wrapper, or document "
                "why it stays command-only"
            )

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Workflow/command parity validation failed with {len(errors)} error(s)", file=sys.stderr)
        return 1

    matched = len(set(commands) & set(workflows))
    documented = (
        len(ALLOWED_RENAMES)
        + len(ALLOWED_ORPHAN_WORKFLOWS)
        + len(ALLOWED_ORPHAN_COMMANDS)
        + len(ALLOWED_CONTENT_DIFFERENCES)
    )
    print(
        f"Workflow/command parity validation passed: {matched} matched pair(s), "
        f"{documented} documented exception(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
