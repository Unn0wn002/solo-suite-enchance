---
description: Audit dependencies - CVEs, licenses, supply chain
argument-hint: [project path]
---
Use the dependency-audit skill on: $ARGUMENTS

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

## Next Recommended Command
/…
```
