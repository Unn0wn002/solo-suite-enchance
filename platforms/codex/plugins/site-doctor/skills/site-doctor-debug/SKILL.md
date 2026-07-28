---
name: site-doctor-debug
description: "Systematically debug a website or database problem from a symptom or error message Use when the user explicitly invokes $site-doctor-debug or asks for this site-doctor debug workflow."
---

# Site Doctor Debug

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Debug the problem described in the user's supplied arguments and surrounding request.

Decide which layer the symptom belongs to. Browser, frontend, network, or
server symptoms: Use $website-debug. Database errors, slow queries,
locks, or connection problems: Use $database-debug. If it is unclear,
start with website-debug and follow the request path down until the first
layer where behavior diverges from expectation.

## Output — evidence-based audit format
Never just "good" or "bad" — every claim names its proof. If nothing was actually inspected for an area, say "not checked", don't guess. End with exactly:

```
## Status
PASS / WARNING / FAIL

## Evidence Checked
- File: …
- Config: …
- Page: …
- Command output: …
- Screenshot: …
- Connector data: …
(only the lines that apply — but at least one; no evidence, no finding)

## Findings
1. …
2. …

## Risk Level
Low / Medium / High / Critical

## Required Fixes
1. …

## Suggested Tasks
→ `.solo/tasks.md` entries with stable T-IDs

## Verification Steps
1. …

## Next Recommended Skill
No follow-up skill is implied here; choose the next validated skill for the current workflow.
```

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
