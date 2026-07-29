# Solo Suite Enchance Capability Catalog

This is the human-readable companion to `capability-inventory.json`. It
lists every native plugin, skill, and command currently shipped by the
three adapters, then maps the learned upstream role capabilities to the
native Solo Suite route.

## Compatibility legend

| Surface | Claude | Antigravity | Codex |
| --- | --- | --- | --- |
| Plugin packages | yes, native | yes, Claude-compatible mirror | yes, Codex-native package |
| Skills | yes, 80 | yes, 80 | yes, 185 skill files |
| Commands | yes, 126 slash commands | yes, 126 slash commands | yes, 126 explicit skill mappings |
| Capability routing | `/project:capability-map` | `/project:capability-map` | `$capability-routing` |

The upstream names below are fully learned and routed, but they are not
pretended to be separate native packages when the current suite implements
the behavior through an equivalent Solo Suite plugin.

## Native plugin, skill, and command inventory

### ai

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Make AgentRooms, output auditing, and evidence contracts the governance layer for every multi-role run.
- Skills (2):
  - `agent-room-templates/SKILL.md`
  - `ai-output-auditor/SKILL.md`
- Commands (6):
  - Claude/Antigravity: `/ai:agent-rooms` / Codex: `$ai-agent-rooms`
  - Claude/Antigravity: `/ai:compare-models` / Codex: `$ai-compare-models`
  - Claude/Antigravity: `/ai:handoff-check` / Codex: `$ai-handoff-check`
  - Claude/Antigravity: `/ai:prompt-improve` / Codex: `$ai-prompt-improve`
  - Claude/Antigravity: `/ai:repair-cycle` / Codex: `$ai-repair-cycle`
  - Claude/Antigravity: `/ai:review-output` / Codex: `$ai-review-output`

### browser

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Add a repeatable responsive, console, form, and accessibility smoke matrix for website changes.
- Skills (1):
  - `browser-qa-engineer/SKILL.md`
- Commands (5):
  - Claude/Antigravity: `/browser:console-errors` / Codex: `$browser-console-errors`
  - Claude/Antigravity: `/browser:form-submit-test` / Codex: `$browser-form-submit-test`
  - Claude/Antigravity: `/browser:mobile-test` / Codex: `$browser-mobile-test`
  - Claude/Antigravity: `/browser:smoke-test` / Codex: `$browser-smoke-test`
  - Claude/Antigravity: `/browser:visual-check` / Codex: `$browser-visual-check`

### design

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Route design-system, interaction, responsive, and accessibility work from shared acceptance criteria.
- Skills (1):
  - `ui-ux-designer/SKILL.md`
- Commands (3):
  - Claude/Antigravity: `/design:component-system` / Codex: `$design-component-system`
  - Claude/Antigravity: `/design:ui-review` / Codex: `$design-ui-review`
  - Claude/Antigravity: `/design:ux-flow` / Codex: `$design-ux-flow`

### dev

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Add frontend, backend, TypeScript, Python, and GSAP implementation adapters without duplicating role logic.
- Skills (2):
  - `code-reviewer/SKILL.md`
  - `fullstack-developer/SKILL.md`
- Commands (4):
  - Claude/Antigravity: `/dev:code-review` / Codex: `$dev-code-review`
  - Claude/Antigravity: `/dev:fix-bug` / Codex: `$dev-fix-bug`
  - Claude/Antigravity: `/dev:implement-feature` / Codex: `$dev-implement-feature`
  - Claude/Antigravity: `/dev:refactor-code` / Codex: `$dev-refactor-code`

### docs

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Generate ADRs, OpenAPI, changelogs, setup guides, and runbooks from approved project artifacts.
- Skills (1):
  - `documentation-writer/SKILL.md`
- Commands (4):
  - Claude/Antigravity: `/docs:api` / Codex: `$docs-api`
  - Claude/Antigravity: `/docs:runbook` / Codex: `$docs-runbook`
  - Claude/Antigravity: `/docs:setup-guide` / Codex: `$docs-setup-guide`
  - Claude/Antigravity: `/docs:update` / Codex: `$docs-update`

