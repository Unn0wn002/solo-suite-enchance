# Capability Deduplication Report

One canonical skill is maintained per repository concern. Source components may contribute evidence or role
tags, but are not copied repeatedly.

| Overlap | Default | Optional alternative | Disabled/redundant | Decision |
| --- | --- | --- | --- | --- |
| Architecture and relationship graph | Graphify | Native bounded search | code-review-graph | Graphify is the sole graph engine; the duplicate hook-capable graph is rejected. |
| Symbol navigation and editing | Graphify plus bounded native search | Client-native symbol tools when already available | Serena | Avoid a broad MCP permission surface for targeted symbol work. |
| Current external documentation | Primary official documentation | Reviewed host web lookup | Context7 and copied READMEs | Use current primary sources without activating an extra MCP server. |
| Repository export and handoff | Repomix filtered snapshot | Native file selection | Full permanent dumps | Use occasionally, filter aggressively, and keep output outside startup context. |
| Coding client | Active Codex, Claude, or Antigravity host | None | Aider and simultaneous coding clients | Keep repository mutation and credentials inside the selected host's reviewed boundary. |
| Product planning | `product-discovery` | Source-specific story-map reference | Repeated PM plugins | Story mapping and acceptance criteria share one canonical planning route. |
| UI, architecture, frontend, backend, database, QA, security, DevOps, docs, analytics | One role-named canonical skill each | Profile-scoped optional skills | Repeated role assignments from source plugins | Role tags aggregate; source directories are locked once. |

The 69 catalog rows normalize to 57 unique source paths. The remaining 12 rows are role assignments marked
`DUPLICATE_CAPABILITY` in the compatibility matrix, not extra installed copies.
