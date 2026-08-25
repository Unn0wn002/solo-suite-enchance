# Solo Suite Enchance

Solo Suite Enchance is a cross-platform AI development extension platform for Claude Code, Codex, and Antigravity. It provides portable plugins, skills, commands/workflows, agent roles, shared `.solo/` project memory, Graphify adapters, security checks, and release/validation gates.

## Repository boundary

This repository contains **AI tooling only**. It does not contain, host, deploy, or persist the MysteryMart/Website application or its product data. Application repositories may install or consume Solo Suite, but their application source, runtime configuration, databases, deployment metadata, and business data remain in those application repositories.

The bundled surfaces are:

| Surface | Location |
| --- | --- |
| Portable project skills/rules/workflows | `.agents/` |
| Claude project adapters, commands, permissions | `.claude/` |
| Shared project-memory contract | `.solo/` |
| Agent roles, profiles, manifests, security policy | `agent-platform/` |
| Claude distribution | `platforms/claude/` |
| Codex distribution | `platforms/codex/` |
| Antigravity distribution | `platforms/antigravity/` |
| Validation, audit, bootstrap and installer tooling | `scripts/` |
| Agent-specific audit evidence | `docs/agent-audit/` |

Generic website-development, browser, SEO, frontend, backend, database, and deployment **skills** remain valid AI capabilities. They are instructions for working on other projects; they are not a bundled website application.

## Current repair/update state

The repository includes the consolidated 2026-08-25 repair update: safer command authorization, canonical agent routing, hardened Claude permissions, dependency/security remediation, generated-skill parity, Claude↔Antigravity distribution parity, `/full-audit` command parity, immutable CI action pins, and Linux/Windows distribution validation.

## Validate

```powershell
npm ci
npm test
npm run agent:validate
python scripts/agent-security.py --npm-audit
```

`npm test` validates the generated capability inventory and core tooling contract. `agent:validate` verifies generated mirrors, platform structure, workflow/command parity, distribution parity, licenses, links, generated audit/token reports, and Graphify snapshot consistency.

Graphify is an optional, explicitly provisioned project-local intelligence tool. This distribution does not commit a pre-generated `graphify-out/` snapshot. After explicitly installing the audited Graphify toolchain, a user may generate a graph in the active project when graph-backed analysis is needed.

## Claude Code

Register `platforms/claude/` as the Solo Suite marketplace and install the required plugins. Install `solo` first because it owns the `.solo/` lifecycle. Use `/solo:start-session`, `/solo:run-cycle`, or `/solo:full-team-dev` as appropriate.

## Codex

Register `platforms/codex/` and install the required plugins. Codex exposes migrated workflows as skills; use `platforms/codex/COMMAND-MAP.md` for command-to-skill mappings. Start a new Codex task after installing or updating plugins so newly installed skills are discovered.

## Antigravity

Use the validated adapter under `platforms/antigravity/`. `platforms/antigravity/ANTIGRAVITY.md` documents the Google/Gemini configuration targets and platform assumptions.

## Global user installation

The reviewed Windows installer can promote the audited portable skills and native platform distributions into the current user's agent configuration directories. Inspect targets first:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install-global-agent-platforms.ps1 -WhatIf
```

Then run the installer only when a user-level installation is explicitly wanted. Existing destinations are backed up below `~/.solo-suite-global-backups/`. Graphify remains separately version-pinned and opt-in.

## Repository intelligence

See `CORE_REPOSITORY_INTELLIGENCE.md`. Graphify installation is explicit and project-local; cloning or installing Solo Suite never silently enables hooks, MCP servers, global tool installers, or application dependencies.

## Capability references

- `CAPABILITY_CATALOG.md` — complete native capability catalog.
- `capability-inventory.json` — generated inventory used by tests.
- `CAPABILITY_ROADMAP.md` — phase-owned capability evolution.
- `suite-manifest.json` — platform/distribution summary.
- `THIRD_PARTY_NOTICES.md` — attribution and license notices.

## Safety boundary

Do not commit application secrets, environment files, production data, deployment credentials, or copied application source into this repository. Keep application-specific implementation and data in the application repository that consumes Solo Suite.
