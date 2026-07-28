---
name: analytics-audit
description: Audit a website's analytics and tracking implementation — tag/pixel installation and firing, event and conversion coverage, GA4 or other analytics setup integrity, data-layer consistency, duplicate or double-counting tags, consent-mode integration, and whether the data collected actually answers the business questions. Use whenever the user asks to review their analytics, tracking setup, GA4/Google Analytics, tag manager, event tracking, conversion tracking, "is my tracking working", or why their analytics data looks wrong. Distinct from observability (system health) — this is product/marketing analytics.
---

# Analytics Audit

Analytics is decision-making infrastructure — and it's usually quietly broken: tags firing twice, conversions not tracked, events named inconsistently so reports are noise, or tracking that violates consent. The result is decisions made on wrong numbers. Audit whether the tracking is installed correctly, covers what matters, and produces trustworthy data. (This is product/marketing analytics — for system health, error rates, and uptime, that's **observability**.)

## Setup

Identify the analytics stack (GA4, and/or Segment, Amplitude, Mixpanel, Plausible, Matomo, Meta Pixel, etc.), whether a tag manager is used (GTM), and what business questions the data is supposed to answer (which conversions, funnels, and KPIs matter). Get access to the property/tag manager if possible, or inspect the site's network requests and data layer. The tracker scanner from **compliance-check** (`scan_trackers.py`) also surfaces which analytics/pixels are actually present on the page — reuse it as a starting inventory.

## 1. Installation & firing (does it even work?)

- **Base tag installed correctly** on every page (a tag missing from some templates = blind spots). Confirm it actually fires — check the network requests / analytics debug view / real-time report, don't assume from the code.
- **Fires once, not multiple times**: double-installed tags (e.g. GA hardcoded AND in GTM) cause double-counted pageviews and halve bounce rate — a very common, data-corrupting mistake. Look for the same tag loaded twice.
- **Correct property/measurement ID**: production sending to the production property, not a test/dev property or someone's old ID; staging not polluting production data.
- **Loads without blocking** the page (async/deferred — ties to performance-tuning) and doesn't error in console.
- SPA/client-routing: virtual pageviews fire on route changes (SPAs often only track the initial load, missing all in-app navigation).

## 2. Event & conversion coverage (does it capture what matters?)

- **Key conversions tracked**: the actions that define success (signup, purchase, lead form, key click) actually fire events and are marked as conversions/goals. A site tracking pageviews but not conversions can't measure what it's for.
- **Funnel coverage**: the steps of critical journeys are all tracked so you can see where users drop (add-to-cart → checkout → purchase). Gaps mean you can't diagnose drop-off.
- **Meaningful events**, not just pageviews: important interactions (form submits, video plays, downloads, key CTAs, search usage) captured where they inform decisions — without tracking everything into noise.
- **E-commerce / revenue tracking** correct if applicable (GA4 enhanced ecommerce, purchase value, currency) — revenue numbers matching the actual backend.

## 3. Data quality & consistency

- **Consistent event naming**: a clear, documented naming convention followed everywhere. `signup`, `sign_up`, `SignUp`, `registration` for the same action fragments the data into useless slivers — this is the most common analytics data-quality failure. Check for naming drift.
- **Consistent parameters/properties**: events carry the expected properties, named and typed consistently, so you can segment and compare.
- **Data layer** (if used) populated consistently and correctly before tags read it; no undefined/empty values where data should be.
- **Internal traffic filtered**: your own team's/office's/bot traffic excluded so it doesn't inflate numbers; known bots filtered.
- **Cross-domain / subdomain tracking** configured if the journey spans domains (otherwise sessions break and referrals get misattributed).
- **Attribution & UTM**: campaign tagging consistent so marketing sources are correctly attributed; UTM conventions followed.

## 4. Consent & privacy integration (analytics is where privacy and tracking meet)

- **Consent mode / gating**: analytics respects the consent state — non-essential tracking doesn't fire (or runs in a cookieless/consent-mode fashion) before consent where required. This overlaps heavily with **compliance-check** — a tag that fires pre-consent is both an analytics setup detail and a compliance gap.
- **PII not sent to analytics**: no emails, names, or other personal data in URLs, event parameters, or user IDs sent to analytics tools (a common accidental violation — and against most analytics ToS). Check that query strings with PII aren't captured.
- IP anonymization / appropriate data-retention settings configured where required.

## 5. Reporting & usefulness

- **The data answers the questions**: can the setup actually report on the KPIs the business cares about? If not, that's the core finding — coverage gaps trace back to unmeasurable goals.
- Conversions/goals configured so they show in reports; key segments and audiences defined; dashboards reflect real KPIs, not vanity metrics.
- Data retention settings appropriate; historical continuity (note if a migration, e.g. UA→GA4, created a break in the data).
- Someone can trust and use the numbers — the ultimate test.

## Report format

Shared audit structure (Summary → Scorecard → Findings → Fix order), grouped **Installation / Coverage / Data Quality / Consent / Reporting**. Each finding names the tag/event/page and the concrete fix (the duplicate to remove, the event to add, the naming to standardize, the consent gate to apply). Rank by how badly it corrupts or blocks decision-making — double-counting tags and untracked conversions outrank a minor naming inconsistency. Route consent/PII findings to compliance-check, tag load performance to performance-tuning, and reuse compliance-check's tracker scanner for the initial inventory.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
