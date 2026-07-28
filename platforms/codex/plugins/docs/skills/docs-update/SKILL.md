---
name: docs-update
description: "Create or refresh the README and core project docs, reconciled against reality Use when the user explicitly invokes $docs-update or asks for this docs update workflow."
---

# Docs Update

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $documentation-writer in docs-update mode for the user's supplied arguments and surrounding request.

Read .solo/prd.md and .solo/architecture.md, and the actual code/config for real commands
and values. Write/refresh a README: what it is + who for, quick start, features/usage with
examples, tech stack, structure, links. Reconcile against current reality - fix drifted
commands/config/names (code wins over stale docs). Every example must actually work.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
