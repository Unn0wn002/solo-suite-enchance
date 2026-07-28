---
name: connector-auditor
description: Use live Vercel, Supabase, GitHub, and Cloudflare data when a connector or MCP is available, instead of guessing from local files. Use when auditing those services, testing RLS against the real schema, or syncing issues, and you want real configuration rather than assumptions. Three tiers — live (connector/MCP/API) → local config files → neither. Vendor probes are read-only; local project-memory updates are allowed, while external writes require an explicit command with confirmation.
---

# Connector Auditor

**AgentRoom proposal mode:** if `.solo/stack.md`, tasks, decisions, or another target is listed under the trusted seat's `proposes`, write `.solo/proposals/<seat>-<run_id>.md` with the target and idempotent proposed patch/entries; do not edit the target. Only the memory steward merges, and missing seat/run identity stops the update. Direct writes remain normal outside a stewarded room.

Audits are only as good as their inputs. This skill gets the *real* configuration when it can, and is honest about which tier it used. **Read-only toward vendor infrastructure when auditing** — it inspects, it does not change remote services. `/stack:connector-check` may update only the local `.solo/stack.md` connector section. The external write path (creating/closing GitHub issues via `/git:sync-issues`) always confirms first.

## The three tiers (try in order, state which you used)
1. **Live** — a connector / MCP / API is available: pull real data read-only.
   - **Vercel**: projects, environments, env-var *names* (never print secret values) and which env they're in, latest deployments/status, domains.
   - **Supabase**: tables, columns, constraints, and **RLS policies + whether RLS is enabled** per table; auth settings.
   - **GitHub**: issues, PRs, branches, checks — for `/git:sync-issues` and `/git:pr-review`.
   - **Cloudflare**: DNS records, SSL/TLS mode, proxy status, page/security rules.
2. **Local config** — no connector: read the repo's own config (`vercel.json`, Supabase migrations/policy SQL, `.github/`, `wrangler.toml`, `.env.example`) and say the picture is config-derived, not live.
3. **Neither** — ask for the minimum needed, or proceed on stated assumptions and clearly flag them.

## Principles
- **Never expose secret values** — reference env vars by name and location only.
- **Read-only for audits**; any mutation (issues) needs an explicit command and a confirm-diff first.
- Always label the tier so findings carry the right confidence.
- **Scope is exactly these four**: Vercel, Supabase, GitHub, Cloudflare. Payments and tag platforms are handled by their own audits' provider-API instructions (`/stack:audit-payments`, `/stack:audit-tags`), not by this skill.

## Working with other skills
Backs `/stack:connector-check` (the pre-audit tier report, written to `.solo/stack.md` under `## Connectors`); feeds `/stack:audit-vercel` and `/stack:audit-supabase` (real config), `authz-security-reviewer`'s `rls-test` (live schema/policies), and `git-workflow-manager`'s `sync-issues` / `pr-review` (live GitHub).

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
