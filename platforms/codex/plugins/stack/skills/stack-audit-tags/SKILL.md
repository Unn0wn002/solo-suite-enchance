---
name: stack-audit-tags
description: "Audit analytics tags - GTM install, GA4 firing once, conversions, consent mode, Meta/TikTok pixels, PII leakage, form & funnel tracking Use when the user explicitly invokes $stack-audit-tags or asks for this stack audit-tags workflow."
---

# Stack Audit Tags

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $tag-audit on the user's supplied arguments and surrounding request.

Read .solo/stack.md first (offer $stack-intake if missing). Reuse site-doctor's tracker
scanner for the inventory. Check GTM installed once & correctly, GA4 firing once (not
double-counting), conversion events, checkout/sign-up funnel coverage, form tracking,
consent mode (tags not firing before consent), Meta/TikTok pixels, and PII leakage into
tags/pixels. Rank by impact - double-counting, untracked conversions, and PII/pre-consent
firing first. Delegate depth to site-doctor's analytics-audit / compliance-check (flag
consent/PII as legal-weight, not legal advice). Write fixes to .solo/tasks.md.


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
