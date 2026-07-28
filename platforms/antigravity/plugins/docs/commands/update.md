---
description: Refresh the README and core docs against reality
argument-hint: [what changed, or "refresh the README"]
---
Use the documentation-writer skill in docs-update mode for: $ARGUMENTS

Read .solo/prd.md and .solo/architecture.md, and the actual code/config for real commands
and values. Write/refresh a README: what it is + who for, quick start, features/usage with
examples, tech stack, structure, links. Reconcile against current reality - fix drifted
commands/config/names (code wins over stale docs). Every example must actually work.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
