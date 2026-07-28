---
name: site-doctor-animation
description: "Audit motion design and GSAP animation implementation — correctness, performance, accessibility, and design consistency Use when the user explicitly invokes $site-doctor-animation or asks for this site-doctor animation workflow."
---

# Site Doctor Animation

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $animation-design-audit on the user's supplied arguments and surrounding request.

If no path was provided, ask for the project's local codebase path (this is
a source-scan, not a live-URL check). Run the bundled scanner first, then
work through Correctness / Performance / Accessibility / Design.

## Output — evidence-based audit format
Never just "good" or "bad" — every claim names its proof. If nothing was actually inspected for an area, say "not checked", don't guess. End with exactly:

```
## Status
PASS / WARNING / FAIL

## Evidence Checked
- File: …
- Command output: …
(only the lines that apply — but at least one; no evidence, no finding)

## Findings
1. …

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
