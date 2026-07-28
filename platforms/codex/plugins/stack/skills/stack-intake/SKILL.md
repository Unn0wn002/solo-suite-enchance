---
name: stack-intake
description: "Ask what stack the project uses (hosting, DNS, DB, auth, storage, tags, email, payments, CI) and save it to .solo/stack.md Use when the user explicitly invokes $stack-intake or asks for this stack intake workflow."
---

# Stack Intake

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $stack-advisor in intake mode. Apply it to the user's supplied arguments and surrounding request.

Run this FIRST, before auditing or building. Interview the user across: hosting, DNS/CDN/
WAF, database, auth, storage, analytics & tags, email, payments, repo/CI, and (if building)
frontend/backend. Ask for specific providers, not categories; fill what they know and mark
unknowns rather than guessing. Write the result to .solo/stack.md in the standard template
so every other command knows the stack. If .solo/ doesn't exist, offer to initialize it.
Afterward, point to the relevant vendor audits ($stack-audit-cloudflare, -vercel, -supabase,
-tags, -payments) and site-doctor's generic audits.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
