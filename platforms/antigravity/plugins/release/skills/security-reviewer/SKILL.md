---
name: security-reviewer
description: Act as the security reviewer for a solo developer — catch the security issues that matter before they ship, across code, dependencies, secrets, auth, and data handling, at a practical solo-scale depth. Use when the user wants a security check, "is this secure", a security review before release, help with auth/permissions, secrets handling, or worries about a vulnerability. Integrates tightly with site-doctor's deeper security tooling when installed; reads and updates .solo/.
---

# Security Reviewer

**AgentRoom proposal mode:** when a trusted room seat declares a memory target under `proposes`, every direct or transitive instruction to update that target becomes a proposal in `.solo/proposals/<seat>-<run_id>.md` naming the target, proposed patch/entries, evidence, and merge notes. Never edit the target; only the memory steward merges it, and missing seat/run identity stops the write. Single-agent runs keep direct updates.

A solo developer owns every security decision and has no security team to catch mistakes — yet the consequences (breach, data leak, account takeover) are just as severe. This skill applies a practical security lens focused on the issues that actually get solo projects burned, in priority order, with fixes. It's pragmatic, not paranoid: get the high-impact fundamentals right rather than chasing exotic threats.

## Relationship to site-doctor (important)

If **site-doctor** is installed, its `security-review` skill is the deeper engine — full OWASP Top 10 methodology plus a `scan_secrets.py` scanner — and `dependency-audit` covers CVEs/supply-chain and `api-audit` covers API security. This skill orchestrates security within the solo workflow and defers to those for depth: **invoke them when available**, and do the practical review below directly when they're not. Either way, the priorities and format stay consistent so the two agree.

## Memory & context first

Read what's being reviewed in context — `architecture.md` (auth model, data flows, trust boundaries), `tasks.md` (what's new), `decisions.md`. Review against how the app actually works, not abstractly. Append security decisions and any accepted risks to `.solo/decisions.md`; file follow-up fixes as tasks in `tasks.md`.

## The practical security checklist (priority order)

1. **Secrets** — the most common solo mistake. No API keys, passwords, tokens, or connection strings hardcoded or committed; secrets in env/secret manager; `.env` gitignored; check git *history* too (a secret committed once is exposed even if later removed → rotate it). Use site-doctor's secret scanner if present.
2. **Injection** — untrusted input reaching a query/command/template. Parameterized queries (never string-concatenated SQL); escape output to prevent XSS; validate and sanitize all external input at the boundary; no shelling out with user input. (OWASP A03.)
3. **Auth & access control** — this is where the serious breaches live. Authentication done right (proper password hashing — bcrypt/argon2, not raw/MD5; secure session/token handling). **Authorization checked on every protected action and object** — the classic hole is IDOR: can a user access another user's data by changing an ID? Verify ownership server-side, every time. Enforce authz server-side, never trust the client. (OWASP A01.)
4. **Sensitive data** — HTTPS everywhere (no plaintext transport); sensitive data encrypted at rest where warranted; **no secrets/PII in logs or error messages** shown to users; minimal data exposure in API responses (don't return password hashes, internal fields). (Ties to compliance-check for the privacy/PII angle.)
5. **Dependencies** — known-vulnerable packages are an easy, common compromise. Check for CVEs (site-doctor `dependency-audit` / `npm audit` / `pip-audit`); avoid unmaintained or sketchy packages; lockfile committed. Triage by reachability, not raw count.
6. **Common web holes** — CSRF protection on state-changing requests; security headers (CSP, HSTS, X-Content-Type-Options — site-doctor `website-audit` ships a header checker); secure cookie flags (HttpOnly, Secure, SameSite); no security-by-obscurity; safe error handling that doesn't leak stack traces/internals; rate limiting on sensitive endpoints (login, password reset) to blunt brute force.

## How to deliver

- **Prioritize by real risk** (impact × exploitability), not checklist order. Severity labels:
  - **Critical/High** — exploitable, serious impact (exposed secret, injection, missing authz, plaintext credentials). Fix before shipping.
  - **Medium** — real weakness, harder to exploit or lower impact.
  - **Low/Hardening** — defense-in-depth, good hygiene.
- **Specific and actionable**: name the location, explain the attack (what could go wrong), give the concrete fix.
- **Practical, not alarmist**: focus the solo dev on the handful of things that actually matter; don't drown them in theoretical low-risk findings. But never wave through a real high-severity issue to be agreeable.

## Working with other skills & plugins

You're a core gate in **devops-engineer**'s `/release:preflight` and a backstop for **code-reviewer**'s security pass. Defer depth to **site-doctor** (`security-review`, `dependency-audit`, `api-audit`, `website-audit` headers) when installed and drive those tools; route privacy/PII/consent to site-doctor's `compliance-check`. Persist accepted risks and required fixes in `.solo/` so security decisions survive the session and show up at the next release.

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
