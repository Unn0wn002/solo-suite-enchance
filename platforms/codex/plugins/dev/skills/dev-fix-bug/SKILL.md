---
name: dev-fix-bug
description: "Fix a bug by root cause - reproduce, diagnose, fix, verify, add a regression test Use when the user explicitly invokes $dev-fix-bug or asks for this dev fix-bug workflow."
---

# Dev Fix Bug

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $fullstack-developer in fix-bug mode for the user's supplied arguments and surrounding request.

Read .solo/ for context. Reproduce first, find the actual root cause (not the symptom),
fix it, verify, and add a test so it can't silently return. Route deeper: website-debug
(blank page/CORS/500/hydration/WebSockets), database-debug (locks/connections/slow
queries), security-review for security bugs - from site-doctor when installed. Log
anything surprising in .solo/decisions.md.


Log the bug (repro, severity, status) in **`.solo/bugs.md`**; log the root-cause decision in `.solo/decisions.md`.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
