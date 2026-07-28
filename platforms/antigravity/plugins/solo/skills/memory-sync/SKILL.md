---
name: memory-sync
description: Mirror the project's .solo/ memory out to external tools so status and notes live where you want them — an Obsidian vault (project notes, linked and searchable) and a Grafana dashboard (project health metrics and release/audit annotations). Use when the user says sync, "push to Obsidian", "update my vault", "sync to Grafana", "project dashboard", mirror project status, or wants .solo/ reflected in their notes app or a dashboard. Reads .solo/; writes to the destination idempotently and never deletes the user's own content.
---

# Memory Sync

`.solo/` is the project's source of truth, but you often want it reflected elsewhere — as linked notes in your Obsidian vault, or as a live health dashboard in Grafana. This skill pushes the memory outward: it reads `.solo/`, transforms it for the destination, and writes it **idempotently** (update in place, never duplicate, never delete the user's own content). It's one-way by default — `.solo/` stays authoritative; the destinations are mirrors.

## Setup (both modes)

Read **all** `.solo/*.md` files (the full 16-file contract: project, stack, prd, architecture, api-contract, data-contract, env-contract, design, tasks, decisions, risks, bugs, tests, release, monitoring, handoff). If `.solo/` doesn't exist, there's nothing to sync — offer `/solo:start-session` / initialization first.

Sync targets are remembered in `.solo/config.md` so you only configure them once. **`.solo/config.md` may contain ONLY non-secrets**:

- the service URL (e.g. the Grafana base URL)
- non-secret resource identifiers (dashboard UID, datasource name, vault path)
- the **name** of the environment variable that holds the token (e.g. `token_env: GRAFANA_API_TOKEN`) — **never the token value itself**

**Token handling rules (hard requirements):**

- Read token values from the named environment variable (or the OS secret store / keychain / credential manager) at run time. If the variable is unset, stop and tell the user how to set it — do not ask them to paste the token into chat or into any file.
- On first configuration, **add `.solo/config.md` to `.gitignore` automatically** (create `.gitignore` if needed) and tell the user; local settings must never be committed.
- **Never sync secrets**: exclude `.solo/config.md`, `.env*`, and anything matching secret patterns from Obsidian notes, Grafana dashboards, and annotations. The env-contract note syncs variable *names* only, never values.
- **Redact logs and reports**: URLs are fine; tokens, Authorization headers, and cookie values never appear in output, even on error. Print `Authorization: Bearer ***redacted***` style placeholders when echoing requests.

### Safety: preview first, confirm before writing

This skill is **manual-only at the execution boundary**: invoke the user-facing `/solo:sync-obsidian` or `/solo:sync-grafana` command, and never perform an external write merely because this skill was loaded for planning or routing. Every external write is gated:

1. **Default is a dry run.** First produce a preview: which notes/dashboard/annotations *would* be created or updated, with a diff-style summary. No external write happens in the preview.
2. **Explicit confirmation** ("yes, apply") is required before any write to the vault, the Grafana API, or any other destination.
3. Report exactly what was written afterward, so re-runs stay idempotent and auditable.

## Mode: Obsidian (`/solo:sync-obsidian`)

Mirror the memory into an Obsidian vault as clean, linked markdown notes — turning project memory into part of your second brain.

