---
name: software-architecture
description: Define system boundaries, data flows, interfaces, deployment assumptions, and architectural decisions for a scoped change. Activate when multiple components or consequential tradeoffs are involved; do not activate for a local edit with no boundary impact.
---

# Software architecture

Use the `architecture` profile.

1. Start from approved outcomes, constraints, and current repository evidence.
2. Use Graphify only when cross-file relationships or architecture paths materially matter.
3. Define components, ownership, trust boundaries, data lifecycle, failure modes, interfaces, and migration/rollback strategy.
4. Record alternatives and the evidence behind the selected tradeoff.
5. Avoid new infrastructure, services, or dependencies without a clear requirement and operating owner.

Output an architecture decision, component/interface map, risks, verification plan, and implementation handoff. Confirm the design is testable, observable, reversible where practical, and compatible with current deployment constraints.
