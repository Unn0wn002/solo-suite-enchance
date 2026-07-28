---
description: Audit infrastructure - cloud, TLS, DNS, firewall
argument-hint: [IaC files, cloud, or server details]
---
Use the infrastructure-audit skill on: $ARGUMENTS

If no target was provided, ask about the stack (bare server / containers /
serverless, which cloud, how it's provisioned). Review network exposure, TLS,
DNS, containers, secrets management, and resilience. Only probe systems the
user owns. Produce the report grouped by Network / TLS / DNS / Containers /
Secrets / Resilience.

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
