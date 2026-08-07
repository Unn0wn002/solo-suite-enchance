# PRD — Solo Suite Enchance (website)

> **Provenance note**: this PRD was **reverse-engineered from existing evidence**
> (site copy in `app/page.tsx`/`app/layout.tsx`, `README.md`, `CAPABILITY_CATALOG.md`,
> and the 2026-08-07 lifecycle audit) rather than written from a live interview,
> per the product-manager skill's normal "interview before writing" rule. The
> user explicitly approved this fast path over a fresh interview. Anything
> below that is inferred rather than confirmed is marked so, and unconfirmed
> items are collected in **Open questions** at the end — treat this as a
> first draft to correct, not a final spec.

## Problem

Solo developers and small teams want the leverage of a full product
organization (PM, architect, designer, engineers, QA, security, release) but
can't staff one. The site's job is to convert that audience by making the
underlying product's operating loop legible in under a minute of scrolling.
*(Inferred from the hero copy's explicit framing: "Ship like a company. Think
like a solo." — `app/page.tsx:97`.)*

## Users (specific, primary first)

1. **Primary**: an individual developer or very small team shipping a real
   product solo, already comfortable with Claude/Codex/Antigravity, evaluating
   whether to adopt a structured multi-role workflow. *(Inferred from
   `app/page.tsx:113`: "Built for ambitious one-person teams shipping real
   products.")*
2. **Secondary**: someone comparing agentic dev-tooling products who wants to
   see concrete numbers (plugin/skill/command counts) before installing.
   *(Inferred from the "signal-strip" stat block, `app/page.tsx:155-163`.)*

*Unconfirmed: whether there is a specific ICP beyond "solo/small-team
developer" (e.g. indie hackers vs. agency freelancers vs. internal tools
teams) — see Open questions.*

## Goals / Non-goals

**Goals**
- Communicate the product's five-stage operating loop (Intake → Shape → Build
  → Prove → Ship) and its three-runtime portability (Claude/Codex/Antigravity)
  clearly enough to drive an install.
- Signal credibility through concrete, real numbers (19 plugins, 80–185
  skills, 126 commands) rather than generic marketing claims.

**Non-goals** *(inferred from what does not exist in `app/`, not from a
stated decision — confirm before treating as intentional)*
- No authenticated user area, dashboard, or account system today.
- No live product usage/demo beyond the static "flight deck" preview panel
  (`app/page.tsx:117-152`, which is illustrative UI, not a live run).
- No blog/content marketing surface, no pricing page, no docs site — this is
  a single-page conversion surface only.

## User stories

- As a solo developer evaluating dev-tooling products, I want to see what
  stages of the product lifecycle are covered so that I can judge fit before
  installing.
  Acceptance: [ ] the workflow section (`#workflow`) names all lifecycle
  stages the product claims to cover; [ ] the number matches what's actually
  shipped (currently the page shows a 16-stage loop copy while the signal
  strip shows "16 workflow stages" — confirmed consistent as of this audit).
- As a prospective user, I want to install the product on my own Claude/Codex/
  Antigravity setup, so that I can try it immediately.
  Acceptance: [ ] the README's install commands for all three runtimes are
  copy-pasteable and current (confirmed present at `README.md:60-221`, not
  independently executed in this audit).
- As a returning visitor, I want to trust that stated capability counts (80
  skills, 126 commands, 19 plugins) are accurate, so that the credibility
  signal isn't false advertising.
  Acceptance: [ ] counts on the page match `capability-inventory.json` and the
  actual `platforms/*` filesystem (confirmed matching for Claude/Antigravity
  as of 2026-08-07; two in-repo docs — `parity/README.md` in Claude and
  Antigravity — were found stale at 125/79 and fixed as part of this same
  session, see `decisions.md`).

## Scope

### MVP (already shipped, this PRD documents it retroactively)
- Single-page marketing site with hero, system overview, workflow loop,
  AgentRooms/modules showcase, three-runtime proof section, and a CTA.
- Static OG/Twitter social cards, favicon.
- Cloudflare Workers deployment via Vinext/Wrangler.

### Later (explicitly deferred — confirmed absent, not confirmed intentional)
- SEO fundamentals: `robots.txt`, `sitemap.xml`, structured data (see
  `.solo/risks.md`, P0).
- Monitoring/analytics instrumentation (see `.solo/risks.md`, P0).
- A CI/CD pipeline gating changes to this site (see `.solo/risks.md`, P0).
- Any live "try it" / interactive demo beyond the static flight-deck mockup.

## Success metrics (how we'll know it worked)

*Not established anywhere in the repo — no analytics are wired (confirmed by
the 2026-08-07 audit), so there is currently no way to measure conversion,
time-on-page, or install-through-rate from this site. This is itself a gap:
see Open questions.*

## Risks & assumptions (riskiest first)

1. **Assumption**: the primary conversion action is "install the suite,"
   not e.g. "star the repo" or "read the docs." The CTA copy ("Start a
   full-team run", `app/page.tsx:105`) supports this but it's a client-side
   state toggle only (`setRunStarted(true)`) — it does not actually link to
   install instructions or scroll to them. **This may be a real UX gap**: a
   visitor clicking the primary CTA gets a checkmark, not the README's install
   commands.
2. **Assumption**: stated capability counts (19/80/126) are the credibility
   mechanism that matters most to the target user. If the real objection is
   "does this actually work reliably," the counts alone don't address it —
   the site has no case studies, testimonials, or before/after evidence.
3. **Risk**: the site currently fails the product's own production-readiness
   bar (see `.solo/risks.md`) — shipping a marketing page for a "production
   readiness" product that isn't itself production-ready is a credibility
   risk if a technical visitor inspects it (e.g. via browser devtools network
   tab or view-source for security headers).

## Open questions

1. Is there a specific ICP narrower than "solo/small-team developer"?
2. What is the actual primary conversion goal — install, GitHub star, docs
   read, something else — and should the hero CTA link there directly instead
   of only toggling local state?
3. What analytics/success metric should be wired in first (see
   `.solo/risks.md` P0/P1 monitoring gap) — page views, CTA clicks, install
   completions?
4. Should `app/chatgpt-auth.ts` be wired up, rewritten, or deleted? It is
   currently unreferenced dead code implementing a header-trusting auth
   pattern (see `.solo/risks.md`).
5. Is a D1 database actually needed for this site at all, or should
   `db/index.ts`/`db/schema.ts`/`drizzle.config.ts` be removed until there is
   a real feature that needs one? Right now they exist unconfigured and
   `db/index.ts` will throw if ever called.
