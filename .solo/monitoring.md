# Monitoring — Solo Suite Enchance (website)

## What exists today

*(Rewritten 2026-08-07 during the Audit #2 remediation pass. The previous
version of this section still said "Nothing at the application level" and
listed T4 as outstanding, after T4 had already shipped — recorded as finding
F-06 in `docs/audit/MASTER_AUDIT.md`. Keep this section matched to
`worker/index.ts`.)*

**Error capture — implemented (T4).** `worker/index.ts` wraps every request in
a try/catch and calls `reportError()` on the way out:

1. `console.error` with method, URL, and full stack — always on, surfaced via
   Cloudflare Workers logs and `wrangler tail`.
2. An optional fire-and-forget POST to `MONITORING_WEBHOOK_URL` (see
   `.dev.vars.example`), dispatched through `ctx.waitUntil` so it cannot delay
   or fail the real response. Unset by default; setting one env var upgrades
   this to real external notification without a code change.

Deliberately dependency-free — no Sentry/Datadog/OTel SDK, no account, no new
supply-chain surface. That was the point: a single-page marketing site should
not take an observability vendor dependency before it has a single user.

**Platform request logs.** `"observability":{"enabled":true}` in the generated
`dist/server/wrangler.json` gives request-level logs in the Cloudflare
dashboard. Platform-level only — it is not application error tracking.

**Bundle transfer size — measured and enforced.** `performance-budget.json` +
`tests/bundle-budget.test.mjs` fail the build if the client bundle exceeds its
declared gzip budget. This is a build-time guard, not runtime monitoring, but
it is the only performance signal that currently exists at all.

## What's still missing

1. **No alert destination is actually configured.** The webhook path exists and
   is tested-by-construction, but `MONITORING_WEBHOOK_URL` is unset, so today
   an error reaches `console.error` and stops there. Nobody is paged.
2. **No uptime/health check.** Nothing polls the deployed URL. A total outage
   would be noticed by a human visiting the site. `/health-check` is proposed
   in `MASTER_AUDIT.md` §K and is not built.
3. **No Core Web Vitals / RUM.** Bundle size is measured; LCP, INP, CLS and
   TTFB are not (`MASTER_AUDIT.md` H-1).
4. **No product analytics** — and this is an open product question, not an
   oversight. See `prd.md` Open Question #3 before building anything here.

## Alerts

**None configured.** Signal now exists (see above); no destination consumes it.
The smallest useful next step is setting `MONITORING_WEBHOOK_URL` to a Slack or
Discord incoming webhook — that converts the existing code path into a real
alert with no code change and no new dependency.
