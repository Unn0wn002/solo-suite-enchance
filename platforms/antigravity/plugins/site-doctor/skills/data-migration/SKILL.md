---
name: data-migration
description: Plan and safely execute data migrations — moving data between databases or engines, large schema restructures, ETL/import jobs, splitting or merging tables, and backfills at scale — with validation, integrity checks, rollback, and zero-downtime cutover. Use whenever the user is migrating data, changing database engines (e.g. MySQL to Postgres), importing a large dataset, restructuring how data is stored, doing an ETL job, or asks how to move data safely without downtime or loss. Extends database-fix (which covers in-place schema changes) to full data moves.
---

# Data Migration

Moving data is where silent, permanent loss happens — a truncated import, a mis-mapped column, a cutover that drops writes made during the copy. The discipline is: **never destroy the source until the target is proven correct**, validate row-for-row, and make every step reversible. This extends `database-fix` (in-place schema changes) to full data moves between tables, databases, or engines.

**Manual execution boundary:** planning, validation queries, and migration scripts may be prepared automatically, but no migration, cutover, bulk write, destructive statement, or external data transfer may execute until the user has reviewed the exact plan, target, restore point, and rollback path and explicitly approved that step. Stop at each state-changing boundary.

## Plan before touching data

1. **Define source and target** precisely: schemas, engines, encodings, and the exact field-to-field mapping (including type conversions and any transformation logic).
2. **Set success criteria**: what "correct" means — row counts match, checksums agree, spot-checked records are identical, referential integrity holds.
3. **Choose downtime posture**: can you take a maintenance window (simpler) or must it be zero-downtime (needs dual-write/sync + cutover)?
4. **Write the rollback plan first** — how to get back to the source-of-truth if validation fails at any stage. If there's no rollback, there's no migration, just a gamble.
5. **Always back up the source first** (hand off to backup-recovery) and keep it read-intact until the target is signed off.

## 1. The safe migration pattern

Never a one-shot destructive move. The reliable sequence:
1. **Copy** source → target (source stays untouched and authoritative).
2. **Validate** the target thoroughly (section below).
3. **Sync** any changes made to the source during the copy (for anything but a frozen source).
4. **Cut over** reads/writes to the target.
5. **Keep the source** as a fallback for a defined period before decommissioning.

The source remains the source of truth until step 4 succeeds and validation passes — so a failure at any point is a no-op, not a loss.

## 2. Field mapping & transformation

- **Explicit mapping** for every column — no implicit "same name = same thing." Watch type conversions (string→date parsing, numeric precision, boolean representations, `NULL` vs empty vs sentinel).
- **Encoding**: source and target charset/collation (UTF-8 vs latin1, emoji/multibyte handling) — a mismatch corrupts text silently. Verify with multibyte samples.
- **Cross-engine gotchas** (e.g. MySQL→Postgres): `AUTO_INCREMENT`→sequences/identity, `ENUM`→text+CHECK or native enum, `TINYINT(1)`→boolean, backtick vs double-quote identifiers, `0000-00-00` invalid dates, case-sensitivity of identifiers and collations, `TIMESTAMP` semantics. For a portable target, prefer TEXT+CHECK over native ENUMs and application-generated UUIDs (aligns with database-fix's cross-engine rules).
- **Referential integrity**: migrate parents before children, or defer FK validation and check at the end; preserve or remap keys consistently so relationships survive.
- Handle transformations (splitting/merging fields, deduplication, cleaning) as explicit, tested steps — and log what was transformed.

## 3. Executing at scale

- **Batch, don't big-bang**: migrate in chunks (by ID range or time window) so a failure is resumable and you're not holding one giant transaction that locks tables or exhausts memory/disk. Make batches idempotent (safe to re-run) with progress tracking so you can restart from the last good batch.
- **Throttle** to avoid overwhelming the source or target (and, if the source is live, to not degrade the app — coordinate with database-debug on load).
- Disable non-essential indexes/triggers on the target during bulk load, rebuild after (much faster), then re-enable constraints and validate.
- Monitor progress and resource use throughout (ties to observability).

## 4. Validation — the non-negotiable step

Prove correctness before trusting the target:
- **Row counts** match per table (accounting for any intentional filtering/dedup — explain discrepancies, don't wave them away).
- **Checksums / hashes** on columns or rows to confirm content matches, not just cardinality — counts can match while data is subtly wrong.
- **Referential integrity**: no orphaned rows on the target (FK checks / the integrity queries from database-audit).
- **Spot-check** real records end-to-end, including edge cases: NULLs, unicode, boundary values, the oldest and newest rows, records with special characters.
- **Application-level validation**: point a copy of the app at the target and exercise critical flows — the ultimate proof the data is usable, not just present.

## 5. Zero-downtime cutover (when a window isn't acceptable)

- **Dual-write or CDC**: while validating, keep the target current with ongoing changes — either the app writes to both, or change-data-capture / logical replication streams source→target continuously.
- **Cut over** when the target is caught up and validated: switch reads first (verify), then writes, ideally behind a feature flag so you can flip back instantly.
- **Reconcile** immediately after cutover to confirm nothing was lost in the switch; keep the source in sync briefly as a fallback.
- This is the same expand→migrate→contract philosophy as safe schema changes — the app works at every intermediate step.

## 6. After cutover

- Monitor the target under real load (errors, latency, integrity) before declaring done (observability).
- **Keep the source** read-only as a fallback for a defined period; decommission only after confidence and after it's covered by backups.
- Document what was migrated, the mapping, any transformations, and any records that needed manual handling.

## Report / plan format

**Planning**: a step-by-step migration plan — mapping table, batch strategy, validation checks, cutover approach, and rollback at each stage. **Auditing a proposed migration**: flag the risks (unvalidated mapping, no rollback, big-bang cutover, encoding mismatch, source destroyed too early). Either way, the through-line is: source stays authoritative until the target is validated, every step is reversible, and correctness is proven with counts + checksums + spot checks, not assumed. Route in-place schema mechanics to database-fix and load concerns to database-debug.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
