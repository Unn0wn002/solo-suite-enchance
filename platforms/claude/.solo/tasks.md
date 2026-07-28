# Solo Suite — audit remediation tracker

Source: read-only marketplace audit (Graphify-indexed, adversarially verified),
2026-07-27. Baseline commit `a31be03` on `release/v1.0.27`.

T-001 – T-004 were completed in an earlier session (ci.yml plugin-count
derivation, ci.yml smoke-test derivation, `scan_secrets.py` cp1252 crash, and
`tests/test_ci_plugin_counts.py`).

Status legend: `todo` · `in-progress` · `done` · `blocked`

| ID | Title | Pri | Size | Status | Evidence |
|----|-------|-----|------|--------|----------|
| T-005 | Resolve forked url_guard.py | MEDIUM | M | done | canonical header in `plugins/site-doctor/lib/url_guard.py`; mirrored to seo; byte-identity asserted by `tests/test_url_guard.py::MirroredCopiesStayIdentical` (4 tests) + `self_check.py`; both mutation-tested RED on drift; SECURITY.md + README updated |
| T-006 | Consolidate URL-origin helpers | MEDIUM | M | done | `normalized_hostname`/`same_site_url`/`same_audit_origin` moved into url_guard.py; 3 duplicate defs deleted (extract_meta, scan_trackers, check_headers incl. its divergent `same_site`); 1,220-case equivalence proof vs old impl, 0 mismatches; `OriginBinding` + `NoDuplicateOriginHelpers` tests |
| T-007 | Repair parity ownership | MEDIUM | S | done | Determined GENERATED (parity/README.md documents the generator; no retirement evidence in CHANGELOG). Constants 18/102/56/159 -> 19/125/79/184; regenerated via `tools/parity.py generate` (rule 7, not hand-patched): counts 19/125/79/184, seo present (22 cmds + 22 skills), 66 stale `source_sha256` -> 0. Stale "102-command map" message literal made derived. New `tests/test_parity_contract.py` (7 tests) pins constants to filesystem + manifest to a fresh generation. parity/README.md counts corrected. |
| T-008 | Shorten command descriptions (<=60) | MEDIUM | L | done | 114 of 125 command descriptions rewritten to <=60 chars (max was 296); all 125 now <=60, 0 missing, 0 with ': '; `tests/test_description_limits.py` asserts the limit, YAML-safety, distinctness, and near-neighbour separation (mutation-tested RED) |
| T-009 | Shorten + sync plugin descriptions (<=200) | MEDIUM | M | done | 15 (not 13 - `dev` 207 and `release` 202 were also over) plugin.json descriptions cut to <=200; all 19 marketplace entries mirrored exactly; mandated contract content restored after an initial over-trim (gate self-attested/copyable/not-proof + 6 commands, stack /stack:connector-check, ai 24 room-* agents); sync + limit tests added |
| T-010 | Add SEO metadata (seo, seo-flow, seo-maps) | MEDIUM | XS | done | `seo-flow` and `seo-maps` added to seo plugin.json `keywords` and marketplace `tags` (`seo` already present); keywords == tags asserted; each declared skill proven to exist on disk |
| T-011 | Correct README network-skill count (5 -> 7) | MEDIUM | XS | done | README:338 now names 7 skills / 2 plugins (5 site-doctor + seo-schema, seo-sitemap), verified by `grep -rl "from url_guard import"`; README:9 + SECURITY.md also corrected |
| T-012 | Separate SEO trigger responsibilities | MEDIUM | M | done | seo-optimization narrowed to the site-doctor generalist pass with a `Do NOT use` clause naming seo-schema/sitemap/hreflang/geo/technical/page; orchestrator's false "single-page check" claim corrected in frontmatter AND body line 8; `tests/test_trigger_routing.py::SeoTriggerSeparation` (5 tests) |
| T-013 | Separate ship-readiness skills | MEDIUM | M | done | 4 ship-readiness skills given exclusive entry conditions - scorer (14 categories) / checkpoint (GO-NO-GO) / artifacts (deploy, rollback, CI) / live-site audit; each names the other three; intentional orchestration preserved; `ShipReadinessSeparation` (7 tests) |
| T-014 | Improve Windows Python fallback | MEDIUM | S | done | `gate_policy._is_windows_store_alias()` refuses zero-byte %LOCALAPPDATA%/Microsoft/WindowsApps stubs with an actionable reason (names exit 9009 + `py -3`); both gate commands gained a Running-helpers callout documenting python / py -3 / the alias trap; `tests/test_windows_python_fallback.py` (11 tests) covers real interpreter, py -3, missing name, alias, non-alias-in-WindowsApps, and off-Windows inertness |
| T-015 | Correct README inventory counts | LOW | XS | done | README:5 "26 skills" -> 27 (disk: 27 site-doctor SKILL.md); README:344 "seventeen" -> "nineteen" (disk: 19); both verified against glob counts and `self_check.py` README-counts check |
| T-016 | Move displayName metadata | LOW | S | done | all 19 `displayName` values mirrored into their marketplace entries (kept in plugin.json too - the manifest schema has no additionalProperties:false, so it validates harmlessly); immutable `name` slugs untouched; completeness+sync test added |
| T-017 | Expand self-check portability coverage | LOW | S | done | `_portability_checks()` hoisted out of the skills-only loop and applied to commands, skills AND agents; `tests/test_self_check_coverage.py` proves detection in all three component types (positive + negative fixtures) |
| T-018 | Canonicalize the output contract | LOW | M | done | canonical block moved to `tools/output_contract.py` (build-time only - tools/ is not in build_release ALLOW_DIRS, so no cross-plugin runtime dependency, no symlinks); `--check`/`--write` CLI; animation.md drift reconciled (had 2 of 6 Evidence Checked lines); 44 carriers now byte-identical; `tests/test_output_contract.py` (7 tests) mutation-tested RED |
| T-019 | Restore Windows launcher guidance | LOW | XS | done | all 7 botched callouts restored to "use `python` (macOS/Linux/Windows) or `py -3` (Windows launcher)"; 0 occurrences of the broken text remain; CHANGELOG:1069's `python3 -> python -> py -3` claim is now truthful |
| T-020 | Correct update_run_state.py paths | LOW | XS | done | `${CLAUDE_PLUGIN_ROOT}`-prefixed the runnable argv at production-ready.md:23 and production-readiness-reviewer/SKILL.md:226; repo-wide sweep found no other runnable CWD-relative helper argv (2 remaining `scripts/...` mentions are prose, deliberately left) |
| T-021 | Cleanup + verify command contract | LOW | XS | done | exactly the 2 confirmed empty dirs removed (`seo/skills/seo-schema/references`, `seo/skills/seo-technical/scripts`) after proving both were empty, untracked and unreferenced; `full-team/commands/verify.md` contradiction resolved by deleting BOTH the placeholder `argument-hint: [no arguments]` and the dangling `$ARGUMENTS` so frontmatter and body agree |
| T-022 | Strengthen self_check.py | LOW | M | done | self_check gained local markdown-link resolution (relative to the containing file), deterministic anchor checking for local .md targets, external schemes excluded, plus argument-hint<->body consistency in both directions; 19 fixture tests with actionable messages |
| T-023 | Extend Windows encoding tests | LOW | M | done | `test_windows_encoding.py` extended from 4 to all 19 shipped scripts (the 15 uncovered ones); 5 new cases - usage-path sweep, non-cp1252 filename+content tree, IDN hostnames through both url_guard copies, full self_check report. FOUND AND FIXED A REAL BUG: `animation_check.py` crashed with UnicodeEncodeError on a non-cp1252 path (4 interpolation sites, same class as T-003); mutation-tested RED |

