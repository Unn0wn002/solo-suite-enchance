# Solo Suite for Codex

Solo Suite is a Codex-native plugin marketplace for planning, designing, building, testing, auditing, and releasing software with shared `.solo/` project memory. This adapter synchronizes 126 workflows from the authenticated Claude v1.0.27 baseline, migrating each legacy command to an explicit Codex skill. The source checkout pins the public base and its reviewed Codex overlay under `parity/artifacts/`. The deterministic install ZIP intentionally omits nested archives and checksum sidecars, so the release workflow publishes the separately attested asset `solo-suite-plugin-v1.0.27-codex-v1.0.27-parity-source.zip` only after normal review, protected-tag validation, and final private-draft asset re-verification. The Claude tag is annotated but unsigned; that caveat and every reconstruction input are recorded under [`parity/`](parity/README.md).

**19 plugins** · **185 skills** · **126 migrated commands** · **28 helper scripts**

The 185 unique skills comprise 80 synchronized specialist skill definitions, 126 command-derived mappings (including merged specialist collisions), and the Codex-native `full-team-orchestrator` meta-skill. The authoritative one-to-one migration is in [`command-map.json`](command-map.json), the readable table is in [`COMMAND-MAP.md`](COMMAND-MAP.md), and the source-to-adapter contract is in [`parity/capabilities.json`](parity/capabilities.json).

## What changed for Codex

Codex plugins use `.codex-plugin/plugin.json` and expose workflows as skills. Invoke a migrated workflow with the specific `$<plugin>-<command>` skill shown in the map:

```text
Legacy lookup                 Codex invocation
/solo:start-session          $solo-start-session
/dev:implement-feature       $dev-implement-feature
/site-doctor:full-checkup    $site-doctor-full-checkup
/gate:production-ready       $gate-production-ready
```

The legacy names are documentation-only migration keys. There is no Claude command runtime or `${CLAUDE_PLUGIN_ROOT}` dependency in this release. Skills that can mutate files, deploy, synchronize externally, submit forms, handle secrets, or touch production are explicit-only through `agents/openai.yaml` policy.

Two implementations remain intentionally platform-native: Codex keeps its executable, resumable AgentRoom runner and its Codex marketplace integrity checker. The canonical Claude AgentRoom files are archived under `parity/claude-rooms`, and both exceptions are declared in the parity manifest. All other commands, specialist instructions, shared helpers, schemas, and policies are checked mechanically against the pinned source archive. A validated package build refuses to proceed unless that archive's SHA-256 is exact and its bundled checker passes against the release tree.

## Install

Unpack the release so it has one enclosing `solo-suite-codex-v1.0.27/` folder, then register that folder as a local marketplace:

```powershell
codex plugin marketplace add "C:\path\to\solo-suite-codex-v1.0.27"
codex plugin add solo@solo-suite-codex
codex plugin add project@solo-suite-codex
codex plugin add dev@solo-suite-codex
```

Before installing a plugin, verify that Codex has exactly one configured
`solo-suite-codex` marketplace and that its `root` is the folder you just
unpacked:

```powershell
codex plugin marketplace list --json
```

Codex selects the first matching marketplace name. If the list contains a
duplicate or an older root, stop: repeat `codex plugin marketplace remove
solo-suite-codex` while reviewing the list after each removal, then add the
intended folder again. Do not install until the name is unique and the root
matches; otherwise a successful-looking `codex plugin add` can install an old
same-name cache. From a source checkout, the optional native smoke check makes
the same guard and verifies all 19 installed trees:

```powershell
python tools/native_install_smoke.py --suite-root . --check-current
```

On macOS or Linux, use the same commands with a POSIX path. Install any combination of component plugins from the inventory below. Start a new Codex task after installing or updating so the new skills are loaded.

For the complete team, install all 18 component plugins plus `full-team`:

```text
ai browser design dev docs gate git growth project release repo
security seo site-doctor solo spec stack test full-team
```

Then invoke:

```text
$full-team-orchestrator
```

