---
name: repo-onboarding
description: "Generate a new-developer onboarding guide from the actual codebase. Use when the user explicitly invokes $repo-onboarding or asks for this repo onboarding workflow."
---

# Repo Onboarding

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $repo-analyzer in onboarding mode. Apply it to the user's supplied arguments and surrounding request.

Read the code (don't guess from names); use existing project tooling as ground truth.

Expected output: run-it-locally steps (install, env-var names, start command), where the entry points live, a folder-by-folder tour, and the first three files a new developer should read.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