## Suggested tasks

| ID | Title | Pri | Size | Status |
|----|-------|-----|------|--------|
| T-SUGGEST-001 | Wire parity into CI | MEDIUM | S | **IMPLEMENTED** |
| T-SUGGEST-002 | Regenerate the Codex adapter from the current canonical tree | MEDIUM | M | recorded, NOT implemented |
| T-SUGGEST-003 | Harden `PYTOK` interpreter selection in the gate tests | MEDIUM | XS | **IMPLEMENTED** (required by T-014) |
| T-SUGGEST-004 | Fix the `animation_check.py` cp1252 crash | HIGH | XS | **IMPLEMENTED** (found by T-023) |
| T-SUGGEST-005 | Wire `tools/output_contract.py --check` into CI | LOW | XS | **IMPLEMENTED** |
| T-SUGGEST-006 | Suite-wide stdout encoding policy | MEDIUM | M | **IMPLEMENTED** |

### T-SUGGEST-001 / 005 — generated artifacts wired into CI (IMPLEMENTED)
- **What landed:** one new step in the `test` job, *Generated artifacts are in
  sync with their generators*, immediately after AgentRooms validation. It runs
  `parity.py generate --source .` then `git diff --exit-code --
  parity/capabilities.json`, and `output_contract.py --check`.
