---
name: gate-before-merge
description: "Hard gate before merge — blocks on missing tests, failing types/lint, no recorded code review, acceptance criteria not shown passing, no security pass on the change, console errors, unreviewed migrations, or no rollback note. Use when the user explicitly invokes $gate-before-merge or asks for this gate before-merge workflow."
---

# Gate Before Merge

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $quality-gatekeeper in before-merge mode. Apply it to the user's supplied arguments and surrounding request.

**Block the merge if ANY is true:** tests missing/failing · types or lint failing (run them; paste the output as evidence) · code review not recorded for the change (`$dev-code-review` or `$git-pr-review` verdict) · acceptance criteria for the change not demonstrated passing (`.solo/tests.md`) · security pass not done on the change (`$git-pr-review` security section or `$security-*` evidence), or an open security issue in it · console error on affected pages (`$browser-console-errors`) · DB migration not reviewed · no rollback note. Critical `$ai-review-output` findings also block. One failed check = NO-GO with the exact blocker.

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
