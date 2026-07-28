# Audit Queries by Engine

Read-only diagnostics. Run against the target and paste results into the report as evidence.
**Policy: nothing in this file may write.** No `ANALYZE`, `VACUUM`, `REINDEX`, `PRAGMA optimize`,
value-setting PRAGMAs, or DML/DDL — those belong to **database-fix** with confirmation, backup
verification, and rollback guidance. A CI policy test (`tests/test_readonly_audit.py`) enforces this.

## Contents
- [PostgreSQL](#postgresql)
- [MySQL / MariaDB](#mysql--mariadb)
- [SQLite](#sqlite)

---

## PostgreSQL

**Tables without a primary key**
```sql
SELECT n.nspname AS schema, c.relname AS table
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r'
  AND n.nspname NOT IN ('pg_catalog','information_schema')
  AND NOT EXISTS (SELECT 1 FROM pg_constraint
                  WHERE conrelid = c.oid AND contype = 'p');
```

**Foreign keys with no index on the leading column** (heuristic — for composite FKs, verify column order manually)
```sql
SELECT tc.table_name, kcu.column_name, tc.constraint_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON kcu.constraint_name = tc.constraint_name
 AND kcu.table_schema   = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND NOT EXISTS (
    SELECT 1
    FROM pg_index i
    JOIN pg_class t ON t.oid = i.indrelid
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = i.indkey[0]
    WHERE t.relname = tc.table_name
      AND a.attname = kcu.column_name);
```

**Unused indexes** (caveats: counters reset on stats reset; a replica may use what the primary doesn't; unique indexes enforce constraints even at zero scans)
```sql
SELECT schemaname, relname AS table, indexrelname AS index,
       idx_scan, pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;
```

**Top queries by total time** (requires the pg_stat_statements extension)
```sql
SELECT round(total_exec_time::numeric, 0) AS total_ms, calls,
       round(mean_exec_time::numeric, 2)  AS mean_ms,
       left(query, 120) AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 15;
```

**Sequential-scan-heavy tables** (index candidates)
```sql
SELECT relname, seq_scan, idx_scan, n_live_tup
FROM pg_stat_user_tables
WHERE seq_scan > idx_scan AND n_live_tup > 10000
ORDER BY seq_scan DESC;
```

**Cache hit ratio** (healthy is > 0.99 for OLTP; lower means the working set exceeds shared_buffers)
```sql
SELECT round(sum(heap_blks_hit)::numeric /
       nullif(sum(heap_blks_hit) + sum(heap_blks_read), 0), 4) AS hit_ratio
FROM pg_statio_user_tables;
```

**Dead tuples / vacuum health**
```sql
SELECT relname, n_dead_tup, n_live_tup,
       last_autovacuum, last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 10;
```

**Idle-in-transaction sessions** (hold locks and block vacuum)
```sql
SELECT pid, usename, state, now() - xact_start AS xact_age,
       left(query, 80) AS last_query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
ORDER BY xact_age DESC;
```

**Largest tables and indexes**
```sql
SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) AS total
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;
```

---

## MySQL / MariaDB

**Tables without a primary key**
```sql
SELECT t.table_schema, t.table_name
FROM information_schema.tables t
LEFT JOIN information_schema.table_constraints c
  ON c.table_schema = t.table_schema
 AND c.table_name   = t.table_name
 AND c.constraint_type = 'PRIMARY KEY'
WHERE t.table_type = 'BASE TABLE'
  AND t.table_schema NOT IN ('mysql','sys','performance_schema','information_schema')
  AND c.constraint_name IS NULL;
```

**Unused indexes** (MySQL 8 sys schema; counters reset on restart)
```sql
SELECT * FROM sys.schema_unused_indexes;
```

**Redundant indexes**
```sql
SELECT table_name, redundant_index_name, dominant_index_name
FROM sys.schema_redundant_indexes;
```

**Statements doing full table scans**
```sql
SELECT query, db, exec_count, no_index_used_count
FROM sys.statements_with_full_table_scans
ORDER BY no_index_used_count DESC
LIMIT 15;
```

**Top statements by total latency**
```sql
SELECT query, db, exec_count, total_latency, avg_latency, rows_examined_avg
FROM sys.statement_analysis
ORDER BY total_latency DESC
LIMIT 15;
```

**Buffer pool sizing signal** (reads hitting disk)
```sql
SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_read%';
-- reads / read_requests should be well under 1%
```

Note: InnoDB auto-creates an index for every foreign key, so "FK without index" is generally not a MySQL finding — check instead that FKs exist at all where the app assumes them.

---

## SQLite

**Corruption and constraint checks** (run these first — they're definitive)
```sql
PRAGMA integrity_check;    -- 'ok' or a list of problems
PRAGMA foreign_key_check;  -- rows violating declared FKs
PRAGMA foreign_keys;       -- 1 = enforced on THIS connection; app must set it per connection
```

**Journal and durability settings** (web workloads want WAL)
```sql
PRAGMA journal_mode;   -- expect 'wal' for concurrent readers + one writer
PRAGMA synchronous;    -- 1 (NORMAL) is the usual WAL pairing
PRAGMA busy_timeout;   -- 0 means writers fail instantly with SQLITE_BUSY
```

**Tables, indexes, and FK coverage**
```sql
SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';
PRAGMA foreign_key_list('table_name');  -- declared FKs per table
PRAGMA index_list('table_name');        -- compare: does an index lead with each FK column?
PRAGMA index_info('index_name');
```

**Query plans** (SEARCH = index used; SCAN = full table read)
```sql
EXPLAIN QUERY PLAN SELECT ... ;
```

**Reclaimable space (read-only)**
```sql
PRAGMA page_count; PRAGMA freelist_count;
-- freelist_count * page_size = reclaimable bytes; a large ratio makes the
-- database a VACUUM candidate — but VACUUM is a WRITE and belongs to the
-- database-fix workflow, never to this audit.
```

> **Maintenance commands moved out of the audit.** `ANALYZE` and
> `PRAGMA optimize` rewrite planner statistics — they mutate database state
> and do NOT belong in a read-only audit. They now live in the
> **database-fix** skill (Maintenance section), which requires explicit
> confirmation, a verified backup, and rollback guidance before running them.
> If query plans look wrong because statistics are stale, record that as a
> finding and hand it to database-fix.
