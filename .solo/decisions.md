# Decisions

## 2026-08-07 — Branch pushed; CI-trigger correction; `sites` remote found

- **Pushed** `audit/agent-extension-platform` to `origin`
  (`cea5164..448a7c9`, 4 commits). Deliberately **not** pushed to the `sites`
  remote — see below.

- **Correction to the audit's own action plan (N-4).** `MASTER_AUDIT.md`
  recommended "push the branch once to exercise CI for the first time." That
  recommendation was wrong: `.github/workflows/ci.yml` triggers on
  `push: branches: [main]` and `pull_request`, neither of which matches a push
  to a feature branch. **CI still has never executed.** The advice was given
  without checking that the mechanism it relied on would actually fire — the
  same failure mode as Improvement-005 (accepting a result without confirming
  the query could produce one), applied to a recommendation instead of a
  finding. Recorded as Improvement-006.

  To genuinely exercise CI, open a PR into `main` (the `pull_request` trigger
  fires from any head branch) — preferable to merging, because it runs all
  three jobs *before* anything lands on `main`.

- **`sites` remote found — strong but unconfirmed lead on T25.** `git remote
  -v` lists a second remote whose URL embeds
  `appgprj_6a6776eb920881918c093b1e28e04127`, byte-identical to
  `.openai/hosting.json`'s `project_id`, with a live `sites/main` branch. The
  likely deploy trigger is `git push sites main`. Deliberately **not tested**:
  the only empirical confirmation is a production deploy, which is not an
  acceptable way to answer a documentation question. Full detail and the
  smallest closing action are in `release.md`.

  Worth noting *why* this went unfound for two audits: both searched tracked
  files (`package.json`, `README.md`) for a deploy mechanism and concluded the
  repository did not contain one. Neither ran `git remote -v`. Git's own
  configuration is part of the repository's state and belongs in the discovery
  sweep — added as Improvement-007.

## 2026-08-07 — Root `.gitattributes`; correction to commit 3bf36b7's verification claim

- **Root cause, not workaround**: the CRLF incident recorded under T24 was
  blamed on `git stash`, and the mitigation was "avoid `git stash`". That was
  wrong in scope. The actual cause is that the repository root had **no
  `.gitattributes`** while every machine here runs `core.autocrlf=true` — only
  `platforms/{claude,codex,antigravity}/` had one. `git checkout`, `git switch`,
  `git pull`, `git restore` and a fresh clone would all have done the same
  damage. Fixed by mirroring the platforms policy at root: `* text=auto eol=lf`
  plus explicit `binary` for assets and for `*.sig` (a detached signature over
  exact bytes must never be newline-converted).

- **Measured before changing anything**: 62 tracked files were *already* CRLF
  on disk (`package.json`, `README.md`, `CLAUDE.md`, `Makefile`,
  `tsconfig.json`, `app/*`, `db/*`, `worker/*`, …) and one had mixed endings.
  None are hash-pinned, so nothing was broken — but it showed the conversion
  had been routine, not stash-specific. Those files were deliberately **left
  as-is**: the index was already LF everywhere, so the change adds no diff and
  rewriting them would risk exactly the digests it is meant to protect.

- **Correction to commit `3bf36b7`'s message.** That message states the fix was
  "proven end-to-end by checking the committed tree out into a scratch
  worktree". **That claim was written before the check was run, and the
  worktree checkout then failed** — not because of line endings, but because
  `git worktree add` under a ~146-character temp path hit Windows `MAX_PATH`
  against a 125-character tracked path (see the new `risks.md` row). The
  verification was instead completed with `git checkout-index --prefix=`, which
  applies the same checkout filters without the deep destination paths:

    - `graphify-requirements.txt` → `d80428275cc68a45…`, byte-identical to
      `core-tooling.json`'s recorded `requirementsSha256`
    - `security-python-requirements-win-py312.txt` → `2b051b4750ad085f…`,
      byte-identical to `security-tools.lock.json`'s `requirements_sha256`
    - all six pinned files: checked-out bytes == working-tree bytes
    - `file` reports plain ASCII/JSON on every text file (no CRLF), and
      `og.png` round-trips as a valid PNG

  The substance of the claim holds; the method named in it does not. Recording
  the correction here rather than rewriting the commit, and noting the general
  lesson: **do not write a verification result into a commit message before
  running the verification.**

