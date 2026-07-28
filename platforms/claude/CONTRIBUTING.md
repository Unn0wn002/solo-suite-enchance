# Contributing to solo-suite

## Ground rules

- **Stdlib only** for helper scripts — no runtime dependencies, ever.
- **Evidence over claims**: README/marketplace counts and workflow claims are
  validated by `self_check.py` and `tests/test_inventory.py`; if you change
  reality, change the claims in the same commit.
- **Safety contracts are not optional**: commands that can write externally,
  mutate production, migrate data, submit forms, or touch secrets use
  `disable-model-invocation: true` and confirm before acting. Skills keep the
  exact two-key frontmatter contract and repeat the manual execution boundary
  in their body, so loading a skill for planning never authorizes an action.
  New commands and skills in those categories must follow `SECURITY.md`.
- Windows, macOS, and Linux all matter: use `${CLAUDE_PLUGIN_ROOT}` for
  helper paths, forward-slash-normalize glob output, and keep the test suite
  green on ubuntu-latest and windows-latest.

## Layout

- `plugins/<name>/.claude-plugin/plugin.json` — manifest ($schema,
  displayName, version, license, repository, homepage required)
- `plugins/<name>/commands/*.md` — slash commands (frontmatter: description,
  argument-hint, optional disable-model-invocation)
- `plugins/<name>/skills/<skill>/SKILL.md` — skills (frontmatter is exactly
  `name` plus `description`; execution safety belongs in the body and in the
  user-facing command's `disable-model-invocation` flag)
- `plugins/ai/skills/agent-room-templates/` — AgentRooms schema, validator,
  templates; `plugins/ai/agents/` — room agent definitions
- `tests/` — offline stdlib unittest suite (loopback fixtures only)

## Before you open a PR

```
python -m unittest discover -s tests -t . -v
python plugins/solo/skills/suite-integrity/scripts/self_check.py . -
python plugins/ai/skills/agent-room-templates/scripts/validate_rooms.py
claude plugin validate .            # when the Claude CLI is available
```

All four must pass. Bump the touched plugin versions, the marketplace
metadata version, and add a CHANGELOG entry (top section, `## x.y.z — date`).

## Releases

`release/build_release.py` (see CI) produces a local, unsigned release
candidate with one enclosing top-level folder, `SHA256SUMS`, `sbom.json`, and
`provenance.json`. Candidates are tested by installing the packaged ZIP into a
disposable project outside the repository and running helpers from a foreign
working directory. Do not publish a local candidate as canonical. Pushing the
reviewed `v<version>` tag triggers three isolated CI stages: a read-only build,
a keyless signer (`contents: read` plus `id-token: write`, with no repository
write permission), and a publisher (`contents: write`, with no checkout or OIDC
permission). Checksums are revalidated at every artifact boundary; the publisher
creates a draft, downloads every remote asset again, byte-compares and
signature-verifies it, promotes the release, and then verifies a fresh public
download before declaring success.

Repository administrators must restrict both the `release-signing` and
`release-publishing` GitHub environments to the intended `v*` tag pattern.
`release-signing` intentionally has no reviewer gate: its job can obtain only a
short-lived OIDC signing identity and cannot publish repository content.
`release-publishing` is the human approval boundary and must require the
intended reviewer(s) before its contents-write job can run. A single-maintainer
repository may allow self-review deliberately, but that repository-side choice
must be checked and recorded. Workflow YAML can name these environments, but it
cannot prove their deployment-branch/tag or reviewer settings. Treat an
unprotected or unverified publishing environment as a release-process blocker.

Before pushing any `v*` tag, a repository administrator must also enable
[GitHub Immutable Releases](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/establish-provenance-and-integrity/prevent-release-changes)
and configure an **active tag ruleset** whose include pattern is exactly
`refs/tags/v*` (or `~ALL`), whose exclude list is empty, and whose rules restrict
both tag updates and tag deletions. The ruleset must have no bypass actors; a
bypass would reopen the tag-movement window while a draft is being promoted.
GitHub
[omits `bypass_actors` unless the caller has ruleset write access](https://docs.github.com/en/rest/repos/rules?apiVersion=2026-03-10#get-a-repository-ruleset),
so store a fine-grained `RELEASE_SETTINGS_AUDIT_TOKEN` scoped only to this
repository with repository **Administration: write** in the protected
`release-publishing` environment. This elevated scope is required to prove that
the bypass list is empty. The no-checkout preflight exposes the token only to
one inline step and also requires GitHub to report
`current_user_can_bypass: never`; every request in that step uses `GET`. The
token is not available to the artifact download or release-write steps. Release
writes use the separate short-lived workflow token. The workflow never changes
repository settings. A missing secret, disabled immutable-release setting, or
nonconforming tag ruleset blocks the release.

For v1.0.27, publish in two reviewed stages from PowerShell. Supply the remote
HEAD OID you independently checked; the first helper refuses a changed remote,
verifies the complete candidate inventory/provenance, and pushes only
`release/v1.0.27` (never `main`):

```powershell
$remote = "https://github.com/unn0wn002/solo-suite.git"
$expectedRemoteHead = "<reviewed 40-hex remote HEAD OID>"
$result = & .\release\prepare-release-branch-v1.0.27.ps1 `
  -RemoteUrl $remote `
  -ExpectedRemoteHead $expectedRemoteHead `
  -ReleaseZip .\dist\solo-suite-plugin-v1.0.27.zip `
  -Sha256Sums .\dist\SHA256SUMS `
  -Provenance .\dist\provenance.json
$result
```

Review the pushed branch and its PR. Only after approving the exact
`APPROVED_COMMIT_OID=<40-hex>` printed above, create the annotated tag with the
second helper:

```powershell
& .\release\publish-approved-tag-v1.0.27.ps1 `
  -RemoteUrl $remote `
  -ApprovedCommitOid "<approved 40-hex OID>"
```

That helper requires `release/v1.0.27` still to equal the approved OID and
refuses an existing tag. The tag triggers the canonical CI rebuild; the local
candidate is not the canonical published artifact. Neither helper merges or
pushes `main`.

Right after cutting a release, regenerate the drift-guard snapshot from the
pristine canonical release tree:

```
python3 release/gen_release_inventory.py --root <extracted-release> \
    --out release/previous-release-inventory.json
```
