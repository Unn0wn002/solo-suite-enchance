---
description: Run one cycle - build, review, test, audit, memory
argument-hint: [optional task ID or focus area]
---
Use the project-memory-manager skill in run-cycle mode to orchestrate one full development
cycle for a single task. $ARGUMENTS

Take one task from selection to done through the whole pipeline, invoking the right skill
at each step and moving the task through .solo/tasks.md as you go:
1. Select the next task (next-step logic) and confirm scope against the PRD. Read
   .solo/stack.md so every step fits the real stack; if it's missing and the task touches
   infrastructure or vendors, offer /stack:intake first.
2. Design first if it needs UX/UI (ui-ux-designer) - skip if not applicable.
3. Implement it end to end (fullstack-developer).
4. Review the change (code-reviewer) - address Must-fix items before proceeding.
5. Test it (qa-engineer) against the acceptance criteria and edges.
6. Audit if relevant: site-doctor's generic audits (security-scan, a11y, perf, ...) or the
   vendor audits when the task touches that vendor - /stack:audit-cloudflare,
   /stack:audit-vercel, /stack:audit-supabase, /stack:audit-tags, /stack:audit-payments. Fold any fixes in.
7. Update docs if the change warrants it (documentation-writer).
8. Save progress (end-session logic) - task to Done, decisions logged, stack.md updated if
   the stack changed, handoff refreshed.
Stop and ask at any gate that needs a human decision (ambiguous scope, a failing Must-fix,
a risky migration). Do one cycle per invocation unless told to continue.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
