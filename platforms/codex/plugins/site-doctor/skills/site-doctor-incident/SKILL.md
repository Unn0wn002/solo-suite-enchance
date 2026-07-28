---
name: site-doctor-incident
description: "Build incident-response readiness or run/review an incident (runbooks, on-call, severity, postmortem) Use when the user explicitly invokes $site-doctor-incident or asks for this site-doctor incident workflow."
---

# Site Doctor Incident

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $incident-response for the user's supplied arguments and surrounding request.

For readiness, produce a plan: severity definitions, on-call/escalation, the
runbooks to write first, and comms templates. During an active incident,
prioritize mitigate-first then communicate then resolve-and-verify. Afterward,
write a blameless postmortem with owned, dated action items.

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
