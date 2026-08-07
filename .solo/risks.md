# Risks — Solo Suite Enchance (website)

Populated from the 2026-08-07 full lifecycle audit (9-agent workflow, every
item independently verified, several adversarially re-checked). Owner column
follows the `.solo/` convention: gates and security/audit skills own this
file. Gates should read this before issuing a verdict.

## Critical

| Risk | Evidence | Owner | Status |
|---|---|---|---|
| `db/index.ts` throws at runtime the moment any code path calls `getDb()` — the D1 binding it requires is unprovisioned (`.openai/hosting.json`: `"d1": null`), with no graceful fallback. | `db/index.ts:5-13` | database-engineer / fullstack-developer | **Mitigated** 2026-08-07 — `hasDb()` safe-check added, throw behavior documented as intentional. Removal-vs-provision product decision still open — T2b. |

## High

| Risk | Evidence | Owner | Status |
|---|---|---|---|
| No CI/CD anywhere at the repository root — nothing gates a broken build, failing test, or security regression before `main`/deploy. | Confirmed absent by two independent searches, 2026-08-07 audit | devops-engineer | **Fixed** 2026-08-07 — `.github/workflows/ci.yml` added (lint+build+test, plus agent-platform validation). Not yet exercised by an actual push/PR. |
| Security-scan evidence is stale and **self-flagged non-fresh by the report that produced it** — the 2026-08-01 refresh attempt did not complete (npm audit `NOT_EXECUTED`; Semgrep blocked by Windows Application Control). | `docs/agent-audit/SECURITY_REPORT.md:86`; `docs/agent-audit/evidence/{npm-audit-summary,security-scanner-summary}.json` dated 2026-07-29 | security-reviewer | **Refreshed** 2026-08-07 — evidence now dated today. Along the way, found and fixed **4 real HIGH-severity CVEs** (see `decisions.md`). Trivy/Gitleaks/npm-audit now clean. Semgrep + pip-audit still can't execute (new, separate finding below) — the refresh is genuine but not 100% green. |
| No CSP or security headers anywhere in the deploy path. | `worker/index.ts`, generated `dist/server/wrangler.json`, `dist/client/_headers` (asset-cache only) all confirmed to lack them | security-reviewer / devops-engineer | **Partially fixed** 2026-08-07 — baseline headers (nosniff/frame-options/referrer-policy/permissions-policy) added and verified present on live responses. CSP deliberately deferred — needs a report-only pass, not a same-session guess — T23. |
| No monitoring, error-tracking, or analytics SDK wired into `app/` or `worker/index.ts` — a production incident would be invisible until a user reports it. | Grepped for 13 common SDK names across `app/` and `worker/`; zero real hits | devops-engineer | **Fixed** 2026-08-07 — dependency-free `console.error` + optional webhook wired into `worker/index.ts`, verified present in a real error path. No external account required; one env var activates a real provider later. |
| ~~Semgrep and pip-audit cannot execute~~ **RESOLVED 2026-08-07**: root cause was Python 3.12 having been fully uninstalled (replaced by 3.13, not moved) while `security-tools.lock.json` hash-pins wheels specifically for the 3.12 target. Fixed by installing Python 3.12.10 (user-approved) alongside 3.13 without touching PATH, then re-bootstrapping. Along the way found and fixed a real live CVE (`cryptography` 49.0.0, PYSEC-2026-3552) in the scanner venv itself. `npm run agent:security` now passes 6/6 with 0 findings. | `npm run agent:security` output, 2026-08-07 (post-fix): all 6 checks `PASSED`, 0 findings each | security-reviewer | **Closed** |
| A diagnostic `git stash`/`git stash pop` (run while investigating the token-report staleness, unrelated to security scanning) silently flipped several hash-pinned files from LF to CRLF via this repo's `core.autocrlf=true` setting, breaking their recorded SHA-256 checks — a self-inflicted issue found and fixed in the same session (see `decisions.md` and `tasks.md`'s T24 entry for the full account). Worth knowing for future sessions: **avoid `git stash` in this repo**, or explicitly set `core.autocrlf=false` for the duration if one is truly needed. | `sha256sum`/`file` output before and after the fix, 2026-08-07 | whoever runs git operations here | Closed, but the underlying `core.autocrlf=true` + hash-pinned-text-file combination remains a latent footgun for any future session |
| `platforms/{claude,antigravity}/tools/parity.py`'s `EXPECTED_TARGET_SKILL_COUNT = 186` doesn't match the 185 Codex skill files the original audit counted on disk. Not independently re-verified or fixed this session. | `EXPECTED_TARGET_SKILL_COUNT = 186` (both files, grepped 2026-08-07) vs. discovery brief's `find platforms/codex/plugins -name openai.yaml \| wc -l` = 185 | software-architect | Open — T26 (new finding, P3) |

