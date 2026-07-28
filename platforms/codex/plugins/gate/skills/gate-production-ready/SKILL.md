---
name: gate-production-ready
description: "Score launch readiness across 14 categories (each /10; matrix-accepted N/A categories leave the denominator — normalized = round(total / (10 × applicable) × 100)) and give a launch status — BLOCKED / SAFE WITH WARNINGS / SAFE TO LAUNCH — with hard blockers that force BLOCKED regardless of score. Use when the user explicitly invokes $gate-production-ready or asks for this gate production-ready workflow."
---

# Gate Production Ready

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $production-readiness-reviewer. Apply it to the user's supplied arguments and surrounding request.

Run the full 14-section checklist — **Product, Architecture, Design, Frontend, Backend, Database, Security, Testing, Performance, SEO, Analytics, Deployment, Monitoring, Documentation** — as evidence, then score each APPLICABLE category **0–10** and report the normalized score `round(total / (10 × applicable) × 100)`, in the skill's exact format. A category is applicable unless it holds an ACCEPTED N/A record under the skill's applicability matrix; **product, architecture, security, testing, deployment, monitoring, and documentation are mandatory and can never be N/A**, so the denominator never drops below 70.

**Vendor-specific checks (Vercel, Supabase, Cloudflare, Grafana, …) run ONLY when that provider is recorded in `.solo/stack.md`** — every skipped vendor check is reported as N/A with its evidence, never scored as a pass.

**Category evidence is machine-checked and must be COMPLETE**: the supported workflow creates all records at FINAL_SHA through `$gate-finalize-evidence` (never earlier — specialists produce raw artifacts only). Every one of the 14 categories needs exactly one accepted `.solo/gate-evidence/<category>.json` record — a **self-attested local evidence** record created through `record_evidence.py` (which executes one policy-validated command and captures the exit code and git-derived HEAD + committed-tree digest) or a machine-readable N/A record (recognized `profile` matching the single canonical `Project profile: <recognized-slug>` line in committed `.solo/project.md`, matrix-permitted category, substantive `reason` >= 20 chars / >= 4 words, non-empty reviewer, structured `applicability` evidence with canonical `profile_source`). `--profile` is required as a cross-check and is never the source of truth. The checker recomputes every artifact digest, rejects missing/outside-project artifacts, duplicate categories, wrong project, missing/malformed/ambiguous profile sources, CLI/profile mismatch, mandatory-category N/A, matrix-violating N/A, and stale records (wrong commit, wrong environment, expired). It validates content but cannot prove which process authored unsigned JSON: the `recorder` field is a copyable label, not a cryptographic origin attestation. Exit 0 is **necessary but not sufficient** for launch, because one category record proves only its captured command; it does not prove every independent control in that category. A nonzero exit always blocks:

```bash
python3 "<skill-root>/../production-readiness-reviewer/scripts/check_evidence.py" .solo/gate-evidence \
    --root . --environment production \
    --project "<repo name>" --profile <project profile>
```

**Reviewer-required controls — separate evidence, fail closed:** a 14/14 checker result does not machine-verify error tracking, mobile core flows, accessibility core flows, authentication, RLS/authorization, payments, transactional email, committed-secret scanning, backup/restore, or rollback. For every applicable control, cite the exact separate artifact and command/live test that produced it. Written plans, category scores, DNS-only email checks, and the existence of a category record are not substitutes for execution evidence. If a control is applicable and that separate evidence is absent, stale, failed, or only claimed, **Launch Status is BLOCKED**. Controls that genuinely do not apply must be explained in the N/A checks; there is no extra machine N/A schema for these subcontrols, so do not describe them as checker-verified.

**Launch is also BLOCKED regardless of score if ANY is true:** SEO basics missing (when SEO is applicable per the matrix) · analytics missing (when analytics is applicable per the matrix) · any applicable reviewer-required control above failed or lacks separate evidence.

You run AFTER the release freeze and are OUTPUT-ONLY: verify `git rev-parse HEAD` equals the FINAL_SHA carried in untracked `.solo/run-state/<run_id>.json` (run-state-v1 — verify mechanically with the gate plugin's `update_run_state.py --root . --run-id <run_id> verify final`) before judging, and write NOTHING tracked. Finish with **Launch Status: BLOCKED / SAFE WITH WARNINGS / SAFE TO LAUNCH** and the ordered must-fix list (in output). (GO/NO-GO wording belongs to `$gate-before-code|before-merge|before-deploy`, not to this gate.)

## Output
End with exactly:
- **Launch Status** — BLOCKED / SAFE WITH WARNINGS / SAFE TO LAUNCH (one hard blocker = BLOCKED; never averaged away)
- **Score block** — every applicable category 0–10, total /(10 × applicable), normalized /100, plus the N/A list, in the skill's exact format
- **Blockers** — each failed check, with its evidence record and the command that clears it
- **Passed checks** — with the evidence record for each
- **N/A checks** — every skipped vendor/profile check with its evidence-backed reason
- **Warnings** — accepted risks (required for SAFE WITH WARNINGS)
- **Suggested tasks** — listed in OUTPUT ONLY (post-freeze this gate writes nothing tracked; `.solo/tasks.md`, `.solo/risks.md`, and handoff memory were finalized BEFORE the freeze commit — a BLOCKED verdict reopens them in the NEXT cycle)
- **Next skill** — what clears the top blocker (next cycle), or nothing on SAFE TO LAUNCH: the run is complete; handoff memory already landed pre-freeze

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
