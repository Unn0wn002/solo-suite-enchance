---
description: Fast single-pass SEO check - use /seo-* for depth
argument-hint: [url]
---
Use the seo-optimization skill on: $ARGUMENTS

If no URL was provided, ask for it. Run the meta extractor, then work through
crawlability, understanding, experience, architecture, i18n, and AI-answer-engine
visibility. Produce the report bucketed by Crawl / Understand / Experience.

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
