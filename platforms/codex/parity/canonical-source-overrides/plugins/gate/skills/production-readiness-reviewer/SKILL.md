---
name: production-readiness-reviewer
description: Score whether an app is actually ready for real users across 14 categories — product, architecture, design, frontend, backend, database, security, testing, performance, SEO, analytics, deployment, monitoring, documentation. Use when the user says production ready, launch readiness, "is it ready to ship", go-live checklist, or preflight. Produces per-category scores (each /10; N/A categories accepted by the applicability matrix leave the denominator, so normalized = round(total / (10 × applicable) × 100)) and a launch status — BLOCKED / SAFE WITH WARNINGS / SAFE TO LAUNCH — where any critical failure forces BLOCKED.
---

# Production Readiness Reviewer

**AgentRoom proposal mode:** raw/final evidence follows the evidence lifecycle,
while any tracked memory target listed under the trusted seat's `proposes` goes
to `.solo/proposals/<seat>-<run_id>.md` with its target and proposed entries.
Never edit that target; only the memory steward merges, and missing seat/run
identity stops the write. `$gate-production-ready` remains output-only after
the freeze.

Answers one question honestly: **is this safe to put in front of real users?**
It runs a fixed checklist, scores each section, and gives an overall verdict —
but a **critical failure overrides the average**. The 14 category records are
a necessary machine-checked floor, not proof of every subcontrol: secrets,
auth/RLS, error tracking, mobile/accessibility core flows, payments,
transactional email, backup/restore, and rollback require separate evidence
cited in the reviewer verdict. Missing or failed evidence for an applicable
control forces **BLOCKED** no matter how good everything else looks. Pull real
signals from `.solo/` and the specialist plugins (don't assume an item passes
just because it exists in the plan or because its parent category has a
record).

## The checklist

### Product
- PRD exists
- MVP scope is clear
- User stories have acceptance criteria
- Non-goals are listed

### Architecture
- Architecture documented (`.solo/architecture.md`) and matches what was built
- API/data/env contracts exist and the implementation honors them
- Key tradeoffs and their rationale recorded
- No unowned "magic" components (everything has a place in the diagram)

### Design
- Core user flows documented
- Mobile states designed
- Empty/loading/error states handled
- Component system exists

### Backend
- API validation exists
- Auth required where needed
- Authorization enforced server-side
- Database constraints exist
- Errors are handled safely

### Frontend
- Responsive layout works
- Forms have validation
- Loading/error/empty states exist
- No console errors
- Accessibility basics pass

### Database
- Schema matches the data contract; constraints live in the database
- Migrations are reviewed, forward-safe, and reversible
- No missing primary keys / unindexed foreign keys on hot paths (`$site-doctor-audit-db`)
- Backups exist AND a restore has been tested (ties to Deployment)

### Security
- No secrets committed
- Env vars separated by environment
- Supabase RLS enabled where needed
- Dependencies audited
- OWASP Top 10 reviewed

### Testing
- Unit tests for business logic
- Integration tests for API/database
- E2E tests for core flows
- Edge cases reviewed

### Performance
- Core Web Vitals measured or estimated against targets (LCP/INP/CLS) — `$site-doctor-perf`
- Images optimized and sized correctly
- Compression and caching headers on
- No obvious N+1 or unindexed hot queries

### SEO
- Pages indexable (no stray noindex; robots.txt sane) — `$site-doctor-seo`
- Titles and meta descriptions on key pages
- Sitemap exists and is reachable
- Canonical and social/OG tags on shareable pages

### Analytics
- Analytics firing once per page view (no double-count) — `$stack-audit-tags`
- Core funnel conversions tracked end-to-end — `$site-doctor-audit-analytics`
- Consent gating verified where required
- No PII in analytics parameters

### Deployment
> **Vendor checks are stack-conditional**: run a vendor's checks ONLY when that provider is recorded in `.solo/stack.md` (Vercel, Supabase, Cloudflare, Grafana, …). If `stack.md` is missing, run `$stack-intake` first. Every skipped vendor check is reported as **N/A** with the evidence ("stack.md records no Cloudflare"), never silently dropped and never scored as a pass.

