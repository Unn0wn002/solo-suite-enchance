---
name: solo-sync-obsidian
description: "Sync .solo/ project memory into an Obsidian vault as linked, idempotent notes Use when the user explicitly invokes $solo-sync-obsidian or asks for this solo sync-obsidian workflow."
---

# Solo Sync Obsidian

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $memory-sync in Obsidian mode. Apply it to the user's supplied arguments and surrounding request.

Read all of .solo/ and mirror it into an Obsidian vault as clean linked markdown: one note
per memory file that exists (Overview/MOC plus the full 16-file contract: Project, Stack, PRD, Architecture, API/Data/Env Contracts, Design, Tasks, Decisions, Risks, Bugs, Tests, Release, Monitoring, Handoff)
with frontmatter and wikilinks; tasks become native checkboxes keeping stable T-IDs. Ask for
the vault path on first run and remember it in .solo/config.md. Update notes in place
(idempotent - no duplicates), write managed content between solo:begin$solo-end markers so
the user's own note content survives, and NEVER delete their notes. Report which notes were
created vs updated. .solo/ stays the source of truth; the vault is a one-way mirror.


SAFETY: writes to the vault only after a dry-run preview and explicit confirmation; never
sync `.solo/config.md`, `.env*`, or secret values into notes; vault path is remembered in
`.solo/config.md` (non-secrets only, gitignored).

Treat the dry run as a PREVIEW and require EXPLICIT CONFIRMATION before writing any note.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