For the approved Graphify, native-search, official-docs, and Repomix routing, see
the root [`CORE_REPOSITORY_INTELLIGENCE.md`](../../CORE_REPOSITORY_INTELLIGENCE.md).
Check the audited Graphify CLI from the repository root:

```powershell
python scripts/bootstrap-graphify.py --check
```

Codex uses the existing `AGENTS.md` and canonical repository-routing skill; no
platform installer is needed.

## Usage

Start with an explicit skill invocation, for example `$solo-self-check` for
mechanical suite/project checks or `$full-team-orchestrator` for the prepared
multi-seat workflow. Each skill reports its evidence, risks, required fixes,
stable task IDs, verification command, and the exact next skill. Mutating,
external-sync, form-submit, deployment, rollback, and production workflows
remain preview/confirmation-gated; invoking a skill does not authorize those
side effects.

Codex's current plugin manifest contract has no plugin-dependency field. Consequently, installing `full-team` does not silently install its components. The orchestrator checks the component list in `plugins/full-team/skills/full-team-orchestrator/references/component-plugins.json`, enforces the v1.0.27 minimum floor and every room-declared skill, and fails closed before preparation when coverage is missing. It may report degraded coverage, but it does not call that report an authoritative full-team run.

## Plugin inventory

| Plugin | Skills | Migrated workflows | Purpose |
|---|---:|---:|---|
| `solo` | 13 | 10 | Shared memory, sessions, sync, self-check, master workflow |
| `project` | 5 | 3 | PRD, architecture, task breakdown |
| `design` | 4 | 3 | UX flow, component system, post-build UI review |
| `dev` | 6 | 4 | Feature work, bug repair, refactoring, code review |
| `test` | 5 | 4 | Unit, integration, end-to-end, and edge-case testing |
| `release` | 6 | 4 | CI, preflight, deployment plan, rollback plan |
| `docs` | 5 | 4 | README, API, setup, and runbook documentation |
| `site-doctor` | 52 | 25 | Website, database, security, SEO, animation, performance, and operations audits |
| `stack` | 14 | 7 | Stack intake, connector checks, and conditional vendor audits |
| `git` | 6 | 5 | Branch, commit, PR, release-note, and issue workflows |
| `spec` | 7 | 5 | Feature, acceptance, API, data, and environment contracts |
| `repo` | 6 | 5 | Read-only repository mapping and risk analysis |
| `security` | 6 | 5 | Threat, authorization, RLS, secret, and abuse-case reviews |
| `browser` | 6 | 5 | Browser smoke, console, visual, mobile, and form QA |
| `gate` | 8 | 6 | Before-code/merge/deploy, evidence finalization, and production gates |
| `ai` | 8 | 6 | Prompt, handoff, output, repair, and AgentRooms workflows |
| `growth` | 2 | 1 | Conditional conversion audit |
| `seo` | 23 | 22 | Dedicated technical, content, schema, local, ecommerce, and AI-search SEO |
| `full-team` | 2 | 1 | Meta-orchestrator and canonical full-team verification workflow |

## Full-team workflow

`$full-team-orchestrator` is the single authoritative full-team entrypoint. It
executes the `full-team-website.json` AgentRoom through `preflight.py`,
`prepare_run.py`, and `run_room.py`; the generated
[`authoritative flow`](plugins/full-team/skills/full-team-orchestrator/references/authoritative-flow.md)
and [`seat/stage map`](plugins/full-team/skills/full-team-orchestrator/references/seat-stage-map.md)
are derived from that JSON. `$solo-full-team-dev` is a compatibility alias that
delegates to the same room and owns no separate schedule.

The room has 15 stages, 24 worker seats, and one memory steward (25 seat
definitions total). It begins with `$stack-intake` before
`$stack-connector-check`, orders architecture before database architecture and
design, performs `$ai-review-output` between major phases, includes
`$test-edge-cases`, and runs `$design-ui-review` after implementation. The
Site Doctor seat declares conditional Vercel, Supabase, Cloudflare, analytics
tag, and payments tasks; each runs only when `.solo/stack.md` records that
provider, otherwise it records an evidence-backed N/A artifact. Every gate
consumes the prepared-room digest and evidence bound to the exact run, gate,
commit, environment, declared prerequisite, producer command, artifact digest,
and maximum age. `run_room.py` additionally binds cited evidence to commands
recorded for the actual producing task. A failed gate enters a status-driven,
bounded three-iteration repair/retest loop; only a freshly revalidated
before-deploy `GO` can reach production, and the strict room completes only
with `SAFE TO LAUNCH`. Every skipped category needs a digest-bound profile
reason permitted by the selected profile's narrow N/A policy.

