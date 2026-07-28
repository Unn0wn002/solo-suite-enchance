---
name: site-doctor-full-checkup
description: "Full-stack checkup - audit the website AND its database, one combined report Use when the user explicitly invokes $site-doctor-full-checkup or asks for this site-doctor full-checkup workflow."
---

# Site Doctor Full Checkup

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Run a complete health check on the user's supplied arguments and surrounding request.

1. Use $website-audit on the site.
2. Use $database-audit on the database.
3. If a local codebase path is available (not just a live URL), also run the
   animation-design-audit skill on it — same as invoking `$site-doctor-animation`
   directly — for the full four-axis GSAP/motion pass rather than just the
   quick presence check website-audit's own category 7 does.
4. Merge all three into one combined report with a single prioritized fix list
   across the whole stack (Critical security first, regardless of layer).
5. Offer to execute the fix list with the website-fix, database-fix skills,
   and (for animation findings) the relevant companion `gsap-*` skill.

## Output — evidence-based, scored
Never just "good" or "bad" — every finding names its proof (file, config, page, command output, screenshot, or connector data). After the audit, always write:
- **Status** — PASS / WARNING / FAIL
- **Site health score** — n/100 with a per-area breakdown (site, database, security, SEO, performance, accessibility, mobile, forms, analytics, animation)
- **Evidence checked** — what was actually inspected, per area; "not checked" where nothing was
- **Critical findings**
- **High findings**
- **Medium findings**
- **Low findings**
- **Fix order**
- **Owner role** (which team-role/plugin owns each fix)
- **Suggested `.solo/tasks.md` entries** (stable T-IDs)
- **Whether release is blocked**
- **Next skill** — the exact next skill invocation

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
