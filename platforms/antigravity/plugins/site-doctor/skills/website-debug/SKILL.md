---
name: website-debug
description: Systematically debug broken website behavior — blank pages, JavaScript errors, failed API calls, CORS errors, 500s, hydration mismatches, WebSocket disconnects, layout breakage, or "works locally but not in production". Use whenever something on a site or web app is broken, erroring, hanging, or behaving strangely and the cause is not yet known, including when the user just pastes an error message or screenshot and says "why is this happening" or "fix this".
---

# Website Debug

Debugging is evidence work. Never patch a symptom you can't reproduce, and never change two things at once — if the fix works you won't know why, and if it doesn't you've contaminated the experiment.

## The loop

1. **Reproduce reliably.** Get exact steps, browser/device, environment (local/staging/prod), and whether it always happens or intermittently. An intermittent bug is usually a race, cache, or environment difference.
2. **Read the actual error.** The full message and stack trace, not the user's paraphrase. Ask for browser console output, network tab, and server logs verbatim.
3. **Isolate the layer.** Walk the request path and find the first place reality diverges from expectation:
   `browser render → JS runtime → network request → server handler → database → response → render`
4. **Bisect.** `git bisect` against a known-good commit, comment out half the suspects, or build a minimal repro. Halving beats guessing.
5. **Fix the root cause**, not the first place the error surfaces.
6. **Verify + protect.** Re-run the repro steps, then add a regression test or assertion so it can't silently return.

## Evidence-gathering commands

```bash
curl -sv https://site.com/api/endpoint          # raw status, headers, body
curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" URL   # quick status+timing
git log --oneline -15                            # what changed recently?
git diff <last-known-good>..HEAD -- <suspect-dir>
```

In the browser: Console (errors), Network tab (failed/slow requests, payloads), Application tab (cookies, storage, service workers — a stale service worker explains a lot of "impossible" bugs).

## Symptom playbooks

### Blank / white page
Check console first. Usual causes in order of likelihood: JS bundle 404 (wrong publicPath/base URL), an uncaught exception during initial render, root element ID mismatch, CSP blocking scripts (console says so explicitly), or an ad-blocker. If the console is clean, view source — is the HTML even there?

### CORS errors
The error is in the browser, the fix is on the **server**. Verify what's actually returned: `curl -s -i -X OPTIONS -H "Origin: https://app.com" -H "Access-Control-Request-Method: POST" https://api.com/route`. Check `Access-Control-Allow-Origin` matches the origin exactly (no trailing slash), that the method/headers are allowed, and — if cookies are involved — that `Access-Control-Allow-Credentials: true` is set and the origin is not `*`. Never "fix" CORS with a browser flag or a public proxy.

### 4xx/5xx from the API
Server logs first — the browser only sees the sanitized result. Match the timestamp, get the stack trace, then ask: did a deploy, env var change, or dependency bump land right before it started? A 502/504 usually means the app process is down or too slow behind the proxy, not an app bug.

### Hydration mismatch (React/Next/SSR)
Server HTML ≠ first client render. Hunt for non-determinism in render: `Date.now()`, `Math.random()`, locale/timezone formatting, `window`/`localStorage` access during render, or user-agent branching. Fix by moving browser-only logic into `useEffect` or gating with a mounted flag — don't blanket-suppress the warning.

### Works locally, broken in production
Diff the environments, not the code: env vars present? build-time vs runtime config? case-sensitive imports (macOS is forgiving, Linux is not)? `devDependencies` needed at runtime? different Node version? CDN/proxy caching an old bundle (hard-refresh + check asset hashes)? Database migrations applied?

### WebSocket problems (connects then drops, or never connects)
- Never connects: is the URL `wss://` on an HTTPS page? Does the reverse proxy forward upgrades? nginx needs `proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";` and a long `proxy_read_timeout`.
- Connects then drops ~30–60s later: an idle timeout at the proxy/load balancer. Implement ping/pong heartbeats below the timeout interval.
- Flaky reconnects: verify exponential backoff with jitter, and that server-side session state survives (or is rebuilt on) reconnect. Log the close code — 1006 means abnormal closure (network/proxy), 1000/1001 are clean.

### Page is slow
Split TTFB from render time (Network tab waterfall). High TTFB → server/database (hand off to **database-debug** if queries are the suspect). Fast TTFB but slow render → oversized bundle, render-blocking resources, N+1 API calls from the client, or huge unoptimized images.

### Build fails
Read the first error, not the last — later errors are usually cascade. Reproduce with a clean install (`rm -rf node_modules && npm ci`) to rule out local state. Lockfile drift and Node version mismatch cause most "works on my machine" build breaks.

## When you find it

State the root cause in one sentence, apply the smallest fix that addresses it, re-run the repro, and add the regression guard. If the fix belongs to a category the **website-fix** skill covers (headers, config, assets), follow its safety workflow. If the root cause turns out to be the database, switch to **database-debug**.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
