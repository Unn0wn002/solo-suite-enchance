# Security Policy

## Reporting a vulnerability

Email **ayakuminozomi@gmail.com** with the subject `[solo-suite security]`.
Include the affected plugin/script, a reproduction, and the impact. Please do
not open a public issue for undisclosed vulnerabilities. You should receive a
response within 7 days; fixes ship in the next patch release with credit if
you want it.

Supported versions: the latest released version only.

## Security design of this suite

- **No runtime dependencies.** Every helper script is Python stdlib only; the
  release ships an SBOM (`sbom.json`) and SHA-256 checksums.
- **Signed releases (version tags).** Pushing a `v<version>` tag uses isolated
  read-only build, OIDC-only signing, and contents-write-only publication jobs;
  no job holds both signing identity and release-write authority. The Claude
  CLI comes from the repository-owned integrity lock with lifecycle scripts
  disabled. Checksums are verified at every artifact boundary, and the
  publisher downloads each draft asset again for exact byte and signature
  verification before promotion. The named protected environments still
  require repository-side reviewer/tag policy configuration. Locally built bundles are unsigned release
  candidates; a temporary GitHub Actions artifact is not the distribution
  channel. Follow README's **Verify a published release** procedure. It obtains
  the exact case-sensitive owner/repository name from GitHub's API and builds
  the expected workflow identity independently of the bundle. Never copy the
  expected identity out of the untrusted signature bundle itself. A missing
  bundle, release asset, manifest entry, or failed checksum/signature is
  **UNVERIFIED**, not a pass.
- **SSRF guard.** All site-doctor **and seo** network scripts route through
  `url_guard.py`: scheme allowlist, private/loopback/link-local/CGNAT/metadata
  refusal on every DNS answer and every redirect hop, and hard response-size
  caps. It also owns the origin-binding helpers (`normalized_hostname`,
  `same_site_url`, `same_audit_origin`) that decide whether a post-redirect
  URL may still be treated as evidence for the requested target. Because
  plugins install independently, the module is **mirrored**, not shared:
  `plugins/site-doctor/lib/url_guard.py` is canonical and
  `plugins/seo/lib/url_guard.py` must remain byte-identical to it. Both
  `tests/test_url_guard.py` and `self_check.py` fail closed on any drift, so a
  security fix cannot land in one copy only. Known residual risk: the stdlib
  socket layer re-resolves at connect time (TOCTOU) — documented in the
  module; do not reuse it as a boundary for untrusted callers.
- **Secret hygiene.** The secret scanner (`scan_secrets.py`) never prints a
  complete matching line or secret value — findings carry only path, line,
  rule, a redacted preview, and a keyed fingerprint. Its optional bounded local
  Git-object history mode emits no source preview at all and never fetches or
  checks out revisions; an incomplete history scan is not a clean result.
  Sync/config conventions store token **names** (environment variables), not
  values; `.solo/config.md` is gitignored.
- **Manual execution boundaries.** User-facing commands that mutate
  production, migrate data, submit forms, sync externally, or handle secrets
  use `disable-model-invocation: true`: /security:secrets-fix, /site-doctor:migrate-data,
  /site-doctor:load-test, /git:sync-issues, /solo:sync-grafana,
  /solo:sync-obsidian, /browser:smoke-test, /browser:form-submit-test,
  /security:rls-test, /site-doctor:security-scan (dynamic mode),
  and /gate:finalize-evidence. Skills keep exactly `name` + `description`
  frontmatter; website-fix, database-fix, data-migration, and memory-sync state
  the same stop/preview/confirmation rule in their body. Loading a skill never
  authorizes a state change. Every boundary requires explicit in-flow
  confirmation before writing.
- **Read-only audits.** Database audits carry a policy test that rejects
  write-capable SQL in the read-only references; browser QA defaults to
  non-production targets with synthetic data.

## Scope notes

The suite's commands and skills are prompts executed by an AI agent — treat
gate verdicts and audit output as evidence-backed *assistance*, not a
certification. `/solo:self-check` verifies static structure only; it is not
proof of runtime health.
