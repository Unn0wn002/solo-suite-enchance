---
description: Define database entities, constraints, and relationships.
argument-hint: <domain or feature>
---
Use the **software-architect** skill to define a data contract (do a lighter inline version if that plugin isn't installed). $ARGUMENTS

Specify entities, fields + types, keys, constraints (NOT NULL / unique / FK / check), relationships and cardinality, and indexes. Keep it consistent with the API contract and note migration impact. Pairs with `/site-doctor:audit-db` and, for Supabase, `/security:rls-test`.


Write the contract to **`.solo/data-contract.md`** (keep consistent with `.solo/api-contract.md`).

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
