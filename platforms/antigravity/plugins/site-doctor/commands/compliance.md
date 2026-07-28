---
description: Check GDPR/CCPA and consent gaps. Not legal advice.
argument-hint: [url]
---
Use the compliance-check skill on: $ARGUMENTS

If no URL was provided, ask for it and which users/regions apply. Run the
tracker scanner, then review consent/cookies, privacy policy, user rights, data
practices, third parties, and security. State clearly this surfaces gaps and is
NOT legal advice - recommend a lawyer for anything consequential.

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
