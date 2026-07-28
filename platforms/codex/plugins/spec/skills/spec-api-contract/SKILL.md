---
name: spec-api-contract
description: "Define the REST/GraphQL API contract before backend implementation. Use when the user explicitly invokes $spec-api-contract or asks for this spec api-contract workflow."
---

# Spec API Contract

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $api-contract-designer. Apply it to the user's supplied arguments and surrounding request.

Define operations, request/response schemas with examples, status codes and the error shape, per-endpoint auth + authorization, and pagination/versioning. Keep it consistent with the data model; write it into `.solo/architecture.md` (or a contract doc).


Write the contract to **`.solo/api-contract.md`** (read `.solo/architecture.md` first).

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
