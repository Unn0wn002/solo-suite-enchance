---
name: website-audit
description: Run a comprehensive technical health audit of a RUNNING website or web app - security headers, performance, SEO, accessibility, broken links, code hygiene, and motion/animation when the codebase is available - producing a severity-ranked report with a concrete fix plan. Use whenever the user asks to audit, check, review, or health-check a site or hands over a URL, asks "what's wrong with my site", mentions slow pages, a Lighthouse-style review, an SEO check or a security check - even if they never say the word "audit". Do NOT use to decide whether to launch - a readiness score belongs to production-readiness-reviewer, a GO/NO-GO checkpoint to quality-gatekeeper, and the deploy/rollback plan to devops-engineer.
---

# Website Audit

**AgentRoom proposal mode:** audit evidence stays in the seat's declared direct artifact. Tasks, decisions, handoff, or any other target declared under `proposes` must be written as `.solo/proposals/<seat>-<run_id>.md` with target and proposed entries, never directly to the target. Only the steward merges; missing seat/run identity is a stop condition.

Produce a report the user can act on. Every finding needs three parts — **evidence** (what you observed), **impact** (why it matters), and **fix** (exactly what to change). A finding without a fix is noise.

## Before you start

1. Get the target: a live URL, a local codebase path, or both. Both is best — the URL shows real behavior (headers, redirects, payload sizes); the code shows causes.
2. Only audit sites the user owns or operates. If it's clearly a third-party site they don't control, decline the active checks and offer general guidance instead.
3. Ask which pages matter most (home, login, checkout, dashboard). Audit those plus 2–3 deep pages — problems hide off the homepage.

## Run the bundled scripts first

They're stdlib-only Python, no installs needed:

```bash
# Security headers, HTTPS redirect, compression, cookie flags, exposed files
python3 "${CLAUDE_PLUGIN_ROOT}/skills/website-audit/scripts/check_headers.py" https://example.com

# Crawl same-domain pages, find broken links + mixed content
python3 "${CLAUDE_PLUGIN_ROOT}/skills/website-audit/scripts/check_links.py" https://example.com --max-pages 30
```
> **Running helpers:** `${CLAUDE_PLUGIN_ROOT}` is set by Claude Code to this plugin's installed root, so the command works from any working directory. If `python3` is not on PATH, use `python` (macOS/Linux/Windows) or `py -3` (Windows launcher) instead.


Use their output as raw evidence, then do the manual checks below. If a script can't reach the site (auth wall, localhost-only), fall back to `curl -sI` and reading the codebase.

## Audit categories (check in this order)

### 1. Security — always first

- HTTP → HTTPS redirect on every page, not just the root.
- Response headers present and sane: `Strict-Transport-Security`, `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options` (or CSP `frame-ancestors`), `Referrer-Policy`, `Permissions-Policy`.
- Cookies carry `Secure`, `HttpOnly`, and an explicit `SameSite`.
- Nothing sensitive reachable: `/.env`, `/.git/HEAD`, `/config.json`, source maps in production, verbose stack traces on error pages.
- Version leakage: `Server` / `X-Powered-By` headers exposing exact versions.
- If the codebase is available: run `npm audit` (or `pip-audit`), grep for hardcoded secrets/API keys (`grep -rEn "(api[_-]?key|secret|password)\s*[:=]" --include="*.{js,ts,jsx,tsx,env,json}" .` then manually verify hits), check that user input reaching HTML/SQL/shell is escaped or parameterized.

### 2. Performance

- Core Web Vitals targets: LCP < 2.5s, INP < 200ms, CLS < 0.1. Estimate from payload sizes and render-blocking resources if you can't measure directly.
- Compression enabled (gzip/brotli) — the header script checks this.
- Caching: static assets get long `Cache-Control` with hashed filenames; HTML gets short/no cache.
- Images: modern formats (WebP/AVIF), explicit `width`/`height` (prevents CLS), `loading="lazy"` below the fold, no multi-MB images.
- JS: bundle size, code splitting, no render-blocking scripts in `<head>` without `defer`/`async`.
- Fonts: `font-display: swap`, preload the primary font, subset if possible.

