---
description: Document API endpoints, auth, examples, and errors
argument-hint: [the API or endpoints to document]
---
Use the documentation-writer skill in API-docs mode for: $ARGUMENTS

Derive from .solo/architecture.md and the actual route/handler code (never aspirational).
Per endpoint: method + path, what it does, auth, params (types, required), real request/
response examples, status/error codes, and gotchas (rate limits, pagination). Generate
from an OpenAPI/GraphQL schema if one exists. Pairs with site-doctor's api-audit.

Base the API docs on the **api-contract-designer** contract in `.solo/` when one exists.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
