# Agent Platform Installation Guide

No administrator access, global install, symlink, hook, or root MCP activation is required for project-scoped use.

## ChatGPT and Codex

1. Open the repository root so `AGENTS.md` and `.agents/skills/` are in project scope.
2. Run `python scripts/validate-agent-skills.py` and `python scripts/validate-agent-platform.py`.
3. Select one phase profile from `agent-platform/profiles/`; start with `planning.yaml`.
4. Invoke a skill by name when deterministic routing matters. Skill bodies and references load on demand.

The 24 audited `addyosmani/agent-skills` workflows are installed project-locally under `.agents/skills/` by default. Codex/ChatGPT invoke the underlying skill directly. An explicitly requested run of `scripts/install-global-agent-platforms.ps1` promotes the safety-adapted copies into the supported user-level skill roots without activating the excluded upstream hook.

## Claude Code

1. Run `python scripts/sync-agent-skills.py`.
2. Confirm `CLAUDE.md` starts with `@AGENTS.md`.
3. Run `python scripts/sync-agent-skills.py --check`.
4. In an interactive Claude session, inspect `/skills`, `/memory`, `/agents`, `/hooks`, and `/mcp`.
5. Keep source-provided hooks and MCP servers disabled unless separately approved.

Eight lifecycle commands are installed under `.claude/commands/`: `/spec`, `/plan`, `/build`, `/test`, `/review`, `/webperf`, `/code-simplify`, and `/ship`. They include the repository safety overlay. The upstream session-start hook is intentionally absent. The reviewed global installer copies these commands to `~/.claude/commands/` and registers the validated plugin distribution at user scope.

## Google Antigravity and Antigravity CLI

1. Open the repository with review or workspace-only permissions.
2. Confirm discovery of `AGENTS.md`, `.agents/skills/`, `.agents/rules/`, `.agents/workflows/`,
   `.agents/agents/`, and `.agents/agents.md`.
3. Use `/skills` in `agy` when a supported CLI is installed.
4. Follow the manual checklist in `PLATFORM_TEST_REPORT.md`; this host has no Antigravity runtime.

Eight equivalent workflows are installed under `.agents/workflows/`; Antigravity uses `/planning` rather than `/plan` to avoid the platform-reserved plan command. Runtime discovery remains `NOT_EXECUTED` on this host. The reviewed global installer copies them to `~/.gemini/config/global_workflows/` and installs the audited Antigravity plugin and skill trees under `~/.gemini/config/`.

## GSAP runtime

`greensock/GSAP` is installed once as the exact project dependency `gsap@3.15.0`, locked by registry integrity in `package-lock.json`. Agents on every platform use that same dependency through the portable `gsap-animation` skill. No global package, CDN fallback, or package lifecycle script is used.

## Optional audited global promotion

When the user explicitly requests availability across every local project, preview and run the reviewed installer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-global-agent-platforms.ps1 -WhatIf
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-global-agent-platforms.ps1
```

The installer writes only below the current user's `.codex`, `.claude`, `.gemini/config`, and
`.solo-suite-global-backups` directories. It installs exact reviewed copies, registers the local Codex and Claude
marketplaces, enables their 19 plugin trees, and backs up existing destinations before replacement. Restart all
three hosts after installation. It does not globally install Graphify, GSAP, package managers, hooks, or MCP
servers.

To promote only the reviewed Graphify host adapters after the audited `graphify==0.9.32` CLI is available, use:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-global-agent-platforms.ps1 -GraphifyOnly -WhatIf
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-global-agent-platforms.ps1 -GraphifyOnly
```

This adds `$graphify` to Codex, `/graphify` to Claude, and `/graphify` to Antigravity without running Graphify's
own platform installers or enabling hooks, MCP, network ingestion, databases, LLM labeling, or global graphs.

## Optional repository-intelligence tools

- Graphify: relationship and architecture graphs only; output remains outside startup context.
- Repomix: occasional filtered repository snapshots and handoffs.

Use `python scripts/bootstrap-graphify.py --check` to detect Graphify. A missing installation can be provisioned
explicitly and project-locally with `python scripts/bootstrap-graphify.py --install`; the bootstrap never runs
from package lifecycle hooks, uses the exact wheel-only requirements lock under `agent-platform/tooling/`, and
never changes global agent configuration. Serena, Context7, Aider, and code-review-graph are rejected
evidence-only sources and have no installation or activation path.

## Project-local security scanners

1. Review `agent-platform/tooling/security-tools.lock.json` and its exact source URLs and SHA-256 hashes.
2. Preview with `python scripts/bootstrap-security-tools.py --dry-run`.
3. Install only into ignored `.tools/security/` with `python scripts/bootstrap-security-tools.py --install`.
4. Verify the pinned install with `python scripts/bootstrap-security-tools.py --check`.
5. Verify every historical HIGH/CRITICAL source decision with
   `python scripts/check-high-risk-remediations.py`.
6. Run all scanners and refresh redacted evidence with
   `python scripts/agent-security.py --npm-audit --full-scanners --write-evidence`.

The Python wheel closure is fail-closed to Windows amd64 with Python 3.12. Native Gitleaks and Trivy assets are
locked for the audited Windows, Linux, and macOS architectures. No global install, package lifecycle hook, MCP
server, credential login, or container socket is used.

## Profiles and capability control

- Activate only the phase profile that owns the next deliverable.
- To disable a capability, remove it from a profile's `enabled_skills` and `optional_skills`, set its manifest
  decision to disabled, regenerate adapters, and validate.
- There is intentionally no default profile that loads every skill.

## Update, verify, and roll back

- Check upstream movement: `python scripts/agent-update-check.py`.
- Refresh isolated audit evidence only after review: `python scripts/audit-agent-sources.py --refresh`.
- Rebuild locks/reports: `python scripts/build-agent-audit.py --write`.
- Verify mirrors: `python scripts/sync-agent-skills.py --check`.
- Roll back by reverting the reviewed project commit or restoring the prior manifest and lock together; do not
  mix adapters from one lock with source decisions from another.
