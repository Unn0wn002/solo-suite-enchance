---
description: Define the API contract before implementation
argument-hint: <feature or endpoints>
---
Use the **api-contract-designer** skill. $ARGUMENTS

Define operations, request/response schemas with examples, status codes and the error shape, per-endpoint auth + authorization, and pagination/versioning. Keep it consistent with the data model; write it into `.solo/architecture.md` (or a contract doc).


Write the contract to **`.solo/api-contract.md`** (read `.solo/architecture.md` first).

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