### full-team

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Orchestrate phase-owned seats with explicit inputs, outputs, workspace rules, and handoff evidence.
- Skills (0):
- Commands (1):
  - Claude/Antigravity: `/full-team:verify` / Codex: `$full-team-verify`

### gate

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Unify acceptance, security, performance, accessibility, and deployment evidence into one release decision.
- Skills (2):
  - `production-readiness-reviewer/SKILL.md`
  - `quality-gatekeeper/SKILL.md`
- Commands (6):
  - Claude/Antigravity: `/gate:before-code` / Codex: `$gate-before-code`
  - Claude/Antigravity: `/gate:before-deploy` / Codex: `$gate-before-deploy`
  - Claude/Antigravity: `/gate:before-merge` / Codex: `$gate-before-merge`
  - Claude/Antigravity: `/gate:finalize-evidence` / Codex: `$gate-finalize-evidence`
  - Claude/Antigravity: `/gate:production-ready` / Codex: `$gate-production-ready`
  - Claude/Antigravity: `/gate:score-project` / Codex: `$gate-score-project`

### git

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Make branch, commit, review, issue sync, and release-note work respect the no-bypass safety contract.
- Skills (1):
  - `git-workflow-manager/SKILL.md`
- Commands (5):
  - Claude/Antigravity: `/git:commit-plan` / Codex: `$git-commit-plan`
  - Claude/Antigravity: `/git:create-branch` / Codex: `$git-create-branch`
  - Claude/Antigravity: `/git:pr-review` / Codex: `$git-pr-review`
  - Claude/Antigravity: `/git:release-notes` / Codex: `$git-release-notes`
  - Claude/Antigravity: `/git:sync-issues` / Codex: `$git-sync-issues`

### growth

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Connect conversion audits and experiments to measurable hypotheses, events, and decision logs.
- Skills (1):
  - `conversion-optimizer/SKILL.md`
- Commands (1):
  - Claude/Antigravity: `/growth:conversion-audit` / Codex: `$growth-conversion-audit`

### project

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Add story-map and before-build risk checks before PRD, architecture, and task breakdown.
- Skills (3):
  - `capability-routing/SKILL.md`
  - `product-manager/SKILL.md`
  - `software-architect/SKILL.md`
- Commands (4):
  - Claude/Antigravity: `/project:architecture` / Codex: `$project-architecture`
  - Claude/Antigravity: `/project:capability-map` / Codex: `$capability-routing`
  - Claude/Antigravity: `/project:prd` / Codex: `$project-prd`
  - Claude/Antigravity: `/project:task-breakdown` / Codex: `$project-task-breakdown`

### release

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Attach reproducible build provenance, deployment strategy, rollback, and CI evidence to every release.
- Skills (2):
  - `devops-engineer/SKILL.md`
  - `security-reviewer/SKILL.md`
- Commands (4):
  - Claude/Antigravity: `/release:ci-setup` / Codex: `$release-ci-setup`
  - Claude/Antigravity: `/release:deploy-plan` / Codex: `$release-deploy-plan`
  - Claude/Antigravity: `/release:preflight` / Codex: `$release-preflight`
  - Claude/Antigravity: `/release:rollback-plan` / Codex: `$release-rollback-plan`

### repo

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Route Graphify, Serena, Repomix, and code-review context by question type instead of activating all tools.
- Skills (1):
  - `repo-analyzer/SKILL.md`
- Commands (5):
  - Claude/Antigravity: `/repo:dependency-map` / Codex: `$repo-dependency-map`
  - Claude/Antigravity: `/repo:find-dead-code` / Codex: `$repo-find-dead-code`
  - Claude/Antigravity: `/repo:map` / Codex: `$repo-map`
  - Claude/Antigravity: `/repo:onboarding` / Codex: `$repo-onboarding`
  - Claude/Antigravity: `/repo:risk-map` / Codex: `$repo-risk-map`