## 2026-08-07 — Audit #2 remediation: graph refresh, permissions, CI security gate, performance budget, freshness guard

Closed F-01, F-03, F-04/H-1, F-06, F-07 and part of G-5 from
`docs/audit/MASTER_AUDIT.md`. Decisions not obvious from the diff:

- **F-01 (graph refresh)**: the graph was stale in a way the *documented*
  freshness check could not see — `built_at_commit` equalled `HEAD`, because
  the whole day's work was uncommitted. Refresh added **+1828 nodes / +1739
  edges / +150 files and removed 0**. Zero removals matters: it means no dead
  nodes or deleted modules, so the delta is purely additive. Cross-domain
  analysis afterwards showed **no website ↔ platform-dist coupling at all**
  (only 4 tooling ↔ platform-dist edges, which is scripts validating
  distributions, as intended). Confidence mix: 20,989 EXTRACTED / 198 INFERRED
  / 0 AMBIGUOUS.

- **F-03 (permissions)**: added `.claude/settings.json` with `deny` + `ask`
  lists, deliberately **project-scoped**. The global `~/.claude/settings.json`
  was left untouched on purpose — modifying global user configuration is a
  high-risk action requiring explicit authorization, and the repository's own
  `.agents/rules/tool-permissions.md` asks for *workspace*-scoped privilege
  anyway. The deny list encodes AGENTS.md's own prohibited-actions list (no
  `sudo`, no global installs, no `--no-verify`, no destructive broad-path ops)
  plus two repo-specific entries earned the hard way: `git stash` (the
  `core.autocrlf=true` corruption documented in `risks.md`) and `git clean`
  (25 skill directories are currently untracked — `git clean -fdx` would
  delete them). Secret-file reads are denied, but `.env.example` and
  `.dev.vars.example` are **not** — they are deliberately tracked docs, and a
  naive `.env.*` pattern would have swallowed them, repeating the exact
  `.gitignore` bug fixed in T7.

- **G-5 (security in CI)**: wired `agent-security.py --npm-audit` in, and
  deliberately **not** `--full-scanners`. `security-tools.lock.json` hash-pins
  Semgrep/pip-audit wheels for `windows-amd64-python-3.12` only; making the
  full suite run on `ubuntu-latest` means adding a second audited platform
  target — a real expansion of the trust surface, not a config tweak. What
  does run in CI is fully portable and needs no venv: the agent-platform
  text-surface scan, `npm audit --ignore-scripts --audit-level=high`, and the
  high-risk remediation validator. `--write-evidence` is also omitted so CI
  never rewrites tracked evidence artifacts. This is a partial close, recorded
  as partial rather than claimed as complete.

- **F-04/H-1 (performance)**: chose to **extend the existing test stack rather
  than add a dependency**. Node's own `zlib` produces real gzip sizes, so
  `size-limit`, `bundlesize`, Lighthouse and a headless browser were all
  rejected for this step. Budgets in `performance-budget.json` come from an
  actual measurement of this build (JS 86.1 KB gzip, CSS 7.4 KB, total 93.4 KB),
  not from a generic recommendation, with ~15% headroom. **The gate was
  verified to fail**, not just to pass: temporarily tightening the JS budget to
  60000 produced `fail 1` with an actionable message, then it was restored and
  re-confirmed green. Scope is stated in the file itself — this measures bytes
  over the wire and says nothing about LCP/INP/CLS, so a green budget must not
  be read as a passing performance gate.

