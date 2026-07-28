---
name: docs-api
description: "Document the API - endpoints, params, auth, request/response examples, errors Use when the user explicitly invokes $docs-api or asks for this docs api workflow."
---

# Docs API

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $documentation-writer in API-docs mode for the user's supplied arguments and surrounding request.

Derive from .solo/architecture.md and the actual route/handler code (never aspirational).
Per endpoint: method + path, what it does, auth, params (types, required), real request/
response examples, status/error codes, and gotchas (rate limits, pagination). Generate
from an OpenAPI/GraphQL schema if one exists. Pairs with site-doctor's api-audit.

Base the API docs on the $api-contract-designer contract in `.solo/` when one exists.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
