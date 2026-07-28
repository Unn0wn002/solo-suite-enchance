---
description: Ask what stack the project uses and save it to memory
argument-hint: [optional - paste what you already know]
---
Use the stack-advisor skill in intake mode. $ARGUMENTS

Run this FIRST, before auditing or building. Interview the user across: hosting, DNS/CDN/
WAF, database, auth, storage, analytics & tags, email, payments, repo/CI, and (if building)
frontend/backend. Ask for specific providers, not categories; fill what they know and mark
unknowns rather than guessing. Write the result to .solo/stack.md in the standard template
so every other command knows the stack. If .solo/ doesn't exist, offer to initialize it.
Afterward, point to the relevant vendor audits (/stack:audit-cloudflare, -vercel, -supabase,
-tags, -payments) and site-doctor's generic audits.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