### security

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Run threat modeling, abuse cases, authorization matrices, secret checks, and RLS evidence before release.
- Skills (1):
  - `authz-security-reviewer/SKILL.md`
- Commands (5):
  - Claude/Antigravity: `/security:abuse-cases` / Codex: `$security-abuse-cases`
  - Claude/Antigravity: `/security:authz-matrix` / Codex: `$security-authz-matrix`
  - Claude/Antigravity: `/security:rls-test` / Codex: `$security-rls-test`
  - Claude/Antigravity: `/security:secrets-fix` / Codex: `$security-secrets-fix`
  - Claude/Antigravity: `/security:threat-model` / Codex: `$security-threat-model`

### seo

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Treat technical SEO, structured data, GEO, content, image, and sitemap checks as acceptance criteria.
- Skills (22):
  - `seo/SKILL.md`
  - `seo-backlinks/SKILL.md`
  - `seo-cluster/SKILL.md`
  - `seo-competitor-pages/SKILL.md`
  - `seo-content/SKILL.md`
  - `seo-content-brief/SKILL.md`
  - `seo-drift/SKILL.md`
  - `seo-ecommerce/SKILL.md`
  - `seo-flow/SKILL.md`
  - `seo-geo/SKILL.md`
  - `seo-google/SKILL.md`
  - `seo-hreflang/SKILL.md`
  - `seo-images/SKILL.md`
  - `seo-local/SKILL.md`
  - `seo-maps/SKILL.md`
  - `seo-page/SKILL.md`
  - `seo-plan/SKILL.md`
  - `seo-programmatic/SKILL.md`
  - `seo-schema/SKILL.md`
  - `seo-sitemap/SKILL.md`
  - `seo-sxo/SKILL.md`
  - `seo-technical/SKILL.md`
- Commands (22):
  - Claude/Antigravity: `/seo:audit` / Codex: `$seo-audit`
  - Claude/Antigravity: `/seo:backlinks` / Codex: `$seo-backlinks`
  - Claude/Antigravity: `/seo:cluster` / Codex: `$seo-cluster`
  - Claude/Antigravity: `/seo:competitor-pages` / Codex: `$seo-competitor-pages`
  - Claude/Antigravity: `/seo:content-brief` / Codex: `$seo-content-brief`
  - Claude/Antigravity: `/seo:content` / Codex: `$seo-content`
  - Claude/Antigravity: `/seo:drift` / Codex: `$seo-drift`
  - Claude/Antigravity: `/seo:ecommerce` / Codex: `$seo-ecommerce`
  - Claude/Antigravity: `/seo:flow` / Codex: `$seo-flow`
  - Claude/Antigravity: `/seo:geo` / Codex: `$seo-geo`
  - Claude/Antigravity: `/seo:google` / Codex: `$seo-google`
  - Claude/Antigravity: `/seo:hreflang` / Codex: `$seo-hreflang`
  - Claude/Antigravity: `/seo:images` / Codex: `$seo-images`
  - Claude/Antigravity: `/seo:local` / Codex: `$seo-local`
  - Claude/Antigravity: `/seo:maps` / Codex: `$seo-maps`
  - Claude/Antigravity: `/seo:page` / Codex: `$seo-page`
  - Claude/Antigravity: `/seo:plan` / Codex: `$seo-plan`
  - Claude/Antigravity: `/seo:programmatic` / Codex: `$seo-programmatic`
  - Claude/Antigravity: `/seo:schema` / Codex: `$seo-schema`
  - Claude/Antigravity: `/seo:sitemap` / Codex: `$seo-sitemap`
  - Claude/Antigravity: `/seo:sxo` / Codex: `$seo-sxo`
  - Claude/Antigravity: `/seo:technical` / Codex: `$seo-technical`

