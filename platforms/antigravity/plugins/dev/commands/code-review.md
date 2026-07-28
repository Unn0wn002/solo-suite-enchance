---
description: Review a change for correctness, security, and design
argument-hint: [diff, file, or "my latest changes"]
---
Use the code-reviewer skill for: $ARGUMENTS

Read the change in context (.solo/ tasks + acceptance criteria + architecture; nearby
code for conventions). Prioritize correctness and edge cases, then security, readability,
design fit, performance, and test coverage. Label findings Must-fix / Should-fix /
Consider, each specific and actionable with the reasoning. Be honest, not a rubber stamp.
Route security depth to security-reviewer / site-doctor; test depth to qa-engineer.

Use **repo-analyzer** for structural context on what the change touches.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
