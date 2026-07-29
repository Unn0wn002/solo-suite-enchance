# Claude v1.0.27 to Codex v1.0.27 parity

The parity baseline is the public Solo Suite Claude `v1.0.27` release, pinned
to an annotated tag object and its peeled commit:

| material | pinned value |
| --- | --- |
| tag | `v1.0.27` |
| tag object | `7495f3ac2c4da972f0f4435028ed468da3135475` |
| commit | `a31be037edaee840479977585e33ac0e57088cb4` |
| tree | `0517f8f10a5406f227eb3177b188b2b1103fcf47` |
| tag signature | not present (`base_tag_signed=false`) |
| base archive SHA-256 | `e6ade834f95695766af5655a2444d49096ba3b0c49b4f1f726a119ef30848caa` |
| base provenance SHA-256 | `a6d59e91229d38dfb284c130957c138a2718912dcd23fea4917670f9b875633b` |

The base archive and the exact public provenance record downloaded from the
release are checked in under `parity/artifacts/`. The archive was independently
rebuilt twice from the clean pinned Git tree and reproduced its digest. The
provenance JSON is the public release CI record (not a locally rebuilt record),
and its digest, artifact digest, commit, tree, and `source_dirty=false` binding
are checked before use. The archive is independently downloadable from the
[Claude v1.0.27 release](https://github.com/Unn0wn002/solo-suite/releases/tag/v1.0.27).
The unsigned tag is an explicit provenance caveat; the commit/tree and release
bytes remain fully pinned and checked.

## Declared adapter overlay

The Codex canonical source is
`solo-suite-plugin-v1.0.27-codex-v1.0.27-parity-source.zip`. It is not claimed to
be byte-identical to the unmodified Claude archive. The checked-in working-tree
manifest records **19 plugins, 126 commands, 80 specialist skills, and 185
target skills** and is pinned separately from the historical archive manifest.
It also records explicit body-adapter waivers for reviewed Codex-native wrappers
and the SEO specialist/command merges; those waivers do not bypass source
hashes, target presence, frontmatter, inventory closure, or helper-file checks.

The historical published overlay archive still declares ten changed paths:

* four Codex-native command sources (`full-team:verify`, release deploy and
  rollback plans, and `solo:full-team-dev`);
* three reviewed gate-policy merges (the reviewer skill, policy module, and
  evidence checker);
* the hardened parity checker;
* the regenerated `parity/capabilities.json`; and
* the embedded `PARITY-SOURCE.json` provenance record.

The historical archive and the current working tree are two different parity
layers. The archive verifier attests the ten published overlay paths and the
historical capability digest. When the target carries the newer working-tree
manifest, it reports `WORKING-TREE PARITY DEFERRED` rather than incorrectly
claiming that the newer target is byte-identical to that historical archive.
The two
intentional platform skill waivers are still
`ai:agent-room-templates` (Codex's executable runner) and `solo:suite-integrity`
(Codex manifest/install validation), and the Codex-only
`full-team:full-team-orchestrator` skill remains explicitly declared in
`capabilities.json`.

## Reproduce and verify

From this checkout, using the bundled base artifacts:

```text
python tools/build_canonical_source.py \
  --base-archive parity/artifacts/solo-suite-plugin-v1.0.27.zip \
  --base-provenance parity/artifacts/solo-suite-plugin-v1.0.27.provenance.json \
  --output parity/artifacts/solo-suite-plugin-v1.0.27-codex-v1.0.27-parity-source.zip

python tools/verify_source_overlay.py \
  --base-archive parity/artifacts/solo-suite-plugin-v1.0.27.zip \
  --base-provenance parity/artifacts/solo-suite-plugin-v1.0.27.provenance.json \
  --canonical-source-archive parity/artifacts/solo-suite-plugin-v1.0.27-codex-v1.0.27-parity-source.zip \
  --target .

python tools/verify_source_overlay.py --canonical-only \
  --canonical-source-archive parity/artifacts/solo-suite-plugin-v1.0.27-codex-v1.0.27-parity-source.zip \
  --target .
```

The first two commands attest the historical archive; a target that uses the
declared working-tree digest receives an explicit deferred message. Run the
capability checker separately for a live Claude snapshot:

```text
python tools/parity.py check \
  --source <current-claude-source> \
  --target .
```

To authenticate the public base rather than use the checked-in copy, run
`tools/verify_source_overlay.py --fetch-public-base` with the canonical archive
argument. Every download URL and redirect is restricted to the GitHub release
host set, and the provenance digest, commit, tree, and clean-source assertion
are checked before the overlay is compared.

`tools/generate_source_overlay_manifest.py` derives the published overlay
manifest from the two archives and fails closed on an undeclared or missing
difference. It is used when the pinned source or an intentional adapter
overlay changes; do not edit the archived ten-path delta by hand.
`tools/parity.py generate` and `tools/parity.py check` remain the
capability-level contract. The checker supports both the 18-plugin historical
source profile and the 19-plugin working-tree profile; a live source update
must be regenerated and reviewed before its digest is promoted to the
working-tree manifest.

The checked-in reference, overlay manifest, and archive digest are recorded in
[`canonical-source.json`](canonical-source.json) and
[`source-overlay-manifest.json`](source-overlay-manifest.json).

The deterministic install ZIP intentionally omits nested archives and checksum
sidecars. The separately attested Codex parity-source archive under
`parity/artifacts/` is a validation input and release asset, not a second copy
embedded inside the install package; verify its digest independently before
using it as the canonical comparison source.
