---
description: Test core user flows in a browser.
argument-hint: [optional URL or flow]
disable-model-invocation: true
---
Use the **browser-qa-engineer** skill in smoke-test mode. $ARGUMENTS

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

## Next Recommended Command
/…
```
