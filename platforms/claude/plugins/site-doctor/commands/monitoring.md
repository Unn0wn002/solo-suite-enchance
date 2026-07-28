---
description: Audit or set up logging, errors, uptime, and alerts
argument-hint: "[audit | setup] [site url or stack description]"
---
Use the observability skill for: $ARGUMENTS

If it's unclear whether the user wants to audit an existing setup or build one,
ask. For an audit, check each layer (logging, error tracking, uptime/health,
metrics, alerts) for blind spots and noise. For setup, give a prioritized plan
starting with the biggest coverage gain for the site's stakes. End with the
single most important gap to close first.


Record what monitoring exists (error tracking, uptime, logs, alerts) in **`.solo/monitoring.md`**.

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
