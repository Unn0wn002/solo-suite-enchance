---
name: api-audit
description: Audit a REST or GraphQL API for design, security, and reliability — authentication and authorization, input validation, rate limiting, error handling and status codes, versioning, pagination, CORS, REST conventions or GraphQL-specific risks (introspection, query depth/complexity, batching abuse), and documentation. Use whenever the user wants to review, audit, or harden an API or backend, asks "is my API secure/well-designed", mentions REST/GraphQL/endpoints, or is about to expose an API publicly. Pairs with security-review for full backend coverage.
---

# API Audit

APIs fail differently from pages: the client is untrusted and often not a browser, so **every guarantee must be enforced server-side**, and errors/limits/contracts matter as much as features. Review design, security, and reliability together — a well-designed but unauthenticated API is still a breach.

## Setup

Identify the style (REST / GraphQL / RPC), how it authenticates, whether it's public or internal, and get either the running endpoint (with authorization to test) or the route/resolver code. Read the code for causes; confirm with safe requests (`curl`, no destructive payloads). Enumerate the endpoints/operations first so coverage is complete.

## Security (do this first)

### Authentication
- Every non-public endpoint requires valid credentials; there are no forgotten unauthenticated routes (test a few directly without a token).
- Token handling is sound: short-lived access tokens, refresh rotation, proper signature validation (reject `alg: none`, verify issuer/audience/expiry on JWTs), revocation works.
- No API keys or secrets in URLs (they leak into logs/history) — use headers.

### Authorization (the most common serious API flaw)
- **Object-level (BOLA/IDOR)**: an authenticated user can't access another user's objects by changing an ID. Test: fetch your resource, then request a resource ID you don't own with your token — it must be denied, not just hidden in the UI.
- **Function-level**: normal users can't hit admin operations; authorization is checked on the server for every request, deny-by-default.
- **Property-level (mass assignment)**: the API doesn't blindly bind request fields to the model — a user can't set `role: admin` or `isVerified: true` by adding it to the payload. Allowlist writable fields.

### Input validation
- Validate type, format, range, and length on **every** input server-side (client validation is UX, not security). Reject unexpected fields.
- Parameterized queries everywhere (no string-built SQL/NoSQL — see **security-review** A03).
- File uploads: validate type/size, store outside the webroot, scan, don't trust the client-provided filename or MIME.

### Rate limiting & abuse
- Rate limits on all endpoints, tighter on auth/reset/OTP and expensive operations. Returns `429` with `Retry-After`.
- Protection against enumeration (uniform responses/timing on login and "forgot password") and against resource exhaustion (pagination caps, payload size limits).

### Transport & CORS
- HTTPS enforced; HSTS. CORS allowlist is explicit (no reflecting arbitrary `Origin`, no `*` with credentials); only the methods/headers actually needed are allowed.

## Design & conventions

### REST
- Nouns for resources, HTTP methods for actions (`GET` safe/idempotent, `POST` create, `PUT`/`PATCH` update, `DELETE` remove) — not `GET /deleteUser`.
- **Correct status codes**: 200/201/204 success, 400 bad input, 401 unauthenticated, 403 unauthorized, 404 not found, 409 conflict, 422 validation, 429 rate-limited, 5xx server. Don't return 200 with an error body.
- **Consistent error shape**: a stable JSON schema (code, message, details) across all endpoints; messages helpful but not leaking internals/stack traces.
- **Pagination** on list endpoints (cursor-based preferred for large/changing sets over offset); consistent `limit` with a hard max; filtering/sorting documented.
- **Versioning** strategy (URL `/v1` or header) so breaking changes don't break clients; deprecation policy.
- Idempotency keys for unsafe operations that may be retried (payments especially).

### GraphQL
- **Introspection disabled in production** (or access-controlled) — it hands attackers the full schema.
- **Depth & complexity limiting**: a maliciously nested query can DoS the server; enforce max depth and query cost analysis.
- **Rate limiting by query cost**, not request count (one request can be arbitrarily expensive).
- **Batching abuse**: aliased/batched queries can bypass naive per-operation rate limits and enable brute force — limit operations per request.
- **N+1 in resolvers**: use DataLoader/batching so a nested query doesn't fan out into hundreds of DB calls (hand off to **database-debug** if resolvers are slow).
- **Field-level authorization**: auth enforced per field/resolver, not just at the query root; error messages don't distinguish "doesn't exist" from "not allowed" when that leaks data.

## Reliability

- Graceful handling of malformed/oversized requests (no crash, no 500 with a stack trace).
- Timeouts and circuit breakers on downstream calls; retries with backoff where safe.
- Consistent behavior under concurrency (no race conditions on writes — see **database-fix** for constraints).
- Observability: request logging, error tracking, and latency metrics per endpoint (hand off to **observability** to build this out).

## Documentation

- An accurate, current spec (OpenAPI/Swagger for REST, the schema + docs for GraphQL) matching real behavior; examples for requests/responses/errors; auth clearly explained. Drift between docs and reality is itself a finding.

## Report format

Shared audit structure (Summary → Scorecard → Findings → Fix order), grouped **Security / Design / Reliability / Docs**. Each finding names the endpoint or resolver, gives a safe repro (the request that demonstrates it), and the fix. Rank by exploitability and blast radius — broken object-level authorization and missing input validation top the list. Route code fixes through the app and any query/schema issues through **database-fix**; overlapping vuln classes are detailed in **security-review**.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
