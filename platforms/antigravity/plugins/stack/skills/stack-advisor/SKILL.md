---
name: stack-advisor
description: Ask a solo developer what tools their project actually uses — hosting, DNS/CDN/WAF, database, auth, storage, analytics, email, payments, repo/CI — and record it as the single source of truth so every audit and build is stack-aware. Use when the user says intake, "what stack", set up the stack, "tell you my stack", before a first audit or build, or when .solo/stack.md is missing. Owns .solo/stack.md; run this first so other commands know the stack instead of guessing.
---

# Stack Advisor

**AgentRoom proposal mode:** when the trusted seat declares `.solo/stack.md`, `.solo/decisions.md`, or another target under `proposes`, put the target and idempotent proposed patch in `.solo/proposals/<seat>-<run_id>.md` instead of editing the target. Only the memory steward merges; missing seat/run identity is a stop condition. Single-agent intake keeps direct updates.

The fastest way to give bad advice is to audit or build without knowing what the project runs on — recommending an S3 lifecycle rule to someone on Cloudinary, or a generic "add a WAF" to someone already behind Cloudflare. This skill fixes that once: it asks what the stack is and writes it to `.solo/stack.md`, which every other command in the suite reads for context. **Run it first.** Ten questions up front make every later audit sharper and every build fit the real tools.

## When to run

- At the **start of a project**, before `/project:architecture` locks choices (capture what's decided; the architect fills the rest).
- Before the **first audit** — `/site-doctor:*` and `/stack:audit-*` all read `stack.md` to target their checks.
- Any time the stack **changes** (new host, swapped database, added payment provider) — update `stack.md` and note the change.

## How to run the intake

Interview, don't assume. Ask across these areas; for each, get the specific product/provider, not a category. Fill what the user knows and **explicitly mark unknowns** (`?` or `TBD`) rather than guessing — a wrong entry is worse than a blank one.

- **Hosting** — Vercel, Netlify, AWS (ECS/EC2/Amplify), Railway, Fly.io, a VPS, etc. Which environments (prod/preview/staging), how deploys happen.
- **DNS / CDN / WAF** — Cloudflare, Vercel DNS, Route53, etc. The domain, SSL/TLS mode, whether traffic is proxied, any firewall/cache rules.
- **Database** — Supabase, Neon, Railway, PlanetScale, RDS, SQLite, etc. Engine (Postgres/MySQL/SQLite), how migrations run.
- **Auth** — Supabase Auth, Clerk, NextAuth/Auth.js, Firebase Auth, custom, etc.
- **Storage** — Supabase Storage, S3, Cloudinary, UploadThing, R2, etc. Buckets and who can read/write.
- **Analytics & tags** — Google Tag Manager, GA4, Meta Pixel, TikTok Pixel, Hotjar, PostHog, Plausible, etc. Whether consent mode is in play.
- **Email** — Resend, SendGrid, Mailgun, Postmark, Google Workspace, etc. Whether SPF/DKIM/DMARC are set.
- **Payments** — Stripe, Xendit, Midtrans, PayPal, etc. Whether webhooks are wired.
- **Repo / CI** — GitHub + Actions, GitLab CI, Vercel CI, etc.
- **Frontend** (if a build) — framework (Next.js/Remix/SvelteKit/…), UI library, styling, state management.
- **Backend** — runtime (Node/Bun/Deno/…), API style (REST/GraphQL/tRPC).

Keep it conversational and quick — offer the categories, let the user rattle off what they know, and follow up only where an audit would need the detail (e.g. Cloudflare SSL mode matters for `/stack:audit-cloudflare`).

## Write `.solo/stack.md`

If `.solo/` doesn't exist, offer to initialize it (project-memory-manager). Write `stack.md` in this structure (extend as needed; keep unknown fields present but blank/`?` so gaps are visible):

```markdown
# Project Stack

## Frontend
- Framework:
- UI library:
- Styling:
- State management:

## Backend
- Runtime:
- API style:
- Auth:

## Database
- Provider:
- Engine:
- Tables:
- Migrations:

## Hosting
- Provider:
- Environment:
- Deployment method:

## DNS/CDN/WAF
- Provider:
- Domain:
- SSL/TLS:
- Firewall rules:
- Cache rules:

## Analytics & Tags
- Google Tag Manager:
- GA4:
- Meta Pixel:
- Other pixels:
- Consent mode:

## Storage
- Provider:
- Buckets:
- Upload rules:

## Email
- Provider:
- SPF:
- DKIM:
- DMARC:

## Payments
- Provider:
- Webhooks:

## Repo / CI
- Repo:
- CI:
```

**Updating** an existing `stack.md`: change only what moved, keep the rest, and if a tool was swapped, append a one-line note to `.solo/decisions.md` (e.g. "2026-07-08 — moved DB from Railway to Supabase") so the history is captured.

## After intake — point to what's now available

Based on what they use, surface the relevant next steps (only the applicable ones):
- Cloudflare → `/stack:audit-cloudflare` · Vercel → `/stack:audit-vercel` · Supabase → `/stack:audit-supabase` · any tags/pixels → `/stack:audit-tags` · payments (Stripe/Xendit/Midtrans/PayPal) → `/stack:audit-payments`.
- Generic depth regardless of vendor: site-doctor's `/site-doctor:audit-infra`, `audit-db`, `security-scan`, `audit-analytics`, `email-check`, etc.
- If building, hand the captured frontend/backend to `/project:architecture`.

## Project memory integration

`stack.md` is part of the `.solo/` contract (project-memory-manager). It's the shared answer to "what does this project run on?" — every audit and build skill in the suite reads it before working so their advice fits the real tools. Keep it current; it's the difference between generic checklists and targeted, correct recommendations.

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (and recommends this intake when `stack.md` is missing), and `/solo:end-session` saves progress — including any stack changes — at the end. `/solo:run-cycle` checks `stack.md` at task selection and may route to the vendor audits this plugin provides. Keep `stack.md` current as tools change so those session commands stay accurate.