- Hosting env vars checked (e.g. Vercel — only if in stack.md, via `$stack-audit-vercel`)
- Preview and production separated
- DNS/SSL checked (e.g. Cloudflare — only if in stack.md, via `$stack-audit-cloudflare`)
- Rollback plan exists
- Backup/restore plan exists (restore actually tested)

### Monitoring
- Error tracking exists
- Uptime check exists
- Logs are searchable
- Alerts are not too noisy

### Documentation
- README updated
- Setup guide works
- API docs exist
- Env vars documented

## Scoring
Score **fourteen categories**, each **0–10**, judged from the checklist evidence above (never from vibes — every score cites what was checked):

1. Product · 2. Architecture · 3. Design · 4. Frontend · 5. Backend · 6. Database · 7. Security · 8. Testing · 9. Performance · 10. SEO · 11. Analytics · 12. Deployment · 13. Monitoring · 14. Documentation

**Total = sum over the APPLICABLE categories. `applicable_max = applicable_category_count * 10`; `normalized_score = round(total / applicable_max * 100)`.** A category is applicable unless it has an ACCEPTED N/A record under the applicability matrix below — the seven mandatory categories (product, architecture, security, testing, deployment, monitoring, documentation) are ALWAYS applicable, so the denominator is never below 70. A serialized AgentRoom N/A item carries `score: 0` and is excluded from both total and denominator. `check_evidence.py` reports the applicable count and denominator; the score block must use the same numbers. Present it exactly like (here: an api-service with seo + analytics N/A, 12 applicable):

```
Production Readiness Score: 83/100  (100/120 across 12 applicable categories; N/A per matrix: seo, analytics)

Product: 9/10
Architecture: 8/10
Design: 9/10
Frontend: 8/10
Backend: 9/10
Database: 7/10
Security: 8/10
Testing: 9/10
Performance: 8/10
SEO: N/A (matrix: seo:api-service)
Analytics: N/A (matrix: analytics:api-service)
Deployment: 9/10
Monitoring: 7/10
Documentation: 9/10

Launch Status: SAFE WITH WARNINGS
```

## Launch status & hard blockers

**Launch is BLOCKED — regardless of score — if ANY of these is true:**
- SEO basics missing (indexable, titles/descriptions, sitemap/robots) — unless SEO holds an accepted N/A record per the applicability matrix
- analytics missing (no measurement of the core funnel) — unless analytics holds an accepted N/A record per the applicability matrix
- error tracking missing
- mobile broken (fails `$browser-mobile-test` at 320/375/768)
- serious accessibility issues (blocking WCAG failures on core flows)
- auth, Supabase RLS, payments, or transactional email **not verified** (claimed ≠ verified — each needs test evidence)
- plus the structural criticals: secrets committed · no auth where needed · RLS off where needed · no backup/rollback

### Machine boundary for hard blockers

`check_evidence.py` verifies the 14 category records, their exact captured
commands, artifacts, freshness, and checkout binding. Because one record runs
one command, **14/14 is necessary but not sufficient for launch** and must not
be presented as machine verification of every checklist item. The shared
`gate_policy.REVIEWER_REQUIRED_CONTROLS` list names the controls outside that
machine guarantee: committed-secret scanning, authentication, RLS/
authorization, error tracking, mobile and accessibility core flows, payments,
transactional email, backup/restore, and rollback.

For every applicable item, the launch verdict must cite a separate artifact
and the command or live test that generated it. Use real specialist evidence
where available (`$browser-mobile-test`, `$site-doctor-a11y`,
`$security-authz-matrix`, manual `$security-rls-test`,
`$stack-audit-payments`, `$site-doctor-email-check`,
`$site-doctor-backups`, `$release-rollback-plan`, and monitoring/security
evidence), while respecting each command's stated limits: an audit or written
plan is not proof of live behavior; email DNS is not delivery; a rollback plan
is not a rollback drill. If the applicable behavior has no executable evidence,
leave it **UNVERIFIED** and return **BLOCKED**. Human-explained subcontrol N/A
does not become a machine-accepted category N/A record.

