---
description: Editorial audit - stale content, media, readability
argument-hint: [url or content source]
---
Use the content-audit skill on: $ARGUMENTS

If no target was provided, ask for the site and audience. Check broken/missing
content (including leftover lorem ipsum / TODOs), stale content, readability,
terminology/tone consistency, spelling/grammar, and duplication. Rank by
visibility and trust impact.

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
