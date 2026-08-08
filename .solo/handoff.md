# Handoff — 2026-08-07 (T24 + line-ending cleanup)

## Done this session (continuing from the earlier P0/P1 passes today)

User said "do T24." What looked like a simple re-download turned into a
deeper fix, done in full with the user's explicit sign-off at each real
decision point:

1. **Root cause diagnosis**: `security-tools.lock.json` hash-pins Semgrep/
   pip-audit wheels for `windows-amd64-python-3.12`. This machine's Python
   3.12 had been fully uninstalled (upgraded to 3.13, not just moved) — the
   bootstrap script correctly refused to install against an unverified
   target rather than silently using different wheels.
2. **Asked the user** to choose between installing Python 3.12 (reuses
   existing reviewed hashes, zero change to the security artifact) or
   regenerating the lock for 3.13 (expands trust surface, redoes part of the
   original audit). User chose installing Python 3.12.
3. **Installed Python 3.12.10** (`python-3.12.10-amd64.exe`, official
   python.org, 25.7 MB, stated before running) — per-user, PATH untouched, so
   the working `python`→3.13 default for everything else in this repo is
   unaffected. `py -3.12` reaches the new one.
4. **All 4 scanners passed** once bootstrapped. Re-ran the full scan and it
   found a **real, live CVE**: `cryptography` 49.0.0 in the scanner venv
   itself (PYSEC-2026-3552 / CVE-2026-69247). Fixed by bumping to 50.0.0,
   with the wheel hash computed locally (`pip download` + `sha256sum`, not
   trusted from a claim) before pinning it in both the requirements file and
   `security-tools.lock.json` (added a `remediations` entry documenting the
   CVE, the verification steps, and that the hash was self-computed).
5. **`npm run agent:security` now passes 6/6 with 0 findings everywhere.**
6. **Found and fixed a self-inflicted issue** while investigating an
   unrelated question (was the stale token report pre-existing?): a
   diagnostic `git stash`/`git stash pop` silently flipped several
   hash-pinned files from LF to CRLF, because this repo has
   `core.autocrlf=true`. That broke 3 hash checks that had nothing to do
   with T24 (`AGENTS.md`, `core-tooling.json`,
   `agent-platform/tooling/graphify-requirements.txt`) plus the just-written
   `TOKEN_AND_CONTEXT_REPORT.md`. Diagnosed precisely (`sha256sum`/`file` on
   each), confirmed content was unchanged (line-ending representation only),
   converted each back to LF, reverified every hash matched. Documented in
   `.solo/risks.md` as a standing footgun for future sessions: **avoid
   `git stash` in this repo**, or set `core.autocrlf=false` for the duration
   if one is genuinely needed.
7. **`npm run agent:validate` now passes fully** — all 7 steps, confirmed via
   a clean end-to-end run (not partial/truncated output).

## Current state

- Branch: `audit/agent-extension-platform`. **Nothing committed** — this
  entire day's work (P2 audit fixes + P0 + P1 + T24) is in the working tree.
- `npx tsc --noEmit` → 0. `npm run lint` → 0. `npm test` → **10/10**.
- `npm run agent:security` → **6/6 passed, 0 findings**.
- `npm run agent:validate` → **fully passes, exit 0**.
- Python 3.12.10 is now installed on this machine at
  `C:\Users\unn0w\AppData\Local\Programs\Python\Python312\` (per-user, not
  on PATH — reachable via `py -3.12`). This is a real, lasting change to the
  machine, not just the repo, worth knowing about for any future session on
  this same machine.
- No stray temp/backup files remain (checked explicitly before finishing).

## Next steps, in order

1. **Review the full diff** before anything gets committed — today's session
   spans docs/agent-audit audit + P0 fixes + P1 fixes + this T24 pass. It's a
   lot in one working tree; consider whether to commit it as one or split it.
2. **T2b** (D1 keep/remove) and **T25** (confirm real deploy trigger) — the
   two remaining open product/ops decisions.
3. **T23**'s CSP half (report-only pass, not done today).
4. Everything else in `tasks.md`'s Todo section (P1 items T7-T12, P2 T21,
   P3 T18-T20, T26) — none blocking, all lower priority than what's done.

## Gotchas / open questions

- **Do not run `git stash` in this repo without first checking
  `core.autocrlf`** — see the risks.md entry. If you must, set
  `core.autocrlf=false` for that one operation.
- Python 3.12.10 is EOL for Windows installers (3.12 is security-patch-only,
  source-release-only past 3.12.10 now). This is fine for its narrow purpose
  here (isolated scanner venv, not general development), but worth knowing
  if anyone later wonders why it's not the newest 3.12.x patch.
