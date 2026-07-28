---
name: security-secrets-fix
description: "Detect exposed secrets and provide rotation/fix steps. Use when the user explicitly invokes $security-secrets-fix or asks for this security secrets-fix workflow."
---

# Security Secrets Fix

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $security-review (site-doctor) to find and fix exposed secrets — do a lighter inline version following the same priorities if site-doctor isn't installed, and say so. Apply it to the user's supplied arguments and surrounding request.

Scan the working tree with the bundled redacting scanner. Scan Git history only
through a dedicated redacting history scanner that emits path, commit, rule ID,
line number, and a keyed fingerprint -- never the matching line or value. If
that safe history scanner is unavailable, mark history coverage UNVERIFIED;
do not substitute `git log -p`, raw diffs, or other commands that can stream
credentials into tool/chat output. For each confirmed finding: rotate, remove
it from code/history, move it to an environment/secret store, and prevent
recurrence (gitignore, pre-commit hook). Never print full secret values.

SAFETY: manual-only (secret handling). Never print secret values; rotate with the user driving; confirm each step before it runs; verify old credentials are revoked afterward.

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
