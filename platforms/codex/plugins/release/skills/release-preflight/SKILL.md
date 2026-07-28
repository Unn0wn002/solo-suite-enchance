---
name: release-preflight
description: "Pre-release checklist - code, security, config, data, infra, monitoring, docs Use when the user explicitly invokes $release-preflight or asks for this release preflight workflow."
---

# Release Preflight

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $devops-engineer in preflight mode for the user's supplied arguments and surrounding request.

Read .solo/ for release scope and what shipped since last release. Report pass/fail on:
code & tests, SECURITY (secrets, deps/CVEs, authz, input - highest stakes), config &
secrets separation, data (backward-compatible migrations + a backup taken), infra (TLS/
DNS/resources), observability (so you'll know if it breaks), and docs. Blockers first.
Drive site-doctor's security-review / dependency-audit / infrastructure-audit / backup-
recovery / observability when installed.

Use $production-readiness-reviewer for the full scored readiness checklist.


Write the preflight result to **`.solo/release.md`**.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
