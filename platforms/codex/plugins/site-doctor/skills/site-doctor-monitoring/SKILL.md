---
name: site-doctor-monitoring
description: "Audit or set up production observability - logging, error tracking, uptime, metrics, alerts Use when the user explicitly invokes $site-doctor-monitoring or asks for this site-doctor monitoring workflow."
---

# Site Doctor Monitoring

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $observability for the user's supplied arguments and surrounding request.

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

## Next Recommended Skill
No follow-up skill is implied here; choose the next validated skill for the current workflow.
```

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