Supported profiles include public marketing site, SaaS application, e-commerce, internal application, API/service, and library/package.

## Shared project memory

The suite uses 16 standard files under `.solo/`:

```text
project.md        stack.md          prd.md            architecture.md
api-contract.md   data-contract.md  env-contract.md   design.md
tasks.md          decisions.md      risks.md          bugs.md
tests.md          release.md        monitoring.md     handoff.md
```

`.solo/config.md` is optional and must contain only non-secret configuration such as service URLs, resource identifiers, and environment-variable names. Token values belong in environment variables or an OS secret store. Add `.solo/config.md` to `.gitignore`; sync workflows exclude it and all detected secrets.

## Production gate

`$gate-production-ready` evaluates exactly 14 categories: Product, Architecture, Design, Frontend, Backend, Database, Security, Testing, Performance, SEO, Analytics, Deployment, Monitoring, and Documentation.

Each applicable category is scored from 0 to 10. A matrix-accepted N/A category contributes neither points nor denominator, so `applicable_max = 10 * applicable_category_count` and the normalized score is `round(total / applicable_max * 100)`. The seven mandatory categories keep the denominator at `/70` or higher; `/140` applies only when all 14 categories are applicable. Production status is one of:

- `BLOCKED`
- `SAFE WITH WARNINGS`
- `SAFE TO LAUNCH`

The direct checker and AgentRoom validator import the same `plugins/gate/lib/gate_policy.py` definitions for category order, six-profile N/A applicability, mandatory categories, denominator, thresholds, and launch-status decision. N/A evidence carries score `0` as a serialization sentinel and can never inflate the total. The gate also validates machine-readable evidence, the prepared-room digest, category-specific real-skill allowlists, nested run/gate identity, exact room-declared category artifacts, a separate project-profile applicability contract, typed provenance, structured actionable warnings, SHA-256 digests, commit/environment identity, chronology, expiration, and maximum age. Evidence from another run, gate, commit, or environment; invented or cross-category skills; substituted or reused artifacts; over-age evidence; changed digests; and provenance that postdates the review are rejected. Production also revalidates the required before-deploy phase evidence and all of its prerequisites. GO/NO-GO wording is reserved for the narrower before-code, before-merge, and before-deploy gates.

## AgentRooms

The `ai` plugin ships four schema-checked declarative room plans:

- `full-team-website.json`
- `production-release.json`
- `site-doctor-audit.json`
- `bug-fix-loop.json`

The v1 schema and validator enforce bounded loops with machine-readable trigger/exit statuses, reachable stages, artifact locks, unique task allocation, one memory steward, implicit `.solo/` effects, gate prerequisites, producer-command bindings, evidence declarations, gatekeeper read coverage, contract-specific gate schemas, exact-run freshness, status-driven transitions, and fail-closed gate routing. `prepare_run.py` requires an explicit profile, reserves a lowercase case-folded run ID per project, and binds the prepared-plan digest into that claim. Instantiated work is isolated under `artifacts/runs/<run-id>/` and `worktrees/runs/<run-id>/`; production additionally requires the same room, run, commit, and environment's before-deploy `GO` evidence.

