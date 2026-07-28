---
name: email-deliverability
description: Audit email deliverability and sending setup for a domain — SPF, DKIM, and DMARC records, reverse DNS/PTR, sender reputation signals, content and configuration that trigger spam filters, list hygiene, and bounce/complaint handling. Use whenever the user asks why their emails go to spam, wants to check SPF/DKIM/DMARC, set up email authentication, improve deliverability, "my transactional emails aren't arriving", or is configuring a domain to send mail. Pairs with infrastructure-audit (DNS) and compliance-check (consent).
---

# Email Deliverability

Email that lands in spam (or gets rejected) is a silent failure — password resets, receipts, and notifications that users never see, with no error surfaced to you. The dominant cause is authentication: a domain that hasn't proven it's allowed to send gets filtered. Audit the DNS auth records first (that's most of deliverability), then reputation, content, and hygiene.

## Run the DNS record checker first

```bash
python3 "<skill-root>/scripts/check_email_dns.py" example.com
```
> **Running helpers:** `<resolved-plugin-root>` is set by Codex to this plugin's installed root, so the command works from any working directory. If `python3` is not on PATH, use `python` (macOS/Linux/Windows) (Windows launcher) instead.

Stdlib-only; queries public DNS for the domain's MX, SPF, DMARC, and (with a selector) DKIM records and parses them for common misconfigurations. Use it as the factual base — it directly answers "are the auth records present and sane?"

## 1. Authentication — SPF, DKIM, DMARC (this is ~80% of deliverability)

All three should exist and align. Missing or broken auth is why most legitimate mail gets spam-foldered or rejected.

- **SPF (Sender Policy Framework)** — a TXT record listing who may send for the domain.
  - Exactly **one** SPF record (multiple SPF records = a hard failure; a very common mistake).
  - Includes every legitimate sender (your mail server, ESP like SendGrid/Postmark/SES, Google Workspace, etc.) via `include:` or IP mechanisms.
  - Ends in `~all` (softfail) or `-all` (hardfail) — not `+all` (which permits anyone). `-all` is strongest once you're sure the list is complete.
  - Watch the **10 DNS-lookup limit** — too many nested `include:`s breaks SPF silently (the checker flags lookup count).

- **DKIM (DomainKeys Identified Mail)** — a cryptographic signature proving the message wasn't forged/altered.
  - A DKIM public key published at `selector._domainkey.domain` for each selector your senders use; the sender signs outgoing mail with the matching private key.
  - Provide the selector to the checker to verify the key resolves. Each ESP has its own selector — make sure each active sender's DKIM is set up.

- **DMARC (Domain-based Message Authentication)** — a policy telling receivers what to do when SPF/DKIM fail, plus reporting.
  - A TXT record at `_dmarc.domain` starting `v=DMARC1`.
  - **Policy** `p=`: `none` (monitor only — start here), `quarantine` (spam-folder failures), or `reject` (block them). Progress none → quarantine → reject as you confirm legit mail passes. `p=none` forever gives you reports but no protection.
  - **Alignment**: DMARC passes only if SPF *or* DKIM passes AND aligns with the visible From domain — so the From domain, SPF domain, and DKIM domain need to line up. Misalignment is a subtle, common failure.
  - **Reporting** (`rua=`) so you receive aggregate reports showing what's passing/failing and catch both spoofing and your own misconfigured senders.

## 2. Infrastructure & reputation

- **Reverse DNS (PTR)**: the sending IP resolves back to a hostname that matches forward DNS — mail servers distrust IPs with no/mismatched PTR. (Managed ESPs handle this; self-hosted senders must set it — ties to infrastructure-audit.)
- **IP/domain reputation**: sending IP not on major blocklists (Spamhaus etc.); domain reputation intact. A shared IP inherits others' reputation; a fresh dedicated IP needs **warm-up** (gradually ramping volume) before sending in bulk, or it looks like a spam burst.
- **Dedicated vs shared** sending IP appropriate to volume; consistent sending patterns (sudden volume spikes look like compromise/spam).
- **TLS** for mail transport (STARTTLS); optionally MTA-STS and TLS-RPT for stricter, reported transport security.
- **BIMI** (optional, advanced): logo display in supporting clients — requires DMARC at enforcement first.

## 3. Content & configuration (spam-filter triggers)

- **Format**: valid, well-formed HTML with a **plain-text alternative** (multipart) — HTML-only mail scores worse. Reasonable text-to-image ratio (not one big image with no text). No broken/oversized HTML.
- **Spam-trigger content**: excessive ALL CAPS, spammy phrasing, too many exclamation marks, misleading subject lines, link shorteners, mismatched/hidden links, attachments users didn't expect.
- **Links & domains**: links use your authenticated domain; tracking/link domains also authenticated; no linking to blocklisted domains.
- **Consistent, recognizable From**: a real, monitored From address on your domain (not `no-reply@` where possible), consistent sender name; a valid Reply-To.
- **List-Unsubscribe header** (and one-click unsubscribe) for bulk/marketing mail — now effectively required by major providers (Gmail/Yahoo) for bulk senders, and its absence hurts deliverability and may violate rules.

## 4. List hygiene & engagement (for bulk/marketing; transactional is lighter)

- **Permission**: only send to people who opted in (ties directly to compliance-check — consent is both a legal and a deliverability issue; purchased lists tank reputation).
- **Bounce handling**: process bounces and **stop sending to hard-bounced addresses** — repeatedly hitting invalid addresses signals a bad sender and hurts reputation.
- **Complaint handling**: honor spam complaints (feedback loops) and unsubscribes promptly; high complaint rates are deliverability poison.
- **Engagement**: providers weigh engagement — sending to chronically unengaged addresses drags reputation; prune or re-engage dormant contacts. Avoid spam-trap addresses (old/purchased lists collect them).
- **Volume consistency**: steady, predictable sending beats erratic spikes.

## 5. Monitoring

- Watch **DMARC aggregate reports** to see pass/fail across senders and catch both spoofing and your own broken configs.
- Monitor bounce rate, complaint rate, and blocklist status over time (ties to observability); investigate deliverability drops early.
- Test with a deliverability/inbox-placement tool and check placement across major providers (Gmail, Outlook, Yahoo) — they filter differently.

## Report format

Shared audit structure (Summary → Scorecard → Findings → Fix order), grouped **Authentication / Infrastructure & Reputation / Content / List Hygiene / Monitoring**. Lead with the authentication findings — SPF/DKIM/DMARC gaps are almost always the biggest lever. Each finding gives the exact record or setting and the fix (the corrected TXT record, the DMARC policy step, the missing include). Rank by deliverability impact: no/broken auth and blocklisted IPs top the list; content tweaks are lower. Route DNS/PTR specifics to infrastructure-audit and consent/permission to compliance-check.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `$solo-next-step` and `$release-preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `$solo-start-session` restores project context at the start (reading `.solo/`), and `$solo-end-session` saves progress, blockers, decisions, and the next task at the end. `$solo-run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `$stack-intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `$stack-intake` first. For vendor-specific depth, the stack plugin adds `$stack-audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.

## Script safety (url_guard)

The bundled script(s) route every outbound request through `<skill-root>/../../lib/url_guard.py` (shipped at `plugins/site-doctor/lib/url_guard.py` in the source tree): HTTPS-first scheme policy (http only where auditing it is the point), refusal of loopback/private/link-local/CGNAT/reserved/multicast and cloud-metadata targets — every DNS answer and every redirect hop is re-validated — plus a hard response-size cap. A refused target prints `BLOCKED unsafe target: <reason>` instead of being fetched. DNS questions necessarily reach the DoH endpoint (Cloudflare by default; `SITE_DOCTOR_DOH` overrides it), which sees the queried names.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
