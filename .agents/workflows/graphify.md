---
description: Query or explicitly refresh the audited Graphify repository graph
---

Follow repository authority and safety boundaries. Invocation does not authorize hooks, MCP configuration, platform installers, network ingestion, database access, LLM providers, global graph mutation, or forced overwrites.

Invoke the `graphify` skill with the workflow arguments.

Accepted modes are `query <question>`, `explain <node>`, `path <source> :: <target>`, `affected <node>`, `hubs`, `extract`, `update`, and `cluster`. Default to `query` when the arguments are a plain-language question. If there are no arguments, show the modes and stop.
