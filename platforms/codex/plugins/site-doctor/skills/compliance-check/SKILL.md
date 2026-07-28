---
name: compliance-check
description: Review a website for common privacy and data-protection compliance gaps — GDPR/CCPA/UK-GDPR obligations, cookie consent and tracker behavior, privacy policy presence and adequacy, data collection and retention practices, user rights (access/deletion/opt-out), and third-party data sharing. Use whenever the user asks about GDPR, CCPA, privacy compliance, cookie consent/banners, "is my site legally compliant", privacy policy review, or handling of personal data. This surfaces gaps and points to obligations — it is not legal advice.
---

# Compliance Check

This skill surfaces likely compliance gaps and explains the obligations behind them so the user knows what to fix and what to take to counsel. **It is not legal advice** — regulations are jurisdiction-specific, fact-dependent, and change; state that plainly and recommend a lawyer for anything consequential. What this skill does well is catch the common, concrete, technical gaps that trip most sites.

## Setup

Determine what personal data the site collects (accounts, forms, analytics, cookies, payment, location), who the users are (EU/UK → GDPR; California → CCPA/CPRA; etc. — obligations follow the *users'* location, not just the company's), and read the site's cookie/consent behavior and privacy policy. Run the cookie/tracker scanner to see what actually fires.

## Run the tracker scan

```bash
python3 "<skill-root>/scripts/scan_trackers.py" https://example.com
```
> **Running helpers:** `<resolved-plugin-root>` is set by Codex to this plugin's installed root, so the command works from any working directory. If `python3` is not on PATH, use `python` (macOS/Linux/Windows) (Windows launcher) instead.

Stdlib-only. Fetches the page and flags cookies set, third-party script/pixel origins, and common analytics/ad trackers — the factual basis for "what's actually collecting data here." Note: it sees server-set cookies and static third-party references; client-set cookies and dynamically injected tags need a real browser to catch fully, so treat it as a floor, not a ceiling.

## 1. Consent & cookies (the most common concrete gap)

- **Prior consent for non-essential cookies/trackers** where required (GDPR/ePrivacy): analytics, advertising, and social pixels should NOT fire *before* the user consents. Many sites show a banner but load Google Analytics/Meta Pixel on page load anyway — that's the classic violation the scanner helps catch.
- **Consent is real, not fake**: granular (accept/reject by category), reject as easy as accept (no "Accept All" button with a buried reject), no pre-ticked boxes, no cookie-wall coercion where prohibited. Consent is logged and withdrawable.
- **Essential vs non-essential** correctly classified — strictly-necessary cookies (session, security, load balancing) don't need consent; analytics/marketing do.
- Cookie policy lists what's set, why, duration, and third parties.

## 2. Privacy policy

- **Present, linked site-wide** (footer), and actually accurate to what the site does — a boilerplate policy that doesn't match real data practices is itself a problem.
- Covers the expected substance: what data is collected, why (purpose/legal basis under GDPR), how long it's kept, who it's shared with, and the user's rights + how to exercise them; contact for privacy questions; international transfer disclosures if data leaves the region.
- Last-updated date; a way for users to be informed of changes.

## 3. User rights

Depending on regime, users can request to **access, delete, correct, port, or opt out**. Check there's a real mechanism:
- GDPR: access, rectification, erasure ("right to be forgotten"), portability, objection — with a stated way to request and a response timeline. (Hand off to the DSAR mechanics if the app must fulfill these — the data has to actually be findable and deletable, which ties to database-audit.)
- CCPA/CPRA: right to know, delete, correct, and **opt out of sale/sharing** — often needs a "Do Not Sell or Share My Personal Information" link and support for opt-out preference signals (Global Privacy Control).
- The mechanism works and isn't just a promise in the policy.

## 4. Data collection & minimization

- **Collect only what's needed** for the stated purpose (data minimization) — forms asking for data with no clear use are a flag.
- **Lawful basis** for processing under GDPR (consent, contract, legitimate interest, etc.) — identifiable per purpose.
- **Retention**: data isn't kept forever with no policy — there's a retention schedule and deletion actually happens (ties to database practices).
- **Special-category / sensitive data** (health, biometric, children's) handled with the extra care its regime requires; children's data (COPPA/GDPR-K) triggers heightened obligations if minors are users.

## 5. Third-party sharing & processors

- Third parties receiving personal data (analytics, ad networks, embedded widgets, payment, support tools) are disclosed; data-processing agreements exist with processors (a GDPR requirement — hand off to any DPA review).
- **International transfers** (e.g. EU data to US services) have a valid transfer mechanism disclosed.
- Embedded third-party content (fonts, maps, videos, social buttons) can leak user data (IP, behavior) to those third parties on load — often before consent. The scanner surfaces these origins.

## 6. Security & breach readiness (compliance-relevant)

- Reasonable security for personal data (encryption in transit/at rest — overlaps security-review); a breach-notification plan (GDPR's 72-hour notification, state breach laws). Not logging PII/secrets (ties to observability and security-review A09).

## Report format

Shared audit structure (Summary → Scorecard → Findings → Fix order), grouped **Consent/Cookies / Privacy Policy / User Rights / Data Practices / Third Parties / Security**. Each finding names the specific gap, the obligation it relates to (and which regime), and the concrete fix (the consent-gating change, the policy addition, the opt-out link). Open and close with the reminder that this identifies gaps and is **not legal advice** — anything consequential goes to a qualified privacy lawyer. Route technical fixes to website-fix, data-findability/deletion to database-audit/fix.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `$solo-next-step` and `$release-preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `$solo-start-session` restores project context at the start (reading `.solo/`), and `$solo-end-session` saves progress, blockers, decisions, and the next task at the end. `$solo-run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `$stack-intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `$stack-intake` first. For vendor-specific depth, the stack plugin adds `$stack-audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.

## Script safety (url_guard)

The bundled script(s) route every outbound request through `<skill-root>/../../lib/url_guard.py` (shipped at `plugins/site-doctor/lib/url_guard.py` in the source tree): HTTPS-first scheme policy (http only where auditing it is the point), refusal of loopback/private/link-local/CGNAT/reserved/multicast and cloud-metadata targets — every DNS answer and every redirect hop is re-validated — plus a hard response-size cap. A refused target prints `BLOCKED unsafe target: <reason>` instead of being fetched.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
