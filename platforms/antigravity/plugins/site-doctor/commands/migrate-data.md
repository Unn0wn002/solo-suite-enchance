---
description: Plan a safe data migration with validation and rollback
argument-hint: [source and target details]
disable-model-invocation: true
---
Use the data-migration skill for: $ARGUMENTS

If details are missing, ask for source, target, and downtime posture. Plan the
copy -> validate -> sync -> cutover -> keep-source sequence with a field mapping,
batch strategy, validation checks (counts + checksums + spot checks), and
rollback at each stage. The source stays authoritative until the target is
validated.

SAFETY: manual-only (data migration). Require a verified, restore-tested backup and explicit user confirmation before any migration step; state the rollback plan first; dry-run/preview where the engine allows it.

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
