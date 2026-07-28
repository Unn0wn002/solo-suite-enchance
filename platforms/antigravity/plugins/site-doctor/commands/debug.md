---
description: Debug a website or database problem from a symptom
argument-hint: [describe the symptom or paste the error]
---
Debug this problem: $ARGUMENTS

Decide which layer the symptom belongs to. Browser, frontend, network, or
server symptoms: use the website-debug skill. Database errors, slow queries,
locks, or connection problems: use the database-debug skill. If it is unclear,
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

## Next Recommended Command
/…
```
