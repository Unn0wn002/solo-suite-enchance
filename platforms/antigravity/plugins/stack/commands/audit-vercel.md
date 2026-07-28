---
description: Audit Vercel - env, domains, middleware, limits, rollback
argument-hint: [project name or domain]
---
Use the vercel-audit skill on: $ARGUMENTS

Read .solo/stack.md first (offer /stack:intake if missing); only audit projects you own.
Use a Vercel connector/MCP for live config if available, else work from vercel.json and
provided settings. Check env vars & secrets (no NEXT_PUBLIC_ secrets; prod-only scoping),
preview protection & non-prod DB, build settings, domains, redirects/rewrites, edge
middleware, function limits, rollback path, image optimization, and Speed Insights. Rank by
risk - exposed secrets and unprotected previews on prod data first. Delegate depth to
site-doctor's deployment-review / performance-tuning. Write fixes to .solo/tasks.md.

Use **connector-auditor** for live Vercel projects, env-var names, and deployments.


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

## Next Recommended Command
/…
```
