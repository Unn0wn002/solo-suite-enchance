---
description: Audit a REST or GraphQL API for security and design
argument-hint: [base url or backend code path]
---
Use the api-audit skill on: $ARGUMENTS

If no target was provided, ask for the API style (REST/GraphQL), how it
authenticates, and how to access it (endpoint with authorization, or resolver/
route code). Enumerate endpoints, then review Security / Design / Reliability /
Docs, with a safe repro per finding. Only test APIs the user is authorized to test.

Compare the live API against the **api-contract-designer** contract in `.solo/` when one exists.

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
