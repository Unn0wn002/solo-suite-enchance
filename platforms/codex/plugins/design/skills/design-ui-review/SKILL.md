---
name: design-ui-review
description: "Review a UI for hierarchy, consistency, clarity, simplicity, and forgiveness Use when the user explicitly invokes $design-ui-review or asks for this design ui-review workflow."
---

# Design UI Review

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $ui-ux-designer in UI-review mode for the user's supplied arguments and surrounding request.

Read .solo/prd.md and .solo/design.md for context. Critique against usability
fundamentals (visual hierarchy, consistency, clarity, simplicity, error-forgiveness),
ranked by impact on the user completing their task, each with a concrete fix. For deep
accessibility, mobile, or forms checks, route to site-doctor's accessibility-review /
mobile-audit / forms-audit and say so.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
