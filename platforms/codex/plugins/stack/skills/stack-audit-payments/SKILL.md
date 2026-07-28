---
name: stack-audit-payments
description: "Audit payments - webhook security, status handling, duplicate protection, refund flow, test vs live keys, exposed secrets, checkout pages Use when the user explicitly invokes $stack-audit-payments or asks for this stack audit-payments workflow."
---

# Stack Audit Payments

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $payments-audit on the user's supplied arguments and surrounding request.

Read .solo/stack.md first for the payment provider (offer $stack-intake if missing); only
audit systems you own. Work from the integration code (checkout, webhook handlers, refund
logic), env config, and provider dashboard details. Check, in money-at-risk order: exposed
secret keys (server key never client-side/committed - run the secret scanner), test vs live
key separation per environment, webhook security (signature verification, replay/idempotency,
2xx-fast + async processing), payment status handling (full state machine incl. pending/
async methods; server-side truth, never client redirect params; verify amounts server-side),
duplicate payment protection (idempotency keys, one intent per order, double-submit guards),
refund flow (server-side + authorized, partial/full, audit trail), and checkout success/
failure pages (success URL is not proof of payment - verify server-side; idempotent
fulfillment; honest pending states). Delegate depth to site-doctor's security-review /
api-audit / forms-audit. Write fixes to .solo/tasks.md.


Run in **Connector mode** (live config via connector-auditor, read-only, never print secrets) when a connector/MCP is available; otherwise **Manual mode** — ask for the specific evidence listed in the skill (settings pastes, env-var *names*, screenshots, config files) and audit exactly what's provided. State which mode was used.

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
