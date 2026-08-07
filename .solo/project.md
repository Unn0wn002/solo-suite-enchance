# Project — Solo Suite Enchance (website)

Project profile: public-marketing-site

## What it is

The public-facing marketing/landing site for **Solo Suite Enchance**, a
"developer operating system" that brings a full product-team workflow
(product, design, engineering, QA, security, release) to Claude, Codex, and
Antigravity. The site itself is a single-page Next.js/Vinext app deployed to
Cloudflare Workers; the larger product it markets is the platform distributed
under `platforms/claude|codex|antigravity/`.

## Who it's for

Solo/small-team developers who want an "advanced team, one person" workflow —
the site's own copy targets "ambitious one-person teams shipping real
products" (`app/page.tsx:113`).

## Current phase

Post-launch, pre-hardening. The site is live (deployed via Cloudflare Workers
per `.openai/hosting.json` + `vite.config.ts`), but a full lifecycle audit on
2026-08-07 found it **NOT PRODUCTION READY** by the suite's own production-gate
standard — see `.solo/risks.md` and `.solo/tasks.md` for the specific gaps.
This file set (`.solo/`) was itself instantiated as a fix arising from that
audit, on this repo's own `.solo/` root for the first time — previously the
`.solo/` contract was designed and shipped to end users but not used on this
repo's own website work.

## Links

- Full audit report: see chat history / delivered file `WEBSITE_LIFECYCLE_AUDIT.md` (2026-08-07)
- Product README: [`README.md`](../README.md)
- Repository conventions: [`AGENTS.md`](../AGENTS.md), [`CLAUDE.md`](../CLAUDE.md)
