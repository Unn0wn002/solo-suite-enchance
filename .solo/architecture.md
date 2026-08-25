# Architecture — Solo Suite Enchance

## Overview

Solo Suite is a repository of AI-agent extension assets and validators, not an application runtime.

## Components

- `.agents/`: canonical portable skills, rules, agents, and workflows.
- `.claude/`: Claude mirrors, commands, agents, and project permissions.
- `platforms/claude/`: native Claude distribution.
- `platforms/codex/`: native Codex distribution and migrated workflow skills.
- `platforms/antigravity/`: Antigravity distribution/adapters.
- `agent-platform/`: roles, profiles, manifests, locks, security policy, and remediation evidence.
- `scripts/`: generators, validators, audit/security tools, installers, and bounded Graphify helpers.
- `docs/agent-audit/`: AI-platform audit evidence.
- `.solo/`: repository-local project memory for Solo Suite maintenance.

## Data boundary

No application database, deployment target, environment template, generated website bundle, or consuming-project source belongs in this repository. Graphify output is derived local intelligence and is not committed by default.

## Validation boundary

Root CI validates tooling tests, generated mirrors, structural/distribution parity, licenses/links/docs, security remediation, Linux platform smoke checks, and the full Windows distribution harness.
