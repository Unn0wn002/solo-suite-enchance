---
name: stack-audit-cloudflare
description: "Audit Cloudflare - DNS, SSL/TLS mode, cache/redirect/WAF rules, bot protection, origin exposure, proxy status Use when the user explicitly invokes $stack-audit-cloudflare or asks for this stack audit-cloudflare workflow."
---

# Stack Audit Cloudflare

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $cloudflare-audit on the user's supplied arguments and surrounding request.

Read .solo/stack.md first (offer $stack-intake if missing); only audit zones you own. Use a
Cloudflare connector/MCP for live config if available, else work from provided settings.
Check proxy (orange/grey) status, origin exposure, SSL/TLS mode (aim Full Strict), DNS,
WAF & bot protection, cache rules (don't cache authenticated HTML), page/transform/redirect
rules, and security headers. Rank by exposure - grey-cloud, reachable origin, and Flexible
SSL first. Delegate depth to site-doctor's infrastructure-audit / website-audit / email-check.
Write fixes to .solo/tasks.md.


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
