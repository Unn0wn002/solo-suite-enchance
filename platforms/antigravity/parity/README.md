# Claude → Antigravity distribution parity

This directory is currently a **copy of the Claude ↔ Codex parity tooling**
(`README.md`, `capabilities.json`, and `../tools/parity.py`) and does not
describe or check Antigravity-specific parity. `../tools/parity.py` is
byte-identical to `platforms/claude/tools/parity.py`: its docstring, CLI, and
checks still reference "the Codex adapter," a `solo-suite-codex-*` target
checkout, and Codex-specific mechanics (e.g. "all 159 Codex `openai.yaml`
policies") that do not exist in this distribution. Running `generate`/`--check`
here would not validate anything about the Antigravity tree — treat this
subdirectory as inherited scaffolding, not an active parity contract, until it
is rewritten (or removed) for an Antigravity-specific target.

## What is actually true about Claude ↔ Antigravity today (observed, not yet enforced by any test)

A full recursive comparison of `platforms/claude/` against `platforms/antigravity/`
(excluding `__pycache__`) shows the two trees are near byte-identical. The only
differences found:

1. **`plugin.json` at each Antigravity plugin root** (19 files, absent from the
   equivalent Claude plugin roots) — content is identical to the
   `.claude-plugin/plugin.json` both platforms also carry. This is an
   install-path convention for Antigravity's Gemini-config loader (see
   `../ANTIGRAVITY.md`: installed under `~/.gemini/config/plugins/`), not a
   functional divergence.
2. **`plugins/project/skills/capability-routing/SKILL.md` genuinely differs in
   content** — the one real behavioral drift found anywhere in the tree.
   Claude's version has an explicit `## Inputs` section, numbered
   `## Routing rules`, and a `## Handoff contract` section; Antigravity's is a
   condensed paragraph lacking that structure. Whether this divergence is
   intentional is undocumented — worth a deliberate decision either way.
3. **`capabilities.json` differs from Claude's** — expected, since it is
   per-target generated output, but see the caveat above about what actually
   generates and consumes it for an Antigravity target today.
4. **`README.md` differs** (branding/install instructions — this file).
5. **Antigravity-exclusive files**: `../ANTIGRAVITY.md`, `../antigravity-manifest.json`.

Both distributions currently ship **19 plugins, 80 specialist skills, and 126
slash commands** — verified by direct filesystem count and cross-checked
against `../antigravity-manifest.json` and `../ANTIGRAVITY.md` (both already
carry the current, correct figures as of this fix).

## If Antigravity-specific parity protection is wanted

No Antigravity-aware drift guard exists today: a change that silently
desynchronizes the Claude and Antigravity trees beyond the two documented
deltas above would not be caught by any test in this distribution. Two options,
neither implemented yet:

- **(a)** Adapt `../tools/parity.py` into a genuine Claude → Antigravity
  checker. The right shape is different from the Codex checker's
  adapter-with-declared-waivers model — Antigravity's actual relationship to
  Claude is "near-identical mirror plus two documented deltas," so a simple
  `diff`-based checker asserting *only* the deltas above are the sole
  differences would be both simpler and more accurate than reusing the Codex
  logic wholesale.
- **(b)** Remove this vestigial `parity/` subdirectory from the Antigravity
  distribution entirely if no Antigravity-specific check is planned, so it
  stops implying a contract that doesn't currently exist.

*(This file was corrected 2026-08-07 as part of a documentation-accuracy pass;
the prior version was a verbatim, semantically wrong copy of
`platforms/claude/parity/README.md` describing Codex mechanics inside the
Antigravity distribution.)*
