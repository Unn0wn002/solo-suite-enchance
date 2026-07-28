---
description: Check every solo-suite component plugin is installed
---
Verify the full-team meta-plugin's dependencies.

Check that each of the 18 component plugins is installed and its commands resolve: **solo, stack, project, design, dev, test, release, docs, site-doctor, seo, git, spec, repo, security, browser, gate, ai, growth**. For each plugin, probe one representative command (e.g. `/solo:self-check`, `/stack:intake`, `/gate:production-ready`, `/seo:audit`) and each plugin's skills directory. Report:

- installed plugins with their versions
- missing plugins, each with its exact install command (`/plugin install <name>@solo-suite`)
- unresolved representative commands or missing skills directories

The meta-plugin's `dependencies` array declares plugin **names only**. It does
not declare version ranges or minimum-version floors, so report installed
versions as informational evidence and never invent a "version mismatch."

If everything is present, recommend `/solo:start-session` (new session) or `/solo:full-team-dev` (full cycle) as the next step.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