Otherwise: **SAFE TO LAUNCH** when the normalized score ≥ 85 and no APPLICABLE category below 7; **SAFE WITH WARNINGS** when the normalized score ≥ 70, with every warning listed and explicitly accepted. Below 70 → **BLOCKED** with the ordered must-fix list to get out.

**The only launch statuses are `BLOCKED`, `SAFE WITH WARNINGS`, and `SAFE TO LAUNCH`.** GO/NO-GO wording belongs to the before-code/before-merge/before-deploy gates, never to this one.


## Machine-readable gate evidence

Every category verdict is backed by an evidence record so a later gate run (or a different reviewer) can audit it. Records live in `.solo/gate-evidence/<category>.json` and follow `schema/gate-evidence-v1.schema.json` (shipped with this skill — a strict `oneOf`: verified evidence OR not-applicable, both with `additionalProperties: false`).

**In the supported workflow, agents and tests NEVER write evidence records by hand: verified records use `scripts/record_evidence.py`, and N/A records use its canonical `record_evidence.py --not-applicable` operation.** The recorder executes a **policy-validated** category command itself. `plugins/gate/lib/gate_policy.py` is also the single runtime source for category order, profile N/A cells, mandatory categories, normalization, launch thresholds, and launch status: the direct checker and isolated AgentRoom validators import the digest-pinned same file. Its per-category FULL-ARGV policy rejects `git log`/`git ls-files` as evidence and rejects `--help`, `--version`, dry-runs, list-only modes, unrelated paths, and arbitrary suffixes. The recorder captures stdout/stderr and the real exit code, derives the commit and COMMITTED-tree digest from git objects itself, hashes the captured output, and writes both files atomically. This prevents accidental hand assertion in an honest run, and the checker re-validates `command_argv` against the same policy module.

**Trust model — self-attested local evidence.** These records are unsigned JSON. `record_evidence.py` is the canonical writer for the supported workflow, but its required `recorder` value is a copyable format label, not proof of process origin. The checker validates schema, policy, digests, freshness, and checkout binding; it cannot distinguish helper output from a manually constructed record that satisfies the same checks. Treat gate acceptance as "self-attested local evidence verified against the current checkout," not as proof that a particular process ran. A trusted CI identity/signature is the upgrade path. The recorder refuses to run on a dirty tree (any modified/deleted/untracked path outside the two generated runtime dirs — ONLY `.solo/gate-evidence/` and `.solo/run-state/` are excluded; there is no override) and refuses the unsupported state where runtime-state files are tracked in HEAD. Every evidence command runs without `shell=True` inside a new POSIX session/process group or a Windows kill-on-close Job Object; a Windows bootstrap releases the real command only after job assignment. A timeout terminates the complete container and readers must drain stdout/stderr to EOF. If a descendant, container member, or reader remains, the recorder refuses to write either artifact or record. This is process-lifecycle containment, not a filesystem/network sandbox; use an OS/container sandbox for hostile code.

```bash
python3 "<skill-root>/scripts/record_evidence.py" \
    --category testing --project "<repo name>" --environment production \
    --root . --reviewer "qa seat" --run-id "$RUN_ID" -- python3 -m pytest -q
```

Document-backed categories (product, architecture, design, documentation — deployment and monitoring are NOT document-backed; see below) use the bundled executable CATEGORY-SPECIFIC content check as their command — required headings per category, substantive-content floors (bytes, words, distinct vocabulary), placeholder/filler rejection (TBD/TODO/lorem ipsum/... fail), and required identifier/decision fields (acceptance-criteria/story bullets for product, a recorded ADR-n/DEC-n/'Decision:' for architecture, concrete breakpoints for design, a runnable example for documentation). It is always WRAPPED through `record_evidence.py`, never run standalone as finalization:

```bash
python3 "<skill-root>/scripts/record_evidence.py" \
    --category product --project "<repo>" --environment production \
    --root . --reviewer "evidence finalizer" --run-id "$RUN_ID" -- \
    python3 "<skill-root>/../../lib/gate_policy.py" \
    verify-artifact product --root .
```