1. **Vault location**: ask for the vault path (or a subfolder like `Vault/Projects/<name>/`) on first run; store it in `.solo/config.md`. If a Desktop Commander / Obsidian-vault tool is available, use it to write files; otherwise write markdown to the given path.
2. **Note mapping** — one note per memory file, under a project folder, with Obsidian frontmatter (`tags`, `updated`) and wikilinks between them:
   - `<Project> — Overview` (index / MOC) linking to all the others, with a status line (task counts, current focus from `handoff.md`).
   - One note per memory file that exists: `<Project> — Stack`, `— PRD`, `— Architecture`, `— API Contract`, `— Data Contract`, `— Env Contract`, `— Design`, `— Tasks`, `— Decisions`, `— Risks`, `— Bugs`, `— Tests`, `— Release`, `— Monitoring`, `— Handoff` (skip files that don't exist yet).
   - Convert `tasks.md` sections into checkbox lists Obsidian renders natively; keep stable T-IDs so links/queries stay valid. Convert `decisions.md` entries into a dated log (optionally one note, or a `Decisions/` folder for Dataview).
3. **Idempotent update**: match notes by their stable names and rewrite their content in place — don't create `Tasks 1`, `Tasks 2`. Preserve anything the user added to a note outside the managed section (write the synced content between clear `<!-- solo:begin --> … <!-- solo:end -->` markers so hand-written notes above/below survive). **Never delete** user notes.
4. **Report**: list which notes were created vs updated and the vault path.

## Mode: Grafana (`/solo:sync-grafana`)

Push project **health** to Grafana so a solo dev gets the team-style dashboard view — burndown, blockers, audit findings, release markers. Because `.solo/` is markdown (not a time-series store), sync means two things:

1. **Dashboard definition**: generate/refresh a Grafana dashboard JSON with panels for the metrics derivable from memory — open vs done vs blocked task counts (stat panels), tasks-done-over-time (from the dates in `decisions.md`/`tasks.md` Done entries), open audit findings by severity (from audit tasks written back by site-doctor/stack audits), and a table of current blockers. If a **Grafana connector/MCP or API** is available (URL and dashboard UID from `.solo/config.md`; token from the environment variable named there), create/update the dashboard directly (match by UID so it updates in place, not duplicates); otherwise emit the dashboard JSON for the user to import.
2. **Annotations / events**: post Grafana annotations for meaningful moments so they show as markers on the dashboard/time-series — releases (from `/release:*` activity), audits run, and key decisions from `decisions.md`. Via the connector/API if present; otherwise emit the annotation payloads. Store processed IDs so re-running doesn't double-post.
3. **Metrics source (optional, if they want live trends)**: if the project already ships metrics to a datasource (Prometheus/Loki/etc. — check `stack.md`), point panels at it and keep the memory-derived panels alongside. Don't stand up new infrastructure unprompted.
4. **Report**: dashboard UID/URL (or the exported JSON), and which annotations were posted.

> Interpretation note: this mode reads "Grapify" as **Grafana** (a dashboard pairs naturally with Obsidian notes as the two places to mirror project state). If you meant a different tool (e.g. Shopify, or another destination), say so — the skill's structure (read `.solo/` → transform → write idempotently → remember target in `config.md`) ports directly to any destination, and adding a mode is small.

## Principles (both modes)

- **`.solo/` is authoritative**; destinations are one-way mirrors unless the user explicitly asks for two-way (which needs conflict handling — don't do it silently).
- **Idempotent**: re-running updates in place; no duplicates, no churn.
- **Non-destructive**: never delete or overwrite the user's own notes/dashboards; write managed content inside markers and match by stable IDs/UIDs.
- **Config once**: remember targets in `.solo/config.md` (non-secrets only: URLs, UIDs, paths, env-var *names*); don't re-ask every run. Keep it gitignored.
- **Secrets stay out**: token values live in environment variables or the OS secret store, never in `.solo/`, never in synced content, never in logs.
- **Preview → confirm → write**: external writes only after an explicit dry-run preview and user confirmation.
- **Degrade gracefully**: use a connector/MCP/API when available; otherwise produce the file/JSON/payloads for manual import and say so.

## Working with other skills & plugins

This runs on the memory that every other skill maintains — so the richer your `.solo/` (PRD, tasks, decisions, audit findings written back by site-doctor and the `/stack:audit-*` skills), the more useful the sync. Good fit at the end of a session (after `/solo:end-session`) or on a release, to snapshot state into your notes and dashboard.

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start and `/solo:end-session` saves it at the end. Syncing typically runs right after end-session (or on a release) to mirror the just-saved state outward. Keep `.solo/` current so what you sync is accurate.
