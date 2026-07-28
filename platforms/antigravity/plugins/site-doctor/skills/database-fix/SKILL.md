---
name: database-fix
description: Safely apply database fixes in PostgreSQL, MySQL, or SQLite — add missing indexes without downtime, write reversible migrations, add constraints to existing data, backfill columns, deduplicate rows, and clean orphaned records. Use when the user says "fix the database issues", "add the missing indexes", "write a migration for", "clean up the orphaned rows", or wants any schema or data change applied from an audit or debug finding.
---

# Database Fix

Schema and data changes are the highest-blast-radius edits in a codebase — a bad one can lock a production table or destroy rows irreversibly. Every fix here follows the same contract: **restore point → smallest safe change → verify → next**.

**Manual execution boundary:** generate and review fixes freely, but never run DDL, DML, maintenance statements, migrations, or database tooling against a live database until the user has confirmed the exact target, restore point, statement, and expected impact. Approval is per state-changing step, not blanket approval for the session.

## Golden rules

1. **Restore point first.** Confirm a recent backup exists (`pg_dump`, `mysqldump`, or a file copy for SQLite) before any DDL or bulk write. For SQLite specifically: `cp app.db app.db.bak` is one command and makes everything below reversible.
2. **Write migrations, not ad-hoc statements**, when the project has a migration tool — with a working `down`/rollback for each `up`.
3. **One logical change per migration.** A failed half-applied mega-migration is far worse than five small ones. Note: MySQL DDL auto-commits (it is not transactional), so on MySQL small migrations aren't just tidy — they're the only rollback granularity you get. PG DDL is transactional; SQLite mostly is.
4. **Preview every bulk write.** Before any `UPDATE`/`DELETE`, run the same `WHERE` as a `SELECT count(*)` and show the number. No mass write without a reviewed WHERE clause and row count.
5. **Verify after each fix** — re-run the audit query that flagged it, and `EXPLAIN` to confirm new indexes are actually used.
6. **Never drop** tables, columns, or data without explicit confirmation naming the object. Prefer rename-then-drop-later (`ALTER TABLE x RENAME TO x_deprecated_20260707`) so there's an undo window.

## Recipes

### Add an index without blocking writes
- PG: `CREATE INDEX CONCURRENTLY idx_orders_user_id ON orders (user_id);` — can't run inside a transaction; if it fails it leaves an INVALID index, so check `\d orders` after and drop/retry on failure.
- MySQL 8 (InnoDB): `ALTER TABLE orders ADD INDEX idx_orders_user_id (user_id), ALGORITHM=INPLACE, LOCK=NONE;`
- SQLite: `CREATE INDEX` takes the write lock for its duration — run at low traffic; it's usually fast.

Composite order: equality-filtered columns first, range columns last (`WHERE user_id = ? AND created_at > ?` → index `(user_id, created_at)`).

### Add NOT NULL to an existing column
Backfill, then constrain — never constrain first:
```sql
UPDATE t SET col = <default> WHERE col IS NULL;   -- preview count first (rule 4)
-- PG (avoids a long table-lock validation on big tables):
ALTER TABLE t ADD CONSTRAINT t_col_nn CHECK (col IS NOT NULL) NOT VALID;
ALTER TABLE t VALIDATE CONSTRAINT t_col_nn;       -- online validation
ALTER TABLE t ALTER COLUMN col SET NOT NULL;      -- instant when a validated CHECK proves it
-- MySQL: ALTER TABLE t MODIFY col <type> NOT NULL;
-- SQLite: no ALTER support for this — table-rebuild pattern below.
```

### Add a foreign key to a table with existing data
Orphans first, or the constraint creation fails (or worse, you "fix" it by deleting rows you didn't inspect):
```sql
SELECT count(*) FROM child c LEFT JOIN parent p ON p.id = c.parent_id
WHERE c.parent_id IS NOT NULL AND p.id IS NULL;
```
Resolve orphans deliberately (delete, reparent, or NULL them — user's call), then:
- PG online pattern: `ALTER TABLE child ADD CONSTRAINT fk ... NOT VALID;` then `VALIDATE CONSTRAINT`.
- SQLite: constraint must exist at table creation → rebuild pattern below, and ensure the app sets `PRAGMA foreign_keys=ON` per connection or the new FK enforces nothing.

### Deduplicate rows, keeping the earliest
```sql
-- PG
DELETE FROM t a USING t b
WHERE a.id > b.id AND a.dedup_key = b.dedup_key;
-- MySQL
DELETE a FROM t a JOIN t b ON a.dedup_key = b.dedup_key AND a.id > b.id;
-- SQLite
DELETE FROM t WHERE id NOT IN (SELECT min(id) FROM t GROUP BY dedup_key);
```
Preview the doomed rows first (rule 4), then add the missing `UNIQUE` constraint immediately so duplicates can't return.

### SQLite table-rebuild pattern
For anything SQLite's limited `ALTER TABLE` can't do (add FK/CHECK, change NOT NULL, alter a type):
```sql
PRAGMA foreign_keys=OFF;
BEGIN;
CREATE TABLE t_new (...corrected definition...);
INSERT INTO t_new SELECT ... FROM t;
DROP TABLE t;
ALTER TABLE t_new RENAME TO t;
-- recreate t's indexes, triggers, and views here
COMMIT;
PRAGMA foreign_keys=ON;
PRAGMA foreign_key_check;   -- must return zero rows
```

### Cross-engine migrations (schema targets PG + MySQL + SQLite)
Stay inside the shared dialect: `TEXT` + `CHECK (col IN (...))` instead of native ENUMs; UUIDs generated in the application, stored as TEXT; `TIMESTAMP DEFAULT CURRENT_TIMESTAMP`; no engine-specific index types in the portable core. Write the migration once, run it against all three engines in CI before calling it done — SQLite's ALTER limitations are usually what breaks first.

### Fix a slow query without touching the schema

## Maintenance statements (moved here from the read-only audit)

`ANALYZE` and `PRAGMA optimize` (SQLite) refresh planner statistics — cheap, but they **write** to the database, so they run here and never inside database-audit. Before running either (or `VACUUM`/`REINDEX`):

1. **Explicit confirmation** — state the exact statement, the target database, and that it mutates state; proceed only after the user confirms.
2. **Backup verification** — confirm a restorable backup/snapshot exists and has been tested (see backup-recovery). "A backup probably exists" does not count.
3. **Mutation warning** — on a busy production system `VACUUM` takes locks and `ANALYZE` changes plans; schedule accordingly.
4. **Rollback guidance** — state how to undo or recover: restore from the verified backup; for plan regressions after `ANALYZE`, re-run `ANALYZE` after fixing data or use the engine's plan-management tools.

Order of attack: refresh statistics (`ANALYZE` — see Maintenance statements above) → add/adjust the index the plan is missing → rewrite the query (avoid `SELECT *`, avoid functions on indexed columns in WHERE, replace `OFFSET` pagination with keyset pagination) → only then consider denormalization or caching.

## Deployment order for production changes

Expand → migrate → contract: add the new structure, backfill and dual-write while both shapes exist, switch reads, then remove the old structure in a later release. The app must work at every intermediate step, because that's where it will be running while the migration executes.

## After fixing

Re-run the relevant audit sections from **database-audit** and show before/after evidence (the query result that flagged the issue, now clean, and the EXPLAIN now using the index).

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
