---
name: design-component-system
description: "Define a lightweight component system - design tokens + core components with states Use when the user explicitly invokes $design-component-system or asks for this design component-system workflow."
---

# Design Component System

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $ui-ux-designer in component-system mode for the user's supplied arguments and surrounding request.

Define design tokens (semantic color roles, a small type scale, a consistent spacing
scale, radius/elevation) and the core component set with their states
(default/hover/focus/disabled/loading/error), plus lightweight usage rules. Constraint
is the point. Write it to .solo/design.md so development builds from a fixed vocabulary
and the UI stops drifting.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
