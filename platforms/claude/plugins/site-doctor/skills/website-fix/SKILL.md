---
name: website-fix
description: Safely apply fixes for website issues found by an audit or debugging session — security headers, HTTPS, caching, images, SEO tags, accessibility, broken links — one change at a time with verification after each. Use when the user says "fix the issues", "fix what the audit found", "apply the fixes", "clean these up", or asks to remediate any finding from a site review, even a single one.
---

# Website Fix

Fixing is riskier than finding. A bad audit wastes time; a bad fix breaks production. Follow the safety workflow every time, even for "trivial" changes.

**Manual execution boundary:** code or configuration patches inside the user-authorized workspace may be prepared and verified, but any production change, external-service mutation, deployment, DNS/TLS/CDN change, destructive action, or side-effecting browser submission requires a preview and explicit user approval before execution.

## Safety workflow

1. **Create a restore point.** New git branch (`git checkout -b fix/audit-YYYY-MM-DD`). If editing server config directly, copy the file first (`cp nginx.conf nginx.conf.bak`).
2. **Prioritize.** Fix in this order: Critical security → data-loss risks → broken functionality → performance → SEO → cosmetic. Within a tier, do quick wins first.
3. **One fix per commit**, with a message naming the finding it resolves. This makes any regression bisectable to a single change.
4. **Verify each fix** before moving on — re-run the specific audit check that flagged it (the check_headers.py / check_links.py scripts, or the manual check).
5. **Summarize** at the end: fixed / skipped / needs-human, each with a one-liner.

## Ask before touching

Never auto-fix these — propose the change and wait for explicit approval:
- Anything in auth, payments, or session handling.
- Deleting files or database records.
- Major-version dependency upgrades.
- CSP in enforce mode on a production site (start with `Content-Security-Policy-Report-Only`, watch for violations, then enforce).
- DNS, TLS certificates, or CDN configuration.

## Fix recipes

### Security headers
Add at the outermost layer you control (proxy > framework > app):

**nginx**
```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

**Express** — `npm i helmet` then `app.use(helmet())` covers the set with sane defaults.

**Next.js** — return them from `headers()` in `next.config.js` for all routes (`source: "/(.*)"`).

### Force HTTPS
nginx: a port-80 server block with `return 301 https://$host$request_uri;`. Behind a load balancer, redirect when `X-Forwarded-Proto` is `http` instead — checking `req.secure` alone will loop.

### Caching
Hashed static assets: `Cache-Control: public, max-age=31536000, immutable`. HTML: `Cache-Control: no-cache` (revalidate, don't skip). Never long-cache HTML that references hashed assets, or users get stuck on stale bundles.

### Mixed content
Replace `http://` asset URLs with `https://` (or protocol-relative `//`). For large codebases: `grep -rn 'src="http://' --include='*.html' --include='*.jsx' .` then fix each; add `Content-Security-Policy: upgrade-insecure-requests` as a safety net, not a substitute.

### Images
Convert to WebP (`cwebp -q 82 in.png -o out.webp` or sharp in a build step), add explicit `width`/`height`, add `loading="lazy"` to below-the-fold images only — lazy-loading the LCP image makes things worse.

### SEO tags
One `<title>` + `meta description` per page; add canonical to duplicate-reachable pages; generate `sitemap.xml` in the build and reference it from `robots.txt`. Verify `robots.txt` isn't blocking `/` (it happens more than you'd think after staging configs leak to prod).

### Accessibility
Write `alt` text that says what the image conveys ("Dashboard showing weekly revenue up 12%"), not "image of chart". Bind labels with `for`/`id`. Replace clickable `<div>`s with `<button>` — you get keyboard and focus behavior for free instead of re-implementing it badly.

### Broken links
Internal: fix the href or add a 301 from the old path. External: update to the live URL, or link an archived copy if the target is gone. Redirect chains: point the origin directly at the final destination.

### Exposed files (.env, .git)
Block at the server *and* remove from the webroot. nginx: `location ~ /\.(env|git) { deny all; return 404; }`. If a secret was ever exposed, **rotate it** — blocking the path doesn't unleak the key.

## After fixing

Re-run the full audit pass on the touched categories and show before/after. Recommend deploying to staging first when one exists; for header and redirect changes, verify on the live domain after deploy since proxies and CDNs can override app-level config.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