- **Scope decision — the Codex half is deliberately NOT in CI.** `parity.py
  --check` needs a Codex adapter checkout, which is a separate downstream
  distribution the runner does not have. Only the source side (the half that
  actually went stale) is enforced per push; the adapter comparison stays a
  release-time step. See T-SUGGEST-002.
- **Scope decision — `parity/` is still NOT shipped.** `build_release.py`
  `ALLOW_DIRS` remains unchanged. `capabilities.json` is a 94 KB QA contract for
  the adapter with no consumer value in an end-user install, and adding it would
  change the packaged-ZIP inventory that CI validates. Wiring the check into CI
  gets the benefit without touching the release artifact.
- **Verification:** ci.yml parses (4 jobs); `bash -n` on the new step passes;
  drifting `plugins/growth/plugin.json` moves the generated hash (guard sees
  it); `output_contract --check` exits 1 on a drifted copy and 0 clean.

### T-SUGGEST-006 — suite-wide stdout encoding policy (IMPLEMENTED)
- **What landed:** a byte-identical `_harden_streams()` in all **17** entry-point
  scripts, called from inside the `__main__` guard, doing
  `stream.reconfigure(errors="backslashreplace")` on stdout and stderr with
  `(AttributeError, ValueError, OSError)` swallowed.
- **Design decisions:**
  * **Inside `__main__` only** — several tests import these modules, and
    hardening at import time would mutate the *test process's* streams.
  * **`errors` only, never `encoding`** — forcing UTF-8 would defeat the
    CP1252 CI matrix leg. Proven byte-identical: the same file with and
    without the call produces 1,209 identical bytes of ASCII report.
  * **Duplicated, not shared** — plugins install independently, so this
    follows the `url_guard.py` precedent: identical copies enforced by test.
  * **Per-site `json.dumps` escaping kept** — it produces cleaner output than
    `\uXXXX` and the two mechanisms are defence in depth, not alternatives.
- **Verification:** with the `json.dumps` fix *removed* from
  `animation_check.py`, the cp1252 run now yields 0 `UnicodeEncodeError` and
  prints `e.g. 設定...` instead of dying — the class is closed even
  where a site is unescaped. 6 new `StreamHardeningPolicy` tests; removing one
  script's call turns them RED.

### T-SUGGEST-003 — Harden PYTOK interpreter selection (IMPLEMENTED)
- **Reason:** `tests/test_gate_policy.py` and `tests/test_gate_evidence.py` both
  chose their interpreter with `PYTOK = "python3" if shutil.which("python3")
  else "python"` — the exact which()-style check T-014 exists to defeat.
  `shutil.which` succeeds on the zero-byte Store alias, so 11 gate tests were
  asserting against a stub that exits 9009.
- **Affected files:** `tests/test_gate_policy.py`, `tests/test_gate_evidence.py`
- **Priority:** MEDIUM · **Size:** XS
- **Evidence:** `shutil.which("python3")` →
  `C:\Users\unn0w\AppData\Local\Microsoft\WindowsApps\python3.EXE`, size 0.
- **Verification:** `PYTOK` resolves to `python` here; the 209 tests in the two
  gate modules plus `test_script_fixes`/`test_url_guard` pass.
- **Implemented because:** directly required by T-014 (its guard exposed the
  latent defect), local, reversible, and evidence-backed.

### T-SUGGEST-004 — animation_check.py cp1252 crash (IMPLEMENTED)
- **Reason:** the T-023 sweep caught `animation_check.py` dying with
  `UnicodeEncodeError` when a finding's path is not cp1252-encodable — the same
  defect class as T-003's `scan_secrets.py` bug, in a second script.
- **Affected files:**
  `plugins/site-doctor/skills/animation-design-audit/scripts/animation_check.py`
