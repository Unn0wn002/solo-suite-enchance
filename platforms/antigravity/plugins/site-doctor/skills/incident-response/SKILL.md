---
name: incident-response
description: Build incident-response readiness and run incidents well — runbooks for common failures, on-call and escalation setup, severity classification, incident command and communication during an outage, and blameless postmortems afterward. Use whenever the user asks about incident response, on-call, runbooks, "what do we do when it breaks", outage handling, escalation, or writing a postmortem. Complements observability (which detects incidents) and website-debug/database-debug (which diagnose them).
---

# Incident Response

Incidents are inevitable; chaos during them is optional. The difference between a 10-minute blip and a 3-hour disaster is preparation: knowing who responds, how to communicate, and what to do — decided *before* the incident, not improvised at 3am under pressure. This skill covers building that readiness and running incidents well. (Detection is **observability**; diagnosis is **website-debug** / **database-debug** — this is the process around them.)

## Two modes

- **Building readiness** (calm, ahead of time): runbooks, on-call, severity definitions, comms templates. Most of this skill.
- **In an active incident** (now, under pressure): stabilize, communicate, resolve, then learn. See the "During an incident" section — keep it short and actionable.

## 1. Severity classification (decide the language before you need it)

Define levels so everyone means the same thing by "it's bad":
- **SEV1 / Critical** — full outage or severe impact (site down, data loss risk, security breach, payments broken). All-hands, page immediately, exec awareness.
- **SEV2 / Major** — significant degradation, major feature broken, many users affected but not total. Urgent, on-call engaged.
- **SEV3 / Minor** — limited impact, workaround exists, small subset affected. Handled in normal hours.
Clear criteria per level so classification is fast and consistent — it drives who's woken and how loud the response is.

## 2. On-call & escalation

- **A real on-call rotation** with clear ownership at all times — everyone knows who's responsible right now, and it's sustainable (not one hero who burns out).
- **Escalation path**: if the first responder can't resolve or doesn't ack, it escalates — secondary on-call, then leads, then management — automatically, with defined timeouts. An alert nobody acks must escalate, not vanish (ties to observability's alerting).
- **Contact info and access** current and reachable during an incident (not stored only in the system that's down); responders have the access and tools to actually fix things.

## 3. Runbooks (the highest-leverage prep)

A runbook is a step-by-step guide for handling a specific, anticipated failure — so the response is executing a known procedure, not inventing one:
- **Cover the likely incidents**: site down, database down/slow, high error rate, deploy gone bad, disk full, cert expired, key dependency down, traffic spike, suspected breach.
- **Each runbook**: how to confirm it's happening, how to diagnose (link to the debug approach), immediate mitigation steps, how to resolve, how to verify recovery, and when/how to escalate.
- **Include the fast mitigations**: rollback the last deploy (hand off to deployment-review), fail over, scale up, enable maintenance mode, disable the broken feature (feature flag). Often you mitigate first (stop the bleeding) and root-cause after.
- Runbooks live somewhere reachable during an outage and are kept current — a runbook referencing a system that changed is worse than none.

## 4. Communication (the part that's usually worst)

- **Internal coordination**: a designated incident channel and an incident commander role for anything serious — one person coordinating, others executing, so responders aren't tripping over each other. For big incidents, separate "fixing it" from "communicating about it."
- **Status communication**: keep users/stakeholders informed (status page, updates at a defined cadence) — silence during an outage erodes trust faster than the outage itself. Say what's affected, that you're on it, and when the next update comes.
- **Templates ready**: pre-written status update / customer notification skeletons so you're not wordsmithing during the crisis.

## During an incident (the short version)

1. **Assess & classify** — what's the impact, what severity, who/what's affected.
2. **Mitigate first** — stop the bleeding (rollback, failover, scale, disable feature) before chasing root cause; restoring service beats understanding it in the moment.
3. **Coordinate** — incident commander for serious ones; clear roles; single source of truth (the incident channel).
4. **Communicate** — tell stakeholders/users early and at a steady cadence, even if the update is "still investigating."
5. **Diagnose & resolve** — hand to website-debug / database-debug for the actual technical diagnosis; apply the fix; **verify recovery** (confirm via monitoring, not hope).
6. **Capture** as you go — timeline, what you saw, what you tried — for the postmortem later.
Resist the urge to skip mitigation and go straight to root cause while users are down.

## 5. Blameless postmortem (where the real value compounds)

After any significant incident, write it up — **blamelessly** (focus on systems and process, not individuals; people act reasonably given the information they had; blame kills the honesty that makes postmortems useful):
- **Timeline**: what happened, when it was detected, what was done, when resolved.
- **Impact**: who/what was affected, for how long, magnitude.
- **Root cause**: the actual underlying cause (and contributing factors) — dig past the proximate trigger. Note what changed (most incidents follow a change).
- **What went well / what didn't**: detection speed, response, communication, the runbook (or its absence).
- **Action items**: concrete, owned, dated improvements — the fix, plus prevention (better monitoring/alerting, a new runbook, a guardrail, a process change). Feed these back into observability, deployment-review, and the runbooks. A postmortem with no tracked action items is theater.

## Report / plan format

**Building readiness**: a prioritized plan — severity definitions, on-call/escalation setup, the runbooks to write first (by likelihood × impact), and comms templates; note the biggest readiness gap. **Running/reviewing an incident**: structured incident notes or a blameless postmortem in the format above. Cross-reference observability (detection/alerting), deployment-review (rollback), and the debug skills (diagnosis) throughout.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
