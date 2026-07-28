---
name: site-doctor-migrate-data
description: "Plan or review a safe data migration (between DBs/engines, large imports, backfills) with validation and rollback Use when the user explicitly invokes $site-doctor-migrate-data or asks for this site-doctor migrate-data workflow."
---

# Site Doctor Migrate Data

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $data-migration for the user's supplied arguments and surrounding request.

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

## Next Recommended Skill
No follow-up skill is implied here; choose the next validated skill for the current workflow.
```

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