### site-doctor

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Make health audits composable across accessibility, content, APIs, dependencies, infrastructure, and observability.
- Skills (27):
  - `accessibility-review/SKILL.md`
  - `analytics-audit/SKILL.md`
  - `animation-design-audit/SKILL.md`
  - `api-audit/SKILL.md`
  - `backup-recovery/SKILL.md`
  - `compliance-check/SKILL.md`
  - `content-audit/SKILL.md`
  - `cost-optimization/SKILL.md`
  - `data-migration/SKILL.md`
  - `database-audit/SKILL.md`
  - `database-debug/SKILL.md`
  - `database-fix/SKILL.md`
  - `dependency-audit/SKILL.md`
  - `deployment-review/SKILL.md`
  - `email-deliverability/SKILL.md`
  - `forms-audit/SKILL.md`
  - `incident-response/SKILL.md`
  - `infrastructure-audit/SKILL.md`
  - `load-testing/SKILL.md`
  - `mobile-audit/SKILL.md`
  - `observability/SKILL.md`
  - `performance-tuning/SKILL.md`
  - `security-review/SKILL.md`
  - `seo-optimization/SKILL.md`
  - `website-audit/SKILL.md`
  - `website-debug/SKILL.md`
  - `website-fix/SKILL.md`
- Commands (25):
  - Claude/Antigravity: `/site-doctor:a11y` / Codex: `$site-doctor-a11y`
  - Claude/Antigravity: `/site-doctor:animation` / Codex: `$site-doctor-animation`
  - Claude/Antigravity: `/site-doctor:audit-analytics` / Codex: `$site-doctor-audit-analytics`
  - Claude/Antigravity: `/site-doctor:audit-api` / Codex: `$site-doctor-audit-api`
  - Claude/Antigravity: `/site-doctor:audit-content` / Codex: `$site-doctor-audit-content`
  - Claude/Antigravity: `/site-doctor:audit-db` / Codex: `$site-doctor-audit-db`
  - Claude/Antigravity: `/site-doctor:audit-deps` / Codex: `$site-doctor-audit-deps`
  - Claude/Antigravity: `/site-doctor:audit-forms` / Codex: `$site-doctor-audit-forms`
  - Claude/Antigravity: `/site-doctor:audit-infra` / Codex: `$site-doctor-audit-infra`
  - Claude/Antigravity: `/site-doctor:audit-mobile` / Codex: `$site-doctor-audit-mobile`
  - Claude/Antigravity: `/site-doctor:audit-site` / Codex: `$site-doctor-audit-site`
  - Claude/Antigravity: `/site-doctor:backups` / Codex: `$site-doctor-backups`
  - Claude/Antigravity: `/site-doctor:compliance` / Codex: `$site-doctor-compliance`
  - Claude/Antigravity: `/site-doctor:cost` / Codex: `$site-doctor-cost`
  - Claude/Antigravity: `/site-doctor:debug` / Codex: `$site-doctor-debug`
  - Claude/Antigravity: `/site-doctor:email-check` / Codex: `$site-doctor-email-check`
  - Claude/Antigravity: `/site-doctor:full-checkup` / Codex: `$site-doctor-full-checkup`
  - Claude/Antigravity: `/site-doctor:incident` / Codex: `$site-doctor-incident`
  - Claude/Antigravity: `/site-doctor:load-test` / Codex: `$site-doctor-load-test`
  - Claude/Antigravity: `/site-doctor:migrate-data` / Codex: `$site-doctor-migrate-data`
  - Claude/Antigravity: `/site-doctor:monitoring` / Codex: `$site-doctor-monitoring`
  - Claude/Antigravity: `/site-doctor:perf` / Codex: `$site-doctor-perf`
  - Claude/Antigravity: `/site-doctor:review-deploy` / Codex: `$site-doctor-review-deploy`
  - Claude/Antigravity: `/site-doctor:security-scan` / Codex: `$site-doctor-security-scan`
  - Claude/Antigravity: `/site-doctor:seo` / Codex: `$site-doctor-seo`

