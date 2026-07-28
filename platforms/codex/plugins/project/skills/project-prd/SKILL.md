---
name: project-prd
description: "Write or update the PRD - problem, users, stories, scoped MVP, success metrics Use when the user explicitly invokes $project-prd or asks for this project prd workflow."
---

# Project PRD

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $product-manager in PRD mode for the user's supplied arguments and surrounding request.

Read .solo/ first if it exists. Interview the user before writing (problem, users,
success, constraints, what exists) - don't spec on guesses. Then write .solo/prd.md
with specific users, user stories + testable acceptance criteria, an MVP scoped to
the riskiest assumption, explicit non-goals, success metrics, and risks. Push back on
vague or over-broad scope. Append scope decisions to .solo/decisions.md.

Use $acceptance-criteria-writer so each user story gets testable, pass/fail acceptance criteria.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
