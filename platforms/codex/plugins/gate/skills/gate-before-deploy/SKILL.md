---
name: gate-before-deploy
description: "Hard gate before deploy — blocks on missing env vars, skipped stack audits, no backup, no monitoring, or no rollback plan. Use when the user explicitly invokes $gate-before-deploy or asks for this gate before-deploy workflow."
---

# Gate Before Deploy

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $quality-gatekeeper in before-deploy mode. Apply it to the user's supplied arguments and surrounding request.

**Block the deploy if ANY is true:** env vars missing in the target (check `.solo/env-contract.md`) · stack audits not done for this release — Vercel/Supabase/Cloudflare, plus tags/payments where `.solo/stack.md` says they're in play · no backup with a tested restore · no monitoring live (`.solo/monitoring.md`) · no rollback plan (`.solo/release.md`). One missing item = NO-GO; record blockers in `.solo/risks.md`.

## Output
End with exactly:
- **Verdict** — GO / NO-GO (one missing blocker = NO-GO; never averaged away)
- **Blockers** — each failed check, with its evidence and the command that clears it
- **Passed checks** — with the evidence for each
- **Nits** — non-blocking improvements
- **Suggested tasks** → `.solo/tasks.md` (stable T-IDs); record open blockers in `.solo/risks.md`
- **Next skill** — what clears the top blocker, or the next phase command on GO

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
