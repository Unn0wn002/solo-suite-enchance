---
description: Core Web Vitals tuning - LCP, INP, CLS, images, caching
argument-hint: [url]
---
Use the performance-tuning skill on: $ARGUMENTS

If no URL was provided, ask for it. Split the timeline into TTFB vs render vs
interactivity, identify the LCP element, and produce findings organized by which
vital each one moves, with current value, target, and expected impact.

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
