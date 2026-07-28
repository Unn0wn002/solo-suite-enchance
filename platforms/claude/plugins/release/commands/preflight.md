---
description: Pre-release checklist across code, infra, and docs
argument-hint: [what you're about to ship]
---
Use the devops-engineer skill in preflight mode for: $ARGUMENTS

Read .solo/ for release scope and what shipped since last release. Report pass/fail on:
code & tests, SECURITY (secrets, deps/CVEs, authz, input - highest stakes), config &
secrets separation, data (backward-compatible migrations + a backup taken), infra (TLS/
DNS/resources), observability (so you'll know if it breaks), and docs. Blockers first.
Drive site-doctor's security-review / dependency-audit / infrastructure-audit / backup-
recovery / observability when installed.

Use **production-readiness-reviewer** for the full scored readiness checklist.


Write the preflight result to **`.solo/release.md`**.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
