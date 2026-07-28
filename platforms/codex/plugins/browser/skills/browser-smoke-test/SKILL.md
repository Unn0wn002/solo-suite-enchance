---
name: browser-smoke-test
description: "Test core user flows in a browser. Use when the user explicitly invokes $browser-smoke-test or asks for this browser smoke-test workflow."
---

# Browser Smoke Test

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $browser-qa-engineer in smoke-test mode. Apply it to the user's supplied arguments and surrounding request.

Drive a real browser/automation tool if one is available and report actual results; otherwise give an exact, repeatable manual test script (URLs, steps, expected results).

SAFETY (Manual-only: walks state-changing flows (sign-up/login/submit).) — per the browser-qa-engineer safety contract:
- Target localhost/staging/test tenant by default; production only with explicit user
  confirmation of environment AND allowed actions.
- Synthetic test data only — never real PII, cards, production credentials, or customer
  accounts. No real payments, emails, SMS, webhooks, or destructive actions.
- Confirm before any side-effecting submission; clean up created records afterward and
  record every side effect (attempted or completed) in the report.

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
