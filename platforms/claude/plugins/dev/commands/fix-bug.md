---
description: Fix a bug by root cause, with a regression test
argument-hint: [bug description or error, paste details]
---
Use the fullstack-developer skill in fix-bug mode for: $ARGUMENTS

Read .solo/ for context. Reproduce first, find the actual root cause (not the symptom),
fix it, verify, and add a test so it can't silently return. Route deeper: website-debug
(blank page/CORS/500/hydration/WebSockets), database-debug (locks/connections/slow
queries), security-review for security bugs - from site-doctor when installed. Log
anything surprising in .solo/decisions.md.


Log the bug (repro, severity, status) in **`.solo/bugs.md`**; log the root-cause decision in `.solo/decisions.md`.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
