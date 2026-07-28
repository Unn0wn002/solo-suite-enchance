---
name: observability
description: Set up or audit production monitoring, logging, error tracking, alerting, and uptime checks for a website or web app — structured logging, error/exception tracking, uptime and health checks, Core Web Vitals field monitoring (RUM), key metrics and dashboards, alert rules that avoid fatigue, and incident readiness. Use whenever the user asks how to monitor their site, "how do I know when it breaks", set up alerts/logging/error tracking, add health checks, catch problems before users do, or is preparing a site for production traffic.
---

# Observability

**AgentRoom proposal mode:** write monitoring evidence only to declared direct targets. Tasks, decisions, handoff, or another target under `proposes` goes to `.solo/proposals/<seat>-<run_id>.md`, never the target. Only the memory steward merges; missing seat/run identity is a stop condition.

You can't fix what you can't see. The goal is to **know something is wrong before users tell you**, and to have enough signal to find the cause fast when it happens. Build in this order — each layer is worthless without the one before it: **logging → error tracking → uptime/health → metrics → alerts → dashboards**.

Two failure modes to design against: **blind spots** (the outage nobody was paged for) and **alert fatigue** (so many alerts that the real one gets ignored). Everything below balances those two.

## When auditing vs building

- **Auditing** an existing setup: check each layer for coverage and gaps — is there a way the site can be fully down with no alert? Are errors swallowed silently? Do alerts actually reach a human? Are logs useful or noise?
- **Building** from scratch: start at the top of the list and stop when the coverage matches the stakes. A weekend project needs uptime + error tracking; a revenue app needs the full stack.

## 1. Structured logging

- **Structured, not string soup**: emit JSON logs with consistent fields (timestamp, level, request ID, user ID where safe, route, latency, status). Structured logs are queryable; `console.log("it broke")` is not.
- **Correlation**: a request ID threaded through every log line for a request (and propagated to downstream services) so you can reconstruct one request's journey.
- **Levels used meaningfully**: ERROR = needs attention, WARN = suspicious, INFO = notable events, DEBUG = off in prod. Don't log everything at ERROR.
- **Never log secrets or PII** — no passwords, tokens, full card numbers, or personal data in logs (this is both a security and a compliance issue; ties to **security-review** A09).
- **Centralized**: ship logs off the box to a searchable store (the platform's log service, ELK/OpenSearch, Loki, or a SaaS) with sane retention — logs trapped on an ephemeral container vanish when it restarts, usually right when you need them.

## 2. Error / exception tracking

- Capture unhandled exceptions and promise rejections on **both** server and client (a global handler + framework error boundary). A silently swallowed error is a blind spot by definition.
- Use an error-tracking service (Sentry or similar) that groups occurrences, captures stack traces + context (release, user, request), and dedupes — not a flood of identical emails.
- **Source maps** uploaded for production so minified client stack traces are readable.
- Tag errors with **release/version** so you can see "errors spiked after the 3pm deploy" at a glance.
- Set a **user-impact threshold** for alerting (a new error hitting many users pages; a rare edge case files a ticket).

## 3. Uptime & health checks

- **External uptime monitor** hitting the site from outside every minute (UptimeRobot, Pingdom, Better Stack, or a cloud check) — internal monitoring can't tell you the whole box/region is unreachable.
- **Health-check endpoint** (`/health` or `/healthz`) that verifies real dependencies (database reachable, cache reachable, critical downstreams) and returns a meaningful status — not a static `200 OK` that's green while the DB is down. Keep it cheap and unauthenticated-but-unrevealing.
- **Synthetic checks** for critical flows (can a user actually log in / check out?), not just "does the homepage return 200".
- Check TLS certificate expiry and domain expiry (surprisingly common outage causes).

## 4. Metrics — the four golden signals

Track these per service, they cover most of what matters:
- **Latency** — response time, as percentiles (p50/p95/p99), never just the average (the average hides the slow tail users feel).
- **Traffic** — requests/sec, so you can correlate problems with load.
- **Errors** — error rate (5xx and app errors) as a percentage of traffic.
- **Saturation** — how full the resources are (CPU, memory, DB connections, queue depth) — the leading indicator of the *next* outage.

Add **field Core Web Vitals (RUM)**: real-user LCP/INP/CLS from actual visitors (web-vitals library → your analytics, or a RUM provider). Lab scores from **performance-tuning** tell you the potential; RUM tells you what users get and what Google ranks on.

Business-level signals too where they exist (signups/min, checkout success rate) — a drop there catches problems that infrastructure metrics miss.

## 5. Alerting — page on symptoms, not causes

- **Alert on user-facing symptoms** (error rate up, latency up, site down, checkout failing), not on every internal metric wiggle. Symptom-based alerts catch problems you didn't predict; cause-based alerts create noise.
- **Thresholds with duration** ("error rate > 5% for 5 minutes") to avoid flapping on momentary blips.
- **Severity tiers**: page a human for user-impacting incidents; send lower-severity issues to a channel/ticket. Not everything is a 3am wake-up.
- **Every alert is actionable and routed** — it reaches someone who can act, and says what's wrong and where to look. An alert nobody owns is noise.
- **Tune continuously**: delete alerts that cry wolf, add alerts for incidents that slipped through. Alert fatigue is a real outage risk — the ignored-because-usually-false alert is how real ones get missed.

## 6. Dashboards & readiness

- One at-a-glance dashboard with the golden signals + key business metrics, so during an incident you see system state immediately.
- Include recent deploys on the timeline (most incidents follow a change — correlating is half the diagnosis).
- Basic incident readiness: know who's on call, where the runbook is, and how to roll back. (Detailed debugging lives in **website-debug** / **database-debug**.)

## Report / plan format

**Auditing**: shared audit structure, one section per layer, each finding naming the specific blind spot or noise source and the fix. **Building**: a prioritized setup plan — what to add first for the biggest coverage gain given the site's stakes, with concrete tool/config suggestions (framework-appropriate) and example config where useful. Either way, end with the single most important gap to close first.

## Project memory integration (solo-team)

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
