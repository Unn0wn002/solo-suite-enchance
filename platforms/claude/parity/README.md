# Claude ↔ Codex capability parity

`capabilities.json` is the deterministic parity contract for the Solo Suite
adapter. The Claude checkout is canonical: it owns the 19 plugin IDs, 126
command definitions, 80 specialist skills, shared helper files, and AgentRoom
source files. The Codex checkout is regenerated from that source and is allowed
only the adapter differences declared in the manifest.

`capabilities.json` is **generated, never hand-edited**. The counts above and
the `EXPECTED_*` constants in `tools/parity.py` are literal drift guards, and
`tests/test_parity_contract.py` fails closed if either goes stale, if a recorded
`source_sha256` stops matching disk, or if the committed manifest differs from a
fresh generation.

Generate the contract after changing the canonical source:

```text
python tools/parity.py generate --source <solo-suite-v1.0.27-release-work>
```

Then check the adapter:

```text
python tools/parity.py --check \
  --source <solo-suite-v1.0.27-release-work> \
  --target <solo-suite-codex-v1.0.27>
```

The check compares against a Codex adapter checkout, which is a separate
downstream distribution and is not part of this repository. It reports failures
whenever the canonical tree has moved ahead of the last published adapter; that
is expected between releases and is resolved by regenerating the adapter, not by
editing this contract.

The checker is standard-library-only and fails closed. It verifies the exact
command-map IDs/paths and explicit-only policy, normalized specialist bodies,
byte hashes for helper/schema files, all 159 Codex `openai.yaml` policies, and
the byte-exact Claude AgentRoom archive under `parity/claude-rooms`.

Two skills are platform adapters rather than byte-identical copies:

* `ai:agent-room-templates` — Codex has a native runner, trust journal, and
  state machinery. The canonical Claude tree is archived for review.
* `solo:suite-integrity` — Codex validates Codex manifests and installed
  plugin metadata, so its implementation is intentionally native.

The only other permitted differences are the Codex-only
`full-team:full-team-orchestrator` skill and the six gate runtime support files
listed in `capabilities.json`. Any additional skill, helper, policy, or archive
file is a parity failure.
