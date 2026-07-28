---
name: cost-optimization
description: Find and reduce cloud, hosting, and database spend without hurting reliability — over-provisioned compute, idle/orphaned resources, inefficient database usage, bandwidth and egress waste, unattached storage and old snapshots, expensive managed services, and missed savings plans or reserved capacity. Use whenever the user wants to cut their cloud bill, reduce hosting/AWS/GCP/Azure costs, asks "why is my bill so high", "how do I save money on infrastructure", or wants a cost review. Pairs with infrastructure-audit and database-audit.
---

# Cost Optimization

Cloud bills grow by accretion — resources spun up and forgotten, instances sized for a spike that never recurs, data quietly egressing. The goal is to cut waste, not corners: every recommendation must preserve reliability and performance. Find the waste, quantify it, and rank by savings-per-effort with the risk of each change stated.

## Setup

Get the cost breakdown if available (cloud billing console / cost explorer — group by service and by resource), the infrastructure picture (from infrastructure-audit if done), and the workload shape (steady vs bursty, read vs write heavy). Attack the biggest line items first — spend is usually concentrated in a few services (compute, database, storage, egress), so start there rather than trimming pennies off small ones.

## 1. Compute — usually the biggest line

- **Right-sizing**: instances sized far above actual CPU/memory utilization. If something runs at 10% CPU, it's 3–4× too big. Check real utilization (from observability's saturation metrics) before downsizing — don't right-size on a guess and cause a slowdown.
- **Idle & orphaned**: instances/VMs running nothing, dev/test environments left on 24/7, load balancers with no targets, instances behind removed features. Stop or schedule them (dev environments off nights/weekends is often a big, zero-risk win).
- **Purchasing model**: steady baseline workloads on on-demand pricing are overpaying — savings plans / reserved instances / committed-use discounts cut 30–70% for predictable load. Spot/preemptible for fault-tolerant batch work. Match the commitment to the *steady* portion, not the peak.
- **Serverless vs always-on**: spiky/low-traffic workloads may be cheaper serverless; constant high-traffic workloads may be cheaper on reserved compute. Check the crossover.
- **Autoscaling** so you pay for peak only during peak, not provisioning for peak permanently.

## 2. Database

- Over-provisioned instance class (same right-sizing logic — check utilization first; a struggling DB should NOT be downsized).
- **Idle / oversized**: dev databases running production-sized instances; read replicas nobody reads; multi-AZ on non-critical environments.
- Inefficient usage driving cost: missing indexes causing full scans burn CPU/IO (hand off to database-audit — a query fix can shrink the instance you need); unbounded connection counts forcing a bigger tier.
- Storage tier and IOPS provisioning matched to actual need; automated backups retained sensibly (not thousands of old snapshots — see storage below).
- Reserved/committed pricing for the steady database baseline.

## 3. Storage & snapshots

- **Orphaned volumes**: unattached block storage (detached EBS/persistent disks) billed forever — a classic silent cost. List and clean.
- **Old snapshots/backups**: manual snapshots from years ago, backups with no retention policy piling up. Set lifecycle policies; keep what recovery actually requires (coordinate with backup-recovery), delete the rest.
- **Storage class**: infrequently-accessed data on hot/standard storage — move to infrequent-access or archive tiers (lifecycle rules automate this). Don't archive data you need to read frequently (retrieval fees bite).
- Object storage: incomplete multipart uploads and old versions accumulating; enable lifecycle cleanup.

## 4. Network / bandwidth / egress

- **Egress is the sneaky one**: data transfer out (especially cross-region and to the internet) is expensive and often invisible until the bill. A CDN cuts origin egress dramatically for static/cacheable content (and improves performance — ties to performance-tuning).
- Cross-AZ / cross-region chatter between services billed as transfer — colocate talkative services.
- NAT gateway data processing charges; unused elastic IPs (billed when unattached on some clouds).

## 5. Managed services & licensing

- Expensive managed services where a cheaper tier or self-managed option fits the actual need; premium support/features not being used.
- Duplicate or overlapping tools (two monitoring stacks, two log services); consolidate.
- Log/metric retention longer than needed — observability data volume is a real cost; keep detailed data short, aggregates longer.
- Per-seat SaaS licenses for departed users or unused seats.

## 6. Visibility & governance (so waste doesn't creep back)

- **Tagging** resources by team/environment/project so cost is attributable — you can't optimize what you can't attribute.
- Budgets and cost alerts (hand off to observability) so spend spikes get noticed, not discovered at invoice time.
- A regular review cadence; automated cleanup of orphaned resources.

## Report format

Shared audit structure, but each finding leads with **estimated monthly savings** and a **risk rating** (safe / needs-validation / has-tradeoffs). Group by service (Compute / Database / Storage / Network / Managed services). Rank by savings-per-effort, flagging the zero-risk wins first (orphaned volumes, idle dev environments, old snapshots). Always note where a change could hurt reliability or performance — validate right-sizing against real utilization from observability, and never trade an outage for a few dollars.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
