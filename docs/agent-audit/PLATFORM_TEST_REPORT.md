# Platform Test Report

Structural checks prove repository shape only. Runtime commands are reported separately; unavailable or unauthenticated platforms are `NOT_EXECUTED`, never passed by inference.

## Requested-source verification (2026-08-02)

| Check | Status | Evidence |
| --- | --- | --- |
| Canonical skills and Claude mirrors | `PASSED` | 39/39; `validate-agent-skills.py` and sync check pass. |
| Claude lifecycle commands | `PASSED` | 9 adapted command files present, including `/graphify`. |
| Antigravity lifecycle workflows | `PASSED` | 9 adapted lifecycle workflow files present, including `/graphify`. |
| Global installer dry-run | `PASSED` | All destinations resolved below the approved current-user configuration roots. |
| Global installation | `PASSED` | 39 portable skills per host, 19 native plugins per host, 9 Claude commands, and 11 Antigravity global workflows installed with recoverable configuration backups. |
| Active project hook roots | `PASSED` | 0; upstream session hook excluded. |
| Agent platform integrity | `PASSED` | 12 roles, 14 profiles, 39 skills. |
| Application tests | `PASSED` | Build plus 6 Node tests pass. |
| Application lint | `PASSED` | ESLint exits 0 after isolated audit clone cleanup. |
| Graphify | `PASSED` | Exact CLI 0.9.32 detected. |
| GSAP | `PASSED` | ESM import reports 3.15.0. |
| npm/package vulnerability audit | `NOT_EXECUTED` | npm is unavailable; pnpm refuses to audit `package-lock.json` without a pnpm lock. |
| Full external scanner refresh | `NOT_EXECUTED` | Windows Application Control blocked the installed Semgrep executable; no new scanner evidence was written. |

## OpenAI Codex

| Check | Status | Evidence |
| --- | --- | --- |
| AGENTS.md discovery surface | `PASSED` | Root project instruction file exists. |
| .agents/skills discovery surface | `PASSED` | 39 canonical skills found, including all 24 audited Addy lifecycle skills and the reviewed Graphify adapter. |
| Unique trigger descriptions | `PASSED` | Descriptions compared exactly. |
| CLI availability | `NOT_EXECUTED` | Codex desktop is active, but direct CLI execution was denied by the host. |
| Explicit sample skill invocation | `PASSED` | Exact canonical reply `agent-extension-audit` observed in a read-only ephemeral process. |
| Implicit sample skill activation | `PASSED` | Exact canonical reply `agent-extension-audit` observed in a read-only ephemeral process. |

## Claude Code

| Check | Status | Evidence |
| --- | --- | --- |
| CLAUDE.md import | `PASSED` | First-line import checked. |
| Synchronized skills | `PASSED` | 38 mirrors present. |
| Lifecycle commands | `PASSED` | 8 safety-adapted command files are present under `.claude/commands/`. |
| Intentional agents | `PASSED` | 12 generated role adapters. |
| Audited hooks | `PASSED` | No root hooks activated. |
| Approved MCP servers | `PASSED` | No root MCP servers activated. |
| CLI availability | `NOT_EXECUTED` | Claude Code is not installed on this host. |
| /doctor | `PASSED` | Claude Code reported no installation issues. |
| /skills | `NOT_EXECUTED` | /skills isn't available in this environment. |
| /memory | `NOT_EXECUTED` | /memory isn't available in this environment. |
| /agents | `NOT_SUPPORTED` | The /agents wizard has been removed.  Ask Claude to create or update subagents for you (e.g. "create a code-reviewer subagent that ..."), or edit the files directly:   - .claude/agents/       (this project)   - ~/.claude/agents/     (all projects)  Docs: https://code.claude.com/docs/en/sub-agents |
| /hooks | `NOT_EXECUTED` | /hooks isn't available in this environment. |
| /mcp | `PASSED` | No MCP servers are configured. Add one with `claude mcp add`. Usage: /mcp [reconnect\|enable\|disable [<server>\|all]]. With no server name, applies to all. |

## Google Antigravity

| Check | Status | Evidence |
| --- | --- | --- |
| AGENTS.md | `PASSED` | Shared instructions exist. |
| .agents/skills | `PASSED` | 39 portable skills found. |
| .agents/rules | `PASSED` | Portable rules directory checked. |
| .agents/workflows | `PASSED` | Existing workflows plus 8 safety-adapted lifecycle workflows are present. |
| Custom agents | `PASSED` | 12 generated role adapters. |
| CLI discovery | `NOT_EXECUTED` | Antigravity CLI is not installed; manual checklist required. |
| /skills listing | `NOT_EXECUTED` | Install the supported CLI/IDE and follow the manual checklist. |
| rule discovery | `NOT_EXECUTED` | Install the supported CLI/IDE and follow the manual checklist. |
| workflow discovery | `NOT_EXECUTED` | Install the supported CLI/IDE and follow the manual checklist. |
| custom-agent discovery | `NOT_EXECUTED` | Install the supported CLI/IDE and follow the manual checklist. |
| review/sandbox permissions | `NOT_EXECUTED` | Install the supported CLI/IDE and follow the manual checklist. |

## Manual Antigravity checklist

1. Open the repository in a supported Antigravity surface with workspace-only or review permissions.
2. Confirm `AGENTS.md`, `.agents/skills/`, `.agents/rules/`, `.agents/workflows/`, and `.agents/agents/` are discovered from documented locations.
3. Confirm `/skills` lists the 38 canonical names and an explicit plus an implicit `agent-extension-audit` request selects the expected skill.
4. Confirm no root MCP server or hook is active and no skill requests unrestricted non-workspace access.
5. Record the platform version, command output, and result here; until then these checks remain `NOT_EXECUTED`.
