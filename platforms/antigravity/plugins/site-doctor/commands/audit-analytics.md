---
description: Audit tracking - tag firing, GA4, coverage, consent
argument-hint: [url or analytics stack]
---
Use the analytics-audit skill on: $ARGUMENTS

If no info was provided, ask for the analytics stack and the business questions
the data should answer. Check installation/firing (watch for double-counting
tags), event & conversion coverage, data-quality/naming consistency, consent
integration, and reporting usefulness. Rank by how badly each issue corrupts
decision-making.

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
