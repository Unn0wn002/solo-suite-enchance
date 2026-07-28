---
name: stack-connector-check
description: "Test which vendor connectors are live before auditing — per-connector tier (live / local config / manual) with evidence, written to .solo/stack.md. Use when the user explicitly invokes $stack-connector-check or asks for this stack connector-check workflow."
---

# Stack Connector Check

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $connector-auditor to check connector availability. Apply it to the user's supplied arguments and surrounding request.

Read `.solo/stack.md` first (offer `$stack-intake` if missing). For each connector in scope — Vercel, Supabase, GitHub, Cloudflare, or just the one named — report the tier actually reached: **live** (a connector/MCP/API answered a read-only probe; name the call and what it returned), **local config** (name the file: `vercel.json`, Supabase migrations/policy SQL, `.github/`, `wrangler.toml`), or **neither → Manual mode**. No probe, no claim — a tier is asserted only from a real response or a real file, never assumed. External probes are read-only: never mutate vendor state or print secret values. The command's only write is the idempotent local project-memory update below.

Write the result to `.solo/stack.md` under `## Connectors` (replace the section if it exists — idempotent, no duplicates), and end by recommending which `$stack-audit-*` commands can run in Connector mode versus Manual. Payments and tag platforms are checked inside their own audits (`$stack-audit-payments`, `$stack-audit-tags`), not here.

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
