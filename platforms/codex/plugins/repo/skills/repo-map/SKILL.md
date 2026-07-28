---
name: repo-map
description: "Map the codebase structure, entry points, and important files. Use when the user explicitly invokes $repo-map or asks for this repo map workflow."
---

# Repo Map

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $repo-analyzer in map mode. Apply it to the user's supplied arguments and surrounding request.

Read the code (don't guess from names); use existing project tooling as ground truth.

Expected output: entry points and how a request flows, routing, config/env loading, and the main folders with what owns what — each claim naming the file/path that proves it.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
