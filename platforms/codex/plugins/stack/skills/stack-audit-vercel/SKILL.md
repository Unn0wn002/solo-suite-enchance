---
name: stack-audit-vercel
description: "Audit Vercel - build, env vars, preview vs prod, domains, redirects, middleware, function limits, rollback, images, insights Use when the user explicitly invokes $stack-audit-vercel or asks for this stack audit-vercel workflow."
---

# Stack Audit Vercel

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $vercel-audit on the user's supplied arguments and surrounding request.

Read .solo/stack.md first (offer $stack-intake if missing); only audit projects you own.
Use a Vercel connector/MCP for live config if available, else work from vercel.json and
provided settings. Check env vars & secrets (no NEXT_PUBLIC_ secrets; prod-only scoping),
preview protection & non-prod DB, build settings, domains, redirects/rewrites, edge
middleware, function limits, rollback path, image optimization, and Speed Insights. Rank by
risk - exposed secrets and unprotected previews on prod data first. Delegate depth to
site-doctor's deployment-review / performance-tuning. Write fixes to .solo/tasks.md.

Use $connector-auditor for live Vercel projects, env-var names, and deployments.


Run in **Connector mode** (live config via connector-auditor, read-only, never print secrets) when a connector/MCP is available; otherwise **Manual mode** — ask for the specific evidence listed in the skill (settings pastes, env-var *names*, screenshots, config files) and audit exactly what's provided. State which mode was used.

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
