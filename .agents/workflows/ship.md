---
description: Run the pre-launch checklist via parallel fan-out to canonical project agents, then synthesize a go/no-go decision
---

Follow repository authority and safety boundaries. Invocation does not authorize commits, pushes, deployments, destructive operations, package/MCP installation, credential access, or external writes; obtain explicit approval where required.

Invoke the shipping-and-launch skill.

`/ship` is a **fan-out orchestrator**. It runs three canonical project personas in parallel against the current change, then merges their reports into a single go/no-go decision with a rollback plan. The personas operate independently — no shared state, no ordering — which is what makes parallel execution safe and useful here.

## Phase A — Parallel fan-out

Spawn three subagents concurrently using the Agent tool. **Issue all three Agent tool calls in a single assistant turn so they execute in parallel** — sequential calls defeat the purpose of this command.

In Claude Code, each call passes `subagent_type` matching an agent present in `.claude/agents/`:

1. **`software-architect`** — Run the code-quality and architecture pass: correctness risks, readability, coupling, architectural consistency, and performance implications. Output prioritized findings with file/line evidence.
2. **`security-reviewer`** — Run a vulnerability and threat-model pass. Check OWASP Top 10, secrets handling, auth/authz, dependency risk, and least privilege. Output the standard security report.
3. **`qa-engineer`** — Analyze verification coverage for the change. Identify gaps in happy path, edge cases, error paths, regressions, concurrency, accessibility, and runtime/browser checks. Output the standard QA coverage analysis.

In harnesses without an Agent tool, invoke each persona's system prompt sequentially and treat their outputs as independent reports — the merge phase still works.

Constraints:
- Subagents cannot spawn other subagents.
- Each subagent gets its own context window and returns only its report to this main session.
- Agent names in this command must resolve to checked-in project adapters; do not invent or rely on undeclared plugin-only personas.

**Persona resolution.** Project-level definitions in `.claude/agents/` are authoritative for this command. If a user-level agent with the same canonical name exists, normal host precedence may customize it, but `/ship` must remain valid using only repository-defined adapters.

## Phase B — Merge in main context

Once all three reports are back, the main agent synthesizes them:

1. **Code Quality & Architecture** — Aggregate Critical/Important findings from `software-architect` and any failing tests, lint, or build output. Resolve duplicates.
2. **Security** — Promote any Critical/High `security-reviewer` findings to launch blockers. Cross-reference architecture findings that affect trust boundaries.
3. **Testing & Runtime Quality** — Pull coverage and regression gaps from `qa-engineer`; include browser/runtime checks when applicable.
4. **Performance** — Combine architect and QA evidence; cross-check Core Web Vitals for user-facing web changes when available.
5. **Accessibility** — Require keyboard access, focus visibility, semantics, contrast, and reduced-motion checks for user-facing changes.
6. **Infrastructure** — Verify env vars, migrations, monitoring, feature flags, and rollback prerequisites directly.
7. **Documentation** — Verify README, ADRs, changelog, runbook, or migration notes when the change requires them.

## Phase C — Decision and rollback

Produce a single output:

```markdown
## Ship Decision: GO | NO-GO

### Blockers (must fix before ship)
- [Source persona: Critical finding + file:line]

### Recommended fixes (should fix before ship)
- [Source persona: Important finding + file:line]

### Acknowledged risks (shipping anyway)
- [Risk + mitigation]

### Rollback plan
- Trigger conditions: [what signals would prompt rollback]
- Rollback procedure: [exact steps]
- Recovery time objective: [target]

### Specialist reports (full)
- [software-architect report]
- [security-reviewer report]
- [qa-engineer report]
```

## Rules

1. The three Phase A personas run in parallel when the host supports it.
2. Personas do not call each other. The main agent merges in Phase B.
3. The rollback plan is mandatory before any GO decision.
4. If any persona returns a Critical finding, the default verdict is NO-GO unless the user explicitly accepts the risk.
5. **Skip the fan-out only if all of the following are true:** the change touches 2 files or fewer, the diff is under 50 lines, and it does not touch auth, payments, data access, or config/env. Otherwise, default to fan-out.
