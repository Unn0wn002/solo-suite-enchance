# Tool permission governance

Keep tool access workspace-scoped and least-privileged. Do not activate root MCP configuration or automatic tool-call hooks. Before any new external tool is enabled, record its exact version, permissions, network destinations, credential needs, telemetry behavior, and rollback path in the audit evidence.

Reject tools that forward prompts, tool inputs, tool outputs, repository content, or credentials through an unaudited wrapper. Prefer repository-local deterministic validation over automatic networked policy hooks.
