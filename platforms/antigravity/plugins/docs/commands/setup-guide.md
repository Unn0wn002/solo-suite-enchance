---
description: Write a tested from-scratch setup guide
argument-hint: [project, or "getting started"]
---
Use the documentation-writer skill in setup-guide mode for: $ARGUMENTS

Read the actual code/config for the real setup. Walk through, in order, tested as if you'd
never seen the project: prerequisites (tools + versions), installation (real copy-pasteable
commands), configuration (EVERY required env var - name, purpose, example; don't leave a
hidden one undocumented), database/services setup, running it + how to verify, and common
problems with fixes. A missing step makes it worse than nothing.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
