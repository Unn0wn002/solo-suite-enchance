---
name: graphify
description: Run the audited Graphify CLI for architecture, dependency, impact, path, and cross-file relationship analysis. Activate when the user explicitly requests Graphify or a repository graph query; do not activate for a simple known-file edit.
---

<!-- GENERATED from .agents/skills by scripts/sync-agent-skills.py; do not edit. -->

# Graphify

Use only the audited `graphify` CLI version `0.9.32` from the current `PATH` or the repository-local bootstrap. Keep all access bounded to the active repository.

Before running a graph operation:

1. Resolve the repository root and run `python scripts/bootstrap-graphify.py --check` when that reviewed bootstrap exists. Otherwise run `graphify --version` and require exactly `0.9.32`.
2. Inspect `git status --short -- graphify-out` without changing files.
3. Reuse `graphify-out/graph.json` for read-only operations. Do not rebuild an existing graph merely because a query was requested.

Supported read-only modes:

- `query <question>`: `graphify query "<question>" --budget 2000`
- `explain <node>`: `graphify explain "<node>"`
- `path <source> :: <target>`: `graphify path "<source>" "<target>"`
- `affected <node>`: `graphify affected "<node>" --depth 2`
- `hubs`: `graphify god-nodes --top 10`

Supported write modes, only when explicitly requested:

- `extract`: `graphify extract . --code-only --no-viz`
- `update`: `graphify update . --no-cluster`
- `cluster`: `graphify cluster-only . --no-viz --no-label`

If `graphify-out/` has pre-existing uncommitted changes, do not run a write mode until the user confirms how to preserve them. Never use `--force`, `--global`, database extraction, URL ingestion, repository cloning, watchers, LLM-backed labeling, platform installers, Git hooks, MCP configuration, or Graphify memory writes unless separately audited and explicitly authorized.

Summarize results with relevant node names and repository-relative paths. Do not paste the full graph or load `graphify-out/` into startup context.
