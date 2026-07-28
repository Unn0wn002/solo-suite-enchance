---
name: gate-score-project
description: "Score production readiness across 14 categories (each /10; matrix-accepted N/A categories leave the denominator, normalized /100) — scoring only, no launch verdict; the gate itself is $gate-production-ready. Use when the user explicitly invokes $gate-score-project or asks for this gate score-project workflow."
---

# Gate Score Project

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $production-readiness-reviewer, scoring only. Apply it to the user's supplied arguments and surrounding request.

Run the 14-section checklist (Product, Architecture, Design, Frontend, Backend, Database, Security, Testing, Performance, SEO, Analytics, Deployment, Monitoring, Documentation) as evidence and produce the skill's exact score block — every applicable category 0–10, total /(10 × applicable), normalized /100, with N/A categories listed per the skill's applicability matrix (mandatory categories are never N/A) — but stop there: **no Launch Status, no verdict**. Would-be hard blockers met along the way are listed as risks with their fix invocations, not turned into a verdict. Vendor checks stay stack-conditional (only providers in `.solo/stack.md`; others N/A with evidence). Use this as the trend metric between gate runs; when you need the enforced verdict, run `$gate-production-ready`.

Record the dated score in `.solo/project.md` so progress is visible across sessions.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
