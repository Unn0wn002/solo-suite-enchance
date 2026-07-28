---
name: database-debug
description: Diagnose live database problems in PostgreSQL, MySQL, or SQLite — connection failures, "too many connections", pool exhaustion, hanging queries, deadlocks, lock contention, "database is locked", sudden slowness, replication lag, disk-full, or suspected corruption. Use whenever a database is down, slow right now, throwing errors, or blocking an application, including when the user just pastes a database error message and asks why.
---

# Database Debug

Diagnose with read-only queries first. Killing sessions, restarting services, or changing settings comes only after you know what's happening and the user approves — on a struggling database, a reflexive restart can turn a slowdown into an outage with crash recovery on top.

## Triage: classify before digging

Ask (or determine): is the database **unreachable**, **erroring**, or **slow**? And **what changed** in the last hour — deploy, migration, traffic spike, config edit, disk filling? Most sudden database problems are downstream of a change; find the change and you're halfway done.

## Playbooks

### Can't connect (refused / timeout)
Work outward from the process:
1. Is it running? `pg_isready -h host -p 5432` / `mysqladmin ping` / for SQLite, does the file exist and is it readable by the app user?
2. Listening where you think? `ss -tlnp | grep 5432` — PG's `listen_addresses` and MySQL's `bind-address` default to localhost; a remote app can't reach that.
3. Allowed in? PG: `pg_hba.conf` entry for the client's IP/user/database (error message names the missing entry). Firewall/security group open on the port?
4. TLS mismatch: client requiring SSL against a server without it (or vice versa) fails with misleading errors — test with `sslmode=disable` once, diagnostically, never as the fix.

### Too many connections / pool exhausted
See who's holding them:
- PG: `SELECT state, count(*) FROM pg_stat_activity GROUP BY state;` — a pile of `idle in transaction` means the app opens transactions and doesn't commit/rollback (often a missing `finally` around request handlers).
- MySQL: `SHOW PROCESSLIST;` and `SHOW VARIABLES LIKE 'max_connections';`
- Compare app pool size × instance count against the server's max. The durable fix is fixing the connection leak or adding a pooler (pgbouncer) — raising max_connections just moves the cliff.

### Queries hanging / everything waiting
Find the blocker, not the victims:
```sql
-- PostgreSQL: who blocks whom
SELECT blocked.pid AS blocked_pid, left(blocked.query, 60) AS blocked_query,
       blocking.pid AS blocking_pid, left(blocking.query, 60) AS blocking_query,
       blocking.state AS blocking_state
FROM pg_stat_activity blocked
JOIN unnest(pg_blocking_pids(blocked.pid)) AS bp(pid) ON true
JOIN pg_stat_activity blocking ON blocking.pid = bp.pid;
```
MySQL: `SELECT * FROM sys.innodb_lock_waits;`
The root blocker is very often an `idle in transaction` session or a long-running migration taking an exclusive lock. To clear it (with approval): PG `SELECT pg_terminate_backend(<pid>);`, MySQL `KILL <id>;`. Then fix why it held the lock.

### Deadlocks
The engine already resolved it (one transaction was killed) — your job is prevention. Read the deadlock report (PG logs; MySQL `SHOW ENGINE INNODB STATUS;` LATEST DETECTED DEADLOCK section) to see the two lock orders. Fixes, in order of preference: make all code paths touch tables/rows in one consistent order; shorten transactions; add retry-with-backoff for the transient remainder. Deadlock retries are normal to have; frequent deadlocks are a design smell.

### "database is locked" (SQLite)
SQLite allows one writer. Standard remediation set:
1. `PRAGMA journal_mode=WAL;` — readers stop blocking the writer.
2. Set `busy_timeout` (e.g. 5000ms) on **every** connection so writers queue instead of failing instantly.
3. Keep write transactions short; never hold one across an await/network call.
4. One writer connection per process where possible; if multiple processes write heavily, the honest fix is graduating to PG/MySQL.

### Suddenly slow (was fine yesterday)
- Recent deploy or migration? A new query shape or a dropped index shows up here.
- Stale statistics → bad plans: PG `ANALYZE;` (check `last_autoanalyze`), MySQL `ANALYZE TABLE`, SQLite `ANALYZE;`. Cheap to run, frequently the whole fix after bulk loads.
- One bad query eating the box: PG `SELECT pid, now()-query_start AS age, left(query,80) FROM pg_stat_activity WHERE state='active' ORDER BY age DESC;` then `EXPLAIN (ANALYZE, BUFFERS)` the culprit (on a copy of the query, not by re-running an expensive write).
- PG bloat: heavy update/delete tables with lagging autovacuum read far more pages than their live rows justify — check dead-tuple counts (queries in database-audit's references).
- System level: disk latency, swap, a backup job or ANALYZE running during peak.

### Disk full
Emergency order: free space first (rotate/compress logs, drop known-temp objects), because some engines can't even start transactions to clean up at 100%. PG-specific: WAL accumulation from a dead replication slot is a classic silent disk-filler — `SELECT slot_name, active FROM pg_replication_slots;` and drop abandoned slots. Then set up growth alerts at 80%.

### Suspected corruption
Stop writes. Take a file-level copy before any repair attempt. SQLite: `PRAGMA integrity_check;` and recover with `.recover`. PG/MySQL: corruption usually means restore-from-backup; attempt in-place repair only on the copy. If there's no backup, say so plainly and make the copy the first backup.

## Handoffs

Structural findings (missing index, schema problem) → **database-fix** for safe remediation. If the symptom started as a slow web page, close the loop with **website-debug** to confirm the page is healthy end-to-end.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
