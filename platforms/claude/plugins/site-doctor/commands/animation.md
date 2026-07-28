---
description: Audit motion and GSAP - correctness, speed, motion safety
argument-hint: [project path]
---
Use the animation-design-audit skill on: $ARGUMENTS

If no path was provided, ask for the project's local codebase path (this is
a source-scan, not a live-URL check). Run the bundled scanner first, then
work through Correctness / Performance / Accessibility / Design.

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
