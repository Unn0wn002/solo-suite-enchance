---
name: seo-audit
description: "Full-site SEO audit — routes across every relevant seo-* sub-skill and produces one scored, prioritized report Use when the user explicitly invokes $seo-audit or asks for this seo audit workflow."
---

# SEO Audit

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $seo on the user's supplied arguments and surrounding request.

If no URL was provided, ask for it. Detect business type, run the always-on
sub-skills plus whichever conditional ones apply, and combine everything into
one scored report per the seo skill's format.

## Output
See the seo skill's "Output — evidence-based audit format" section — this
command always ends with that exact structure (Status/Evidence/Score/
Findings/Risk/Fixes/Tasks/Verification/Next skill).

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
