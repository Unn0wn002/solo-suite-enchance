---
name: payments-audit
description: Audit a payment integration — Stripe, PayPal, Xendit, Midtrans, or any provider — for webhook security, payment status handling, duplicate-payment protection, refund flow, test vs live key separation, exposed secret keys, and checkout success/failure pages. Use when the user wants a payments review, "check my Stripe/payments", webhook verification, double-charge or duplicate payment concerns, refund handling, payment key safety, or checkout flow correctness. Vendor-aware front end to site-doctor's security-review, api-audit, and forms-audit; reads .solo/stack.md.
---

# Payments Audit

**AgentRoom proposal mode:** preserve raw audit evidence in the seat's declared direct artifact. Any tasks, decisions, handoff, stack update, or other target listed under `proposes` goes to `.solo/proposals/<seat>-<run_id>.md` with its target and proposed entries; never edit that target. Only the memory steward merges, and missing seat/run identity stops the write.

Payments is the code path where bugs cost real money in both directions — double charges that burn customer trust, an unverified webhook that lets anyone mark an order "paid," a leaked secret key that lets anyone move funds, or a live key in staging quietly charging real cards during tests. This skill audits the payment integration end to end: keys and environments, webhooks, state handling, duplicates, refunds, and the checkout surface. The failure modes are the same across providers (Stripe, PayPal, Xendit, Midtrans, and similar), so the checklist is provider-aware but vendor-neutral.

## Setup

Read `.solo/stack.md` for the payment provider(s) and webhook setup; offer `/stack:intake` if it's missing. **Only audit systems you own.** Work from the actual integration code (checkout flow, webhook handlers, refund logic), environment config, and provider dashboard details the user shares. One framing rule up front: **raw card data should never touch your server** — use the provider's hosted checkout / elements / tokenization so PCI scope stays minimal; a custom form posting card numbers to your backend is a serious finding on its own.

## What to check

1. **Exposed secret keys (highest stakes)** — the secret/server key (`sk_live_…`, Midtrans Server Key, Xendit secret API key, PayPal client secret) must never be client-side, committed, in a `NEXT_PUBLIC_`-style var, or in logs. Only the publishable/client key belongs in the browser. Check the repo **and git history** — a key committed once is exposed even if later removed; rotate it. Run site-doctor `security-review`'s `scan_secrets.py` (it catches payment keys). Prefer restricted/least-privilege keys where the provider supports them.

2. **Test vs live keys** — test keys in dev/preview, live keys **only** in production, enforced by environment-scoped config (ties to `/stack:audit-vercel` env scoping). Both failure directions are real: a live key in staging means test runs charge real cards; a test key in prod means the site silently collects no money. Verify the key prefix per environment (`sk_test_` vs `sk_live_`, sandbox vs production), and that each environment has its **own webhook endpoint + signing secret** pointing at the matching mode.

3. **Webhook security** — the webhook is your payment source of truth, so it must be trustworthy:
   - **Signature verification on every event**: Stripe's `Stripe-Signature` + signing secret (via the SDK), Xendit's callback token, Midtrans's `signature_key` hash, PayPal's webhook verification. An unverified endpoint lets anyone POST "payment succeeded."
   - **Replay & idempotency**: store processed event IDs and skip duplicates; respect timestamp tolerance; expect provider retries (return 2xx fast, process async) and out-of-order delivery.
   - Endpoint is HTTPS-only, does no privileged work before verification, doesn't log secrets or full payloads with PII, and never trusts amount/status from anywhere except the verified event or a server-side API fetch.

4. **Payment status handling** — model the **full state machine**, not just success: pending, requires-action (3DS/SCA), processing, succeeded, failed, expired, canceled, refunded, disputed. Async methods (bank transfer / virtual account / e-wallets — the norm with Xendit and Midtrans) can sit pending for hours or days, so orders need a real pending state and an expiry path. Status transitions happen **server-side from verified webhooks or API lookups — never from client redirect params**. Verify amount and currency server-side against the order (never trust a client-sent amount — price tampering is the classic checkout hole). When in doubt, reconcile against the provider API.

