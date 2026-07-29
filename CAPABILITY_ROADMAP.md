# Solo Suite Enchance Capability Roadmap

This roadmap applies the learning corpus from `EC Solo Suite Learns` to the
existing Solo Suite Enchance distributions. It is intentionally additive:
upstream repositories remain reference material, while this project keeps one
shared `.solo/` memory contract and platform-native adapters.

The exact current inventory is generated in
`capability-inventory.json`. It includes every plugin, every Claude/Antigravity
skill and command, Codex skill-file counts, upstream learning sources, and an
implementation idea for each plugin.

## Core design rule

Do not turn the suite into a flat list of every available tool. Select a
phase-owned team, pass explicit artifacts between roles, and record what was
not activated. Every capability should declare:

- owner role and lifecycle phase;
- required inputs;
- produced artifact or evidence;
- downstream handoff;
- acceptance or release gate;
- platform adapter;
- security and license notes.

## Phase routing

| Phase | Primary plugins | Learned implementation |
| --- | --- | --- |
| Discover | `project`, `spec`, `growth` | Add story mapping, before-build risk review, market sizing, KPI hypotheses, and non-goals before implementation. |
| Design | `design`, `browser`, `seo` | Treat design tokens, responsive behavior, WCAG, browser smoke checks, metadata, structured data, and GEO as acceptance criteria. |
| Architecture | `project`, `repo`, `stack`, `spec` | Use C4 boundaries, stack intake, Graphify plus bounded native search, API/data contracts, and an ADR before code. |
| Implement | `dev`, `design`, `security` | Route frontend, backend, TypeScript/Python, database, GSAP, auth, and secure coding work to owned seats. |
| Verify | `test`, `browser`, `site-doctor`, `security` | Reuse the PRD acceptance contract for unit, integration, E2E, edge-case, performance, accessibility, and security evidence. |
| Release | `gate`, `release`, `git`, `docs` | Require reproducible provenance, CI, deployment strategy, rollback, review, changelog, runbook, and release evidence. |
| Operate | `stack`, `site-doctor`, `docs`, `solo` | Monitor real infrastructure, incidents, dependencies, content, cost, and project memory. |
| Orchestrate | `full-team`, `ai`, `solo` | Enforce AgentRoom ownership, no shared-writer collisions, proposal mode, evidence boundaries, and end-session memory. |

## Plugin-by-plugin suggestions

- `ai`: make AgentRooms and output auditing mandatory for multi-agent runs.
- `browser`: add a standard responsive/console/form/accessibility smoke matrix.
- `design`: connect design-system and interaction decisions to story acceptance.
- `dev`: add adapters for JavaScript/TypeScript, Python, backend, frontend/mobile,
  and GSAP patterns from the learning corpus.
- `docs`: generate ADR, OpenAPI, changelog, setup, and operational artifacts.
- `full-team`: use explicit seats, declared write scopes, and handoff artifacts.
- `gate`: unify functional, accessibility, performance, security, and deployment
  evidence into one release decision.
- `git`: enforce safe branch/commit/review flows and block bypass conventions.
- `growth`: tie conversion recommendations to measurable experiments and events.
- `project`: add story mapping and before-build risk review before PRD and
  architecture.
- `release`: attach source commit, build artifact, deployment, rollback, and CI
  provenance to each release.
- `repo`: route Graphify, bounded native search, primary official documentation,
  and Repomix; rejected repository tools have no activation path.
- `security`: combine threat modeling, abuse cases, authorization matrices,
  secret checks, RLS evidence, frontend security, and MCP governance.
- `seo`: make technical SEO, schema, sitemap, image, content, and GEO checks
  part of the website definition of done.
- `site-doctor`: compose audits for accessibility, content, APIs, dependencies,
  infrastructure, observability, email, compliance, and mobile.
- `solo`: preserve project memory, decisions, handoffs, blockers, and next-step
  selection across Claude, Codex, and Antigravity.
- `spec`: turn feature briefs and API contracts into downstream test contracts.
- `stack`: capture the actual vendor stack before running vendor-specific audits.
- `test`: model QA as evidence-producing workflows, not free-form review.

## Command and skill implementation ideas

The current 126 Claude/Antigravity commands and their Codex skill mappings
remain available. The next improvement is a routing layer that selects a
minimal set of them:

1. `/project:capability-map` (and `$capability-routing` on Codex) reads the request,
   current phase, risk, and stack, then writes `.solo/capability-plan.md`.
2. The plan lists activated plugins, skills/commands, inputs, outputs, gates,
   excluded capabilities, and the next handoff.
3. `/solo:run-cycle` consumes that plan before selecting implementation work.
4. `/full-team:verify` rejects runs missing a declared owner, acceptance
   contract, or evidence location.
5. `/repo:map` chooses Graphify for architecture, bounded native search for
   symbols, primary official sources for current docs, and Repomix for bounded
   snapshots.
6. `/gate:production-ready` checks the plan’s evidence checklist rather than
   re-inventing a generic checklist.

## Delivery order

### Must ship first

- capability inventory and routing plan;
- story-map/before-build handoff into `.solo/prd.md`;
- acceptance-contract link from spec → test → gate;
- repository-intelligence routing rules;
- AgentRoom write-scope and evidence checks;
- cross-platform parity tests for the new routing capability.

### Should ship next

- GSAP animation quality profile with reduced-motion and cleanup checks;
- security and accessibility evidence bundles;
- release provenance and rollback artifact templates;
- operational runbooks and stack-specific audit selection.

### Later

- authenticated capability dashboard in the website;
- metrics-driven plugin recommendations;
- semantic Graphify indexing when a supported LLM backend is configured;
- automatic upstream drift reports and license review queues.
