---
description: Build incident readiness or run an incident review
argument-hint: "[readiness | active | postmortem] [context]"
---
Use the incident-response skill for: $ARGUMENTS

For readiness, produce a plan: severity definitions, on-call/escalation, the
runbooks to write first, and comms templates. During an active incident,
prioritize mitigate-first then communicate then resolve-and-verify. Afterward,
write a blameless postmortem with owned, dated action items.

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
