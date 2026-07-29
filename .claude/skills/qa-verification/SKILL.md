---
name: qa-verification
description: Design and execute risk-based unit, integration, end-to-end, accessibility, performance, and edge-case verification. Activate when behavior needs proof or regression coverage; do not activate merely to restate untestable requirements.
---

<!-- GENERATED from .agents/skills by scripts/sync-agent-skills.py; do not edit. -->

# QA verification

Use the `qa` profile.

1. Trace tests to acceptance criteria, architecture boundaries, and highest-risk failure modes.
2. Select the lowest-cost layer that can prove each behavior; reserve end-to-end tests for critical cross-boundary paths.
3. Cover success, denial, invalid data, concurrency/retry, recovery, accessibility, and relevant performance limits.
4. Keep fixtures deterministic and avoid production credentials, personal data, or uncontrolled external services.
5. Distinguish `PASSED`, `FAILED`, `BLOCKED`, and `NOT_EXECUTED`; attach the exact command and evidence.

Output a test matrix, implemented checks where requested, results, residual risk, and release-gate handoff. Never disable a failing test to make the suite pass.
