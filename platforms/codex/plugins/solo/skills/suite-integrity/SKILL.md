---
name: suite-integrity
description: "Validate a Solo Suite Codex source checkout or installed plugin mechanically, including manifests, skills, UI metadata, command mappings, helper paths, marketplace sources, AgentRooms, release versions, documented counts, and optional .solo project memory. Use for self-check requests, suite wiring checks, plugin integrity checks, and verification after adding or renaming a plugin or skill."
---

# Check Solo Suite integrity

Resolve `<skill-root>` to the directory containing this `SKILL.md`. Run the checker with the same Python interpreter used for the repository tests:

```text
<python> <skill-root>/scripts/self_check.py <suite-or-plugin-root> <project-root>
```

Pass `-` as `<project-root>` to skip `.solo/` memory checks. On a source checkout, install the hash-locked validation dependencies from `requirements-dev.lock` with `--require-hashes` first. On an installed plugin, the script discovers the plugin from its own location when the root argument is omitted.

The checker supports two modes:

- `source-checkout`: validate the repo marketplace, every plugin, all skills, the command migration map, release inventory, AgentRooms, and documentation counts.
- `installed-plugin`: validate the current cached plugin without assuming sibling plugins or a source-repository marketplace exist. AgentRooms is a suite-level contract: when the cached plugin is `ai` without the sibling `gate` plugin, the checker reports a warning and defers that check until a full suite root is available.

Treat a clean result as evidence that structural checks passed, not as proof of security, functional correctness, or production readiness. Report every warning and failure with its path, then run the relevant unit tests and plugin validator before calling the suite healthy.

End with summary, findings, risks, required fixes, suggested `.solo/tasks.md` entries with stable task IDs, verification evidence, and the next `$solo-*` skill to invoke.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
