# Tests — Solo Suite Enchance

Repository-level test scope is AI tooling only.

- `tests/capability-inventory.test.mjs`: generated capability inventory/catalog integrity.
- `tests/core-tooling.test.mjs`: repository-intelligence tooling contract.
- `scripts/sync-agent-skills.py --check`: generated Claude skill mirror parity.
- Structural, workflow/command, distribution, license, link, audit, token-report, and Graphify-snapshot checks run in CI.
- Native Claude/Codex/Antigravity validation runs in Linux smoke jobs and the Windows full-distribution harness.
- Dependency/remediation security validation runs separately and fails closed for new high/critical dependency findings.

Application UI, rendered HTML, bundle-budget, browser, database, or deployment tests do not belong in this repository.
