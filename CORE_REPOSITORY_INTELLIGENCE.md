# Core Repository Intelligence

Solo Suite uses one audited graph tool and one optional export tool:

| Tool | Use it for | Policy |
| --- | --- | --- |
| [Graphify](https://github.com/Graphify-Labs/graphify) | Architecture, dependencies, and cross-file relationships | Audited direct version `0.9.32`; explicit project-local bootstrap |
| [Repomix](https://github.com/yamadashy/repomix) | Filtered repository exports and handoffs | Optional; approve and pin separately before use |

Aider, Serena, Context7, and code-review-graph are rejected integration sources. They remain in audit evidence for provenance, but no profile, skill, hook, MCP definition, installer, or platform adapter activates them.

## Graphify bootstrap

The repository never installs tools during `npm install`, plugin discovery, or agent startup. Check the audited Graphify version without changing files:

```powershell
python scripts/bootstrap-graphify.py --check
```

If it is missing, inspect the plan and explicitly provision it:

```powershell
python scripts/bootstrap-graphify.py --dry-run
python scripts/bootstrap-graphify.py --install
```

The installer creates `.tools/graphify/venv`, installs the exact dependency set in `agent-platform/tooling/graphify-requirements.txt` from wheels only, disables pip configuration and cache use, and verifies `graphifyy==0.9.32`. It does not use administrator access, global installation, shell pipelines, Graphify platform installers, Git hooks, or MCP configuration. `.tools/` is ignored.

If an audited Graphify `0.9.32` already exists on `PATH`, the bootstrap reuses it and performs no installation.

## Graph data is derived, not distributed

Solo Suite does not commit a pre-generated `graphify-out/` snapshot. A graph describes the repository in which it was generated, so shipping one from the Solo Suite distribution would mix derived project state into the reusable AI-tooling repository.

Generate or refresh graph data only when explicitly needed in the active project:

```powershell
graphify extract . --code-only --no-viz
graphify update . --code-only --no-viz
graphify cluster-only . --no-viz
```

After initialization, query the local graph with the reviewed `graphify` skill: `$graphify` in Codex and `/graphify` in Claude or Antigravity. Supported bounded modes include `query`, `explain`, `path`, `affected`, and `hubs`.

Keep `graphify-out/` outside startup prompt context and out of distribution commits by default. If a repository intentionally commits a graph snapshot, `scripts/check-graph-freshness.py` validates that snapshot fail-closed. An absent snapshot is reported as `NOT_INITIALIZED`, not as a validation failure.

Do not run `graphify hook install`, `graphify claude install`, or other Graphify platform installers from repository setup because they can create automatic hooks or mutate platform instructions. Solo Suite already provides reviewed cross-platform adapters.

To install only those reviewed adapters globally after confirming Graphify `0.9.32`, run `scripts/install-global-agent-platforms.ps1 -GraphifyOnly`. This does not run Graphify's own platform installers.

## Safe replacements

- Symbol navigation: Graphify first when initialized, then bounded native search and existing client-native workspace editing.
- Current library documentation: primary official documentation through the active client's reviewed web access.
- Coding: the active Codex, Claude, or Antigravity client.
- Review graph: Graphify only.
- Export/handoff: selected files directly, or an explicitly approved and pinned Repomix installation.

## Verify

```powershell
node scripts/check-core-tooling.mjs
python scripts/validate-agent-platform.py
python scripts/check-graph-freshness.py
```

The core-tooling check reports optional Repomix as `MISSING` without treating it as a platform failure. Graphify, when installed, must match the audited version.
