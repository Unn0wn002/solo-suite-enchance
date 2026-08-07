# Core Repository Intelligence

Solo Suite uses one graph tool and one optional export tool:

| Tool | Use it for | Policy |
| --- | --- | --- |
| [Graphify](https://github.com/Graphify-Labs/graphify) | Architecture, dependencies, and cross-file relationships | Audited direct version `0.9.32`; explicit project-local bootstrap |
| [Repomix](https://github.com/yamadashy/repomix) | Filtered repository exports and handoffs | Optional; approve and pin separately before use |

Aider, Serena, Context7, and code-review-graph are rejected integration
sources. They remain in audit evidence for provenance, but no profile, skill,
hook, MCP definition, installer, or platform adapter activates them.

## Graphify bootstrap

The repository never installs tools during `npm install`, plugin discovery, or
agent startup. Check the audited Graphify version without changing files:

```powershell
python scripts/bootstrap-graphify.py --check
```

If it is missing, inspect the plan and explicitly provision it:

```powershell
python scripts/bootstrap-graphify.py --dry-run
python scripts/bootstrap-graphify.py --install
```

The installer creates `.tools/graphify/venv`, installs the exact dependency
set in `agent-platform/tooling/graphify-requirements.txt` from wheels only,
disables pip configuration and cache use, and verifies `graphifyy==0.9.32`.
It does not use administrator access,
global installation, shell pipelines, Graphify platform installers, Git hooks,
or MCP configuration. `.tools/` is ignored.

If an audited Graphify `0.9.32` already exists on `PATH`, the bootstrap reuses
it and performs no installation.

## Use Graphify

Host-native invocations use the reviewed `graphify` skill: `$graphify` in Codex and `/graphify` in Claude or
Antigravity. Use `query`, `explain`, `path`, `affected`, or `hubs` for read-only work. The `extract`, `update`, and
`cluster` modes write only to the active repository's `graphify-out/` and must be requested explicitly.

Build or refresh code-only data without an API key:

```powershell
graphify extract . --code-only --no-viz
graphify update . --code-only --no-viz
graphify cluster-only . --no-viz
```

Query the existing graph:

```powershell
graphify query "Which modules depend on the profile generator?"
graphify explain "scripts/generate-agent-adapters.py"
graphify path "scripts/build-agent-audit.py" "agent-platform/manifest.yaml"
```

Keep `graphify-out/` outside startup prompt context. Do not run `graphify hook
install`, `graphify claude install`, or other platform installers from repo
setup because they can create automatic hooks or mutate platform instructions.
The repository already provides reviewed cross-platform instructions and skill
adapters.

To install only those reviewed adapters globally after confirming Graphify `0.9.32`, run
`scripts/install-global-agent-platforms.ps1 -GraphifyOnly`. This does not run Graphify's own platform installers.

## Safe replacements

- Symbol navigation: Graphify first, then bounded `rg` search and existing
  client-native workspace editing.
- Current library documentation: primary official documentation through the
  active client's reviewed web access.
- Coding: the active Codex, Claude, or Antigravity client.
- Review graph: Graphify only.
- Export/handoff: selected files directly, or an explicitly approved and pinned
  Repomix installation.

## Verify

```powershell
node scripts/check-core-tooling.mjs
python scripts/validate-agent-platform.py
```

The core-tooling check reports optional Repomix as `MISSING` without treating
it as a platform failure. Graphify must match the audited version.
