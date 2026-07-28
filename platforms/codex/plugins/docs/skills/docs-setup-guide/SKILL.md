---
name: docs-setup-guide
description: "Write a from-scratch setup guide someone can actually follow, tested end to end Use when the user explicitly invokes $docs-setup-guide or asks for this docs setup-guide workflow."
---

# Docs Setup Guide

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $documentation-writer in setup-guide mode for the user's supplied arguments and surrounding request.

Read the actual code/config for the real setup. Walk through, in order, tested as if you'd
never seen the project: prerequisites (tools + versions), installation (real copy-pasteable
commands), configuration (EVERY required env var - name, purpose, example; don't leave a
hidden one undocumented), database/services setup, running it + how to verify, and common
problems with fixes. A missing step makes it worse than nothing.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
