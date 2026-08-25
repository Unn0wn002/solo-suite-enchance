# Token and Context Report

Generated from measured file sizes, word counts, metadata counts, and profile composition. These are context-pressure indicators, not exact model-token savings.

## Estimated startup-context sources

| Source | Bytes | Words | Loading behavior |
| --- | ---: | ---: | --- |
| `AGENTS.md` | 3310 | 406 | Startup instruction surface |
| `CLAUDE.md` | 546 | 79 | Startup instruction surface |
| Canonical skill metadata | 12748 description characters | 39 skills | Metadata first; bodies on demand |

## Duplicate descriptions

- Exact duplicate canonical descriptions: 0.
- Cross-platform mirrors are generated copies and should not be loaded together by one platform.

## Large instruction and reference files

| File | Bytes | Words |
| --- | ---: | ---: |
| `.agents/skills/code-review-and-quality/SKILL.md` | 21033 | 2990 |
| `.agents/skills/security-and-hardening/SKILL.md` | 21002 | 2735 |
| `.agents/skills/idea-refine/examples.md` | 20284 | 3008 |
| `.agents/skills/doubt-driven-development/references/orchestration-patterns.md` | 18201 | 2542 |
| `.agents/skills/doubt-driven-development/SKILL.md` | 16982 | 2424 |
| `.agents/skills/test-driven-development/SKILL.md` | 16967 | 2219 |
| `.agents/skills/performance-optimization/SKILL.md` | 15639 | 1993 |
| `.agents/skills/interview-me/SKILL.md` | 14849 | 2323 |
| `.agents/skills/git-workflow-and-versioning/SKILL.md` | 14563 | 1984 |
| `.agents/skills/browser-testing-with-devtools/SKILL.md` | 14529 | 1886 |

## Large generated files

- `graphify-out/`, dependencies, build output, coverage, media, caches, and repository dumps are excluded through `.graphifyignore`, `.repomixignore`, and `.claudeignore`.
- Generated Graphify and Repomix output is not a startup instruction source.

## MCP tool-count risks

- Root MCP activation files: 0.
- Repository files with MCP in the filename outside dependencies/temp: 0; none detected.
- Exposing multiple broad MCP servers increases metadata, permission, and prompt-injection surface. Profiles therefore name external tools but do not activate servers.

## Recommended active profile sizes

| Profile | Roles | Enabled skills | Optional skills | External tools | Target max active skills |
| --- | ---: | ---: | ---: | ---: | ---: |
| `analytics` | 1 | 1 | 1 | 0 | 2 |
| `architecture` | 1 | 1 | 4 | 1 | 4 |
| `backend` | 1 | 1 | 3 | 0 | 4 |
| `database` | 1 | 1 | 3 | 0 | 4 |
| `design` | 1 | 1 | 2 | 0 | 3 |
| `devops` | 1 | 1 | 2 | 1 | 3 |
| `documentation` | 1 | 1 | 1 | 1 | 2 |
| `frontend` | 1 | 1 | 3 | 0 | 4 |
| `full-audit` | 2 | 3 | 2 | 2 | 4 |
| `gsap-animation` | 1 | 1 | 2 | 0 | 3 |
| `planning` | 1 | 1 | 2 | 0 | 3 |
| `qa` | 1 | 1 | 2 | 0 | 3 |
| `release` | 3 | 3 | 1 | 2 | 4 |
| `security` | 1 | 1 | 2 | 3 | 3 |

## Suggested token-reduction actions

- Start with `planning` for new work, then switch to the single phase profile that owns the next artifact.
- Load role definitions, complete skill bodies, and references only after metadata routing selects them.
- Keep Graphify for relationships, bounded native search for symbols, primary official sources for current docs, and Repomix for bounded exports.
- Keep Aider, Serena, Context7, and code-review-graph out of profiles and activation surfaces; their audit records remain evidence-only.
- Do not place copied READMEs, full repository maps, source clones, or broad MCP inventories in startup instructions.
- Re-run this measured report after adding skills or profiles; do not claim exact token savings without tokenizer-based measurement for the actual host/model.
