---
name: repository-intelligence-routing
description: Select the smallest repository-intelligence tool for architecture, symbol, documentation, snapshot, or coding-client work. Activate before broad repository analysis or tool selection; do not activate for a simple known-file edit.
---

<!-- GENERATED from .agents/skills by scripts/sync-agent-skills.py; do not edit. -->

# Repository intelligence routing

Use one primary route:

- Graphify for architecture, dependency, relationship, path, and cross-file questions. Reuse `graphify-out/graph.json`; use incremental update after accepted repository changes.
- For targeted symbols and references, query Graphify first, then use bounded native repository search such as `rg`; use client-native symbol editing only when it is already available and workspace-scoped.
- For current, version-specific external library documentation, use primary official documentation through the active client's reviewed web access.
- Repomix only for filtered, bounded snapshots or handoffs; never keep full dumps in startup context.
- Use the active Codex, Claude, or Antigravity client for edits.

Do not install, configure, or activate Aider, Serena, Context7, or code-review-graph. Their audited sources are retained as rejected evidence only.

If Graphify or Repomix is unavailable, use bounded repository search and document the fallback. Do not install or activate tools silently, expose MCP servers, create automatic hooks, or grant non-workspace filesystem access.
