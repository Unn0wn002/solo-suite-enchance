---
name: design-ux-flow
description: "Map a user flow - steps, decision points, and the error/empty/edge states Use when the user explicitly invokes $design-ux-flow or asks for this design ux-flow workflow."
---

# Design UX Flow

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $ui-ux-designer in UX-flow mode for the user's supplied arguments and surrounding request.

Read .solo/prd.md for the user stories. Map entry -> steps -> decision points -> success,
plus the loading/empty/error/edge states people forget. Minimize steps and cognitive
load; one clear primary action per screen; match the user's mental model, not the schema.
Write flows to .solo/design.md.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
