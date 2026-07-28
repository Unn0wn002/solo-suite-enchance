# Security policy

## Supported release

Solo Suite Codex `1.0.27` is the supported release in this package. Its Claude v1.0.27 public release asset is pinned under `parity/artifacts/` together with the exact public CI provenance record; the deterministic install ZIP intentionally omits nested archives. The Codex source is a declared ten-path adapter overlay, not byte identity with the unmodified Claude archive. The annotated upstream tag is unsigned, so the commit/tree and release bytes are reproducible but do not constitute a cryptographic upstream signature.

## Reporting a vulnerability

Do not include credentials, tokens, private keys, customer data, or an exploitable production target in a report. Use a [private GitHub security advisory](https://github.com/Unn0wn002/Solo-Suite-Codex/security/advisories/new) when you have repository access, or the same private channel through which you received the package. Do not disclose a vulnerability in a public issue.

Include the affected plugin/skill, release version, platform, minimal reproduction with synthetic data, impact, and any proposed mitigation. Avoid public disclosure until the maintainer has had a reasonable opportunity to investigate and distribute a corrected package.

## Security boundaries

- Skills are instruction packages, not a sandbox. Review proposed commands and diffs before approving writes.
- Mutation, deployment, external sync, secret handling, browser submission, and production workflows are explicit-only and require confirmation at the point of effect.
- `.solo/config.md` may name token environment variables but must never store token values. Keep it out of version control.
- Site Doctor network helpers block unsafe targets and revalidate redirects, but this does not replace network egress controls.
- The structural self-check verifies package consistency; it is not a security certification or production-readiness verdict.
- AgentRooms files are declarative plans. A runner must enforce their locks, workspaces, stage order, evidence, and confirmation rules.
- The AgentRoom digest chain detects projection, journal, or project-registry-head tampering when at least one authority remains intact. A same-user attacker able to restore all local authorities to one older consistent snapshot is outside this local-file guarantee; use an OS-protected or remote monotonic anchor for that threat model.
- AgentRoom private staging is a coordination boundary, not a same-user process sandbox. Run hostile adapters in an independently configured OS/container sandbox.

## Release integrity

Verify the distributed ZIP with its adjacent `.sha256` file or `RELEASE-CHECKSUMS.txt`. Review `RELEASE-PROVENANCE.json` and `SBOM.spdx.json` before installation. The repository copy of `RELEASE-PROVENANCE.json` is explicitly an unbound source template; the packager replaces it inside each artifact. Publication packages are built only from a clean committed tree and their generated provenance is bound to that exact commit. The packager reads committed blobs directly so untracked Git attributes, replacement refs, filters, and working-tree line endings cannot alter the archive, and it refuses to overwrite tracked source. A mismatch means the artifact must not be installed.

Future GitHub releases are rebuilt from the published version tag, revalidated, smoke-tested, and uploaded without overwrite semantics by `.github/workflows/publish-release.yml`. Public repositories also receive GitHub/Sigstore build-provenance attestations for the ZIP and checksum sidecar. GitHub supports attestations for private repositories only on eligible GitHub Enterprise Cloud plans; after confirming eligibility, set the repository variable `ENABLE_PRIVATE_ATTESTATIONS` to `true`. Verify an attested asset with `gh attestation verify <archive.zip> --repo Unn0wn002/Solo-Suite-Codex` while authenticated to GitHub.

Dependabot monitors the hash-locked Python validation dependencies and every pinned GitHub Action weekly. CodeQL is scheduled for pushes and pull requests to `main` and a weekly scan. Public repositories run it automatically. For private repositories, first enable GitHub Code Security and then set the repository variable `ENABLE_PRIVATE_CODEQL` to `true`; until then, its analysis job safely skips.
