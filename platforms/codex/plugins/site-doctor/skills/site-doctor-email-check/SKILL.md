---
name: site-doctor-email-check
description: "Audit email deliverability - SPF, DKIM, DMARC, reverse DNS, reputation, spam triggers Use when the user explicitly invokes $site-doctor-email-check or asks for this site-doctor email-check workflow."
---

# Site Doctor Email Check

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $email-deliverability for the user's supplied arguments and surrounding request.

If no domain was provided, ask for it (and the DKIM selector if known). Run the
email DNS checker, then review authentication (SPF/DKIM/DMARC - the biggest
lever), infrastructure/reputation, content, list hygiene, and monitoring. Lead
with the authentication findings.

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