## Medium

| Risk | Evidence | Owner | Status |
|---|---|---|---|
| `app/chatgpt-auth.ts` trusts an `oai-authenticated-user-email` header verbatim as identity; currently unreferenced/inert, but a spoofable-identity risk the moment it's wired into a route without an edge-level trust check. | `app/chatgpt-auth.ts:10-22` | security-reviewer | Open — see `prd.md` Open Q4 |
| No rollback or incident-response plan exists for this deployment. | Zero matches for "rollback"/"incident" in README/docs (case-insensitive, repo-wide) | devops-engineer / release manager | Open — T6 |
| No environment-variable documentation — `NEXT_PUBLIC_SITE_URL` silently falls back to `localhost:3000` in production if unset. | `app/layout.tsx:19-20`; no `.env.example` anywhere | technical-writer / devops-engineer | Open — T7 |
| No SEO baseline (`robots.txt`, `sitemap.xml`, structured data). | Confirmed absent repo-wide | SEO specialist | Open — T3 |
| `platforms/antigravity/tools/parity.py` is a byte-identical, unadapted copy of Claude's Codex-parity checker — it does not actually check anything Antigravity-specific despite `platforms/antigravity/parity/` implying it does. *(New finding, surfaced 2026-08-07 while fixing the parity README drift — not previously confirmed by the original audit, which only established the README text was wrong.)* | `diff platforms/claude/tools/parity.py platforms/antigravity/tools/parity.py` → empty (byte-identical) | software-architect | Open — T21 (decide: adapt or remove) |
| Semgrep is licensed LGPL-2.1-or-later — a copyleft obligation on a tool dependency, different in kind from the MIT/Apache-2.0 covering everything else in `THIRD_PARTY_NOTICES.md`. | `THIRD_PARTY_NOTICES.md:19`, `agent-platform/tooling/security-tools.lock.json:20` | technical-writer | Informational — confirm understood, no action required unless redistribution changes |

## Low

| Risk | Evidence | Owner | Status |
|---|---|---|---|
| Unused `gsap@3.15.0` dependency shipped with zero imports in `app/`. | Verified by repo-wide search | frontend-developer | Open — T11 |
| No accessibility polish beyond a handful of `aria-*` attributes — no skip link, no `:focus-visible`, no `prefers-reduced-motion` (the last one required by this repo's own `AGENTS.md` quality bar). | `app/globals.css` grepped for `prefers-reduced-motion` — zero hits | frontend-developer | Open — T8 |
| No unit/component/e2e tests of the site's actual interactive behavior (menu toggle, tab switching) — only a starter-artifact smoke test exists. | `tests/rendered-html.test.mjs` read in full | qa-engineer | Open — T9 |
| ~3MB of binary release artifacts committed to git under `platforms/codex/parity/artifacts/`. | `git ls-files` confirms tracked | devops-engineer | Pre-existing, informational only |

## Accepted / bounded (not open items)

- GSAP's `LicenseRef-GSAP-Standard-No-Charge` license (not a standard permissive SPDX license) — reviewed and accepted as a bounded product-use dependency per `docs/agent-audit/LICENSE_REPORT.md`. Ongoing obligation to stay within "package use" terms, not a defect.
- The six rejected third-party sources (Aider, Serena, Context7, code-review-graph, `protect-mcp`, `block-no-verify`) — verified remediated, no residual integration risk, per `agent-platform/security/high-risk-remediations.json`.
