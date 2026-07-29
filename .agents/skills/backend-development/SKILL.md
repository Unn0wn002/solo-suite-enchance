---
name: backend-development
description: Implement or review server APIs, domain logic, authorization boundaries, validation, failure handling, and observability. Activate for backend or service changes; do not activate for database-only schema analysis or frontend-only work.
---

# Backend development

Use the `backend` profile.

1. Confirm the API/data contract, caller identity, authorization rule, and failure semantics.
2. Validate untrusted input at the boundary and enforce authorization at the resource operation.
3. Keep side effects idempotent where retries are possible and bound network, memory, and query work.
4. Avoid secret exposure in errors and logs; add useful structured diagnostics without personal data.
5. Add unit and integration coverage for success, denial, invalid input, dependency failure, and replay/retry behavior.

Output code, contract changes, tests, operational notes, and database/QA handoffs. Verify migrations and external dependencies are explicit rather than silently installed or configured.