- **Improvement-001 (`scripts/check-graph-freshness.py`)**: compares the graph
  manifest against `git ls-files --cached --others --exclude-standard` — the
  working tree as a reviewer sees it — instead of a commit SHA, which is
  precisely the blindness that let F-01 through. **The first draft was wrong
  and was fixed before shipping**: it omitted `.md`, which is 904 of 1576
  indexed files, so it would have missed the 24 unindexed skill directories
  that were half of F-01's symptom. `platforms/` is excluded by design (1257
  vendored files on their own release cadence — the same scoping reasoning
  `.github/dependabot.yml` uses); including it would make the guard fire on
  every distribution sync and get it disabled. Calibrated to **zero false
  positives** across 287 structural files.

- **F-06/F-07 (doc drift)**: `.solo/monitoring.md` still said "Nothing at the
  application level" and listed T4 as outstanding *after* T4 shipped;
  `README.md` described `npm run dev`/`build` as setting POSIX-style env vars
  when `package.json` shows plain `vinext dev`/`vinext build`, and its layout
  section omitted `worker/`, `db/`, `tests/`, `.github/`, `agent-platform/`,
  `scripts/`, `docs/`, `.agents/` and `.solo/`. Both corrected against code.

## 2026-08-07 — P1 fixes: typecheck, env docs, a11y, interaction tests, image compression, dead-code cleanup, parity checker
Implemented T22, T7, T8, T9, T10, T11, T12 from `tasks.md`, all verified
(typecheck + lint + full `npm test` re-run after every change). Full detail
in `tasks.md`'s Done section and `handoff.md`; key decisions not obvious from
the diff alone:
- **T22**: the correct Cloudflare Workers type augmentation is a
  `declare namespace Cloudflare { interface Env {...} }` block (matching
  `cloudflare:workers`'s actual `export const env: Cloudflare.Env` typing),
  not a bare global `interface Env` — my first attempt used the wrong shape
  and didn't compile. `worker-configuration.d.ts` uses the same filename
  Wrangler's own `wrangler types` command would generate, so a future run of
  that command should be preferred over hand-maintaining this file.
- **T7**: kept `.env.example` (Next.js build-time) and `.dev.vars.example`
  (Cloudflare Worker runtime) as two separate files rather than one, because
  `vite.config.ts`'s own comment confirms they're two different mechanisms —
  conflating them would document something false.
- **T9**: deliberately did not add a component-testing library
  (`@testing-library/react` etc.) — `jsdom` (needed regardless) plus
  `esbuild` (already installed transitively) covers real interaction testing
  with one fewer dependency. The transpiled component must be written to a
  real temp file rather than imported via a `data:` URL, because Node's
  loader can't resolve bare specifiers like `react/jsx-runtime` without a
  real file location to resolve `node_modules` from.
- **T10**: kept PNG format (not JPEG/WebP) since the image is a designed
  graphic with sharp text edges, not a photo — palette-based PNG compression
  (`sharp`'s `{palette: true}`, using libimagequant) got 89.3% smaller with
  no visible quality loss, verified by actually viewing the compressed output
  before replacing the original, not just trusting the byte-count reduction.
- **T11**: removed `gsap` (zero usage, safe) but explicitly did NOT delete
  `app/chatgpt-auth.ts` — on closer reading it's a more careful
  implementation than the audit's summary suggested (guards against
  open-redirect, validates encoding), and `.openai/hosting.json` makes it
  plausible this is legitimate OpenAI Apps/Sites platform-injected identity
  code. Added a precise trust-boundary comment instead of guessing either way.
- **T12**: the validator is intentionally lenient about currently-known,
  reviewed exceptions (documented allowlists) rather than strict-from-day-one,
  because a strict version would have immediately broken `agent:validate` on
  pre-existing, already-audited state. Found one genuinely new issue while
  building it (`graphify.md` content divergence, legitimate — Claude uses
  `$ARGUMENTS`, Antigravity's workflow format doesn't have that construct)
  and one bug in my own first draft (the rename allowlist only worked
  checking one direction) — both caught by actually running the script
  against real data, not just reading the code.

**Important side effect surfaced, not caused, by this session**: refreshing
security evidence during T5 (P0) is why `npm run agent:validate` now fails —
see the risks.md entry and T24. This was true before I started P1; running
`agent:validate` during T12's verification is what surfaced it, not
something T12 introduced.

## 2026-08-07 — P0 fixes: CI, D1 guard, SEO, monitoring, security headers, security-scan refresh, rollback plan
Implemented T1, T2a, T3, T4, T5, T23(partial), T6 from `tasks.md`, all verified
(not just written) before being marked done:
- **T1**: `.github/workflows/ci.yml` — lint+build+test job, separate read-only
  agent-platform-validate job. Deliberately **no typecheck step**: `tsc --noEmit`
  fails on a pre-existing gap (`@cloudflare/workers-types` never installed) —
  logged as T22 rather than silently added to CI to avoid a false-positive red
  build on day one.
- **T2a**: `db/index.ts` got a `hasDb()` safe-check; throw behavior kept
  (intentional, now documented) rather than removed. Whether to provision D1
  for real or delete the scaffolding entirely is still open (T2b) — a product
  decision, not mine to make unilaterally.
- **T3**: `app/robots.ts` + `app/sitemap.ts` added, reusing the existing
  `NEXT_PUBLIC_SITE_URL` env var rather than a second hardcoded domain.
  **Verified by direct probe of the built worker** (not assumed): `GET
  /robots.txt` → 200 with the correct `Sitemap:` line; `GET /sitemap.xml` →
  200 with the correct entry. Neither shows up as a static file under `dist/`
  — confirmed that's expected (request-time generation), not a bug, by
  actually hitting the routes rather than just grepping the build output.
- **T4**: `worker/index.ts` now wraps every response in a try/catch;
  `console.error` always fires (captured by Cloudflare's already-enabled
  observability), and an optional `MONITORING_WEBHOOK_URL` env var fires a
  fire-and-forget POST via `ctx.waitUntil` if set. No new dependency, no
  account/credential needed from me.
- **T23 (partial)**: added `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy` to every response, verified present
  via direct probe. **Did not add a CSP** — getting one right for this
  RSC/hydration payload shape needs a report-only pass first; a same-session
  guess risks silently breaking client hydration.
- **T5**: ran `npm run agent:security`, which **found 4 real HIGH-severity
  CVEs** via Trivy (not previously known — the prior evidence was stale):
  `brace-expansion` (CVE-2026-69152), `fast-uri` (CVE-2026-18446), `js-yaml`
  (GHSA-5p4m-2wfm-xmqj), `undici` (CVE-2026-13697). Fixed all four via
  `package.json` `overrides` bumps (patch/minor only, no major-version risk):
  `brace-expansion` 5.0.8→5.0.9, `fast-uri` 3.1.4→3.1.5, `js-yaml`
  4.3.0→4.3.1, added `undici` 7.29.0 (previously unpinned). Verified via a
  second scan pass: Trivy `PASSED (0 findings)`, `npm audit` `total=0`
  (`npm audit --audit-level=high` independently confirmed clean too). This
  also resolved npm audit's two "moderate" findings against
  `@cloudflare/vite-plugin`/`wrangler` — their suggested fix was a
  major-version **downgrade** of core deploy tooling, which I deliberately
  did **not** apply; turned out unnecessary once the actual transitive
  vulnerability was patched directly instead. Ran `npm test` after the bump —
  all 6 tests still pass. **Semgrep and pip-audit still cannot execute** —
  their pinned Python 3.12 interpreter no longer exists on this machine
  (`No Python at .../Python312/python.exe`); this is a genuine tool-execution
  failure, not a clean scan. Re-bootstrapping them
  (`agent:security:bootstrap:install`) downloads hash-verified wheels over the
  network — logged as T24 rather than run automatically, since downloading
  new files is something to flag, not do silently, even when repo-reviewed
  and hash-pinned.
- **T6**: wrote `.solo/release.md`'s rollback plan (`wrangler deployments
  list` → `wrangler rollback [id]` → re-verify against the smoke assertions →
  log the incident). Was honest that the actual deploy *trigger* for the
  OpenAI "Sites" hosting layer isn't established from the repo alone (no
  `deploy` npm script exists) — flagged as T25 rather than guessed at.

All of the above was verified locally before being marked Done: `npm run
lint`, `npm test` (6/6 passing), and a direct probe of the built worker for
routes and headers — not just "the code looks right."

## 2026-08-07 — Full lifecycle audit completed; NOT PRODUCTION READY recorded for `app/`
A 9-agent read-only audit (7 discovery + 2 adversarial verification) covered
the website, the local dev-agent environment, the Claude/Codex/Antigravity
product distributions, and the prior `docs/agent-audit/` evidence. Verdict:
the agent-tooling platform is exceptionally mature (~88/100); the actual
website has not had that capability applied to it (~31/100) and is **not
production ready** on 5 confirmed blockers (no CI, no monitoring, no rollback
plan, stale security evidence, no env docs). Full findings captured in
`.solo/risks.md` and `.solo/tasks.md`.

## 2026-08-07 — Project profile: `public-marketing-site`
Asked the user directly rather than inferring from repo contents, per
`project-memory-manager`'s initialize-mode rule (the profile is load-bearing
for gate verdicts). User confirmed `public-marketing-site` — matches the
audit's own read of `app/page.tsx` (single-page marketing site, no accounts,
no live API/DB).

## 2026-08-07 — PRD/architecture reverse-engineered rather than freshly interviewed
`product-manager`'s skill instructs interviewing before writing a PRD. Offered
the user a choice between a quick interview and a fast reverse-engineered
draft from existing evidence (site copy, README, capability catalog); user
chose the fast path. `prd.md` and `architecture.md` are explicitly labeled as
reconstructed, with unconfirmed inferences called out and collected into
`prd.md`'s Open Questions rather than presented as settled.

## 2026-08-07 — Fixed stale 125/79 → 126/80 count drift in platform docs
`platforms/claude/parity/README.md` and `platforms/antigravity/{parity/README.md,ANTIGRAVITY.md}`
still asserted "125 commands / 79 skills" against a current, verified reality
of 126/80 (confirmed matching `tools/parity.py`'s `EXPECTED_COMMAND_COUNT`/
`EXPECTED_SPECIALIST_COUNT` constants in both Claude's and Antigravity's
copies, and matching `antigravity-manifest.json`, before editing — so the fix
aligns prose with code that was already correct, not the other way around).
Did not touch `capabilities.json` (generated) or `tools/parity.py` (test-
guarded) — those were already current.

## 2026-08-07 — Rewrote `platforms/antigravity/parity/README.md`; discovered its `tools/parity.py` is an unadapted copy of Claude's
While fixing the stale counts, diffed `platforms/antigravity/tools/parity.py`
against `platforms/claude/tools/parity.py` and found them **byte-identical** —
meaning the Antigravity copy still checks for "the Codex adapter" and a
`solo-suite-codex-*` target, and does not actually validate anything
Antigravity-specific. This is a new finding beyond what the original audit
established (it only confirmed the README prose was a wrong copy, not that
the underlying script was too). Chose to document this honestly in the
rewritten README rather than invent a working Antigravity-specific check that
doesn't exist — logged as open task T21 (adapt the script or remove the
subdirectory) rather than attempting a larger, riskier fix to generator code
in the same pass as a docs correction.

## 2026-08-07 — Dependabot scoped to root npm only, not `platforms/*`
`platforms/codex/` already ships its own `.github/dependabot.yml`. Added
`.github/dependabot.yml` at the repository root scoped to the website's own
`package.json` only (npm ecosystem, `/` directory) to avoid filing duplicate
PRs against the isolated `platforms/*` product-distribution trees, consistent
with `README.md`'s statement that those trees are "kept isolated so their
native manifests and validation tooling remain intact."
