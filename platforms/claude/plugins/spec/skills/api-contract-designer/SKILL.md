---
name: api-contract-designer
description: Define the REST or GraphQL API contract before the backend is built, including the data shapes it exposes. Use when the user says API contract, endpoint design, request/response shape, "design the API", or before implementing backend routes. Produces a precise contract the frontend, backend, docs, and API audit can all rely on.
---

# API Contract Designer

Design the interface before the implementation so frontend and backend can build in parallel and nothing drifts. Works for REST and GraphQL.

## What to define
- **Operations**: each endpoint/route (REST) or query/mutation (GraphQL) — purpose, path/name, method.
- **Inputs**: path/query params, body schema, required vs optional, types, validation rules (length, format, ranges).
- **Outputs**: response schema(s) and the exact fields, with example payloads.
- **Status & errors**: success codes and the full error catalogue (validation, auth, not-found, conflict, rate-limit) with a consistent error shape.
- **Auth & authorization**: which operations need a session, and *who* is allowed (roles/ownership) — mark server-side enforcement as required and hand the authz detail to `authz-security-reviewer`.
- **Cross-cutting**: pagination, filtering/sorting, idempotency (for writes/payments), versioning, and rate limits.
- **Data shapes**: the entities the API exposes and how they map to the data model — keep consistent with `.solo/architecture.md` and any data contract.

## How to work
Confirm the stack (framework, REST vs GraphQL) from `.solo/stack.md`. Produce the contract as clear tables/schemas (and a machine-readable sketch — OpenAPI/GraphQL SDL — when useful). Keep it the single source the implementation must honor; write it into `.solo/architecture.md` or a dedicated contract doc. Note assumptions and open questions instead of guessing.

## Working with other skills
Consumed by `/docs:api` (the contract becomes the API docs) and `/site-doctor:audit-api` (audit checks reality against this contract). Pairs with `authz-security-reviewer` for per-endpoint authorization and `software-architect` for the data model.

## Output
End every run with these seven sections:
1. **Summary** — what was checked or created.
2. **Findings / Work done** — what was found, changed, or decided.
3. **Risks** — anything uncertain, dangerous, incomplete, or blocked.
4. **Required fixes** — must-fix items before moving forward.
5. **Suggested tasks** — concrete entries for `.solo/tasks.md`, each with a stable T-ID.
6. **Verification** — how to prove the result works.
7. **Next command** — the exact next slash command to run.

## Session lifecycle
Runs inside a session the solo plugin bookends: `/solo:start-session` restores `.solo/` context at the start and `/solo:end-session` saves it at the end. Read `.solo/` before acting; write findings, decisions, and tasks back (stable T-IDs) so the next command — or the next agent — picks up cleanly.

## Stack awareness
Check `.solo/stack.md` first and tailor everything to the real stack. For vendor depth the `/stack:audit-*` skills go further: Cloudflare, Vercel, Supabase, analytics/tags, payments. If a sibling skill or connector isn't installed, do a lighter inline version and say so.