5. **Duplicate payment protection** — three layers, all present:
   - **Idempotency keys** on payment-creation API calls, so network retries can't create two charges.
   - **One payment intent per order**: reuse the existing intent/invoice instead of creating a new one per click, backed by a DB-level unique constraint tying order → payment.
   - **Double-submit guards** on the pay button (disable on click, loading state — ties to site-doctor `forms-audit`), plus idempotent webhook fulfillment so a re-delivered "paid" event can't double-ship or double-credit.

6. **Refund flow** — refunds are money out the door: initiated **server-side only**, behind real authorization (who may refund? An unprotected refund endpoint is a direct theft vector — check it like site-doctor `security-review` checks authz). Partial vs full refunds handled; refund webhooks update order/fulfillment state; refunds can *fail*, so their status is tracked; the customer is notified; and there's an audit trail — who refunded what, when, why. Disputes/chargebacks are handled and logged too.

7. **Checkout success/failure pages** — the success URL is **not proof of payment**: anyone can open it directly, so verify status server-side (session/intent lookup) before showing "paid" or fulfilling — and make fulfillment idempotent so a refresh or revisit can't double-fulfill. Failure and cancel pages preserve the cart, explain what happened in human terms, and offer a clean retry. Async methods get an honest pending page ("we'll confirm by email once the transfer clears"), not a fake success. No sensitive parameters leaked in success/failure URLs. (Confirmation emails actually arriving → site-doctor `email-check`.)

## Delegate the depth

Payments-specific checklist here; the engines live elsewhere:
- Secret scanning and refund-endpoint authorization → site-doctor **`security-review`**.
- Webhook endpoint hardening, rate limiting, idempotency patterns → **`api-audit`**.
- Checkout form double-submit and UX → **`forms-audit`**.
- Payment/receipt emails landing in inboxes → **`email-deliverability`**.
Invoke those for depth when installed; do a lighter inline pass when not — but never soft-pedal an unverified webhook or an exposed live key.

## Report & memory

Shared audit format (Summary → Scorecard → Findings [Evidence / Impact / Fix] → Fix order), grouped **Keys / Test-vs-Live / Webhooks / Status Handling / Duplicates / Refunds / Checkout Pages**. Rank by money-at-risk — an exposed live secret, unverified webhooks, and client-trusted amounts lead; a cosmetic failure-page issue is low. Write the prioritized fixes to `.solo/tasks.md` (stable T-IDs) and note the audit in `handoff.md` when `.solo/` exists, so findings reach `/solo:next-step` and `/release:preflight`.

## Two ways to run this audit

State which mode you used — findings carry different confidence. (tiers: provider API/MCP → repo code + env names → ask)

### Mode 1 — Connector mode (live config)
A connector / MCP / API for the payment provider is available (the provider's own API/MCP — Stripe, PayPal, Xendit, Midtrans; **connector-auditor** covers Vercel/Supabase/GitHub/Cloudflare, not payment providers): read the real configuration, read-only, and never print secret values.
- inspect webhook endpoints + signing configuration via the provider API/MCP (Stripe/PayPal/Xendit/Midtrans)
- inspect API key mode (test vs live) — by metadata, never printing keys
- inspect recent webhook delivery failures

### Mode 2 — Manual mode (user-supplied evidence)
No connector: ask the user for the evidence instead of guessing — and audit exactly what they provide.
- ask for the webhook handler code path in the repo
- ask for env variable NAMES for keys/secrets (never values)
- ask for a screenshot of the provider's webhook settings page
- ask how payment status updates the database (code path or description)
- ask for the checkout success/failure URLs to test

Either way, every finding must name its evidence (which setting, file, screenshot, or API field it came from).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill in its audit step when a task touches payments. Keep `.solo/` current as you go so those session commands stay accurate.
