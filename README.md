# Solo Suite Enchance

Solo Suite Enchance is a website-first developer operating system that brings a
full product team workflow to Claude, Codex, and Antigravity. The current
website is the public-facing command center; the repository also contains the
validated platform distributions that power larger projects later.

The suite is built around one shared project-memory contract (`.solo/`) and a
repeatable loop:

`intake → spec → architecture → design → build → review → test → audit → gate → release → document`

## What is in this repository

| Surface | Location | Current state |
| --- | --- | --- |
| Website | `app/` | Production-ready Vinext/Sites landing experience |
| Claude distribution | `platforms/claude/` | 19 plugins, 80 skills, 126 slash commands |
| Codex distribution | `platforms/codex/` | 19 plugins, 185 skills, 126 migrated workflows |
| Antigravity distribution | `platforms/antigravity/` | 19 plugins, 80 skills, 126 slash commands |
| Graphify map | `graphify-out/` | Code graph, report, and historical refreshes |
| Learned capability map | `capability-inventory.json` + `CAPABILITY_ROADMAP.md` | Upstream-informed routing and implementation ideas |
| Complete capability catalog | `CAPABILITY_CATALOG.md` | Every native skill, plugin, command, and learned-role mapping |

The platform folders were copied from the three read-only source checkouts and
kept isolated so their native manifests and validation tooling remain intact.
The website is focused on advanced website delivery today, while the workflow
profiles already cover SaaS applications, e-commerce, internal applications,
APIs, and packages.

## Current validation status

The platform distributions are structurally healthy, but “fully working” means
more than a manifest check. The evidence currently available is:

- Claude: native self-check passes (14/14) and 156 targeted tests pass.
- Antigravity: native self-check passes (14/14) and 156 targeted tests pass.
- Codex: self-check passes (6/6), portable validation passes for all 19 plugins,
  all four AgentRooms validate, and 99 targeted tests pass.
- Codex’s full AgentRoom integration suite contains long-running end-to-end
  cases; those were not treated as passed when they exceeded the bounded local
  test window. Treat this as “validated structure + selected runtime checks,”
  not a blanket production guarantee.

Run the checks from each platform folder:

```powershell
# Claude or Antigravity
python plugins\solo\skills\suite-integrity\scripts\self_check.py . -
python plugins\ai\skills\agent-room-templates\scripts\validate_rooms.py --suite .
python -m unittest tests.test_inventory tests.test_parity_contract tests.test_validate_rooms tests.test_output_contract tests.test_documentation_truth tests.test_readonly_audit tests.test_trigger_routing

# Codex
python plugins\solo\skills\suite-integrity\scripts\self_check.py . -
python plugins\ai\skills\agent-room-templates\scripts\validate_rooms.py --suite .
python tools\validate_plugins.py --official-if-available
python -m unittest tests.test_self_check tests.test_validate_plugins tests.test_command_skills tests.test_validate_rooms tests.test_full_team_preflight tests.test_gate_contracts tests.test_site_doctor_helpers tests.test_parity
```

## Add it to Claude Code

From Claude Code, register the Claude marketplace folder:

```text
/plugin marketplace add C:\path\to\Solo Suite Enchance\platforms\claude
/plugin install solo@solo-suite
/plugin install project@solo-suite
/plugin install design@solo-suite
/plugin install dev@solo-suite
/plugin install test@solo-suite
/plugin install release@solo-suite
/plugin install docs@solo-suite
/plugin install site-doctor@solo-suite
/plugin install stack@solo-suite
/plugin install git@solo-suite
/plugin install spec@solo-suite
/plugin install repo@solo-suite
/plugin install security@solo-suite
/plugin install browser@solo-suite
/plugin install gate@solo-suite
/plugin install ai@solo-suite
/plugin install growth@solo-suite
/reload-plugins
```

Install `solo` first because it owns the shared `.solo/` memory lifecycle. Use
`/solo:start-session` to orient the project, `/solo:run-cycle` for a focused
task, and `/solo:full-team-dev` for the complete website-to-release workflow.

## Add it to Codex

From a PowerShell terminal:

