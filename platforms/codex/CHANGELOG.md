# Changelog

## Unreleased

- Bound release tags to the exact protected default-branch commit at build, before draft creation, and immediately before public publication; added owner-only `v*` tag creation, non-bypassable tag update/deletion protection, and immutable GitHub releases.
- Added a Python 3.12-only, hash-pinned `pip-audit` toolchain; CI and publication now fail closed on live vulnerability checks for both validation and audit locks and attest the two JSON reports.
- Split source-checkout and installed-package validation profiles in README and generated provenance, disclosing that the install ZIP omits the separately attested canonical parity archive and cannot run Git-dependent contributor tests.
- Corrected the supported release in `SECURITY.md` from stale v1.0.12 wording to v1.0.27.
- Unified direct and AgentRoom production-gate policy on one imported definition of the 14 categories, six profile N/A matrices, seven mandatory categories, N/A-adjusted denominator, launch thresholds, and status decision; corrected SaaS SEO, API-service Database, and library Monitoring/Performance applicability drift.
- Reconciled the Codex adapter against the public Claude v1.0.27 annotated tag (commit/tree and release provenance pinned; tag signature absent). The reproducible canonical overlay now declares exactly ten paths: seven reviewed behavior merges, the hardened parity checker, regenerated capabilities, and embedded provenance.
- Added offline canonical-overlay verification before networked provenance fetching and documented a non-destructive remote-main import/PR plan; the current v1.0.27 baseline is the public Claude release asset with an explicit ten-path Codex adapter overlay (the unsigned upstream tag remains a caveat).
- Added a fail-closed native Codex marketplace smoke/duplicate-name guard, so a stale same-name marketplace cannot silently install an older plugin cache.
- Made the canonical source artifact mandatory for validated/CI packaging and package smoke tests; both now rerun the bundled source/target parity checker instead of relying on provenance prose.
- Added `tools/build_canonical_source.py` and `tools/generate_source_overlay_manifest.py`; both require the v1.0.27 base provenance record and fail closed on undeclared source drift. The base and canonical archive digests, tag object, tree, and overlay manifest are pinned in `parity/canonical-source.json`.
- Made `$full-team-orchestrator` and `full-team-website.json` the single authoritative full-team flow; `$solo-full-team-dev` now delegates to it instead of maintaining a divergent phase list.
- Added explicit stack-conditional Vercel, Supabase, Cloudflare, tag, and payments tasks and gate artifacts to the full-team room, aligned the specification/CI/Git/handoff commands, and generated its 15-stage/25-seat documentation from the JSON contract.
- Made `$full-team-verify` delegate to the native preflight, enforce the v1.0.27 component floor, and report Codex-native `codex plugin add ...@solo-suite-codex` repair commands.
- Repaired cross-platform CI evidence: coverage now includes the real validator/build/smoke commands and child Python processes, publishes a complete full-tree report, and gates 68% only after an explicit six-file authoring-helper scope declaration; Windows temporary-path assertions now canonicalize 8.3 aliases.
- Recorded the release repository's auditable CodeQL alert #2 triage as **used in tests** for the auto-deleted synthetic secret-redaction fixture; no query suppression is embedded in source and production findings remain in scope.

## 1.0.27 — 2026-07-15

- Synchronized the Codex adapter with the canonical Solo Suite Claude v1.0.27 capability set: 18 plugins, 56 specialist skills, and all 102 command workflows.
- Added `$full-team-verify` and `$gate-finalize-evidence`, including the newer evidence finalizer, run-state, Gate policy, and Site Doctor helper hardening.
- Added a deterministic source-to-adapter manifest and checker for command mappings, specialist instructions, shared helper hashes, schemas, room archives, and explicit invocation policy.
- Made all 159 Codex skills explicit-only by default.
- Preserved Codex's stronger executable AgentRoom runtime and Codex marketplace self-check as two documented platform adapters; canonical Claude room files are archived for drift detection.
- Parameterized conversion, metadata, packaging, smoke checks, and CI around the authenticated Claude v1.0.27 source rather than the older embedded snapshot.

## 1.0.12 — 2026-07-13

- Added an executable, resumable AgentRoom state machine with explicit profile binding, task/result contracts, workspace and artifact-lock enforcement, recorded command provenance, validator-backed gate routing, adapter write detection, and bounded repair-loop exhaustion.
- Hardened the AgentRoom runtime trust boundary with complete skill/runner/validator fingerprints, run-owned trusted copies, digest-chained state journals, strict cross-registry validation, filtered-byte Git manifests, hidden-index-flag and Gitlink rejection, immutable task contracts, unredirected lease-private staging, live promoted-artifact verification, verified promotion rollback, frozen transitive gate bundles, runner/adapter process-identity-aware recovery, rollback-safe control roots, and concurrent same-stage adapter execution. The local journal guarantee explicitly excludes a coordinated rollback of every same-user authority without an OS/remote monotonic anchor.
- Repaired the Full Team and production-release producer contracts so every applicable production category has at least one room-declared command accepted by its category allowlist; production evidence must now cite both an allowlisted and room-declared producer.
- Added a real full-room integration path that prepares and completes the 15-stage Full Team contract, validates all four gates, exercises a three-reentry NO-GO repair loop, and rejects undeclared writes, changed digests, and unexecuted evidence producers.
- Added a local accessible frontend/API/SQLite golden journey and real detached Git-worktree materialization, plus commit rebind/revalidation that accepts only integrated clean worker commits.
- Added a deterministic Full Team preflight for all 17 component minimum versions, representative skills, every selected-room command, and the complete AgentRoom semantic contract.
- Added Dependabot, least-privilege checkout behavior, private-plan-safe CodeQL and artifact-attestation opt-ins, and an immutable future-release asset workflow.
- Replaced CodeQL's flagged email regular expression with bounded linear validation and fixed a Windows AgentRoom lock race by acquiring the byte lock before touching its unbuffered metadata stream.
- Expanded the suite to 246 tests and 69% measured coverage, raised the CI floor from 62% to 68%, and lifted the phase-gate validator from 55% to 67% coverage.

