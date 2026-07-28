---
name: backup-recovery
description: Audit or design backup and disaster-recovery for a website and its data — backup coverage and frequency, restore testing, retention policies, offsite/cross-region copies, RTO/RPO targets, point-in-time recovery, and a documented recovery runbook. Use whenever the user asks about backups, disaster recovery, "am I backed up", "what happens if the server dies", data loss protection, restore testing, or RTO/RPO. Pairs with database-audit and infrastructure-audit.
---

# Backup & Recovery

A backup you have never restored is a hope, not a backup. The only thing that matters is whether you can get the system back within an acceptable time and with acceptable data loss — everything below serves that. Audit whether real recovery is possible, or design a plan that makes it possible.

## Frame it with RTO and RPO first

Two numbers drive every decision:
- **RPO (Recovery Point Objective)** — how much data can you afford to lose? (Determines backup frequency: hourly backups = up to 1h loss; continuous/PITR = near-zero.)
- **RTO (Recovery Time Objective)** — how long can you be down while recovering? (Determines the recovery *mechanism*: restoring a 500GB dump takes hours; a warm standby is minutes.)

Ask the user what's acceptable for their situation, then check whether the current setup can actually meet it. A mismatch (e.g. "we can't lose more than an hour" but backups run nightly) is the headline finding.

## 1. Coverage — what's actually backed up

- **The database** — the obvious one, but verify it's really running and completing.
- **User-uploaded files / object storage** — often forgotten; the DB references files that aren't backed up, so a restore gives you dangling pointers.
- **Configuration & secrets** — infra config, env config, TLS certs, so you can rebuild the environment, not just the data. (IaC in version control covers much of this — see infrastructure-audit.)
- **Application code** — in version control (that's your backup); confirm the repo itself is safe.
- Gaps kill recoveries: identify anything whose loss would prevent a full restore.

## 2. The 3-2-1 principle

The durable standard: **3 copies, on 2 different media/systems, 1 offsite**. Practically:
- More than one copy (the production data plus at least one backup).
- Not all in the same place — a backup on the same server/disk/account as production dies with it. Cross-region or a separate account/provider.
- At least one truly offsite/isolated copy that a compromise of the main environment can't reach (ransomware and a compromised cloud account both delete reachable backups — immutable/write-once or separate-credential storage defends against this).

## 3. Frequency & retention (must satisfy RPO)

- **Frequency meets RPO**: nightly is fine for a low-change site; a busy transactional app needs continuous archiving / point-in-time recovery so you can restore to any moment, not just last midnight.
- **Retention with a schedule**: e.g. hourly for a day, daily for a month, monthly for a year — enough history to recover from problems discovered late (corruption or a bad deploy noticed days later), without paying to keep everything forever (coordinate with cost-optimization). Automate expiry; don't hoard thousands of snapshots.
- **Point-in-time recovery** for databases where RPO is tight (PG WAL archiving, MySQL binlog, managed-DB PITR) — restores to a specific second, not just the last full backup.

## 4. Restore testing — the part everyone skips

- **Has a restore actually been performed?** An untested backup routinely fails when needed — corrupt archives, missing pieces, credentials no one has, a process no one remembers. If it's never been tested, that's a critical finding regardless of how diligently backups run.
- **Test on a schedule** (quarterly is a reasonable floor): restore to a scratch environment, verify the data is complete and the app comes up.
- **Verify integrity**, not just existence: backups complete without errors, aren't truncated, and are readable. For databases, restore and run integrity checks (ties to database-audit).
- Time the restore — that measured number is your real RTO. If it's longer than acceptable, the mechanism needs to change (standby, faster storage, smaller restore units).

## 5. Recovery mechanism (must satisfy RTO)

- Match mechanism to RTO: restore-from-backup (hours) for relaxed RTO; warm standby / replica promotion (minutes) for tight RTO; multi-region active setup for near-zero.
- **Full disaster scenario**: if the whole region/provider is gone, can you rebuild elsewhere? IaC + offsite backups make this possible; a hand-built server with local backups does not.
- Understand dependencies and order of recovery (database before app, secrets before services).

## 6. The runbook (so recovery works at 3am under stress)

- **A written, tested recovery procedure**: exact steps to restore, who's responsible, where backups live, what credentials are needed, and the order of operations. Tribal knowledge fails precisely when the person who has it is unreachable.
- Access to backups and recovery tools doesn't depend on the thing that's down (don't store the only copy of recovery credentials in the system you're recovering).
- Contact/escalation path; the runbook lives somewhere reachable during an outage.

## Report / plan format

**Auditing**: shared audit structure, with the RTO/RPO reality-check as the lead finding, then Coverage / 3-2-1 / Frequency / Restore-testing / Mechanism / Runbook. Flag "never restore-tested" and "backups in the same place as production" as critical — they mean recovery may silently be impossible. **Designing**: a plan that meets the user's stated RTO/RPO with concrete frequency, storage locations, retention schedule, and a restore-test cadence. Either way, the single most important action is usually: run a real restore test now, then fix whatever it reveals.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
