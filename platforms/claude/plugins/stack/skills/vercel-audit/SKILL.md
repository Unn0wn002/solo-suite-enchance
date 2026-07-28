---
name: vercel-audit
description: Audit a Vercel project — build settings, environment variables, preview vs production environments, domain config, redirects/rewrites, edge middleware, serverless/edge function limits, deployment rollback, image optimization, and Analytics/Speed Insights. Use when the user wants a Vercel review, "check my Vercel", env-var/domain/deploy configuration on Vercel, or asks if their Vercel setup is safe and optimal. Vendor-specific front end to site-doctor's deployment-review and performance-tuning; reads .solo/stack.md; uses a Vercel connector for live config when available.
---

# Vercel Audit

**AgentRoom proposal mode:** preserve raw audit evidence in the seat's declared direct artifact. Any tasks, decisions, handoff, stack update, or other target listed under `proposes` goes to `.solo/proposals/<seat>-<run_id>.md` with its target and proposed entries; never edit that target. Only the memory steward merges, and missing seat/run identity stops the write.

Vercel makes deploying trivial, which means the risks move to configuration: a secret exposed to the browser through a `NEXT_PUBLIC_` var, preview deployments leaking production data or sitting unprotected, functions quietly hitting duration limits under load. This skill audits the Vercel-specific configuration and hands the general release/performance mechanics to site-doctor so the advice is consistent.

## Setup

Read `.solo/stack.md` to confirm Vercel is the host and pick up the framework and domain; if missing, offer `/stack:intake`. **Only audit projects you own.** Prefer a **Vercel connector/MCP if available** to read live project settings, env config, and deployments; otherwise work from `vercel.json`, the project's config, and dashboard details the user provides.

## What to check

1. **Environment variables & secrets (highest stakes)** —
   - **No secrets exposed to the client**: anything prefixed `NEXT_PUBLIC_` (or framework-equivalent) ships to the browser. Secret keys, DB URLs, and service tokens must NOT be public-prefixed. This is the most common and most damaging Vercel mistake.
   - **Environment scoping**: production secrets set for Production only; Preview/Development not using prod credentials; no secrets committed to the repo (→ site-doctor `security-review` secret scanner).
   - Required vars present per environment (a missing prod var = broken deploy); sensitive values encrypted (Vercel does this) and not echoed in build logs.
2. **Preview vs production parity & protection** —
   - **Preview deployments protected** (Vercel Authentication / password / trusted IPs) so they aren't public URLs exposing unreleased features or real data.
   - Preview environment doesn't point at the production database (a preview writing to prod data is dangerous); use a separate/branch database.
   - Environments similar enough that "works in preview, breaks in prod" gaps are minimized (→ `deployment-review` parity).
3. **Build settings** — correct framework preset, build command, output dir; build not silently ignoring type/lint errors that should block; reproducible installs (lockfile committed, `npm ci`-equivalent); build not leaking secrets to logs.
4. **Domain config** — production domain assigned and canonical; www↔apex redirect consistent; SSL provisioned; if DNS is elsewhere (e.g. Cloudflare — check `stack.md`), records point correctly and don't conflict.
5. **Redirects / rewrites** — correct, not looping, order-correct; no rewrite unintentionally exposing an internal path or proxying somewhere unsafe; SEO redirects use the right status codes (→ site-doctor `seo`).
6. **Edge middleware** — does what's intended (auth gating, redirects, geolocation); not adding latency to every request unnecessarily; auth checks in middleware are actually enforced (not bypassable by path); no secrets in middleware that runs at the edge.
7. **Serverless / edge function limits** — functions within duration/memory/size limits for the plan; cold-start and bundle size reasonable; long tasks moved off the request path (queue/background) rather than risking timeouts under load (→ site-doctor `load-testing` for behavior under concurrency); region choice sensible relative to the database.
8. **Deployment rollback** — you can promote a previous deployment quickly (Vercel keeps them — confirm the path is known); a bad deploy is revertible in minutes; understand that instant rollback of code still needs backward-compatible DB migrations (→ site-doctor `deployment-review` / `database-fix`).
9. **Image optimization** — using `next/image` or Vercel's image optimization (not shipping full-size images); sensible sizes/formats; not accidentally running up image-optimization usage/cost. (Perf depth → site-doctor `performance-tuning`.)
10. **Analytics / Speed Insights** — Web/Speed Insights enabled if wanted (real-user Core Web Vitals feed site-doctor `performance-tuning`); note this is separate from marketing tags (→ `/stack:audit-tags`).

## Delegate the depth

Vercel-specific checklist here; general mechanics in site-doctor:
- Build reproducibility, env parity, rollback, CI → **`deployment-review`**.
- Image optimization, bundle size, Core Web Vitals → **`performance-tuning`**.
- Secret scanning → **`security-review`**; function behavior under load → **`load-testing`**; domain/DNS → **`infrastructure-audit`**.
Invoke those for depth; don't duplicate. Lighter inline pass if site-doctor isn't installed.

## Report & memory

Shared audit format (Summary → Scorecard → Findings [Evidence / Impact / Fix] → Fix order), grouped **Env & Secrets / Preview↔Prod / Build / Domain / Redirects / Middleware / Functions / Rollback / Images / Insights**. Rank by real risk — a public-prefixed secret or an unprotected preview on prod data tops the list; a missing Speed Insights toggle is low. Write prioritized fixes to `.solo/tasks.md` and note the audit in `handoff.md` when `.solo/` exists.

## Two ways to run this audit

State which mode you used — findings carry different confidence. (connector-auditor tiers: live → local config files → ask)

### Mode 1 — Connector mode (live config)
A connector / MCP / API is available (via **connector-auditor**): read the real configuration, read-only, and never print secret values.
- inspect project settings
- inspect environment variables (names + which environment — never values)
- inspect build command
- inspect framework preset
- inspect domains
- inspect redirects/rewrites
- inspect deployment protection
- inspect function regions
- inspect recent failed deployments

### Mode 2 — Manual mode (user-supplied evidence)
No connector: ask the user for the evidence instead of guessing — and audit exactly what they provide.
- ask the user to paste Vercel project settings
- ask for env variable names only, not secrets
- ask for build logs
- ask for a domain settings screenshot
- ask for vercel.json / next.config from the repo if present

Either way, every finding must name its evidence (which setting, file, screenshot, or API field it came from).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle. Keep `.solo/` current as you go so those session commands stay accurate.