**Deployment and monitoring never pass on document content alone.** A `release.md`/`monitoring.md` with enough bytes and headings is a plan, not a deployment or a monitor. **Deployment** evidence binds the DEPLOYED RESULT to FINAL_SHA: a GitHub Actions run bound to the CURRENT HEAD with a successful conclusion (`gh run view <id> --exit-status --json headSha,conclusion,status` — the recorder and checker both parse the captured JSON and require `headSha` == derived HEAD and `conclusion` == "success"; an arbitrary old run or release can never prove the current commit, and `gh release view` was removed for exactly that reason), or a bounded-timeout `curl -sSf -m <s>` of the **committed `version-endpoint:`** declared in `.solo/stack.md` at HEAD whose captured response must CONTAIN the derived HEAD (a generic 200 proves nothing about which commit is live). `gh run view` additionally requires `--gh-config-dir <external-directory>` pointing outside the repository at an existing GitHub CLI config containing a regular `hosts.yml`. The recorder exposes that reference only to `gh` as `GH_CONFIG_DIR`; it does not inherit `GH_TOKEN`/`GITHUB_TOKEN`, does not read/copy/hash/log config contents or tokens, and omits the local path from evidence (an opaque metadata id binds preview to confirmation). POSIX ownership/mode checks are enforced; Windows reparse points are rejected, but a current-user-only Windows ACL remains an operator responsibility. **Monitoring** evidence uses the **committed `health-endpoint:`** with a bounded timeout, and the captured response must be an explicit health contract — JSON `status`/`state`/`health` in the OK set, or the committed `health-expect:` marker; a generic homepage response is refused, and `gh run view` is no longer monitoring evidence (a green CI run is not a monitor). Both endpoint targets are still bound to hosts recorded in the COMMITTED `.solo/stack.md` at HEAD (live evidence targets the project's own stack — someone else's always-green site proves nothing). When nothing is executable, the category stays explicitly **UNVERIFIED** and the gate is **BLOCKED** — by design, never papered over with a document check.

Produced record (evidence branch of the schema):

```json
{
  "schema": "solo-suite/gate-evidence-v1",
  "status": "verified",
  "recorder": "record_evidence.py/v1",
  "project": "acme-site",
  "commit": "<git rev-parse HEAD, determined by the recorder>",
  "tree_digest": "<sha256 over the tracked tree, excluding only .solo/gate-evidence/** and .solo/run-state/**>",
  "environment": "production",
  "timestamp": "2026-07-10T14:03:00Z",
  "category": "testing",
  "command": "python3 -m pytest -q",
  "command_argv": ["python3", "-m", "pytest", "-q"],
  "command_id": "pytest",
  "resolved_executable": "/usr/bin/python3",
  "exit_code": 0,
  "duration_seconds": 41.2,
  "artifact": ".solo/gate-evidence/artifacts/testing.log",
  "artifact_sha256": "<sha256 of the captured output>",
  "reviewer": "qa seat",
  "expires": "2026-07-17T14:03:00Z"
}
```

**Evidence lifecycle — one supported workflow.** `.solo/gate-evidence/` stays **untracked/gitignored**; records are generated only AFTER the finalization commit, so writing them never changes the commit they describe. Committing evidence files is an unsupported state that both the recorder and the checker refuse. The lifecycle:

1. Specialists produce their raw artifacts (`.solo/*.md`, code, tests, plans, docs) as they work. They do **not** write final category records — a record minted against an intermediate commit is invalid by construction.
2. ALL tracked memory updates (tasks, decisions, risks, handoff) land first; then commit EVERYTHING — code, CI, release plans, documentation, project memory. That commit is **FINAL_SHA**, recorded with `scripts/update_run_state.py --root . --run-id <run_id> advance final` into the UNTRACKED `.solo/run-state/<run_id>.json` — the formal **run-state-v1** contract (`schema/run-state-v1.schema.json`; exact lowercase keys `schema`, `run_id`, `base_sha`, `integration_sha`, `final_sha`). The helper derives the SHA from `git rev-parse HEAD` itself, enforces monotonic transitions, freezes `final_sha` (never rewritten — a new freeze means a new run id), writes atomically, and validates against the schema. A commit cannot contain its own SHA, so tracked files are structurally impossible carriers.
3. The **Evidence Finalization Coordinator** verifies HEAD equals FINAL_SHA mechanically (`update_run_state.py … verify final` exits 0), returns the exact human handoff, and pauses. Only the user invokes manual-only `$gate-finalize-evidence`; after its preview and separate explicit confirmation, that command re-runs every applicable category command through `record_evidence.py` and writes all 14 records (verified, or matrix-permitted N/A via `record_evidence.py --not-applicable`) against FINAL_SHA. The coordinator only verifies the resulting set.
4. After FINAL_SHA nothing tracked may change — only untracked `.solo/gate-evidence/` and `.solo/run-state/` files may be created (gitignore both). The recorder and checker enforce this fail-closed (index vs HEAD including rename/copy sources AND destinations, working tree vs index, non-ignored untracked files; a git failure is never 'clean'), and the recorder re-checks HEAD and cleanliness AFTER each evidence command executes. The gatekeeper is OUTPUT-ONLY and the memory steward never runs after the finalizer.
5. `$gate-production-ready` verifies the full set with `check_evidence.py`, which derives HEAD itself and requires every record's `commit` to equal it EXACTLY.

**Category-record completeness rules (enforced, not advisory):** the checker passes only when **every one of the 14 categories has EXACTLY ONE accepted record** — either a verified evidence record or a machine-readable **N/A record**. Duplicate records for a category are rejected. This is category-record completeness, not machine verification of the reviewer-required subcontrols above; those remain a separate, fail-closed condition for the launch verdict. **No specialist phase ever writes a category record** — specialists produce raw artifacts and N/A candidates only, and the **user-invoked evidence-finalization command** mints all 14 records at FINAL_SHA via `$gate-finalize-evidence`; the coordinator never invokes it or authors a record. The specialist phases determine which raw artifact BACKS each category (product→PM, architecture→architect, design→designer, frontend→browser QA, backend→code review, database→DB engineer, security→security, testing→QA, performance/SEO/analytics→site doctor, deployment→release manager, monitoring→DevOps, documentation→docs), but a record minted against an intermediate commit is invalid by construction, so the records themselves come last, all at once.

**Verification rules:** every record is first validated STRICTLY against the bundled JSON Schema by a built-in evaluator (the `jsonschema` package is never required); verified records must then (a) carry `status: verified`, `recorder`, and `command_argv` (schema-required), (b) have `commit` EXACTLY equal to the HEAD the checker derives itself (`--commit` is optional and must match derived HEAD or the run is a usage error), (c) have `tree_digest` equal to the recomputed COMMITTED-tree digest at HEAD (from `git ls-tree`, excluding `.solo/gate-evidence/**`), (d) pass `command_argv` RE-VALIDATION against the shared category policy — including canonical executable identity: argv[0] is re-resolved through PATH/absolute-path rules and the recorded `resolved_executable` must equal it, with unresolvable or project-local executables rejected — plus the live-target binding and, for bound command ids (gh run view), the output binding re-checked from the hashed artifact, (e) match the **target environment** and **project**, (f) be **unexpired** (default max age 7 days), (g) report the **captured** `exit_code` 0, (h) name a **non-empty reviewer**, and (i) name an artifact **inside the project root** whose **recomputed SHA-256** equals `artifact_sha256`. The checker also fails the whole gate when the working tree is dirty outside the two generated runtime dirs (ONLY `.solo/gate-evidence/` and `.solo/run-state/` are excluded) or when runtime-state files are tracked in HEAD.

### Applicability matrix (normative)

An N/A record is accepted ONLY where this matrix permits it. **Product, Architecture, Security, Testing, Deployment, Monitoring, and Documentation are MANDATORY — never N/A, for any profile.** The normative matrix lives once in `plugins/gate/lib/gate_policy.py`; `check_evidence.py`, `validate_gate_evidence.py`, and AgentRoom room validation import it, while cross-path tests exercise all six profiles.