### 3. SEO

- Unique `<title>` (< 60 chars) and `meta description` (< 160 chars) per page.
- Exactly one `<h1>` per page, logical heading order.
- `robots.txt` exists and doesn't accidentally block the whole site; `sitemap.xml` exists and is referenced.
- Canonical tags on pages reachable via multiple URLs.
- Open Graph + Twitter card tags on shareable pages.
- Structured data (JSON-LD) where content type fits (articles, products, org).
- Clean 404s (real 404 status, not a 200 "not found" page); redirect chains ≤ 1 hop.

### 4. Accessibility

- Every meaningful `<img>` has descriptive `alt`; decorative images use `alt=""`.
- All form inputs have associated `<label>`s (or `aria-label`).
- Interactive elements are real `<button>`/`<a>`, not clickable `<div>`s; visible focus states.
- Color contrast ≥ 4.5:1 for body text; information never conveyed by color alone.
- `<html lang="...">` set; landmarks (`<main>`, `<nav>`) used; skip link on nav-heavy sites.
- Keyboard-only walkthrough of the primary flow: can you complete it without a mouse?

### 5. Links & assets

- Broken internal and external links (the crawl script covers this).
- Mixed content: `http://` resources loaded on `https://` pages.
- Missing favicon / touch icons; oversized or 404ing assets.

### 6. Code hygiene (when the codebase is available)

- Leftover `console.log`/`debugger`, commented-out blocks, TODO/FIXME hotspots.
- Unhandled promise rejections, missing error boundaries (React), missing global error handler.
- Environment config: secrets in env vars, not committed; separate dev/prod configs.
- Dependency health: outdated majors, deprecated packages, lockfile committed.

### 7. Animation & motion design (when the codebase is available)

- If GSAP (or another animation library) is in use: cleanup on unmount, layout-triggering properties animated directly, `prefers-reduced-motion` handling. Full checklist and the bundled scanner live in **animation-design-audit** — run it directly for anything beyond a quick presence check.

## Severity rubric

| Severity | Meaning | Examples |
|---|---|---|
| Critical | Exploitable or data-exposing right now | exposed .env, no HTTPS, injectable input |
| High | Broken functionality or major ranking/UX damage | broken checkout link, site-wide noindex, 5 MB LCP image |
| Medium | Degrades quality, fix this sprint | missing CSP, no cache headers, missing alt text |
| Low | Polish | version header leakage, missing OG tags |

## Report format

ALWAYS use this exact structure:

```
# Website Audit — <site> — <date>

## Summary
<2–3 sentences: overall state + the one thing to fix first>

## Scorecard
| Category | Status | Critical | High | Medium | Low |
|---|---|---|---|---|---|

## Findings
### [SEVERITY] <short title>
- Evidence: <what was observed, with the URL/file/line>
- Impact: <why it matters>
- Fix: <specific change, with a code/config snippet when possible>

## Recommended fix order
<numbered list, Critical → Low, quick wins flagged>
```

## After the report

Offer to apply the fixes with the **website-fix** skill — it handles prioritization, one-change-at-a-time application, and verification. Don't start changing files inside the audit itself; keep measurement and treatment separate so the user can review findings first.

## Project memory integration (solo-team)

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.

## Script safety (url_guard)

The bundled script(s) route every outbound request through `${CLAUDE_PLUGIN_ROOT}/lib/url_guard.py` (shipped at `plugins/site-doctor/lib/url_guard.py` in the source tree): HTTPS-first scheme policy (http only where auditing it is the point), refusal of loopback/private/link-local/CGNAT/reserved/multicast and cloud-metadata targets — every DNS answer and every redirect hop is re-validated — plus a hard response-size cap. A refused target prints `BLOCKED unsafe target: <reason>` instead of being fetched.
