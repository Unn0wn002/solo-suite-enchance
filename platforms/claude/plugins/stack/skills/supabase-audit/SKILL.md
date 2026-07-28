---
name: supabase-audit
description: Audit a Supabase project — Row Level Security (RLS) policies, public/private table exposure, auth settings, API key usage, storage bucket policies, edge functions, database indexes, slow queries, backups, and realtime rules. Use when the user wants a Supabase review, "check my Supabase", RLS/security/database configuration on Supabase, or asks if their Supabase is safe. Vendor-specific front end to site-doctor's security-review, database-audit, and backup-recovery; reads .solo/stack.md; uses a Supabase connector for live config when available.
---

# Supabase Audit

**AgentRoom proposal mode:** preserve raw audit evidence in the seat's declared direct artifact. Any tasks, decisions, handoff, stack update, or other target listed under `proposes` goes to `.solo/proposals/<seat>-<run_id>.md` with its target and proposed entries; never edit that target. Only the memory steward merges, and missing seat/run identity stops the write.

Supabase exposes your Postgres database directly through an auto-generated API — which is powerful and, without Row Level Security, catastrophic: a table with RLS off is readable and writable by anyone with the public anon key, which ships in your frontend. The overwhelming majority of Supabase data breaches are exactly this. So this audit leads with RLS and exposure, then covers auth, keys, storage, and database health, delegating the deep database and security mechanics to site-doctor.

## Setup

Read `.solo/stack.md` to confirm Supabase is the database/auth/storage provider; if missing, offer `/stack:intake`. **Only audit projects you own.** Prefer a **Supabase connector/MCP if available** to read live RLS policies, table grants, and settings; otherwise work from migrations, policy SQL, and dashboard details the user provides. Treat anon-key-reachable surface as untrusted-by-default.

## What to check

1. **RLS on every exposed table (the #1 thing)** —
   - **RLS enabled** on every table in an API-exposed schema (typically `public`). A table with RLS disabled is fully open via the anon key — anyone can read/write all rows. Enumerate tables and confirm RLS is ON for each; a single table with it off is a critical finding.
   - **Policies are correct, not just present**: `USING` (read) and `WITH CHECK` (write) clauses actually scope rows to the right user (e.g. `auth.uid() = user_id`); no policy that's effectively `true` for all; separate, correct policies per operation (select/insert/update/delete). An overly permissive policy is as bad as no RLS.
   - Tables that should never be client-reachable live in a non-exposed schema or have deny-all policies.
2. **Public/private table & schema exposure** — know exactly what the anon (public) role can reach; sensitive tables (payments, PII, internal) not exposed through the API; views and functions (`SECURITY DEFINER` especially) don't leak data around RLS; the `service_role` bypasses RLS entirely, so anything using it must be server-side only.
3. **API key usage** —
   - **`service_role` key never in client code / never shipped to the browser / never committed** — it bypasses all RLS and is effectively a database admin key. This is a critical, common leak (pair with site-doctor `security-review` secret scanner and check git history).
   - `anon` key is the only key in frontend code, and it's safe *only because* RLS is correct (which is why #1 matters).
   - Keys scoped and rotated where needed; JWT secret protected.
4. **Auth settings** — email confirmation / secure flows enabled as appropriate; strong password and OTP settings; redirect URLs allowlisted (open redirects in auth are dangerous); session/JWT expiry sensible; OAuth providers configured correctly; leaked-password protection on if available; rate limiting on auth endpoints.
5. **Storage bucket policies** — buckets intentionally public vs private (a bucket set public exposes every object's URL); RLS-style access policies on storage objects scoping who can read/write/upload; upload constraints (type, size) enforced; no sensitive files in a public bucket. (Ties to site-doctor `security-review`.)
6. **Database indexes & slow queries** — indexes on foreign keys and common filter/sort columns; missing indexes causing sequential scans; slow queries identified and addressed. **Delegate the deep pass to site-doctor `database-audit`** (schema, indexes, query analysis, integrity) — it's the engine for this and its schema conventions (TEXT+CHECK over ENUMs, app-generated UUIDs) match how the suite designs schemas.
7. **Edge functions** — secrets via env (not hardcoded); authorization enforced inside the function (don't assume the caller is trusted); input validated; no over-broad CORS; not using `service_role` in a way reachable by untrusted callers.
8. **Realtime rules** — realtime enabled only on intended tables; subscriptions respect RLS so a client can't subscribe to rows it can't read; no sensitive table broadcasting changes to unauthorized listeners.
9. **Backups** — automated backups on and at a frequency matching how much data loss is tolerable; **point-in-time recovery** considered for anything important; a restore has actually been tested. **Delegate to site-doctor `backup-recovery`** for the RTO/RPO framing and restore-test discipline.

## Delegate the depth

Supabase-specific checklist here; the engines live in site-doctor:
- RLS/keys/exposure/storage as security issues → **`security-review`** (+ secret scanner).
- Indexes, slow queries, schema, integrity → **`database-audit`** (and `database-debug` for live issues, `database-fix` for safe migrations).
- Backups, PITR, restore testing → **`backup-recovery`**.
- PII/consent if user data is involved → **`compliance-check`**.
Invoke those for depth; don't duplicate. Lighter inline pass if site-doctor isn't installed — but never soft-pedal an RLS-off or exposed-`service_role` finding.

## Report & memory

Shared audit format (Summary → Scorecard → Findings [Evidence / Impact / Fix] → Fix order), grouped **RLS & Exposure / Keys / Auth / Storage / Database / Edge Functions / Realtime / Backups**. Rank by real exposure — RLS disabled on any exposed table and a client-side `service_role` key are critical and lead; a missing non-critical index is low. Write prioritized fixes to `.solo/tasks.md` and note the audit in `handoff.md` when `.solo/` exists, so they reach `/solo:next-step` and `/release:preflight`.

## Two ways to run this audit

State which mode you used — findings carry different confidence. (connector-auditor tiers: live → migrations/policy SQL → ask)

### Mode 1 — Connector mode (live config)
A connector / MCP / API is available (via **connector-auditor**): read the real configuration, read-only, and never print secret values.
- inspect tables, columns, and constraints
- inspect RLS: enabled per table + every policy's definition
- inspect auth settings (providers, email confirmations, JWT expiry)
- inspect storage buckets and their policies
- inspect edge functions and exposed schemas/API settings

### Mode 2 — Manual mode (user-supplied evidence)
No connector: ask the user for the evidence instead of guessing — and audit exactly what they provide.
- ask for the schema (migrations folder or SQL dump — no data)
- ask for policy SQL, or screenshots of Auth → Policies per table
- ask which tables must be private vs public (the intent, to test against)
- ask for auth settings screenshots
- ask for env variable names used (anon vs service_role usage — names only)

Either way, every finding must name its evidence (which setting, file, screenshot, or API field it came from).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle. Keep `.solo/` current as you go so those session commands stay accurate.
