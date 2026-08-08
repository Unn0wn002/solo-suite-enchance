---
description: Conduct a five-axis code review — correctness, readability, architecture, security, performance
---

Follow repository authority and safety boundaries. Invocation does not authorize commits, pushes, deployments, destructive operations, package/MCP installation, credential access, or external writes; obtain explicit approval where required.


Invoke the code-review-and-quality skill.

Review the current changes (staged or recent commits) across all five axes:

1. **Correctness** — Does it match the spec? Edge cases handled? Tests adequate?
2. **Readability** — Clear names? Straightforward logic? Well-organized?
3. **Architecture** — Follows existing patterns? Clean boundaries? Right abstraction level?
4. **Security** — Input validated? Secrets safe? Auth checked? (Use security-and-hardening skill)
5. **Performance** — No N+1 queries? No unbounded ops? (Use performance-optimization skill)

Categorize findings as Critical, Important, or Suggestion.
Output a structured review with specific file:line references and fix recommendations.
