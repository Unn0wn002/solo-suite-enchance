---
description: Write the PRD - problem, users, stories, MVP, metrics
argument-hint: [idea or feature to spec]
---
Use the product-manager skill in PRD mode for: $ARGUMENTS

Read .solo/ first if it exists. Interview the user before writing (problem, users,
success, constraints, what exists) - don't spec on guesses. Then write .solo/prd.md
with specific users, user stories + testable acceptance criteria, an MVP scoped to
the riskiest assumption, explicit non-goals, success metrics, and risks. Push back on
vague or over-broad scope. Append scope decisions to .solo/decisions.md.

Use **acceptance-criteria-writer** so each user story gets testable, pass/fail acceptance criteria.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
