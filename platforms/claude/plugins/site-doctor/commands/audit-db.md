---
description: Audit a PostgreSQL, MySQL, or SQLite database
argument-hint: [environment-variable/profile name, db file path, or schema dump]
---
Use the database-audit skill to audit: $ARGUMENTS

If no target was provided, first ask for the engine and how to access it.
For PostgreSQL/MySQL, request only the NAME of an environment variable,
client profile, local socket, or secret-store reference -- never ask the user
to paste a credential-bearing connection string into chat or command
arguments. A SQLite file path or schema dump is also acceptable. Confirm that
any live account is read-only before connecting. Use the read-only
queries from the skill's references/audit-queries.md, work through all six
categories, and produce the standard severity-ranked report. Finish by
offering to apply fixes with the database-fix skill.

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
