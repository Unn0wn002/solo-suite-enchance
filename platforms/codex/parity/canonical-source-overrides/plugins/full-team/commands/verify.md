---
description: Verify the full-team installation by delegating to the native fail-closed preflight.
argument-hint: [no arguments]
---
This skill is a reporting wrapper; it deliberately has no second dependency,
version, or room implementation. Run the native preflight shipped by the
orchestrator against the selected AgentRoom:

```text
<python> <resolved-plugin-root>/skills/full-team-orchestrator/scripts/preflight.py \
  <suite-root>/plugins/ai/skills/agent-room-templates/agentsrooms/full-team-website.json \
  --suite-root <suite-root>
```

Use the returned JSON as the source of truth. It checks all 17 component
plugins, each contract `minimum_version`, each representative skill, every
command declared by the room, and the room validator. A `FAIL` result is
fail-closed: list the missing or skewed component skills or commands and stop.
Installed versions below the contract floor are failures, not informational
warnings; do not continue in degraded mode without naming the lost checks.

When a component is missing or below its floor, give the Codex installer
syntax exactly as:

```text
codex plugin add <plugin-name>@solo-suite-codex
```

Do not emit the legacy Claude slash-command installer syntax, and do not claim that
installing `full-team` automatically installs its components. After a passing
preflight, recommend `/solo-start:session` for a new project or
`/full-team:orchestrator` for the authoritative full cycle.
