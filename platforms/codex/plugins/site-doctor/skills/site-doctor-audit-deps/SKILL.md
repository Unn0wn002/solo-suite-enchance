---
name: site-doctor-audit-deps
description: "Audit dependencies - CVEs, outdated packages, licenses, supply-chain risk, tree health Use when the user explicitly invokes $site-doctor-audit-deps or asks for this site-doctor audit-deps workflow."
---

# Site Doctor Audit Deps

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $dependency-audit on the user's supplied arguments and surrounding request.

If no path was provided, ask for the project directory. Run the ecosystem audit
tool (npm audit / pip-audit) plus the manifest checker, then triage: rank
vulnerabilities by severity AND reachability (not raw count), flag outdated/
abandoned packages, check licenses (esp. AGPL/copyleft), and assess supply-chain
risk. Note safe-now vs needs-planning fixes.

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
