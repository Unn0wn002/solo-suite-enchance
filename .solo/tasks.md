# Tasks

Seeded 2026-08-07 from the audit's priority action plan; updated same day
after the P0 pass, then again after the P1 pass. T-IDs are stable; reference
them from `decisions.md`/`handoff.md`.

## Doing

*(none right now)*

## Todo

### P0 — remaining
- [ ] T2b: Decide whether to provision D1 for a real feature or remove the scaffolding entirely (guard is in place; the underlying product decision is still open — see `prd.md` Open Question #5)  (feature: database)
- [ ] T23: Add a Content-Security-Policy — needs a report-only pass against the real RSC/hydration payload before enforcing, not a same-session guess (baseline headers are done, see Done)  (feature: security)
- [ ] T25: Deploy-trigger for the "Sites" hosting layer — **strong lead found 2026-08-07**: a `sites` git remote exists whose URL embeds `.openai/hosting.json`'s exact `project_id`, with a live `sites/main`, so `git push sites main` is the likely trigger. Still **unconfirmed** — the only empirical test is a production deploy. Confirm with whoever owns the OpenAI Sites project (trigger? which branch does prod track? Sites-layer rollback path?) and replace `.solo/release.md`'s "Deploy mechanism" section with the answer.  (feature: release)

### P1 — remaining
- [ ] T2b, T23-CSP (see above, carried from P0 remainder)

### P2 — recommended
- [x] T13–T17 (see Done)

### P3 — optional
- [ ] T18: Add dark-mode support (the design-token structure already supports it)  (feature: design)
- [ ] T19: Add CodeQL/Dependabot to the Claude and Antigravity product distributions' own CI, matching what Codex's distribution already has  (feature: security)
- [ ] T20: Reconcile the three different Graphify version numbers appearing across the prior audit's own artifacts (0.9.27 / 0.9.29 / 0.9.32)  (feature: tooling)

## Blocked

- [ ] Refresh the persisted Graphify graph after AI-work command/document changes. The audited bootstrap requires an explicit project-local `--install` opt-in when Graphify 0.9.32 is not already available, so unattended repair runs must not fabricate or hand-edit graph evidence.

## Done

### AI-work repair-cycle reconciliation (2026-08-25)

- [x] T27: Root CI has executed repeatedly on pull requests. Current repair-cycle evidence includes successful website typecheck/lint/build/tests, dependency/remediation security, generated-skill and structural/parity validation, and Claude/Codex/Antigravity distribution jobs; the old "CI has still never executed" state was stale.
- [x] T21: The vestigial `platforms/antigravity/parity/tools/parity.py` path no longer exists. Cross-distribution parity is now enforced by the maintained repository-level platform validator instead of that obsolete subdirectory.
- [x] T26: Re-verified through the full Windows Claude/Codex/Antigravity distribution validation suite. The current parity contract uses `EXPECTED_TARGET_SKILL_COUNT = 186` and passes; the older audit note claiming 185 and predicting a failing parity test is stale.

### Audit #2 remediation (2026-08-07)

Findings from `docs/audit/MASTER_AUDIT.md`. Full rationale in `decisions.md`.

- [x] **F-01**: Refreshed the stale Graphify graph. It had been stale in a way
      the documented `built_at_commit` vs `HEAD` check could not detect (both
      were `cea51645`; the day's work was uncommitted). Delta: **+1828 nodes,
      +1739 edges, +150 files, 0 removed**. All seven previously-absent
      structural files (`ci.yml`, `robots.ts`, `sitemap.ts`,
      `worker-configuration.d.ts`, `page-interactions.test.mjs`, …) now
      indexed. Verified afterwards: **zero website ↔ platform-dist coupling**,
      20,989 EXTRACTED / 198 INFERRED / 0 AMBIGUOUS edges.
- [x] **F-03**: Added `.claude/settings.json` — project-scoped `deny`/`ask`
      permission boundaries encoding AGENTS.md's own prohibited-actions list,
      plus `git stash` and `git clean` (both are documented data-loss risks in
      *this* repo specifically). Global user config deliberately untouched.
- [x] **F-04 / H-1**: Added real performance measurement — the repository's
      weakest area (scored 25/100) had no instrument at all. `performance-budget.json`
      + `tests/bundle-budget.test.mjs`, zero new dependencies (Node `zlib`).
      Measured baseline: **JS 86.1 KB gzip, CSS 7.4 KB, total 93.4 KB**. Gate
      verified to *fail* on a simulated regression, then restored.
- [x] **Improvement-001**: Added `scripts/check-graph-freshness.py`, wired into
      `agent:validate`, the `Makefile`, and CI. Compares the graph manifest
      against the working tree (tracked + untracked), not a commit SHA. First
      draft omitted `.md` and would have missed half of F-01's symptom — caught
      and fixed before shipping. Zero false positives across 287 files.
- [x] **F-06 / F-07**: Fixed verified documentation drift — `.solo/monitoring.md`
      claimed no application monitoring existed after T4 had shipped it;
      `README.md` misdescribed the npm scripts and omitted ~9 top-level
      directories from its layout section.
- [x] **G-5 (partial)**: Added a portable dependency + remediation security gate
      to CI (`agent-security.py --npm-audit`). Deliberately **not** the full
      6-scanner suite — those wheels are hash-pinned to
      `windows-amd64-python-3.12` and running them on `ubuntu-latest` requires
      expanding the audited trust surface to a second platform. Recorded as
      partial, not claimed as closed.

### P0 (2026-08-07)
- [x] T1: Root CI workflow (`.github/workflows/ci.yml`) — typecheck + lint + build + test job, plus a read-only agent-platform-validate job.
- [x] T2a: Guarded `db/index.ts` with a `hasDb()` safe-check + clarifying docs (throw behavior kept, now documented as intentional). Full removal-vs-provision decision remains T2b.
- [x] T3: Added `app/robots.ts` + `app/sitemap.ts`. **Verified working** by probing the built worker directly.
- [x] T4: Wired dependency-free error observability into `worker/index.ts` (`console.error` + optional `MONITORING_WEBHOOK_URL` webhook).
- [x] T5: Refreshed security-scan evidence and **fixed 4 real HIGH-severity CVEs** (brace-expansion, fast-uri, js-yaml, undici). Verified via a second scan pass and `npm test`. Semgrep/pip-audit still can't execute — see T24 above (escalated in severity during P1).
- [x] T23 (partial): Added baseline security headers (nosniff/frame-options/referrer-policy/permissions-policy). CSP intentionally deferred.
- [x] T6: Wrote the rollback plan into `.solo/release.md`.

### T24 (2026-08-07, done after user said "do T24")
- [x] T24: Re-bootstrapped Semgrep + pip-audit. Real root cause was deeper than a simple re-download: `security-tools.lock.json` hash-pins wheels specifically for `windows-amd64-python-3.12`, and this machine's Python 3.12 had been **fully uninstalled and replaced** by 3.13 (not just moved) — the bootstrap script correctly refused to install against an unverified target. Asked the user how to proceed (install Python 3.12 alongside 3.13, vs. regenerate the lock for 3.13 — a bigger, riskier trust-surface expansion); user chose installing Python 3.12. Installed **Python 3.12.10** (the last version with an official Windows installer — 3.12 has been security-patch-only, source-release-only since then; stated file/source/size before running: `python-3.12.10-amd64.exe`, `https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe`, 25.7 MB) per-user, without modifying PATH (default `python` still resolves to 3.13; `py -3.12` reaches the new one). All 4 scanners then passed. Re-ran the full scan and found a **real, live CVE** in the scanner venv's own `cryptography` 49.0.0 (PYSEC-2026-3552 / CVE-2026-69247) — fixed by bumping to 50.0.0, with the wheel hash computed locally via `pip download` (not trusted from a claim) before pinning it. `npm run agent:security` now passes 6/6 with 0 findings everywhere, matching gitleaks/trivy which were already clean.
- [x] **Self-inflicted issue found and fixed in the same pass**: while diagnosing an unrelated stale-report question, ran a diagnostic `git stash`/`git stash pop` — this repo has `core.autocrlf=true`, and the stash round-trip silently flipped several already-hash-pinned files (`AGENTS.md`, `core-tooling.json`, `agent-platform/tooling/graphify-requirements.txt`, `agent-platform/tooling/security-python-requirements-win-py312.txt`, and the just-regenerated `TOKEN_AND_CONTEXT_REPORT.md`) from LF to CRLF, breaking their recorded SHA-256 checks and causing three NEW `agent:validate` failures that had nothing to do with T24 itself. Diagnosed via `sha256sum` + `file` on each flagged path, confirmed each file's *content* was unchanged (only line-ending representation), converted each back to LF, and reverified every hash matched its recorded value before moving on. Documented here in full rather than glossed over, since it's exactly the kind of silent, tool-induced drift this repo's own hash-pinning exists to catch — and it did.
- [x] `npm run agent:validate` now passes **fully** (all 7 steps, exit 0) — confirmed via a clean end-to-end run, not partial output.

### P1 (2026-08-07)
- [x] T22: Added `@cloudflare/workers-types` + a shared `worker-configuration.d.ts` (matching Wrangler's own `wrangler types` convention — `declare namespace Cloudflare { interface Env {...} }` + `type Env = Cloudflare.Env`). `tsc --noEmit` now genuinely passes (was never working before, confirmed pre-existing). Re-added the typecheck step to CI. Two real bugs found and fixed along the way: (1) `cloudflare:workers`'s `env` export types against `Cloudflare.Env`, not the bare global `Env` — the first attempt using only a global `interface Env` didn't compile; (2) ESLint's `@typescript-eslint/triple-slash-reference` disallows `path`-style references — switched to relying on tsconfig's `**/*.ts` auto-include instead, and used `type Env = ...` instead of an empty `extends {}` interface to satisfy `@typescript-eslint/no-empty-object-type`.
- [x] T7: Added `.env.example` (Next.js build-time vars) and `.dev.vars.example` (Cloudflare Worker runtime vars) — these are two different mechanisms (confirmed via `vite.config.ts`'s own comment), documented as such rather than conflated into one file. Fixed `.gitignore`'s `.env*` pattern, which would have swallowed `.env.example` itself.
- [x] T8: Added `prefers-reduced-motion` handling, `:focus-visible` styles, and a skip-to-content link (`app/globals.css` + `app/page.tsx`).
- [x] T9: Added `tests/page-interactions.test.mjs` — real interaction tests (menu toggle, nav-link-closes-menu, tab switching, CTA state) using jsdom + esbuild-transpiled-on-the-fly `.tsx` (no new test-library dependency beyond `jsdom`). Two non-obvious bugs fixed to get this working: Node 21+'s built-in read-only `navigator` global needed `Object.defineProperty` instead of plain assignment; `import()` of a transpiled `data:` URL can't resolve bare specifiers like `react/jsx-runtime` (no file location to walk up from) — switched to writing the transpiled output to a real gitignored temp file. Wired into `npm test`. Verified stable across 3 repeated runs.
- [x] T10: Compressed `public/og.png` 2.24MB → 246KB (89.3% reduction) via `sharp` (already installed), and fixed the resized dimensions (1200×675) that had drifted from the stale 1536×1024 declared in `app/layout.tsx`. Visually verified quality held up (crisp text, no visible artifacts) before replacing the original. `next/image` adoption doesn't apply — `page.tsx` has zero in-page `<img>` elements to convert (confirmed, not assumed).
- [x] T11: Removed the unused `gsap` dependency (zero imports anywhere, verified via search and a clean `npm install`/build afterward). Did **not** delete `app/chatgpt-auth.ts` — added a detailed trust-boundary comment instead, since `.openai/hosting.json` suggests this is plausibly legitimate OpenAI Apps/Sites platform-injected identity, not random dead code; its safety depends on a deployment-topology fact not established from the repo alone.
- [x] T12: Added `scripts/validate-workflow-command-parity.py`, wired into `agent:validate`, the `Makefile`, and CI. Found **two new, previously-undetected issues** while building it: (1) a real content divergence in `graphify.md` between Claude and Antigravity (legitimate — Claude's uses `$ARGUMENTS`, a Claude-specific templating construct; documented as an explicit exception, not silently allowed); (2) the `ALLOWED_RENAMES` allowlist only worked in one direction in my own first draft (caught and fixed before considering this done). Validator passes cleanly against current state (8 matched pairs, 3 documented exceptions).