### solo

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Keep project memory, decisions, handoffs, and next-step selection stable across every platform.
- Skills (3):
  - `memory-sync/SKILL.md`
  - `project-memory-manager/SKILL.md`
  - `suite-integrity/SKILL.md`
- Commands (10):
  - Claude/Antigravity: `/solo:end-session` / Codex: `$solo-end-session`
  - Claude/Antigravity: `/solo:full-team-dev` / Codex: `$solo-full-team-dev`
  - Claude/Antigravity: `/solo:handoff-memory` / Codex: `$solo-handoff-memory`
  - Claude/Antigravity: `/solo:next-step` / Codex: `$solo-next-step`
  - Claude/Antigravity: `/solo:project-status` / Codex: `$solo-project-status`
  - Claude/Antigravity: `/solo:run-cycle` / Codex: `$solo-run-cycle`
  - Claude/Antigravity: `/solo:self-check` / Codex: `$solo-self-check`
  - Claude/Antigravity: `/solo:start-session` / Codex: `$solo-start-session`
  - Claude/Antigravity: `/solo:sync-grafana` / Codex: `$solo-sync-grafana`
  - Claude/Antigravity: `/solo:sync-obsidian` / Codex: `$solo-sync-obsidian`

### spec

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Turn feature briefs and API contracts into the shared input for design, architecture, implementation, and QA.
- Skills (2):
  - `acceptance-criteria-writer/SKILL.md`
  - `api-contract-designer/SKILL.md`
- Commands (5):
  - Claude/Antigravity: `/spec:acceptance` / Codex: `$spec-acceptance`
  - Claude/Antigravity: `/spec:api-contract` / Codex: `$spec-api-contract`
  - Claude/Antigravity: `/spec:data-contract` / Codex: `$spec-data-contract`
  - Claude/Antigravity: `/spec:env-contract` / Codex: `$spec-env-contract`
  - Claude/Antigravity: `/spec:feature-brief` / Codex: `$spec-feature-brief`

### stack

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Capture the real hosting, database, auth, CDN, analytics, email, and payment stack before vendor-specific audits.
- Skills (7):
  - `cloudflare-audit/SKILL.md`
  - `connector-auditor/SKILL.md`
  - `payments-audit/SKILL.md`
  - `stack-advisor/SKILL.md`
  - `supabase-audit/SKILL.md`
  - `tag-audit/SKILL.md`
  - `vercel-audit/SKILL.md`
- Commands (7):
  - Claude/Antigravity: `/stack:audit-cloudflare` / Codex: `$stack-audit-cloudflare`
  - Claude/Antigravity: `/stack:audit-payments` / Codex: `$stack-audit-payments`
  - Claude/Antigravity: `/stack:audit-supabase` / Codex: `$stack-audit-supabase`
  - Claude/Antigravity: `/stack:audit-tags` / Codex: `$stack-audit-tags`
  - Claude/Antigravity: `/stack:audit-vercel` / Codex: `$stack-audit-vercel`
  - Claude/Antigravity: `/stack:connector-check` / Codex: `$stack-connector-check`
  - Claude/Antigravity: `/stack:intake` / Codex: `$stack-intake`

### test

- Plugin compatibility: Claude yes / Antigravity yes / Codex yes
- Implementation idea: Use acceptance criteria as a QA contract and combine unit, integration, E2E, edge-case, and performance checks.
- Skills (1):
  - `qa-engineer/SKILL.md`
- Commands (4):
  - Claude/Antigravity: `/test:e2e` / Codex: `$test-e2e`
  - Claude/Antigravity: `/test:edge-cases` / Codex: `$test-edge-cases`
  - Claude/Antigravity: `/test:integration` / Codex: `$test-integration`
  - Claude/Antigravity: `/test:unit` / Codex: `$test-unit`

## Learned role capability mapping

