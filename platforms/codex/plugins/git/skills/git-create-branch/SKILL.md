---
name: git-create-branch
description: "Create a safe branch name from the current task and give the exact git command. Use when the user explicitly invokes $git-create-branch or asks for this git create-branch workflow."
---

# Git Create Branch

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $git-workflow-manager in create-branch mode. Apply it to the user's supplied arguments and surrounding request.

Derive a safe `type/scope-desc` branch name from the current `.solo/tasks.md` task (or the provided text), confirm the base branch, and output the exact `git checkout -b` command. Don't switch branches or run git for the user unless asked.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
