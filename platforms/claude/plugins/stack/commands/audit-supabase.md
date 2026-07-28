---
description: Audit Supabase - RLS, auth, keys, storage, indexes
argument-hint: [project ref or name]
---
Use the supabase-audit skill on: $ARGUMENTS

Read .solo/stack.md first (offer /stack:intake if missing); only audit projects you own.
Use a Supabase connector/MCP for live policies/settings if available, else work from
migrations and provided config. LEAD with RLS: confirm RLS is ON with correct row-scoping
policies on every API-exposed table, and that the service_role key is never client-side or
committed. Then auth settings, storage bucket policies, edge functions, indexes/slow
queries, realtime rules, and backups. Rank by exposure - RLS-off tables and leaked
service_role key are critical. Delegate depth to site-doctor's security-review / database-
audit / backup-recovery. Write fixes to .solo/tasks.md.

Use **authz-security-reviewer** (rls-test) and **connector-auditor** for live schema/policies.


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
