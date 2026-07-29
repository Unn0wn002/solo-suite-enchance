# Agent Platform Installation Guide

No administrator access, global install, symlink, hook, or root MCP activation is required.

## ChatGPT and Codex

1. Open the repository root so `AGENTS.md` and `.agents/skills/` are in project scope.
2. Run `python scripts/validate-agent-skills.py` and `python scripts/validate-agent-platform.py`.
3. Select one phase profile from `agent-platform/profiles/`; start with `planning.yaml`.
4. Invoke a skill by name when deterministic routing matters. Skill bodies and references load on demand.

## Claude Code

1. Run `python scripts/sync-agent-skills.py`.
2. Confirm `CLAUDE.md` starts with `@AGENTS.md`.
3. Run `python scripts/sync-agent-skills.py --check`.
4. In an interactive Claude session, inspect `/skills`, `/memory`, `/agents`, `/hooks`, and `/mcp`.
5. Keep source-provided hooks and MCP servers disabled unless separately approved.

## Google Antigravity and Antigravity CLI

1. Open the repository with review or workspace-only permissions.
2. Confirm discovery of `AGENTS.md`, `.agents/skills/`, `.agents/rules/`, `.agents/workflows/`,
   `.agents/agents/`, and `.agents/agents.md`.
3. Use `/skills` in `agy` when a supported CLI is installed.
4. Follow the manual checklist in `PLATFORM_TEST_REPORT.md`; this host has no Antigravity runtime.

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