## 1.0.11 — 2026-07-11

### Advanced website hardening — 2026-07-11

- Added stack intake, a dedicated pre-deploy gate, complete gate prerequisites, mandatory advanced-web evidence, and a three-iteration repair/retest loop to the Full Team website room.
- Strengthened production evidence with category-specific real-skill allowlists, typed provenance, chronology checks, and structured actionable warnings.
- Replaced 42 invalid `$plugin-command` follow-ups with real contextual skills and fixed the command converter so the placeholder cannot return.
- Fixed installed-cache self-check discovery when a personal marketplace exists above an unrelated cache plugin.
- Added 63 behavior and regression tests across Site Doctor helpers, AgentRoom routing, evidence contracts, release reproducibility, and repository hygiene, bringing the suite to 174 tests and measured coverage to 65%; CI enforces a 62% floor.
- Split architecture/database and documentation/release-management stages, bound all gate evidence to the exact run, gate, commit, environment, and artifact digest, and made every negative or insufficient verdict stop or enter the bounded repair loop.
- Added prepared-room digests, exact prerequisite/producer bindings, per-project run-ID reservations, run-scoped artifacts, maximum-age enforcement, machine-readable loop signals, a profile-specific N/A contract, and independent before-deploy revalidation; an all-N/A score can no longer approve production.
- Added a hash-locked eight-package validation environment, LF-only repository policy, committed-blob packaging immune to local Git attributes and replacement refs, byte-reproducibility tests across clean clones, tracked-output protection, and fail-closed dirty/no-commit release checks.

### Codex-native release

- Converted the 17-component Solo Suite v1.0.10 marketplace to 18 native Codex plugins using `.codex-plugin/plugin.json` and repo-local `.agents/plugins/marketplace.json` metadata.
- Migrated all 100 legacy command workflows one-to-one into explicit Codex skills. Added `command-map.json` and `COMMAND-MAP.md` for deterministic migration lookup.
- Added the `full-team` meta-plugin and `full-team-orchestrator`, with an honest component-availability check because the current Codex plugin manifest has no plugin-dependency field.
- Added UI metadata for all 157 skills and explicit-only policy for workflows involving mutation, deployment, synchronization, form submission, secrets, or production access.

### Security and runtime hardening

- Added the installed-root-aware Site Doctor launcher and external-working-directory regression coverage.
- Reworked secret findings to emit only path, line, rule, redaction, and SHA-256 fingerprint; added realistic leak regression fixtures and scanner self-suppression.
- Removed write-capable SQL from the read-only database audit and routed maintenance work to the explicitly confirmed database-fix workflow.
- Secured memory synchronization, token configuration, sync exclusions, log redaction, dry-run defaults, browser form submission, and production-side-effect policy.
- Corrected HSTS, redirect, mixed-content, DMARC, recursive SPF, nested-H1, tracker, cookie, and dependency-range behavior.

### AgentRooms and gates

- Added the strict AgentRooms v1 JSON Schema, semantic validator, memory-steward ownership, unique task allocation, workspaces, artifact locks, bounded loops, implicit `.solo/` effects, and gate evidence requirements.
- Rebuilt all four room templates and added a declarative Codex runner adapter. Room JSON remains a validated execution plan, not an unclaimed automatic runtime.
- Standardized production readiness on 14 categories (140 points only when all are applicable), three launch statuses, provider-aware applicability, artifact digests, and commit/environment/expiry validation.

### Release engineering and documentation

- Added source-checkout and installed-cache self-check modes, complete native manifest validation, Windows/Ubuntu CI, coverage, package smoke tests, SBOM, provenance, and checksums.
- Updated the Site Doctor DOCX for Codex and removed comments/legacy invocation text. Structural Open XML checks pass; visual rendering remains unverified where Office/LibreOffice is unavailable.
- Corrected plugin, skill, workflow, and helper counts and removed unsupported standalone-skill and uniform-output-contract claims.

## 1.0.10 — 2026-07-10

The supplied historical source release contained 17 plugins, 56 specialist skills, 100 Claude-oriented commands, 10 helper scripts, SSRF protection, AgentRooms templates, and the original shared `.solo/` workflow. That archive is optional external historical material and is not bundled or required for the current Codex release build; `RELEASE-PROVENANCE.json` pins its verified SHA-256 digest.