| Category      | N/A permitted for profiles                              |
| ------------- | ------------------------------------------------------- |
| product       | never (mandatory)                                       |
| architecture  | never (mandatory)                                       |
| design        | api-service, library-package                            |
| frontend      | api-service, library-package                            |
| backend       | public-marketing-site, library-package                  |
| database      | public-marketing-site, library-package                  |
| security      | never (mandatory)                                       |
| testing       | never (mandatory)                                       |
| performance   | library-package                                         |
| seo           | internal-application, api-service, library-package      |
| analytics     | internal-application, api-service, library-package      |
| deployment    | never (mandatory)                                       |
| monitoring    | never (mandatory)                                       |
| documentation | never (mandatory)                                       |

**The supported workflow creates N/A records only through the canonical `record_evidence.py --not-applicable` operation.** Before finalization, `.solo/project.md` must be a committed regular file containing exactly one standalone `Project profile: <recognized-slug>` line. The operation reads that blob from HEAD, requires the CLI `--profile` to match it, fixes `profile_source` to `.solo/project.md`, validates the matrix cell, rejects missing/malformed/ambiguous/symlink-backed or caller-selected sources and mandatory categories, and generates the timestamps. The checker independently repeats the committed-profile derivation; its `--profile` argument is a required cross-check, never the source of truth. The schema requires the `recorder` format label on the N/A branch, so omitting or changing it fails validation; copying that label into otherwise conforming JSON is still possible and is not proof of origin. Each record must carry the bound recognized `profile`, a substantive `reason` (>= 20 characters and >= 4 words — one character is a rejection), a non-empty `reviewer`, and a **structured `applicability` object** naming the matrix cell, the canonical profile source, and what was actually inspected:

```json
{"schema": "solo-suite/gate-evidence-v1", "status": "not-applicable",
 "recorder": "record_evidence.py/v1",
 "project": "acme-api", "commit": "<sha, derived by the canonical N/A operation>", "environment": "production",
 "timestamp": "2026-07-10T14:03:00Z", "category": "seo",
 "profile": "api-service",
 "reason": "API service exposes no public HTML pages; nothing to index",
 "applicability": {"matrix": "seo:api-service",
                   "profile_source": ".solo/project.md",
                   "checked": ["router exposes JSON endpoints only",
                                "no robots.txt/sitemap by design"]},
 "reviewer": "gatekeeper", "expires": "2026-07-17T14:03:00Z"}
```

Verify the full category-record set mechanically with the bundled checker (exit 0 = category-record complete and verified to each captured command's limits; it remains necessary but not sufficient for launch, and accepted N/A categories leave the scoring denominator):

```bash
python3 "<skill-root>/scripts/check_evidence.py" .solo/gate-evidence \
    --root . --environment production \
    --project "<repo/project name>" --profile saas-application
```

> If `python3` is not on PATH, use `python`. The checker exits 0 only when every record is fresh, complete, and matches the derived HEAD, committed-tree digest, and target environment.

## Working with other skills
Powers `$gate-production-ready` (the full gate) and `$gate-score-project` (checklist + scoring only, no launch verdict), and feeds `$release-preflight`. Delegates evidence-gathering to `security`, `test`, `browser`, `docs`, `release`, `site-doctor`, and the `$stack-audit-*` skills.

## Output
End every run with these seven sections:
1. **Summary** — what was checked or created.
2. **Findings / Work done** — what was found, changed, or decided.
3. **Risks** — anything uncertain, dangerous, incomplete, or blocked.
4. **Required fixes** — must-fix items before moving forward.
5. **Suggested tasks** — concrete entries for `.solo/tasks.md`, each with a stable T-ID.
6. **Verification** — how to prove the result works.
7. **Next skill** — the exact next skill invocation to run.

## Session lifecycle
Runs inside a session the solo plugin bookends: `$solo-start-session` restores `.solo/` context at the start and `$solo-end-session` saves it at the end. Read `.solo/` before acting; write findings, decisions, and tasks back (stable T-IDs) so the next skill — or the next agent — picks up cleanly.

## Stack awareness
Check `.solo/stack.md` first and tailor everything to the real stack. For vendor depth the `$stack-audit-*` skills go further: Cloudflare, Vercel, Supabase, analytics/tags, payments. If a sibling skill or connector isn't installed, do a lighter inline version and say so.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
