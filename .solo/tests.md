# Tests — Solo Suite Enchance (website)

## What's tested today (`npm test` = `tests/*.mjs`, 3 files)

- **`tests/rendered-html.test.mjs`** (the only file that exercises `app/`):
  1. Builds-then-server-renders the Worker's `/` route and asserts HTTP 200,
     `text/html`, exact `<title>` text, brand/CTA copy, and the presence of
     "Claude"/"Codex"/"Antigravity" — plus negative assertions that
     starter-template leftovers (`codex-preview`, `react-loading-skeleton`,
     "Your site is taking shape") are gone.
  2. A static source-string check on `page.tsx`/`layout.tsx`/`package.json`
     for the same starter-artifact regressions, plus confirms `public/og.png`
     exists and the old `SkeletonPreview.tsx` does not.
- **`tests/capability-inventory.test.mjs`** — validates `capability-inventory.json`
  counts and cross-platform file existence. Tests the *platform distributions*,
  not `app/`.
- **`tests/core-tooling.test.mjs`** — validates `core-tooling.json` policy
  (approved tools, rejected list). Tests the *agent tooling*, not `app/`.

## Coverage gaps (from the 2026-08-07 audit)

- **No unit/component tests** for `app/page.tsx`'s actual interactive behavior:
  menu toggle, module-tab switching, `scrollTo`, the `runStarted` CTA state.
- **No accessibility automated tests** (e.g. axe-core).
- **No e2e/browser tests** — no Playwright/Cypress config exists anywhere at
  the repository root.
- **No performance tests** — no Lighthouse/CWV capture exists; `/webperf`
  (an already-built command) has apparently never been run against the
  deployed site.
- **`npm test` requires a prior full build** (`vinext build`) — it was not run
  as part of the audit (out of scope for a read-only pass), so whether it
  currently passes end-to-end is `NOT_EXECUTED`, not confirmed green.
- **No automated tests for the root `scripts/*.py` audit/security tooling
  itself** — its correctness is exercised only by the scripts calling each
  other (e.g. `build-agent-audit.py --check` diffing against disk), not by
  independent test assertions.

## Recommended next test additions (see `tasks.md` T9)

1. Component/interaction tests for `app/page.tsx` (menu, tabs, CTA state).
2. A minimal a11y smoke test (axe or equivalent) against the rendered `/` route.
3. A `/webperf` run captured as a baseline, then re-run after `og.png` is
   compressed (T10) to confirm the fix.
