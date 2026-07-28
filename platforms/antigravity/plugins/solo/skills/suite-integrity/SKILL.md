---
name: suite-integrity
description: Self-check the solo-suite installation and the project's .solo/ memory — validate every plugin.json, confirm every command has a title, purpose, inputs, and output format, confirm every skill has a SKILL.md, verify README and marketplace counts match reality, detect duplicate command names and broken cross-references, validate bundled AgentRooms templates, and report missing .solo/ memory files. Use when the user says self-check, "check the suite", "is everything wired", suite health, plugin integrity, or after adding/renaming commands or skills.
---

# Suite Integrity (self-check)

A suite this size drifts — a renamed command leaves a dangling reference, a README count goes stale, a memory file never gets created. This skill catches that mechanically instead of hoping.

## How to run it
The mechanical checks live in a stdlib-only script — run it first and use its report as evidence:

```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/suite-integrity/scripts/self_check.py" <suite_root> <project_root>
```

- `suite_root` — the folder containing `.claude-plugin/marketplace.json` (it also auto-walks up from the current directory).
- `project_root` — the folder whose `.solo/` should be checked; pass `-` to skip memory checks (e.g. when checking the suite repo itself).

## What it verifies
1. **Every `plugins/*/.claude-plugin/plugin.json` is valid JSON** with `name`, `version`, `description`.
2. **Every command file has**: a title (the file/heading), a purpose (`description:` frontmatter), inputs (`argument-hint:` or `$ARGUMENTS` in the body), and an output format (an `
## What a clean run does — and does not — prove

A clean self-check means the suite's FILES are consistent: manifests parse and carry the required fields, commands/skills have valid official frontmatter, helper references and `${CLAUDE_PLUGIN_ROOT}` paths resolve, counts match reality, references resolve, room templates pass the schema validator, and versions agree. It is **static structure checking — not proof that the suite is healthy at runtime**. It does not execute the helpers against real targets, does not validate gate judgment quality, and cannot detect a well-formed but wrong instruction. Say so in the report. The script also supports **installed-plugin mode**: pointed at a single plugin directory (as in a plugin cache, with no marketplace.json), it validates that plugin's commands, skills, and helper paths.

## Output` or `## Status` section).
3. **Every skill directory has a `SKILL.md`** whose frontmatter is exactly `name` + `description`.
4. **README counts match reality** — plugins, skills, commands, scripts.
5. **`marketplace.json` is correct** — every plugin registered, metadata counts match the filesystem, every `source` path exists.
6. **No duplicate command names** within a plugin (cross-plugin repeats are fine — they're namespaced).
7. **No broken references** — every `/<plugin>:<command>` reference and every skill mention (bolded `**skill**` or unbolded "use the X skill") in a command or skill actually exists; marketplace descriptions only reference existing commands.
8. **No missing `.solo/` memory files** — reports which of the 16 standard files are absent (missing files are a warning, not an error: they're created on first write).
9. **Versions agree** — the CHANGELOG's top entry matches `marketplace.json` `metadata.version`, and the cheatsheet docx version matches site-doctor's `plugin.json`.
10. **AgentRooms templates are structurally valid** — each bundled `agentsrooms/*.json` passes `validate_rooms.py`: every seat in exactly one stage, handoffs only to existing seats in strictly later stages, one writer per artifact per stage, explicit exit gate/criteria, and every referenced command exists.

## After the script
Interpret, don't just paste: group failures by cause, fix what's mechanical (counts, dangling refs) or turn the rest into `.solo/tasks.md` entries. A clean run is the definition of "the suite is healthy"; run it after any change to plugins, and at the start of a project to see which memory files exist yet.

## Output
End every run with these seven sections:
1. **Summary** — what was checked or created.
2. **Findings / Work done** — what was found, changed, or decided.
3. **Risks** — anything uncertain, dangerous, incomplete, or blocked.
4. **Required fixes** — must-fix items before moving forward.
5. **Suggested tasks** — concrete entries for `.solo/tasks.md`, each with a stable T-ID.
6. **Verification** — how to prove the result works.
7. **Next command** — the exact next slash command to run.

## Session lifecycle
Runs inside a session the solo plugin bookends: `/solo:start-session` restores `.solo/` context at the start and `/solo:end-session` saves it at the end. Read `.solo/` before acting; write findings, decisions, and tasks back (stable T-IDs) so the next command — or the next agent — picks up cleanly.
