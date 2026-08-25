---
description: Implement tasks incrementally — build, test, and verify. Add "auto" to run the whole approved plan; scoped commits require explicit authorization.
---

Follow repository authority and safety boundaries. Invocation does not authorize commits, pushes, deployments, destructive operations, package/MCP installation, credential access, or external writes; obtain explicit approval where required.

Invoke the incremental-implementation skill alongside test-driven-development.

## Modes

- **`/build`** — implement the *next* pending task, verify it, mark it complete, then stop. Do not commit unless the user has separately authorized a commit.
- **`/build auto`** — generate the plan if needed, present the full plan, and obtain one explicit approval before autonomous execution. That approval may cover task-scoped commits only when the checkpoint explicitly says so; it never covers pushes, deployments, secrets, destructive actions, or other external writes.

`$ARGUMENTS` selects the mode. Treat `auto` (canonical) or `all` as autonomous mode; anything else (or empty) is the default single-task mode. Autonomous mode is not faster *per task* — it runs the same test-driven loop — it only removes the human stepping *between* approved tasks.

## Default: one task

Pick the next pending task from the plan. Then:

1. Read the task's acceptance criteria.
2. Load relevant context (existing code, patterns, types).
3. Write a failing test for the expected behavior (RED).
4. Implement the minimum code to pass the test (GREEN).
5. Run the relevant regression/full test suite.
6. Run the build to verify compilation.
7. Mark the task complete.
8. If commit authorization is already explicit and still in scope, stage only the files touched by this task plus its task-status update and create one descriptive commit. Otherwise leave the verified changes uncommitted.
9. Stop.

## Autonomous: the whole plan (`/build auto`)

Use this once a spec exists and you want to collapse plan + build into one run. It removes the manual stepping between approved tasks — **not** verification or safety gates.

1. **Require a spec.** Look only for a spec at a known path: `SPEC.md` at the repo root, `docs/SPEC.md`, or a file under `spec/`. A README or arbitrary doc does **not** count. If none exists, stop and tell the user to run `/spec` first — do not invent requirements.
2. **Establish a clean baseline.** Run `git status --porcelain`. If there are uncommitted changes outside the expected planning artifacts (`SPEC.md`, `docs/SPEC.md`, `spec/*`, `tasks/plan.md`, `tasks/todo.md`), stop and require an explicit decision about how to preserve that unrelated work. Autonomous changes must not absorb unrelated local work.
3. **Plan if needed.** If there is no `tasks/plan.md`, invoke planning-and-task-breakdown to generate one.
4. **Single checkpoint.** Present the full plan and wait for an unambiguous affirmative (for example, "approve", "go", or "yes"). The checkpoint must state whether task-scoped commits are included in the approval. Treat hedged responses ("looks reasonable", "I guess") as **not** approved. If commit authorization is included and you generated `tasks/plan.md`, commit only that planning artifact as a preparatory commit; otherwise leave it uncommitted.
5. **Execute every approved task in dependency order.** Use each task's declared dependencies; if they are not explicit, execute in plan order. For each task, run RED → GREEN → regression → build → mark complete. If task-scoped commits were explicitly authorized at the checkpoint, stage only files touched by that task plus its task-status update — never `git add -A` blindly — and create one descriptive commit per task. If commits were not authorized, keep all verified changes uncommitted.
6. **Stop for a safety decision** when:
   - a test cannot be made to pass or the build breaks without an evidence-backed fix → follow debugging-and-error-recovery;
   - the spec is materially ambiguous and repository evidence cannot resolve it safely;
   - a task is high-risk or irreversible — auth/permission changes, destructive data migrations, payments, deletions, deploys, secrets, or anything that cannot be cleanly reverted → follow doubt-driven-development and obtain explicit sign-off before continuing.

   After the blocker is resolved, `/build auto` resumes from the next pending task.
7. **Summarize at the end:** tasks completed, tests added, verification performed, commits made (if any), and anything skipped, blocked, or left for the user.

If any step fails, follow the debugging-and-error-recovery skill.