These JSON files remain declarative contracts rather than hidden autonomous agents. The bundled runner fingerprints every suite skill, gate validator, and imported runtime file; pins exact filtered Git working-tree bytes; rejects hidden index flags, unsupported Git submodules, and redirected/preseeded control paths; and stores state in a digest-chained journal whose projection cannot be forged or rolled back independently of its project-registry head. `next` creates immutable baseline-bound leases with unredirected private artifact roots, and record promotes only the declaring seat's verified files with verified rollback while preserving safe same-stage concurrency. Promoted current-commit artifacts are rehashed at their live project paths before status, issue, and advance. Gate validation and routing consume one frozen transitive evidence bundle, closing live-file swap races. Adapter crashes retain runner and adapter process creation identities so the recorded process tree is terminated and drift blocks retry. Rebind still requires a clean integrated HEAD and restarts exact-commit evidence collection. Coordinated rollback of every same-user journal authority, independent command receipts, and containment of same-user hostile executables require an OS/remote monotonic anchor, trusted receipt mechanism, and OS/container sandbox respectively. See `references/codex-runner-adapter.md` in the AgentRooms skill.

## Runtime and security guarantees

- Site Doctor helpers resolve from the installed plugin root through `plugins/site-doctor/scripts/run_helper.py`; they do not depend on the caller's working directory.
- Network helpers use the shared SSRF guard, validate every redirect hop, default to HTTPS, cap response sizes, and block private, metadata, reserved, and unsafe resolved addresses.
- The secret scanner emits only relative path, line number, rule, redaction, and irreversible SHA-256 fingerprint. It never emits a complete matched line or secret.
- Database audit SQL is read-only. Maintenance writes are routed to explicit fix workflows with confirmation, backup verification, mutation warning, and rollback guidance.
- Browser form submission is manual-only. Use synthetic data and a local, staging, or dedicated test tenant; production and side effects require explicit confirmation.
- External sync defaults to preview and requires confirmation before writing. Logs are redacted, and config/secrets are excluded.

## Standalone use

Install at plugin granularity for reliable dependency resolution. A skill directory is not automatically standalone merely because it contains `SKILL.md`. In particular:

- Site Doctor network skills rely on the plugin-level `lib/url_guard.py` and `scripts/run_helper.py`.
- AgentRooms relies on its schema, templates, references, and validator scripts.
- Production readiness relies on its evidence schema and validator.

Pure text-only skills can be copied to `~/.codex/skills/`, but copy every referenced file and revalidate the result. The package does not claim that every skill folder works independently.

## Validation

### Full contributor test suite (source checkout only)

The full unit suite requires a Git checkout and the checked-in canonical parity
archive. Run it from the source root:

```powershell
python -m pip install --require-hashes -r requirements-dev.lock
python -m unittest discover -s tests -t . -v
python plugins/solo/skills/suite-integrity/scripts/self_check.py . -
python plugins/ai/skills/agent-room-templates/scripts/validate_rooms.py --suite .
python tools/validate_plugins.py --official-if-available
```

`self_check.py` performs structural consistency checks; it is not proof of security or launch readiness. Release provenance, dependency inventory/SBOM, checksums, and exact validation state are shipped at the package root.

Run the current vulnerability audit under Python 3.12. The audit-tool lock is
separate because the current `pip-audit` does not support Python 3.9:

```powershell
python -m pip install --require-hashes -r requirements-audit.lock
python -m pip check
python -m pip_audit --strict --progress-spinner off --disable-pip --no-deps --require-hashes -r requirements-dev.lock
python -m pip_audit --strict --progress-spinner off --disable-pip --no-deps --require-hashes -r requirements-audit.lock
```

Publication-grade packages are built only from a clean Git commit. The packager snapshots `HEAD`, generates release metadata in a disposable staging directory, and leaves tracked source files unchanged:

```powershell
$canonical = Resolve-Path "parity\artifacts\solo-suite-plugin-v1.0.27-codex-v1.0.27-parity-source.zip"
python tools/build_canonical_source.py --base-archive parity\artifacts\solo-suite-plugin-v1.0.27.zip --base-provenance parity\artifacts\solo-suite-plugin-v1.0.27.provenance.json --output $canonical
python tools/verify_source_overlay.py --base-archive parity\artifacts\solo-suite-plugin-v1.0.27.zip --base-provenance parity\artifacts\solo-suite-plugin-v1.0.27.provenance.json --canonical-source-archive $canonical --target .
python tools/verify_source_overlay.py --canonical-only --canonical-source-archive $canonical --target .
python tools/package_release.py --output ..\solo-suite-codex-v1.0.27.zip --validation-state validated --canonical-source-archive $canonical
python tools/smoke_package.py ..\solo-suite-codex-v1.0.27.zip --canonical-source-archive $canonical
git diff --exit-code
git status --short --untracked-files=all
```