```powershell
codex plugin marketplace add "C:\path\to\Solo Suite Enchance\platforms\codex"
codex plugin add solo@solo-suite-codex
codex plugin add project@solo-suite-codex
codex plugin add design@solo-suite-codex
codex plugin add dev@solo-suite-codex
codex plugin add test@solo-suite-codex
codex plugin add release@solo-suite-codex
codex plugin add docs@solo-suite-codex
codex plugin add site-doctor@solo-suite-codex
codex plugin add stack@solo-suite-codex
codex plugin add git@solo-suite-codex
codex plugin add spec@solo-suite-codex
codex plugin add repo@solo-suite-codex
codex plugin add security@solo-suite-codex
codex plugin add browser@solo-suite-codex
codex plugin add gate@solo-suite-codex
codex plugin add ai@solo-suite-codex
codex plugin add growth@solo-suite-codex
codex plugin add seo@solo-suite-codex
codex plugin add full-team@solo-suite-codex
```

Codex exposes the workflows as skills, not Claude slash commands:

```text
$solo-start-session
$dev-implement-feature
$site-doctor-full-checkup
$gate-production-ready
$full-team-orchestrator
```

Use `platforms\codex\COMMAND-MAP.md` for the complete legacy-command to Codex
skill mapping. Start a new Codex task after installing or updating plugins so
the new skills are loaded.

Use `$capability-routing` before a large task to select the smallest
phase-owned set of plugins and skills. It writes `.solo/capability-plan.md`.

## Install the recommended repository-intelligence core

For architecture-aware and token-efficient work, use the approved tools and
local fallbacks after cloning:

- Graphify for architecture and cross-file relationships;
- bounded native search for symbols and references;
- primary official documentation for current library guidance;
- Repomix for filtered repository snapshots.

Aider, Serena, Context7, and code-review-graph are retained only as rejected
audit evidence and are not installed or activated.

Follow [`CORE_REPOSITORY_INTELLIGENCE.md`](CORE_REPOSITORY_INTELLIGENCE.md).
The guide covers Claude, Codex, and Antigravity. Graphify installation is
explicit, project-local, and user-controlled; cloning this repository never
silently changes global agent configuration.

```powershell
node scripts\check-core-tooling.mjs
```

The check is read-only and reports which optional tools are available.

## Add it to Antigravity

Antigravity does not expose a single standardized marketplace CLI in this
checkout. The adapter is therefore installed by copying the validated plugin
and skill trees into the Google/Gemini configuration directories:

```powershell
$source = (Resolve-Path "C:\path\to\Solo Suite Enchance\platforms\antigravity").Path
$config = Join-Path $HOME ".gemini\config"
New-Item -ItemType Directory -Force (Join-Path $config "plugins") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $config "skills") | Out-Null
Copy-Item "$source\plugins\*" (Join-Path $config "plugins") -Recurse -Force
Get-ChildItem "$source\plugins" -Directory | ForEach-Object {
  $skills = Join-Path $_.FullName "skills"
  if (Test-Path $skills) {
    Copy-Item "$skills\*" (Join-Path $config "skills") -Recurse -Force
  }
}
```

Restart Antigravity after copying. The adapter keeps the Claude-compatible
`/plugin:*` command names and the same `.solo/` project memory convention.
`platforms\antigravity\ANTIGRAVITY.md` documents the target directories and
platform-specific assumptions.

Use `/project:capability-map` before a large task to select the smallest
phase-owned set of plugins and commands.

## Website development

The website lives in `app/` and deploys through the Sites project configured in
`.openai/hosting.json`.

```powershell
npm.cmd ci
$env:WRANGLER_LOG_PATH = ".wrangler\wrangler.log"
npx.cmd vinext dev
npx.cmd vinext build
```

The `npm run dev` and `npm run build` scripts use POSIX-style environment
assignment for CI/Linux. On Windows, use the explicit `npx.cmd` commands above.

## Repository layout

```text
app/                         Solo Suite Enchance website
platforms/claude/            Claude marketplace distribution
platforms/codex/             Codex-native distribution
platforms/antigravity/       Antigravity adapter distribution
capability-inventory.json    Exact plugin, skill, command, and routing inventory
CAPABILITY_ROADMAP.md        Upstream-informed implementation ideas and phases
graphify-out/                Persistent code graph and reports
public/og.png                Social preview card
```

## Scope and roadmap

The current website surface is optimized for advanced website projects. The
platform distributions already provide the larger-project workflow primitives:
shared memory, stack intake, AgentRooms, security and quality gates, release
evidence, browser QA, SEO, and documentation. The next expansion is to add
project-specific dashboard routes and authenticated workspace state without
changing the platform contracts.
