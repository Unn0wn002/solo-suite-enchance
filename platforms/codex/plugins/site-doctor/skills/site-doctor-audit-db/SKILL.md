---
name: site-doctor-audit-db
description: "Run a full database audit (schema, indexes, queries, security, integrity) for PostgreSQL, MySQL, or SQLite Use when the user explicitly invokes $site-doctor-audit-db or asks for this site-doctor audit-db workflow."
---

# Site Doctor Audit DB

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $database-audit to audit the user's supplied arguments and surrounding request.

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

## Next Recommended Skill
No follow-up skill is implied here; choose the next validated skill for the current workflow.
```

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
