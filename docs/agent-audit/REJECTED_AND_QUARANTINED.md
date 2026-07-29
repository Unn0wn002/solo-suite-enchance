# Rejected and Quarantined Items

## Current decision totals

- `BLOCKED`: 0
- `QUARANTINED`: 0
- `REJECTED`: 6 unique paths
- Historical `CRITICAL`: 1 source component finding
- Residual integrated `CRITICAL`/`HIGH`: 0

`plugins/protect-mcp` is rejected because it automatically invokes an unaudited npm package around every
tool call. `plugins/block-no-verify` is rejected as an installable hook command because it mutates automatic
hook configuration and offers a global out-of-repository target; only their policy intent was retained in
repository-local rules and deterministic validation.

The four `HIGH`-risk sources—Aider, code-review-graph, Context7, and Serena—are rejected and retained only as
audit evidence. Graphify, bounded native repository search, primary official documentation, and the active
coding host replace their intended functions without adding another MCP server, hook, or credential boundary.

The two HIGH-risk Wshobson source paths that contributed useful concepts use independently written,
instruction-only `devops-release` and `backend-development` skills. No source installer, hook, agent, command,
download pipeline, or cleanup script was copied. `agent-platform/security/high-risk-remediations.json` and
`scripts/check-high-risk-remediations.py` fail closed if any of the eight records regains an unsafe path.

Any future source with an unknown license, unresolved pin, confirmed credential collection, exfiltration,
verification bypass, destructive default, or hidden automatic execution must move to `BLOCKED` or
`QUARANTINED`; its evidence stays documented while its files remain outside the canonical library.
