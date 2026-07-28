---
name: cloudflare-audit
description: Audit a Cloudflare setup for a site — DNS records, SSL/TLS mode, redirect and cache rules, page/transform rules, WAF and bot protection, security headers, origin exposure, and proxy (orange-cloud) status. Use when the user wants a Cloudflare review, "check my Cloudflare", DNS/SSL/WAF/cache configuration on Cloudflare, or asks if their Cloudflare is set up safely. Vendor-specific front end to site-doctor's infrastructure-audit and website-audit; reads .solo/stack.md; uses a Cloudflare connector for live config when available.
---

# Cloudflare Audit

**AgentRoom proposal mode:** preserve raw audit evidence in the seat's declared direct artifact. Any tasks, decisions, handoff, stack update, or other target listed under `proposes` goes to `.solo/proposals/<seat>-<run_id>.md` with its target and proposed entries; never edit that target. Only the memory steward merges, and missing seat/run identity stops the write.

Cloudflare sits in front of everything — DNS, TLS, caching, and the WAF — so a misconfiguration here undermines the whole site: an exposed origin lets attackers skip the WAF entirely, a "Flexible" SSL mode leaves traffic unencrypted to your server, a grey-clouded record means no protection at all. This skill audits the Cloudflare-specific configuration and hands the underlying mechanics (DNS/TLS/network exposure, security headers) to site-doctor's generic engines so the two agree.

## Setup

Read `.solo/stack.md` first to confirm Cloudflare is the DNS/CDN/WAF provider and pick up the domain; if `stack.md` is missing, offer `/stack:intake`. **Only audit zones you own/control.** For configuration, in order of preference: use a **Cloudflare connector/MCP if one is available** to read live zone settings; otherwise work from an exported config or the dashboard details the user provides. External behavior (headers, redirects, TLS from the outside) can be probed directly.

## What to check

1. **Proxy status (orange vs grey cloud)** — records serving web traffic should be **proxied** (orange). A grey-clouded record exposes the origin directly and bypasses Cloudflare's CDN, WAF, and DDoS protection entirely — check this first, it silently negates everything else.
2. **Origin exposure** — the origin IP must not be discoverable or directly reachable. If attackers can hit the origin directly (leaked IP, grey-clouded subdomain, historical DNS), they skip the WAF. Lock the origin to only accept traffic from Cloudflare (Authenticated Origin Pulls / IP allowlist of Cloudflare ranges / Cloudflare Tunnel). This is the highest-impact Cloudflare-specific finding.
3. **SSL/TLS mode** — should be **Full (Strict)**. "Flexible" leaves the Cloudflare→origin hop unencrypted (and users see a padlock that lies); "Full" (non-strict) doesn't validate the origin cert. Full (Strict) end-to-end. Plus: minimum TLS version 1.2+, HSTS, Always Use HTTPS, TLS 1.3 on. (Deep TLS review → site-doctor `infrastructure-audit`.)
4. **DNS records** — correct and intentional; no dangling records pointing at decommissioned services (subdomain-takeover risk); CAA records restricting who can issue certs; email records (SPF/DKIM/DMARC) present if the domain sends mail (→ `/stack:audit-tags` is analytics, → site-doctor `email-check` for these). Sensible TTLs. (Deep DNS → `infrastructure-audit`.)
5. **WAF rules** — the managed ruleset enabled; sensible custom rules; rate limiting on sensitive endpoints (login, API, password reset); no overly broad allow rules punching holes through it.
6. **Bot protection** — Bot Fight Mode / managed bot rules appropriate to the site; challenge/JS-detection on abuse-prone paths without breaking legitimate traffic or accessibility.
7. **Cache rules** — static assets cached with sane TTLs; **HTML/authenticated responses not over-cached** (a cache rule that caches personalized or logged-in pages can leak one user's data to another — a serious and common misconfiguration); cache-bypass for API/auth routes; correct handling of query strings and cookies in the cache key.
8. **Page rules / Transform rules / Redirect rules** — redirects correct and not looping; no conflicting or shadowed rules (order matters); transform/header rules doing what's intended; www↔apex canonicalization consistent.
9. **Security headers** — CSP, HSTS, X-Content-Type-Options, Referrer-Policy, etc., whether set at Cloudflare (Transform Rules / managed headers) or origin. (Run site-doctor's `check_headers.py` from `website-audit` for the authoritative external header check.)

## Delegate the depth

This skill owns the Cloudflare-specific checklist; the underlying analysis lives in site-doctor:
- DNS, TLS, and network-exposure mechanics → **`infrastructure-audit`**.
- Security headers (with the header scanner) → **`website-audit`**.
- Email DNS (SPF/DKIM/DMARC) → **`email-deliverability`** (`/site-doctor:email-check`).
Invoke those for the deep pass; don't duplicate them here. If site-doctor isn't installed, apply the checklist directly at a lighter depth.

## Report & memory

Shared audit format (Summary → Scorecard → Findings [Evidence / Impact / Fix] → Fix order), grouped **Proxy & Origin / TLS / DNS / WAF & Bots / Cache / Rules / Headers**. Rank by real exposure — grey-clouded records, a reachable origin, and Flexible SSL top the list; a suboptimal cache TTL is lower. If `.solo/` exists, write the prioritized fixes into `tasks.md` (stable T-IDs) and note the audit in `handoff.md`, so `/solo:next-step` and `/release:preflight` see them.

## Two ways to run this audit

State which mode you used — findings carry different confidence. (connector-auditor tiers: live → local config files → ask)

### Mode 1 — Connector mode (live config)
A connector / MCP / API is available (via **connector-auditor**): read the real configuration, read-only, and never print secret values.
- inspect DNS records and proxy (orange-cloud) status
- inspect SSL/TLS mode and edge certificates
- inspect cache rules, page rules, and redirect rules
- inspect WAF / security rules and bot settings
- inspect firewall events for recent blocks/challenges

### Mode 2 — Manual mode (user-supplied evidence)
No connector: ask the user for the evidence instead of guessing — and audit exactly what they provide.
- ask for a DNS records screenshot (values may be redacted)
- ask which SSL/TLS mode is set (screenshot of SSL/TLS tab)
- ask for screenshots of Rules (cache/redirect) and Security/WAF pages
- ask for the origin host so exposure can be checked from outside
- ask for wrangler.toml or CF config in the repo if present

Either way, every finding must name its evidence (which setting, file, screenshot, or API field it came from).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle. Keep `.solo/` current as you go so those session commands stay accurate.
