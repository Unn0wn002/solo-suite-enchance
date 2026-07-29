---
name: database-engineering
description: Design or review schemas, migrations, constraints, indexes, query behavior, data access controls, and recovery plans. Activate for persistent-data changes or database diagnostics; do not activate for in-memory model changes with no storage impact.
---

# Database engineering

Use the `database` profile.

1. Define data ownership, lifecycle, sensitivity, cardinality, and access paths.
2. Prefer database-enforced constraints for invariants and least-privilege policies for access.
3. Review query plans and indexes against real access patterns; do not add speculative indexes.
4. Make migrations forward-safe, bounded, observable, and reversible when the datastore supports it.
5. Define backup, restore, reconciliation, and partial-failure behavior for material data changes.

Output schema/contract decisions, migration plan, query/index evidence, security boundaries, and verification results. Never run destructive migrations or production data changes without explicit authority and recovery evidence.
