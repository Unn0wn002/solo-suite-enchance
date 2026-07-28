---
description: Score launch readiness /100 only, with no verdict
argument-hint: [optional scope]
---
Use the **production-readiness-reviewer** skill, scoring only. $ARGUMENTS

Run the 14-section checklist (Product, Architecture, Design, Frontend, Backend, Database, Security, Testing, Performance, SEO, Analytics, Deployment, Monitoring, Documentation) as evidence and produce the skill's exact score block — every applicable category 0–10, total /(10 × applicable), normalized /100, with N/A categories listed per the skill's applicability matrix (mandatory categories are never N/A) — but stop there: **no Launch Status, no verdict**. Would-be hard blockers met along the way are listed as risks with their fix commands, not turned into a verdict. Vendor checks stay stack-conditional (only providers in `.solo/stack.md`; others N/A with evidence). Use this as the trend metric between gate runs; when you need the enforced verdict, run `/gate:production-ready`.

Record the dated score in `.solo/project.md` so progress is visible across sessions.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