- **Priority:** HIGH · **Size:** XS
- **Evidence:** reproduced at line 184 against a fixture named
  `設定ファイル/index.js`; four path interpolations at lines 169/177/187/196.
- **Verification:** the fixture now reports cleanly; mutation-tested RED.
- **Implemented because:** T-023 explicitly requires failures to expose real
  encoding assumptions rather than be skipped.

### T-SUGGEST-005 — Wire the output-contract check into CI
- **Reason:** `tools/output_contract.py --check` guards 44 files but only runs
  via the test suite; a CI step would fail faster and more legibly.
- **Affected files:** `.github/workflows/ci.yml`
- **Priority:** LOW · **Size:** XS
- **Evidence:** the drift in `animation.md` survived until T-018 precisely
  because no mechanism compared the copies.
- **Verification:** a CI step running `--check` exits 0.
- **Why not implemented:** a CI change is a release-process decision
  (T-SUGGEST-001 covers the same call for parity).

### T-SUGGEST-006 — Suite-wide stdout encoding policy
- **Reason:** two scripts have now shipped the same cp1252 crash
  (`scan_secrets.py` in T-003, `animation_check.py` in T-023). Both were fixed
  per-print-site. A single `sys.stdout.reconfigure(errors="backslashreplace")`
  at each entry point would make the class impossible rather than repeatedly
  patched, and `grep -rn reconfigure --include=*.py .` returns nothing today.
- **Affected files:** all 19 shipped scripts.
- **Priority:** MEDIUM · **Size:** M
- **Evidence:** two independent occurrences of one defect class; the T-023
  sweep only proves the *usage* and *path* surfaces, not every future print.
- **Verification:** the existing cp1252 sweep must stay green, and
  `tests/test_windows_encoding.py`'s cp1252 assertions must still hold
  byte-for-byte for ASCII output.
- **Why not implemented:** it changes output behaviour for every shipped
  script and interacts with the CP1252 CI matrix leg — a product decision, not
  a local fix.

### T-SUGGEST-001 — Wire parity into CI
- **Reason:** `tools/parity.py` went a full release stale precisely because
  nothing ran it. `tests/test_parity_contract.py` (added under T-007) now guards
  the source side, but the `--check` half still has no scheduled runner.
- **Affected files:** `.github/workflows/ci.yml`, `release/build_release.py`
  (`ALLOW_DIRS` excludes `parity`, so the contract is not even shipped).
- **Priority:** MEDIUM · **Size:** S
- **Evidence:** `grep -rln parity .github/workflows/ci.yml tests/*.py
  release/*.py` returned nothing before T-007; `ALLOW_DIRS = (".claude-plugin",
  ".github", "plugins", "release", "tests")` at `release/build_release.py:40`.
- **Verification:** a CI job that runs `parity generate` and fails on a dirty
  `git diff --exit-code parity/capabilities.json`.
- **Why not implemented:** adding a CI job is a release-process change and needs
  a decision about whether a Codex checkout is available to the runner.

### T-SUGGEST-002 — Regenerate the Codex adapter
- **Reason:** `parity --check --target <codex-v1.0.27>` reports 88 differences.
  These are **pre-existing** and not caused by this work: e.g.
  `plugins/design/skills/ui-ux-designer/SKILL.md` is byte-identical to git HEAD
  in this repo (6,235 bytes) but 6,572 bytes in the Codex checkout. The
  canonical tree is at metadata version 1.0.30; the adapter is 1.0.27.
- **Affected files:** none in this repository — the Codex distribution only.
- **Priority:** MEDIUM · **Size:** M
- **Evidence:** 88 `- ` failure lines; `command-map.json` has 125 entries on
  both sides but differing field values; 24+ normalized specialist body
  mismatches across skills untouched by this work.
- **Verification:** `parity --check` exits 0 after the adapter is rebuilt.
- **Why not implemented:** the Codex checkout is the designated READ-ONLY
  reference; fixing it would require modifying it.

## Notes

- Working repo: `solo-suite-v1.0.27-release-work` (all changes here).
- Read-only reference: `Solo Suite Codex/solo-suite-codex-v1.0.27` — never modified.
- `.solo/` is in `release/build_release.py` `EXCLUDE_DIRS`, so this tracker is
  never packaged into a release artifact.
