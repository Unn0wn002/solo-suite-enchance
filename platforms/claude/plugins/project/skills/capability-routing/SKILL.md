---
name: capability-routing
description: Route a project request to the smallest phase-owned Solo Suite team using the capability inventory, upstream learning notes, explicit handoffs, and evidence gates. Use before starting discovery, design, architecture, implementation, QA, security, release, or operations work.
---

# Capability Routing

Use this skill before activating a large set of plugins. The learned corpus
shows that phase-driven teams outperform a flat plugin dump.

## Inputs

Read, when available:

- `capability-inventory.json`
- `suite-manifest.json`
- `.solo/prd.md`, `.solo/architecture.md`, `.solo/stack.md`, `.solo/tasks.md`
- the user request and the current repository state

If the inventory is unavailable, use the plugin names and phase table in
`CAPABILITY_ROADMAP.md`.

## Routing rules

1. Identify the lifecycle phase: Discover, Design, Architecture, Implement,
   Verify, Release, Operate, or Orchestrate.
2. Select one owner role and only the supporting plugins required for that phase.
3. Prefer existing Solo Suite skills and commands; use upstream capabilities as
   implementation guidance, not as an automatic activation list.
4. Declare the input artifact, output artifact, next handoff, and evidence gate.
5. List excluded plugins and why they are not needed.
6. Route repository questions by intent:
   - Graphify for architecture and cross-file relationships;
   - bounded native search and client-native workspace editing for symbols;
   - primary official sources through reviewed host web access for current docs;
   - Repomix for bounded snapshots and handoffs.
   Aider, Serena, Context7, and Code Review Graph are rejected audit sources
   with no activation path.
7. Preserve upstream attribution and check licenses before promoting content.

## Output

Write `.solo/capability-plan.md` with:

```markdown
# Capability Plan — <request>
## Phase and owner
## Activated plugins
## Activated skills / commands
## Inputs
## Outputs and handoffs
## Acceptance and evidence gates
## Excluded capabilities
## Risks, licensing, and security notes
## Next skill
```

The plan is a routing decision, not a second PRD. Keep it short enough to read
before a task starts.

## Handoff contract

End with: **Owner · Inputs · Work · Output · Evidence · Next command**.