| Role | Learned upstream capabilities | Native Solo Suite route | Status |
| --- | --- | --- | --- |
| Product Manager | `storymap-skill`, `before-you-build`, `conductor`, `business-analytics`, `startup-business-analyst` | `project`, `growth`, `spec` | Learned + routed; exact upstream package remains attribution/reference material |
| UI/UX Designer | `ui-design`, `accessibility-compliance`, `brand-landingpage`, `documentation-generation` | `design`, `browser`, `seo`, `docs` | Learned + routed; exact upstream package remains attribution/reference material |
| Software Architect | `c4-architecture`, `cloud-infrastructure`, `backend-development`, `database-design`, `full-stack-orchestration` | `project`, `repo`, `stack`, `spec`, `dev` | Learned + routed; exact upstream package remains attribution/reference material |
| Frontend Developer | `javascript-typescript`, `frontend-mobile-development`, `developer-essentials`, `application-performance`, `accessibility-compliance` | `dev`, `design`, `browser` | Learned + routed; exact upstream package remains attribution/reference material |
| GSAP Animation Developer | `gsap-core`, `gsap-timeline`, `gsap-scrolltrigger`, `gsap-plugins`, `gsap-utils`, `gsap-react`, `gsap-performance`, `gsap-frameworks` | `dev`, `design`, `browser` | Learned + routed; exact upstream package remains attribution/reference material |
| Backend Developer | `backend-development`, `api-scaffolding`, `backend-api-security`, `api-testing-observability`, `javascript-typescript`, `python-development` | `dev`, `security`, `spec`, `test` | Learned + routed; exact upstream package remains attribution/reference material |
| Database Engineer | `database-design`, `database-migrations`, `database-cloud-optimization`, `data-validation-suite` | `stack`, `security`, `site-doctor`, `test` | Learned + routed; exact upstream package remains attribution/reference material |
| QA Engineer | `qa-orchestra`, `unit-testing`, `tdd-workflows`, `performance-testing-review`, `deployment-validation` | `test`, `browser`, `site-doctor`, `gate` | Learned + routed; exact upstream package remains attribution/reference material |
| Security Reviewer | `security-scanning`, `security-compliance`, `backend-api-security`, `frontend-mobile-security`, `verification-integrity`, `tool-permission-governance` | `security`, `git`, `gate`, `site-doctor` | Learned + routed; exact upstream package remains attribution/reference material |
| DevOps Engineer | `cicd-automation`, `deployment-strategies`, `deployment-validation`, `cloud-infrastructure`, `kubernetes-operations`, `observability-monitoring`, `incident-response` | `release`, `stack`, `site-doctor`, `git`, `gate` | Learned + routed; exact upstream package remains attribution/reference material |
| Technical Writer | `code-documentation`, `documentation-generation`, `documentation-standards`, `c4-architecture` | `docs`, `project`, `spec` | Learned + routed; exact upstream package remains attribution/reference material |
| Data Analyst | `business-analytics`, `data-engineering`, `data-validation-suite`, `startup-business-analyst` | `growth`, `stack`, `site-doctor`, `spec` | Learned + routed; exact upstream package remains attribution/reference material |
| Token Reduction and Repository Intelligence | `Graphify`, `Bounded Native Search`, `Official Documentation Lookup`, `Repomix` | `repo`, `ai` | Learned + routed; exact upstream package remains attribution/reference material |

## Repository-intelligence commands

- Graphify: `graphify update .`, `graphify query "..."`, `graphify explain "..."`, `graphify path "A" "B"`
- Native search: bounded symbol lookup with `rg`, followed by client-native workspace editing
- Official docs: current, version-specific primary documentation through reviewed host web access
- Repomix: bounded repository snapshots and handoffs
- Rejected: Aider, Serena, Context7, and Code Review Graph have no activation path

## Recommended entry points

1. Use `/project:capability-map` or `$capability-routing`.
2. Read the generated `.solo/capability-plan.md`.
3. Activate only the listed owner and supporting plugins.
4. Pass the declared artifact to the next handoff and gate.
