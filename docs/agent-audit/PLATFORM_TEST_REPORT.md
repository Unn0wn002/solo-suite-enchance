# Platform Test Report

Structural checks prove repository shape only. Runtime commands are reported separately; unavailable or unauthenticated platforms are `NOT_EXECUTED`, never passed by inference.

## OpenAI Codex

| Check | Status | Evidence |
| --- | --- | --- |
| AGENTS.md discovery surface | `PASSED` | Root project instruction file exists. |
| .agents/skills discovery surface | `PASSED` | 14 canonical skills found. |
| Unique trigger descriptions | `PASSED` | Descriptions compared exactly. |
| CLI availability | `PASSED` | codex-cli 0.144.1 |
| Explicit sample skill invocation | `PASSED` | Exact canonical reply `agent-extension-audit` observed in a read-only ephemeral process. |
| Implicit sample skill activation | `PASSED` | Exact canonical reply `agent-extension-audit` observed in a read-only ephemeral process. |

## Claude Code

| Check | Status | Evidence |
| --- | --- | --- |
| CLAUDE.md import | `PASSED` | First-line import checked. |
| Synchronized skills | `PASSED` | 14 mirrors present. |
| Intentional agents | `PASSED` | 12 generated role adapters. |
| Audited hooks | `PASSED` | No root hooks activated. |
| Approved MCP servers | `PASSED` | No root MCP servers activated. |
| CLI availability | `PASSED` | 2.1.207 (Claude Code) |
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
| .agents/skills | `PASSED` | 14 portable skills found. |
| .agents/rules | `PASSED` | Portable rules directory checked. |
| .agents/workflows | `PASSED` | Only intentional workflows are present. |
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
3. Confirm `/skills` lists the 14 canonical names and an explicit plus an implicit `agent-extension-audit` request selects the expected skill.
4. Confirm no root MCP server or hook is active and no skill requests unrestricted non-workspace access.
5. Record the platform version, command output, and result here; until then these checks remain `NOT_EXECUTED`.
