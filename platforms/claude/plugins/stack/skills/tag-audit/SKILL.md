---
name: tag-audit
description: Audit a site's analytics tags and pixels — Google Tag Manager installation, GA4 firing correctly (no double-counting), conversion events, consent mode, Meta Pixel / TikTok Pixel, PII leakage into tags, form tracking, and checkout/sign-up funnel tracking. Use when the user wants a tag/pixel/tracking review, "check my GTM/GA4/pixels", conversion tracking, consent mode, or asks why their analytics data looks wrong. Vendor-specific front end to site-doctor's analytics-audit and compliance-check; reads .solo/stack.md; reuses the tracker scanner.
---

# Tag Audit

**AgentRoom proposal mode:** preserve raw audit evidence in the seat's declared direct artifact. Any tasks, decisions, handoff, stack update, or other target listed under `proposes` goes to `.solo/proposals/<seat>-<run_id>.md` with its target and proposed entries; never edit that target. Only the memory steward merges, and missing seat/run identity stops the write.

Marketing tags are decision-making infrastructure that's usually quietly broken — GA4 double-counting because it's installed twice, conversions untracked, or pixels firing before consent and sending user emails into the URL. The result is wrong numbers *and* a privacy liability. This skill audits the tag/pixel layer specifically, leaning on site-doctor's `analytics-audit` (data quality) and `compliance-check` (consent, PII) for the deep mechanics.

## Setup

Read `.solo/stack.md` to see which tags/pixels are in play (GTM, GA4, Meta, TikTok, Hotjar, etc.) and whether consent mode is expected; if missing, offer `/stack:intake`. **Reuse site-doctor's tracker scanner** for the factual inventory of what actually fires: run it via `/site-doctor:compliance` (its compliance-check skill owns `scan_trackers.py`); if site-doctor isn't installed, do the tracker inventory manually from a page crawl. It's a static floor — it sees server-set cookies and static third-party references; JS-injected tags and consent-gated behavior need a real browser with the consent banner UNaccepted to confirm what fires pre-consent.

## What to check

1. **GTM installed correctly** — the container snippet present on every page (missing from some templates = blind spots), in the right place, firing, and only **one** container (duplicate containers cause chaos). No leftover test/staging container ID in production.
2. **GA4 firing once, not double** — the classic data-corrupting bug: GA4 loaded both hardcoded *and* via GTM double-counts every pageview and halves bounce rate. Confirm exactly one GA4 load path. Correct Measurement ID (prod property, not a dev/old one; staging not polluting prod). SPA route changes fire page_view events (SPAs often only track the initial load).
3. **Conversion events** — the actions that define success (sign-up, purchase, lead, key click) actually fire events and are marked as conversions/key events in GA4. A site tracking pageviews but not conversions can't measure what it's for.
4. **Checkout / sign-up funnel tracking** — each step of the critical funnels fires an event so drop-off is visible (view → add-to-cart → checkout → purchase; or landing → form-start → sign-up). Gaps mean you can't diagnose where users fall out. E-commerce/revenue events correct if applicable (values, currency) and matching the backend.
5. **Form tracking** — form starts and submissions tracked (and errors, ideally); tracking distinguishes success from failure; not double-firing on validation retries. (UX side → site-doctor `forms-audit`.)
6. **Consent mode** — non-essential tags (analytics, ads, pixels) do **not** fire before consent where required, or run in a consent-mode/cookieless fashion until granted. Many sites show a banner but load GA4/Meta on page load anyway — the scanner (banner unaccepted) helps catch this. Consent choices are respected and withdrawable. **This overlaps heavily with site-doctor `compliance-check`** — a tag firing pre-consent is both a tag-setup detail and a compliance gap.
7. **Meta Pixel / TikTok Pixel (and others)** — installed correctly, firing once, with the right pixel ID; standard + conversion events configured; consent-gated like everything else; advanced matching not sending raw PII (see below).
8. **PII leakage into tags (privacy-critical)** — no emails, names, phone numbers, or other personal data in URLs, event parameters, or user IDs sent to GA4/pixels (a common accidental violation and against most tools' ToS). Check query strings and form-field values aren't captured verbatim; hashed identifiers where matching is intended, not raw PII. (→ site-doctor `compliance-check`.)

## Delegate the depth

Tag-specific checklist here; the engines are in site-doctor:
- Tag firing, double-counting, event/conversion coverage, naming consistency, data quality → **`analytics-audit`** (`/site-doctor:audit-analytics`).
- Consent gating, PII, cookie/tracker behavior (with the scanner) → **`compliance-check`** (`/site-doctor:compliance`) — *not legal advice*, but catches the concrete gaps.
- Tag load performance → **`performance-tuning`**; form UX → **`forms-audit`**.
Invoke those for depth; don't duplicate. Lighter inline pass if site-doctor isn't installed.

## Report & memory

Shared audit format (Summary → Scorecard → Findings [Evidence / Impact / Fix] → Fix order), grouped **GTM / GA4 / Conversions & Funnel / Forms / Consent / Pixels / PII**. Rank by impact — double-counting GA4, untracked conversions, and PII-into-tags or pixels-before-consent lead; a minor event-naming nit is low. Write prioritized fixes to `.solo/tasks.md` and note the audit in `handoff.md` when `.solo/` exists. Because consent/PII findings carry legal weight, flag them clearly and route to `compliance-check` (and a lawyer for anything consequential).

## Two ways to run this audit

State which mode you used — findings carry different confidence. (tiers: GTM/GA4 API or container export → page crawl → ask)

### Mode 1 — Connector mode (live config)
A connector / MCP / API for the tag platform is available (GTM/GA4 API or a container export; **connector-auditor** covers Vercel/Supabase/GitHub/Cloudflare, not tag platforms): read the real configuration, read-only, and never print secret values.
- inspect the GTM container (tags, triggers, variables) via API/export
- inspect GA4 data streams and key events
- crawl key pages to observe which tags actually fire

### Mode 2 — Manual mode (user-supplied evidence)
No connector: ask the user for the evidence instead of guessing — and audit exactly what they provide.
- ask for a **locally reviewed/redacted** GTM container export (JSON). Treat
  every export as potentially sensitive: custom HTML, variables, identifiers,
  endpoints, and embedded configuration can contain credentials or personal
  data. Prefer a local file path and never paste or reproduce sensitive values.
- ask for screenshots of GA4 events/key events and Tag Assistant output
- ask for the site URL to check tag firing from the outside
- ask which conversions are supposed to be tracked (the intent)

Either way, every finding must name its evidence (which setting, file, screenshot, or API field it came from).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle. Keep `.solo/` current as you go so those session commands stay accurate.
