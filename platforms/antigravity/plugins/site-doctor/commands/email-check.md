---
description: Audit deliverability - SPF, DKIM, DMARC, reputation
argument-hint: "[domain] [optional dkim selector]"
---
Use the email-deliverability skill for: $ARGUMENTS

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

## Next Recommended Command
/…
```
