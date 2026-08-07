# Architecture — Solo Suite Enchance (website)

> **Provenance note**: reverse-engineered from the existing codebase (not a
> forward design), per the same user-approved fast path as `prd.md`. This
> documents what is actually built, cited to file/line, rather than proposing
> a new design — read it as as-built architecture, then use `/project:architecture`
> normally for any *future* redesign.

## Overview

A single-page, client-rendered marketing site built on Next.js's App Router
but executed through Vinext (a Vite-based Next-compatible runner) and deployed
as a Cloudflare Worker. There is no live backend today — the "backend" that
exists (a Drizzle/D1 client and a ChatGPT-auth helper) is scaffolded but
unconnected to any route.

## Stack (with one-line justification each — justification is inferred from
what's pinned, not from a documented decision)

- **Next.js 16.2.12 (App Router) + React 19.2.8** — modern, well-documented,
  large-community; matches the "boring by default" guidance even though it's
  run through a non-standard runner (see next point).
- **Vinext 0.0.50 (Vite-based) instead of the `next` CLI** — `dev`/`build`/
  `start` all shell out to `vinext` (`package.json:9-11`); reason not
  documented anywhere found in-repo. *(Open question: why Vinext over
  standard Next.js tooling? Worth a `decisions.md` entry once answered.)*
- **Tailwind CSS 4.2.1** — utility CSS with design tokens as CSS custom
  properties (`app/globals.css:3-14`).
- **TypeScript 5.9.3, `strict: true`** (`tsconfig.json:7`) — sound default.
- **Drizzle ORM 0.45.2 + Cloudflare D1** — scaffolded (`db/index.ts`,
  `drizzle.config.ts`) but **not provisioned** (`.openai/hosting.json`:
  `"d1": null`) and **not used** (`db/schema.ts` is an empty placeholder). This
  is a moving part with zero current payoff — see Risks below and
  `prd.md`'s Open question #5.
- **Cloudflare Workers + Wrangler 4.114.0** — the actual deploy target
  (`worker/index.ts` as Worker entry, confirmed via the generated
  `dist/server/wrangler.json`).
- **GSAP 3.15.0** — declared as a dependency but **unused** (no import
  anywhere under `app/`, confirmed by search). Dead weight as shipped.

## Components (responsibility + boundaries)

- **`app/layout.tsx`** — root HTML shell, font loading (`next/font/google`:
  Geist/Geist Mono), and all `<head>` metadata (title, OG, Twitter, favicon).
- **`app/page.tsx`** (321 lines, `"use client"`) — the entire visible product.
  One component owns hero, system overview, workflow track, AgentRooms module
  tabs, runtime-proof grid, and the closing CTA, driven by three local
  `useState` values (`menuOpen`, `activeModule`, `runStarted`). No child
  components are extracted — every section is inline JSX inside one function.
  **Boundary concern**: this is a single, large, monolithic component; there
  are no error boundaries and no code-splitting below the page level.
- **`app/globals.css`** — design tokens (`--ink`, `--cream`, `--gold`,
  `--mint`, `--blue`, `--violet`, `--coral`) plus all component styling.
- **`worker/index.ts`** — the Cloudflare Worker entry. Special-cases
  `GET /_vinext/image` for on-the-fly image optimization, otherwise delegates
  every request to Vinext's `app-router-entry` handler. This is the *only*
  real "backend" boundary in the app, and it does no application logic of its
  own.
- **`app/chatgpt-auth.ts`** — a self-contained, **unreferenced** module
  implementing header-trusting ChatGPT-platform identity helpers
  (`getChatGPTUser`, `requireChatGPTUser`, sign-in/out path builders). No
  route imports it. Treat as either dead code to remove or a half-finished
  integration to either finish or delete — see Risks.
- **`db/index.ts` / `db/schema.ts` / `drizzle.config.ts`** — a Drizzle-over-D1
  client boundary with an intentionally empty schema (`db/schema.ts:1-4`
  points at `examples/d1/db/schema.ts` as the template to copy from when a
  real feature needs it). `getDb()` throws if the D1 binding (`env.DB`) is
  missing, which it currently is in every environment.

## Data model

**None in active use.** `db/schema.ts` is empty by design (`export {}`).
`examples/d1/db/schema.ts` shows the intended pattern (a `notes` table:
id/title/content/createdAt) as reference material, not live schema. Zero
migrations exist (`drizzle/meta/_journal.json`: `"entries": []`).

## API surface

**None in active use.** The only route the repo contains is
`examples/d1/app/api/notes/route.ts` (GET/POST), explicitly scoped to the
`examples/` reference directory and not wired into `app/`. There is no
authentication, no input validation, and no API versioning to speak of today
because there is no live API to apply them to.

## Cross-cutting

- **Auth**: none active. `app/chatgpt-auth.ts` exists but is unwired; it trusts
  an `oai-authenticated-user-email` header verbatim as identity
  (`app/chatgpt-auth.ts:10-22`) — if ever connected to a route, this needs an
  edge-level check that only a legitimate proxy can set that header, or it
  becomes a spoofable-identity vulnerability. See `.solo/risks.md`.
- **Errors**: no `error.tsx`, `not-found.tsx`, or `global-error.tsx` exists
  under `app/` — an unhandled render error or 404 has no custom handling.
- **Config**: the only environment variable the code reads is
  `NEXT_PUBLIC_SITE_URL` (`app/layout.tsx:19-20`), used for `metadataBase`,
  and it is completely undocumented (no `.env.example`, no README section).
  It silently falls back to `http://localhost:3000` if unset — meaning a
  misconfigured production deploy would silently generate wrong canonical/OG
  URLs rather than failing loudly.
- **Logging/observability**: Cloudflare's built-in request-log toggle only
  (`"observability":{"enabled":true}` in the generated `wrangler.json`) — no
  application-level logging, metrics, or error tracking exists in `app/` or
  `worker/index.ts`.

## Non-functional needs (from PRD, where stated — most are not stated)

- **Performance**: not budgeted anywhere in-repo. Current known issue: a
  2.3MB unoptimized `public/og.png` and zero use of `next/image` anywhere in
  `page.tsx`.
- **Security**: no CSP or security headers configured anywhere in the deploy
  path (`worker/index.ts`, generated `wrangler.json`, and the one
  `_headers`-named build artifact only sets asset caching, not security
  headers).
- **Availability/scale**: inherits Cloudflare Workers' edge distribution by
  default; no explicit SLO/SLA target is documented anywhere.

## Risks / things deferred

- The D1/Drizzle scaffold is complexity with no current payoff — either
  provision it for a real feature or remove it so `getDb()` can't be a latent
  runtime landmine (`prd.md` Open question #5).
- `app/chatgpt-auth.ts` is dead code with a real (if currently inert) security
  pattern worth resolving one way or the other rather than leaving unwired.
- No CI/CD, no monitoring, no rollback plan, no SEO baseline — all deferred to
  `.solo/risks.md` and `.solo/tasks.md` (P0/P1 items from the 2026-08-07
  audit) rather than repeated here.
- `gsap@3.15.0` is an unused dependency — either use it (the product's own
  `gsap-animation` skill exists to guide that) or drop it.
