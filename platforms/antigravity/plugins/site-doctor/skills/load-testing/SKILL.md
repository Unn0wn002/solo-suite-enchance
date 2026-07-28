---
name: load-testing
description: Plan and interpret load, stress, and capacity testing for a website or API — designing realistic load scenarios, choosing metrics and thresholds, finding bottlenecks and breaking points, testing spikes and sustained load, and turning results into scaling and capacity decisions. Use whenever the user wants to load test, stress test, check capacity, "can my site handle traffic", prepare for a launch/spike/sale, find performance bottlenecks under load, or size infrastructure. Complements performance-tuning (single-user speed) with a concurrency lens.
---

# Load Testing

Single-user speed (performance-tuning) and behavior-under-load are different questions — a page that's fast for one user can fall over at 500 concurrent. Load testing answers: how much traffic can this handle, where does it break first, and what does it do when it breaks? The goal is to find the limits and the bottleneck *before* real traffic does, in a controlled way.

## Rules of engagement (important)

- **Only load-test systems you own/operate**, and understand load testing can degrade or take down the target — that's partly the point, but it must be intentional.
- **Test against a staging/production-like environment**, not live production, unless you deliberately choose a careful production test with safeguards. Hitting production with heavy synthetic load can cause a real outage and pollute analytics.
- Coordinate: warn anyone who'd be paged, and have a stop/abort plan.

## 1. Define the test before running anything

- **What question are you answering?** "Can we handle the Black Friday spike?" / "How many concurrent users before latency degrades?" / "Where's the bottleneck?" — the question shapes the test type.
- **Realistic load model**: base it on real traffic patterns (or projected) — expected concurrent users, requests/sec, the actual mix of pages/endpoints they hit, think-time between actions, and geographic distribution. Hammering one endpoint at full speed with no think-time is not realistic and gives misleading results.
- **Success criteria / thresholds**: define acceptable latency (e.g. p95 < 500ms) and error rate (< 0.1%) *before* the test, so results are pass/fail against a target, not just numbers.

## 2. Test types (pick by question)

- **Load test**: expected peak load, sustained — does it meet thresholds under normal-max conditions?
- **Stress test**: ramp beyond expected until it breaks — find the breaking point and see *how* it degrades (graceful slowdown vs cascading failure vs crash).
- **Spike test**: sudden sharp traffic jump (launch, viral moment, sale open) — does it absorb the spike or fall over? Tests autoscaling reaction time.
- **Soak / endurance test**: moderate load for hours — reveals slow problems: memory leaks, connection-pool exhaustion, disk filling, degradation over time that a short test misses.
- **Scalability test**: increase load stepwise to see how added capacity translates to throughput (does it scale linearly, or hit a wall?).

## 3. Realistic scenarios

- **Model real user journeys**, not just endpoint hammering: a user logs in, browses, searches, adds to cart, checks out — with think-time between steps and realistic data variety.
- **Vary the data**: different users, different parameters, cache-busting variety — testing with one cached request massively overstates capacity (you're testing the cache, not the app).
- **Include the expensive paths**: the operations you suspect are heavy (complex queries, report generation, search, writes) proportional to real usage — the bottleneck usually hides in these.
- Ramp up gradually (and include the ramp in analysis) rather than instant full load, unless spike-testing specifically.

## 4. What to measure

- **Latency as percentiles**: p50/p95/p99, never just average — the average hides the tail that real users feel. p99 blowing up while p50 looks fine is a common and important signal.
- **Throughput**: requests/sec actually served (not just offered) — where does it plateau?
- **Error rate**: percentage of failed/timed-out requests as load climbs — the point where errors start is a key limit.
- **Resource saturation on the system under test**: CPU, memory, disk I/O, network, **database connections**, queue depth — this is how you find *what* the bottleneck is (ties directly to observability's golden signals; watch server metrics during the test, not just client-side numbers).
- **The breaking point**: the load level where thresholds are breached or the system fails, and the failure mode.

## 5. Finding the bottleneck (the actual value of the test)

When it degrades, find *why* — the constraint is usually one of:
- **Database**: slow queries under concurrency, connection pool exhausted, lock contention (hand off to database-debug — load testing surfaces DB limits vividly).
- **Application**: CPU-bound handlers, thread/worker pool limits, memory pressure, blocking I/O, inefficient code paths that only hurt at scale.
- **Infrastructure**: undersized instances, network/bandwidth limits, load balancer limits, no autoscaling or too-slow scaling (ties to infrastructure-audit and cost-optimization).
- **External dependencies**: a downstream API or service that rate-limits or slows under your load.
Correlate the latency/error inflection with which resource saturated first — that's your bottleneck.

## 6. From results to decisions

- **Capacity headroom**: how far is expected peak from the breaking point? Enough margin for spikes and growth? If peak is close to the limit, you're one busy day from an outage.
- **Scaling strategy**: does adding capacity actually help (scale out), or is there a single bottleneck (one database, a lock) that more app servers won't fix? Load testing distinguishes these.
- **Fix and re-test**: address the top bottleneck, then re-run to confirm the limit moved — one iteration rarely finds the final ceiling.
- Autoscaling tuning: does it react fast enough for spikes? (Spike test validates this.)

## Report / plan format

**Planning a test**: a test plan — scenarios, load model, thresholds, environment, and what to monitor. **Interpreting results**: the numbers (throughput plateau, latency percentiles vs thresholds, error onset, breaking point), the identified bottleneck with evidence (which resource saturated), and capacity/scaling recommendations with headroom assessment. Either way, tie the constraint to the right specialist — database-debug for DB limits, infrastructure-audit for capacity, performance-tuning for per-request efficiency — and always watch server-side saturation metrics (observability) during the run, not just client-side latency.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
