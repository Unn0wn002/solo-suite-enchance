---
description: Audit mobile - responsive layout, touch targets, speed
argument-hint: [url]
---
Use the mobile-audit skill on: $ARGUMENTS

If no URL was provided, ask for it. Run the mobile checker, then review
viewport/responsive (test 320/375/768px), touch usability, mobile performance
on throttled conditions, legibility, and PWA readiness. Rank by how badly each
issue blocks a mobile user completing the core task.

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
