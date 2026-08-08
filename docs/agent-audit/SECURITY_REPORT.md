# Security and Supply-Chain Report

This was a static, read-only audit. Pattern matches were reviewed as leads, not treated as proof of malicious intent, and no third-party code or configuration was executed.

## Highest-risk source findings — remediation verified

Historical source severity is preserved for audit integrity. It is not the residual risk of the repository integration. Every item below has a machine-checked remediation record, and no integrated `HIGH` or `CRITICAL` residual risk remains.

### wshobson/agents `protect-mcp` — `CRITICAL`, `REJECTED`

The selected plugin registers `PreToolUse` and `PostToolUse` hooks matching every tool call. They invoke `npx protect-mcp@0.7.4` before and after each call and pass tool inputs/outputs through environment variables. Setup documentation also uses an unpinned `@latest`; the npm artifact was not present, locked, or audited. The hook was not copied, translated, installed, or executed.

### wshobson/agents `block-no-verify` — `HIGH`, `REJECTED`

Its policy goal is sound, but its command edits automatic Claude hook settings and offers a global path outside the repository. No packaged adversarial tests establish resistance to quoting or command-chain bypasses. Only the verification-policy intent is retained in shared instructions.

### aider — `HIGH`

The CLI can mutate repositories, execute subprocesses, access home-directory configuration, send model/API traffic, and collect opt-out analytics. Its documentation includes pipe-to-shell installers; static source review also found TLS-verification overrides in an explicit flag path.

Decision: Rejected; use the active platform client under repository policy. Pin: `5dc9490bb35f9729ef2c95d00a19ccd30c26339c`.

### code-review-graph — `HIGH`

The repository contains MCP configuration and session-start hooks, accepts remote-service credentials, performs repository analysis, and documents download-and-execute installation. Its overlapping graph capability is rejected; Graphify is the sole graph route.

Decision: Rejected; Graphify is the sole relationship graph. Pin: `90d760aa23fac0353637d2e8f2a431aa08f14366`.

### context7 — `HIGH`

The MCP server sends documentation queries to an external service, accepts API credentials, has telemetry/configuration surfaces, and includes package cleanup lifecycle scripts. It is not activated at the repository root.

Decision: Rejected; use primary official documentation through reviewed host web access. Pin: `b250c2515694eee4b6df4db82fa056df9ed3e306`.

### serena — `HIGH`

The MCP server is intentionally capable of broad workspace reading/editing and subprocess use. Auxiliary source contains shell and recursive-removal operations; no server was started during audit.

Decision: Rejected; use Graphify plus bounded native symbol search and client-native editing. Pin: `9a9d07e83d8c1cba3458992707f440c624446c6d`.

## Remediation verification

| Capability | Source risk | Integration | Remediation | Residual risk | Replacement |
| --- | --- | --- | --- | --- | --- |
| `wshobson-agents-plugins-protect-mcp` | `CRITICAL` | `REJECTED` | `VERIFIED` | `NONE` | Repository-local tool-permission governance and deterministic security validation. |
| `wshobson-agents-plugins-block-no-verify` | `HIGH` | `REJECTED` | `VERIFIED` | `NONE` | Repository-local verification-integrity rule and CI/test commands. |
| `aider` | `HIGH` | `REJECTED` | `VERIFIED` | `NONE` | The active Codex, Claude, or Antigravity coding host under repository policy. |
| `code-review-graph` | `HIGH` | `REJECTED` | `VERIFIED` | `NONE` | Graphify is the sole relationship and architecture graph. |
| `context7` | `HIGH` | `REJECTED` | `VERIFIED` | `NONE` | Primary official documentation through reviewed host web access. |
| `serena` | `HIGH` | `REJECTED` | `VERIFIED` | `NONE` | Graphify plus bounded native search and client-native editing. |
| `wshobson-agents-plugins-cloud-infrastructure` | `HIGH` | `ADAPTED` | `VERIFIED` | `LOW` | .agents/skills/devops-release/SKILL.md |
| `wshobson-agents-plugins-python-development` | `HIGH` | `ADAPTED` | `VERIFIED` | `LOW` | .agents/skills/backend-development/SKILL.md |

## Medium- and low-risk findings

