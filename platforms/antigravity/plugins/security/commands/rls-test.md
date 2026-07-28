---
description: Manual-only Supabase RLS check, non-production only
argument-hint: [non-production project ref and optional table]
disable-model-invocation: true
---
Use the **authz-security-reviewer** skill in rls-test mode. This command is
manual-only because live validation can create, update, or delete test rows.
$ARGUMENTS

Start with static policy review. Before any connector or database call, require
all of these from the user's current request:

- explicit authorization and the exact Supabase project reference;
- confirmation that it is a disposable non-production test project/tenant;
- allowed tables, roles, and operations;
- synthetic fixture names, a maximum request/row/time budget, and stop
  conditions;
- cleanup and rollback steps, including how cleanup will be verified.

Never ask the user to paste a connection string, token, service key, cookie, or
real user data. Use an already-authorized connector or environment-variable
name. If any prerequisite is missing, return a static-only review plus the
missing-input checklist and perform no live calls. Never run live write tests
against production.

For an authorized live run, create only run-id-marked synthetic fixtures within
the declared budget. Check anon / owner / non-owner / admin behavior for the
allowed operations, record every mutation, clean up all fixtures, and verify
cleanup. Stop immediately on unexpected data access, wrong environment,
budget exhaustion, or failed cleanup. Give pass/fail per policy and proposed
SQL separately; never apply policy changes in this command.

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
