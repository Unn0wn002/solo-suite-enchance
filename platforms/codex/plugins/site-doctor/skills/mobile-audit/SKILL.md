---
name: mobile-audit
description: Audit a website's mobile experience — responsive layout across breakpoints, touch target sizing, mobile performance on slow networks and weaker devices, viewport and text legibility, mobile-specific interactions, and Progressive Web App (PWA) readiness. Use whenever the user asks about mobile experience, responsive design, "how does my site look on phones", touch usability, mobile performance, PWA/installability, or mobile-first concerns. Complements performance-tuning and accessibility-review with a mobile lens.
---

# Mobile Audit

Most web traffic is mobile, and Google indexes mobile-first — yet sites are usually built and tested on a desktop. The gaps show up as layout breaks at narrow widths, tap targets too small for thumbs, and pages that are fine on fiber but crawl on a mid-range phone over 4G. Audit the experience as a real phone user has it, not as the desktop preview suggests.

## Run the meta/viewport checker first

```bash
python3 "<skill-root>/scripts/check_mobile.py" https://example.com
```
> **Running helpers:** `<resolved-plugin-root>` is set by Codex to this plugin's installed root, so the command works from any working directory. If `python3` is not on PATH, use `python` (macOS/Linux/Windows) (Windows launcher) instead.

Stdlib-only. Fetches the page and checks the viewport meta tag, presence of a web app manifest and theme-color, responsive image hints (`srcset`/`sizes`), and fixed-width/px-heavy layout signals. Use it as the factual base, then do the responsive and interaction checks below (which need real rendering).

## 1. Viewport & responsive layout

- **Viewport meta tag** present and correct: `<meta name="viewport" content="width=device-width, initial-scale=1">`. Missing it makes the page render at desktop width scaled down (tiny, unusable); a fixed `width=` or `maximum-scale=1`/`user-scalable=no` breaks zoom and hurts accessibility.
- **Test across breakpoints**: 320px (small phones), ~375–414px (typical phones), 768px (tablets). At each, check no horizontal scroll, no content cut off, no overlapping elements, images scaling correctly.
- **No fixed-width layouts** forcing horizontal scroll; use fluid/flex/grid, relative units, and `max-width: 100%` on media. The checker flags heavy fixed-px signals.
- **Content parity**: mobile users get the same core content and functionality (mobile-first indexing penalizes hidden/stripped content); nothing critical is display:none'd away on small screens.
- Orientation: works in both portrait and landscape.

## 2. Touch usability

- **Tap target size**: interactive elements at least ~44×44px (iOS) / 48×48px (Android) with adequate spacing so fingers don't hit the wrong one — the #1 mobile UX complaint. (Overlaps accessibility-review's target-size criterion.)
- **Spacing** between tappable elements so adjacent links/buttons aren't a mis-tap trap.
- **No hover-dependent functionality**: menus/tooltips/actions that only appear on hover are unreachable on touch — provide a tap equivalent.
- Gestures (swipe carousels, pull-to-refresh) have accessible alternatives and don't hijack native scrolling.
- Forms: correct `inputmode`/`type` so the right keyboard appears (email, tel, number, url), inputs large enough to tap, labels visible, autofill/autocomplete attributes set — mobile form friction kills conversions (ties to forms-audit).

## 3. Mobile performance (the make-or-break factor)

Mobile means slower CPUs and flakier networks — a page that's fine on desktop can be painfully slow on a phone:
- **Test on throttled conditions** (slow 4G, mid-tier device CPU), not just a fast desktop connection. Field data (RUM) from real mobile users is the truth (hand off to performance-tuning + observability).
- **Payload weight** matters more on mobile: large JS bundles, unoptimized images, and heavy fonts hurt disproportionately (parse/execute cost on weak CPUs drives poor INP). Core Web Vitals thresholds are the same but harder to hit on mobile — treat mobile vitals as the binding constraint.
- **Images sized for mobile viewports** via `srcset`/`sizes` — don't ship a 2000px desktop image to a 375px screen (the checker flags missing responsive hints). Lazy-load below-the-fold.
- Avoid data-heavy autoplay video on mobile; respect data-saver where possible.
- Full performance mechanics live in **performance-tuning** — apply them with a mobile-first priority.

## 4. Legibility & visual

- **Text readable without zoom**: base font ~16px+, sufficient line height, adequate contrast (contrast overlaps accessibility-review, but small screens in sunlight make it more critical).
- Content fits the screen; no truncation of important text; adequate padding so content isn't jammed against edges.
- Respects device settings: `prefers-color-scheme` (dark mode), `prefers-reduced-motion`, and dynamic/large text sizes without breaking layout.
- Safe-area handling for notched devices (`env(safe-area-inset-*)`) so content isn't hidden behind notches/home indicators.

## 5. PWA / installability (where it fits the use case)

Not every site needs to be a PWA, but if offline use or home-screen install matters:
- **Web app manifest** with name, icons (multiple sizes incl. maskable), `start_url`, `display`, and `theme_color` (the checker reports presence).
- **Service worker** for offline capability / caching — with a sane caching strategy that doesn't serve stale content forever (versioned caches).
- HTTPS (required for PWA and service workers).
- Installability criteria met if "add to home screen" is a goal; appropriate icons and splash for iOS/Android.
- If it's not meant to be a PWA, say so — don't recommend one gratuitously.

## Report format

Shared audit structure (Summary → Scorecard → Findings → Fix order), grouped **Viewport/Responsive / Touch / Performance / Legibility / PWA**. Each finding names the breakpoint or element and the concrete fix. Rank by how badly it blocks a mobile user completing the core task — horizontal-scroll layout breaks and un-tappable targets outrank a missing PWA manifest. Route performance mechanics to performance-tuning, overlapping a11y items to accessibility-review, and form issues to forms-audit.

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
