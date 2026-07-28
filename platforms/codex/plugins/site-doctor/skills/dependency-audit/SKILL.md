---
name: dependency-audit
description: Audit a project's dependencies — known vulnerabilities (CVEs), outdated packages, license compliance, unmaintained or abandoned packages, supply-chain risks (typosquatting, dependency confusion, compromised packages), transitive dependency bloat, and lockfile health. Use whenever the user wants to review dependencies, check for vulnerable/outdated packages, audit licenses, assess supply-chain risk, "are my npm/pip packages safe", or clean up their dependency tree. Complements security-review (app code) and deployment-review (CI/CD).
---

# Dependency Audit

Most of the code shipping in a modern app isn't the app's own — it's dependencies, and their dependencies, often hundreds deep. That's where a lot of risk lives: known CVEs, abandoned packages, incompatible licenses, and increasingly, supply-chain attacks. Audit what's pulled in, what's risky, and what should change — prioritized by real exposure, not raw vulnerability counts.

## Run the audit tools first

```bash
npm audit --json            # Node — or: pnpm audit / yarn npm audit
pip-audit                   # Python (pip install pip-audit) — or: safety check
```
Plus the manifest reader script for a cross-ecosystem inventory and staleness/lockfile check:
```bash
python3 "<skill-root>/scripts/check_deps.py" /path/to/project
```
> **Running helpers:** `<resolved-plugin-root>` is set by Codex to this plugin's installed root, so the command works from any working directory. If `python3` is not on PATH, use `python` (macOS/Linux/Windows) (Windows launcher) instead.

Stdlib-only; parses package.json/requirements/lockfiles, reports direct vs transitive counts, pinning, and lockfile presence. Use the ecosystem's own audit tool for CVE data (it has the live advisory database) and the script for structure.

## 1. Known vulnerabilities (CVEs) — but triage by reachability

- Run the ecosystem audit tool; it maps installed versions against advisory databases.
- **Triage, don't panic on the count**: a "47 vulnerabilities" number is meaningless until triaged. Rank by:
  - **Severity** (critical/high first).
  - **Reachability** — is the vulnerable code path actually used? A critical CVE in a dev-only or unused transitive dependency is lower priority than a high in your request-handling path. (This is where raw `npm audit` output misleads — many are transitive and unreachable.)
  - **Exploitability in your context** — does the vulnerable function receive untrusted input? (Ties to security-review.)
- **Fix path**: update to the patched version; if a direct dep, bump it; if transitive, update the parent or use overrides/resolutions to force a safe version. Note when a fix requires a breaking major upgrade (plan it, don't auto-apply).
- Distinguish **production vs dev** dependencies — dev-only vulns (build tools, test frameworks) matter less for runtime security but can still be a CI supply-chain risk (see deployment-review).

## 2. Outdated packages

- **How far behind**: patch (safe, do it), minor (usually safe, do it), major (breaking, plan it). Chronically outdated majors accumulate risk and make future updates harder.
- **Unmaintained / abandoned**: packages with no releases in years, archived repos, or a single unresponsive maintainer are a risk — no security fixes coming, and a prime target for takeover. Flag these and consider replacements.
- **Deprecated packages**: explicitly deprecated by their authors (npm flags these) — migrate off.
- Balance: not every package needs to be bleeding-edge, but security-relevant ones and abandoned ones need action. Keeping reasonably current makes each update small instead of a scary big-bang later.

## 3. License compliance

- **Every dependency's license** identified (including transitive). Incompatible or risky licenses can create legal obligations or block commercial use:
  - **Permissive** (MIT, Apache-2.0, BSD, ISC) — generally fine.
  - **Copyleft** (GPL, LGPL, AGPL) — impose obligations; **AGPL** especially can require open-sourcing your own code if you distribute or even network-serve it. A copyleft dep in a proprietary product is a real finding.
  - **No license / unclear** — legally you may have no right to use it; flag.
- Check for license *changes* between versions (some packages relicense). This isn't legal advice — flag concerns and recommend counsel for anything consequential (ties to compliance-check's framing).

## 4. Supply-chain risk (the fastest-growing threat)

- **Typosquatting**: dependencies whose names are near-misses of popular packages (`expresss`, `lodahs`) — could be malicious impersonators. Verify unfamiliar package names resolve to the intended, reputable package.
- **Dependency confusion**: private/internal package names that could be resolved from a public registry instead — an attacker publishes a public package with your internal name and higher version. Ensure scoping/registry config prevents this (ties to deployment-review's CI security).
- **Compromised packages / install scripts**: packages running `postinstall` scripts (a common malware vector), recently transferred maintainership, or sudden suspicious version bumps. Be wary of packages that execute code on install.
- **Integrity**: lockfile with integrity hashes committed and verified in CI so you install exactly what you audited; `npm ci`/frozen installs rather than resolving fresh (again, deployment-review).
- **Minimize the attack surface**: fewer dependencies = less risk. Flag trivial one-line packages, duplicate packages doing the same job, and unused dependencies that can be removed.

## 5. Dependency tree health

- **Lockfile present and committed** — non-negotiable for reproducible, auditable installs. Its absence means everyone installs potentially different versions.
- **Transitive bloat**: an enormous dependency tree for a small app is both a risk surface and a performance/build cost (and ties to bundle size in performance-tuning). Identify heavy or unnecessary sub-trees.
- **Duplicate versions**: the same package at multiple versions in the tree (bloat and potential inconsistency); dedupe where possible.
- **Unused dependencies**: declared but not actually imported — remove them (less surface, cleaner tree). Conversely, undeclared dependencies (used but relying on transitive resolution) are fragile — declare them.

## Report format

Shared audit structure (Summary → Scorecard → Findings → Fix order), grouped **Vulnerabilities / Outdated / Licenses / Supply-chain / Tree health**. Each finding names the package and version, the specific risk, and the fix (the version to move to, the replacement, the removal, the override). **Rank by real exposure, not the raw audit count** — a reachable critical CVE or an AGPL dependency in a proprietary product tops the list; unreachable transitive lows are batched. Note which fixes are safe-now (patch/minor) vs need-planning (breaking majors). Route reachability/exploitability questions to security-review and CI-integrity to deployment-review.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `$solo-next-step` and `$release-preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `$solo-start-session` restores project context at the start (reading `.solo/`), and `$solo-end-session` saves progress, blockers, decisions, and the next task at the end. `$solo-run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `$stack-intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `$stack-intake` first. For vendor-specific depth, the stack plugin adds `$stack-audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
