---
name: ai-review-output
description: "Review AI-generated code for hallucinations and missing files. Use when the user explicitly invokes $ai-review-output or asks for this ai review-output workflow."
---

# AI Review Output

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $ai-output-auditor in review-output mode (ground it with $repo-analyzer). Apply it to the user's supplied arguments and surrounding request.

Hunt hallucinated APIs / fake imports, missing or half-created files and broken imports, unsafe assumptions (invented env vars, assumed schema, skipped auth/validation, hard-coded secrets), whether it matches the request, and whether it actually builds/runs. Report each with severity and fix.

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
