---
description: Review a PR diff for correctness, tests, docs, risk
argument-hint: [PR number/URL or branch]
---
Use the **git-workflow-manager** skill in pr-review mode. $ARGUMENTS

Review across correctness, security, tests, docs, and risk. Use **repo-analyzer** for context and **authz-security-reviewer** / **security-review** for the security pass; pull live PR data via **connector-auditor** (GitHub) when available. End with a verdict: approve / approve-with-nits / request-changes, plus specific line-level asks.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
