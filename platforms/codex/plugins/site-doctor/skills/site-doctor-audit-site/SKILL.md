---
name: site-doctor-audit-site
description: "Run a full website health audit (security, performance, SEO, accessibility, links) Use when the user explicitly invokes $site-doctor-audit-site or asks for this site-doctor audit-site workflow."
---

# Site Doctor Audit Site

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $website-audit to run a complete audit of the user's supplied arguments and surrounding request.

If no target was provided, first ask for the site URL and/or local project path.
Run the bundled scripts, work through all seven categories, and produce the
standard severity-ranked report. If a local codebase path is available, also
run the animation-design-audit skill on it (same as `$site-doctor-animation`)
for the full four-axis GSAP/motion pass rather than just website-audit's own
quick presence check. Finish by offering to apply fixes with the website-fix
skill (and the relevant companion `gsap-*` skill for animation findings).

## Output — evidence-based audit format
Never just "good" or "bad" — every claim names its proof. If nothing was actually inspected for an area, say "not checked", don't guess. End with exactly:

```
## Status
PASS / WARNING / FAIL

## Evidence Checked
- File: …
- Config: …
- Page: …
- Command output: …
- Screenshot: …
- Connector data: …
(only the lines that apply — but at least one; no evidence, no finding)

## Findings
1. …
2. …

## Risk Level
Low / Medium / High / Critical

## Required Fixes
1. …

## Suggested Tasks
→ `.solo/tasks.md` entries with stable T-IDs

## Verification Steps
1. …

## Next Recommended Skill
No follow-up skill is implied here; choose the next validated skill for the current workflow.
```

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
