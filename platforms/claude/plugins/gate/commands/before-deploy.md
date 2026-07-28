---
description: Gate before deploy - env, audits, backup, monitoring
argument-hint: [optional environment]
---
Use the **quality-gatekeeper** skill in before-deploy mode. $ARGUMENTS

**Block the deploy if ANY is true:** env vars missing in the target (check `.solo/env-contract.md`) · stack audits not done for this release — Vercel/Supabase/Cloudflare, plus tags/payments where `.solo/stack.md` says they're in play · no backup with a tested restore · no monitoring live (`.solo/monitoring.md`) · no rollback plan (`.solo/release.md`). One missing item = NO-GO; record blockers in `.solo/risks.md`.

## Output
End with exactly:
- **Verdict** — GO / NO-GO (one missing blocker = NO-GO; never averaged away)
- **Blockers** — each failed check, with its evidence and the command that clears it
- **Passed checks** — with the evidence for each
- **Nits** — non-blocking improvements
- **Suggested tasks** → `.solo/tasks.md` (stable T-IDs); record open blockers in `.solo/risks.md`
- **Next command** — what clears the top blocker, or the next phase command on GO
