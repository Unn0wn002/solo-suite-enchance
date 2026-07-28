---
name: spec-feature-brief
description: "Turn a rough idea into a clear, decision-ready feature brief. Use when the user explicitly invokes $spec-feature-brief or asks for this spec feature-brief workflow."
---

# Spec Feature Brief

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $acceptance-criteria-writer in feature-brief mode. Apply it to the user's supplied arguments and surrounding request.

Produce a tight brief: problem, goal, users, core user story, in-scope vs **non-goals**, constraints, and success. Write it into `.solo/prd.md`; list open questions instead of guessing.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