| Source | Risk | Surfaces | Decision |
| --- | --- | --- | --- |
| [graphify](https://github.com/Graphify-Labs/graphify) | `MEDIUM` | The CLI can parse the repository and optionally use MCP, database, network, or model-provider integrations. Documentation includes a pipe-to-shell installer; this repository uses the audited CLI version or explicit project-local bootstrap and keeps generated output out of startup context. | Primary relationship graph; run project-locally and keep optional network/database exports off unless explicitly requested. |
| [qa-orchestra](https://github.com/Anasss/qa-orchestra) | `MEDIUM` | The workflow material includes examples for hooks and MCP-backed QA orchestration. It was adapted as bounded verification guidance rather than copied or activated. | Adapt schemas and evidence patterns only; keep orchestration scripts disabled unless separately reviewed for the target project. |
| [repomix](https://github.com/yamadashy/repomix) | `MEDIUM` | The CLI reads and exports repository content and offers an MCP mode. Package manifests contain prepare/build lifecycle scripts, so no package installation was performed; use only filtered snapshots. | Use filtered snapshots only and keep generated outputs outside permanent context. |
| [wshobson-agents](https://github.com/wshobson/agents) | `MEDIUM` | The selected Claude plugin set contains commands, agents, skills, and opt-in hook definitions. Some documentation demonstrates destructive or download-and-execute commands. No hook, command, or MCP configuration from the source was activated. | Use selected plugin trees as pinned references; do not activate bundled hooks or translate them automatically. |
| [gsap-skills](https://github.com/greensock/gsap-skills) | `LOW` | The selected skills are instruction-only, MIT-licensed, and contain no selected lifecycle, hook, MCP, or credential surface. Canonical guidance was independently normalized. | Use the official pinned skills as versioned references; activate only the GSAP skill needed for the current implementation. |
| [storymap-skill](https://github.com/MartinForReal/storymap-skill) | `LOW` | The selected skill is instruction-only and MIT-licensed with no selected executable, hook, MCP, credential, or lifecycle surface. Canonical planning guidance was independently normalized. | Use the original, pinned skill as reference; keep the canonical product-discovery skill original and concise. |

## Requested installation source findings

| Source | Risk | Surfaces | Decision |
| --- | --- | --- | --- |
| [addyosmani-agent-skills](https://github.com/addyosmani/agent-skills) | `MEDIUM` | 24 skills, 8 commands, 4 personas, executable helpers, and an automatic Claude session hook; one skill documented an unpinned MCP install. | Install safety-adapted project skills and commands only; exclude hooks, installers, unpinned MCP/package setup, and direct persona activation. |
| [Graphify](https://github.com/Graphify-Labs/graphify) | `MEDIUM` | CLI plus optional MCP, hooks, model/network integrations, and repository analysis. | Accept the exact 0.9.32 CLI only; do not activate platform installers, hooks, MCP, or model integrations. |
| [greensock-GSAP](https://github.com/greensock/GSAP) | `LOW` | Browser animation runtime with no package lifecycle scripts, agent hooks, MCP definitions, credentials, or detected telemetry. | Install exact `gsap@3.15.0` with lifecycle scripts disabled and route usage through the portable GSAP skill. |

## Controls applied

- All clones were shallow, filtered, non-recursive, and stored under ignored `.tmp/`.
- Git hooks were neutralized for clone operations; submodules, installers, lifecycle scripts, MCP servers, agent hooks, and source-provided commands were not executed.
- No root `.mcp.json` or project hook was activated.
- Rejected sources have no canonical skill, adapter, profile, hook, MCP, or installation path.
- Accepted source-driven capabilities are disabled by default and selected only through bounded profiles.
- Imported lifecycle skills carry a repository safety overlay and local references; automatic hooks and installer instructions were not copied. GSAP is an exact package dependency, not startup agent context.
- Graphify is the sole relationship graph. `code-review-graph` is rejected rather than co-activated.
- Repository-local validators reject root MCP activation, project hooks, verification bypasses, and references to rejected external tools in active profiles.

## Scanner coverage

Requested-source update note (2026-08-01): the repository-local policy/remediation scan passed. A fresh npm audit was `NOT_EXECUTED` because npm is unavailable and pnpm cannot audit an npm lockfile. The installed full scanner suite was attempted, but Windows Application Control blocked Semgrep before scanning; the prior scanner evidence below remains historical and was not represented as a fresh pass.

- Local deterministic secret and dangerous-command scan: implemented by `scripts/agent-security.py`.
- npm audit with lifecycle scripts disabled: **0** findings (0 critical, 0 high, 0 moderate, 0 low).

- Project-local scanner suite: gitleaks_history=PASSED (0 findings), gitleaks_worktree=PASSED (0 findings), pip_audit_graphify=PASSED (0 findings), pip_audit_scanners=PASSED (0 findings), semgrep=PASSED (0 findings), trivy=PASSED (0 findings).
- Raw secret values are never written to evidence. Semgrep metrics and Trivy telemetry/version checks are disabled; Trivy blocks HIGH/CRITICAL findings.
- Reviewed and pinned tools: Semgrep 1.171.0, pip-audit 2.10.1, Gitleaks 8.30.1, and Trivy 0.72.0.
- pip-audit identified three advisories in Semgrep's original `mcp==1.23.3` dependency; the isolated lock uses tested `mcp==1.28.1`, and both Semgrep and pip-audit pass.

## Blocked, quarantined, and rejected

- Historical `CRITICAL`: one source component (`plugins/protect-mcp`); remediation is `VERIFIED` and residual integration risk is `NONE`.
- `BLOCKED`: none; all ten licenses were identified and all source pins resolved.
- `QUARANTINED`: none.
- `REJECTED`: six unique paths: Aider, Serena, Context7, code-review-graph, `plugins/protect-mcp`, and `plugins/block-no-verify`.
- The original severity remains recorded as audit evidence. All eight HIGH/CRITICAL capability records have verified remediations; residual integrated HIGH/CRITICAL count is zero.