### Extracted release package validation

Download the install ZIP and its `.sha256` sidecar plus the separately attested
canonical parity ZIP and its sidecar. Keep all four files together, verify both
sidecars, extract the install ZIP, and run these commands from the extracted
`solo-suite-codex-v1.0.27` folder:

```powershell
python -m pip install --require-hashes -r requirements-dev.lock
python plugins/solo/skills/suite-integrity/scripts/self_check.py . -
python plugins/ai/skills/agent-room-templates/scripts/validate_rooms.py --suite .
python tools/validate_plugins.py --official-if-available
python tools/smoke_package.py ..\solo-suite-codex-v1.0.27.zip --canonical-source-archive $canonical
```

The contributor unit suite and Git cleanliness commands are deliberately not
package-mode checks: the install ZIP has no `.git` directory and does not embed
the separately attested canonical archive.

CI collects coverage from the validation commands and their child Python
processes, then writes the complete `plugins/` + `tools/` report to
`dist/coverage-full.txt` and `dist/coverage-full.json`. The checked-in
`coverage-policy.json` makes the gate scope explicit: only six authoring or
migration/documentation generators are omitted from the 68% gated runtime
floor. They remain visible in the full report and are still compiled and
validated; AgentRoom, gate, security, network, parity, packaging, and install
smoke code is never omitted to make the percentage pass.

The scanner redaction regression intentionally writes credential-shaped values
to an auto-deleted temporary fixture so it can prove that plaintext never
reaches scanner output. In the release repository, CodeQL alert #2 is audited
and dismissed as **used in tests** with that exact rationale. No query
suppression is embedded in source, and no production secret-handling finding is
dismissed by this exception.

The source builder verifies the supplied Claude v1.0.27 archive and provenance
record, applies the ten declared historical overlay paths (including the
byte-pinned historical parity checker), regenerates `capabilities.json`, embeds
`PARITY-SOURCE.json`, and emits a deterministic archive. The independent
overlay verifier then rejects any byte difference not listed in
`parity/source-overlay-manifest.json`. Repeating the build with the pinned
inputs must reproduce the archive digest in `parity/canonical-source.json`.
The current 19-plugin working-tree parity manifest is attested separately; a
historical archive check reports `WORKING-TREE PARITY DEFERRED` when that newer
manifest is present.

The public Claude v1.0.27 release asset, annotated tag, and source tree are
independently reachable and digest-pinned; the checked-in provenance JSON is
the exact public release CI record, also digest-pinned rather than locally
rebuilt. Because the tag is unsigned, the result is accurately described as an **authenticated,
reproducible adapter overlay with an unsigned-tag caveat**, not as a signed
upstream attestation. The manifest proves exactly what changed; the accepted
baseline-scope decision is documented in [`parity/README.md`](parity/README.md)
and [`parity/source-overlay-manifest.json`](parity/source-overlay-manifest.json).

The final status command must print nothing. Intentional release output under ignored `dist/` is omitted by Git.

The Site Doctor command reference and ready-to-adapt prompts are in `site-doctor-cheatsheet.docx`.

## Publisher and license

The original marketplace owner `Ayaya` and the MIT copyright holder Sakura Yukihira refer to the same publisher identity, recorded here as `Sakura Yukihira (Ayaya)`. The public Claude v1.0.27 release, annotated tag, asset, and provenance record are linked from [`parity/canonical-source.json`](parity/canonical-source.json). This Codex adapter is maintained at [Unn0wn002/Solo-Suite-Codex](https://github.com/Unn0wn002/Solo-Suite-Codex), whose visibility and access are controlled by the publisher. See `LICENSE`, `SECURITY.md`, and `CONTRIBUTING.md`.
