---
name: database-audit
description: Audit a database for schema quality, missing or wasted indexes, slow queries, security misconfiguration, data integrity problems, and operational risk. Works with PostgreSQL, MySQL, and SQLite. Use whenever the user asks to audit, review, check, or health-check a database or schema, asks "why are queries slow", "are my indexes right", "is my DB production ready", mentions a migration review, or wants a database checked alongside a website audit.
---

# Database Audit

**AgentRoom proposal mode:** audit evidence stays in the seat's declared direct artifact. Tasks, decisions, handoff, or any other target declared under `proposes` must be written as `.solo/proposals/<seat>-<run_id>.md` with target and proposed entries, never directly to the target. Only the steward merges; missing seat/run identity is a stop condition.

An audit is read-only. Run only SELECTs, EXPLAINs, SHOWs, and **read-only** PRAGMAs (query form, never `PRAGMA x = value`, never `PRAGMA optimize`, never `ANALYZE`/`VACUUM`/`REINDEX`) — never mutate data, schema, or planner statistics while auditing, and prefer a read-only role or a recent snapshot for production databases. Findings get fixed later via the **database-fix** skill.

## Setup

1. Identify the engine and version (`SELECT version();` / `SELECT sqlite_version();`) — the checks and queries differ per engine.
2. Get access without collecting secrets in chat: for PG/MySQL request only
   the **name** of an environment variable, client profile, local socket, or
   secret-store reference, and confirm the resolved account is read-only.
   Never ask for or repeat a credential-bearing connection string. For SQLite,
   use a file path. If live access is unavailable, ask for schema dumps
   (`pg_dump --schema-only`, `mysqldump --no-data`, `.schema`) plus a redacted
   slow-query log and audit from those.
3. Ask what the workload looks like (read-heavy web app? write-heavy ingest?) — a "missing index" on a table written 1000×/sec and read once/day is not a finding.

**Ready-to-run queries for every check below live in `references/audit-queries.md`, grouped by engine. Open it and use those instead of writing queries from scratch.**

## Audit categories

### 1. Schema quality
- Every table has a primary key. (No PK breaks replication, ORMs, and dedup.)
- Foreign keys are declared as constraints, not just implied by naming. On SQLite, additionally verify `PRAGMA foreign_keys` is actually ON — it defaults to OFF per connection, so declared FKs may be silently unenforced.
- Types fit the data: timestamps use timezone-aware types on PG (`timestamptz`), monetary values are not floats, no `TEXT` for things that need range/format constraints without a `CHECK`.
- Cross-engine portability (if the schema targets multiple engines): prefer `TEXT` + `CHECK` constraints over native `ENUM`s, application-generated UUIDs over engine-specific defaults, and `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` — flag engine-specific features that will break a portability contract.
- `NOT NULL` on columns the application always requires; consistent naming convention; soft-delete columns (`deleted_at`) applied consistently and included in unique indexes where needed (a unique email + soft delete = the next signup with that email fails).

### 2. Indexes
- Every foreign key column has an index whose leading column covers it (MySQL/InnoDB creates these automatically; PG and SQLite do not).
- No unused indexes burning write throughput and disk (check scan counters — with the caveat that stats reset and replicas differ).
- No redundant indexes (an index on `(a)` is redundant if `(a, b)` exists).
- Composite index column order matches actual query patterns: equality columns first, then range columns.

### 3. Query performance
- Pull the top queries by total time (pg_stat_statements / sys.statement_analysis / app logs for SQLite) and `EXPLAIN` the worst 5.
- Flag sequential/full scans on large tables, sorts spilling to disk, and nested-loop joins over big row counts.
- If the app code is available, look for N+1 patterns: a query in a loop, or ORM lazy-loading inside list rendering.

### 4. Security
- Application connects with a least-privilege role, not a superuser/root.
- No plaintext secrets in the DB; encrypted values stored with a key-versioning scheme (envelope encryption) so keys can rotate.
- Connections use TLS in production; no `0.0.0.0` bind or open firewall to the DB port.
- App code uses parameterized queries everywhere — grep for string-built SQL (`"... WHERE id = " +`, f-strings/template literals feeding query functions).
- Connection strings not committed to the repo (`grep -rn "postgres://\|mysql://" --include="*.{js,ts,py,env,json,yml}" .` then verify hits).

### 5. Data integrity
- Orphaned rows: children referencing missing parents (found where FK constraints are absent or were added later).
- Duplicate rows in columns that should be unique but lack a constraint.
- NULLs or sentinel values (`''`, `0`, `1970-01-01`) in columns the app treats as required.
- SQLite: run `PRAGMA integrity_check` and `PRAGMA foreign_key_check` — they find real corruption and FK violations directly.

### 6. Operations
- Backups exist, run on schedule, and have been restore-tested at least once (an untested backup is a hope, not a backup).
- Migration history is linear and applied consistently across environments.
- PG: autovacuum keeping up (dead-tuple counts), bloat on hot tables. SQLite: journal mode is WAL for concurrent web workloads, and the freelist isn't huge (VACUUM candidate).
- Disk headroom and growth rate.

## Severity rubric

Critical = data loss/exposure possible now (no backups, root app user, injectable SQL, FK enforcement off with orphaned rows accumulating). High = active performance or correctness damage (missing FK index on a hot join, unconstrained duplicates). Medium = fix this sprint (redundant indexes, missing NOT NULLs). Low = hygiene.

## Report format

Use the same structure as website-audit: Summary → Scorecard by category → Findings (Evidence / Impact / Fix, with the exact query result as evidence) → Recommended fix order. Every fix recommendation should name the migration or command, so the **database-fix** skill can execute the plan directly.

## Project memory integration (solo-team)

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
