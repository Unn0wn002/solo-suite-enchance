---
name: accessibility-review
description: Full WCAG 2.2 AA accessibility audit — keyboard navigation, screen reader semantics and ARIA, color contrast, focus management, forms and error handling, images and media alternatives, and accessible interactive components (modals, menus, tabs, carousels). Use whenever the user wants an a11y audit, accessibility compliance check, WCAG/Section 508/ADA/EAA review, "is my site accessible", "can screen readers use this", or help making a component keyboard-accessible. Deeper than the accessibility section of website-audit.
---

# Accessibility Review

Accessibility is tested through use, not just inspection. The single most valuable check is to **operate the primary flow with keyboard only, then with a screen reader** — automated tools catch maybe 30–40% of WCAG issues; the rest need this. Frame findings against WCAG 2.2 AA (the common legal baseline for ADA, Section 508, and the EU Accessibility Act).

## The four POUR principles

Every criterion rolls up to one of: **Perceivable**, **Operable**, **Understandable**, **Robust**. Group findings this way so the pattern behind them is visible.

## Start with the two manual walkthroughs

### Keyboard-only pass
Unplug the mouse. Complete the core task (sign up, search, checkout, whatever matters). Check:
- **Everything interactive is reachable** by Tab, and **operable** by Enter/Space (and arrow keys for composite widgets).
- **Focus is always visible** — a clear focus indicator on every element (WCAG 2.2 tightened this with Focus Appearance).
- **Tab order is logical** — follows visual/reading order, doesn't jump around.
- **No keyboard traps** — you can Tab out of every component (including modals and embeds).
- **Skip link** to bypass repeated nav on content-heavy pages.
- **Focus is managed** on dynamic changes: opening a modal moves focus into it and traps it there; closing returns focus to the trigger; route changes move focus sensibly.

### Screen reader pass (VoiceOver/NVDA)
Navigate by headings, landmarks, links, and form fields. Check:
- **Headings** form a real outline (one h1, no skipped levels) and are used for structure, not styling.
- **Landmarks** present (`<header>`, `<nav>`, `<main>`, `<footer>`) so users can jump between regions.
- **Link and button text makes sense out of context** — "read more" ×10 is useless; "Read more about pricing" is not.
- **Images** announce meaningful `alt`; decorative images are silent (`alt=""`).
- **Form fields** announce their label, current value, required state, and any error.
- **Dynamic updates** are announced via live regions (`aria-live`) — a toast or async validation message that only appears visually is invisible to SR users.

## Perceivable

- **Text alternatives**: descriptive `alt` for informative images (say what it conveys, not "image"); `alt=""` for decorative; complex images (charts) have a longer text description nearby.
- **Contrast**: body text ≥ 4.5:1, large text (≥ 24px or 19px bold) ≥ 3:1, UI components and graphical objects ≥ 3:1. Check the *actual* rendered colors, including text over images and disabled/placeholder states.
- **Not by color alone**: errors, links, required fields, and statuses must be distinguishable without relying on color (add icon/text/underline).
- **Reflow & zoom**: usable at 200% zoom and 320px width with no loss of content or horizontal scrolling; text spacing adjustable without clipping.
- **Media**: captions for video, transcripts for audio, no content flashing more than 3×/sec.

## Operable

- Everything from the keyboard pass above.
- **Target size** (WCAG 2.2): interactive targets at least 24×24 CSS px (or have adequate spacing) — matters on mobile especially.
- **Timing**: adjustable or dismissible timeouts; auto-advancing carousels can be paused.
- **No motion traps**: respect `prefers-reduced-motion`; provide pause/stop for auto-playing motion.
- **Dragging** (WCAG 2.2): any drag operation has a single-pointer (click/tap) alternative.

## Understandable

- **`<html lang>`** set (and `lang` on inline foreign-language passages).
- **Labels & instructions**: every input has a programmatic label; instructions and format requirements are stated, not implied by placeholder alone (placeholders vanish and fail contrast).
- **Errors**: identified in text, tied to the field (`aria-describedby`), with a clear fix suggestion; error summary at the top for long forms; nothing conveyed by red border alone.
- **Consistent** navigation and component behavior across pages; predictable — no surprise context changes on focus/input.
- **Redundant entry / accessible auth** (WCAG 2.2): don't force re-entering info already provided; don't gate auth behind a cognitive test with no accessible alternative.

## Robust — ARIA and semantics

- **Native first**: use real `<button>`, `<a>`, `<input>`, `<select>`, `<nav>` before reaching for ARIA. The first rule of ARIA is don't use ARIA if a native element does the job — a `<div role="button">` re-implements (badly) what `<button>` gives free.
- **ARIA correctness**: valid roles/states/properties; `aria-expanded`/`aria-controls` on disclosure widgets; `aria-current` for current page; no broken references (`aria-labelledby` pointing at missing IDs).
- **Name, role, value** exposed for every custom control so assistive tech can announce and operate it.

## Common component patterns (get these right — they're where most real failures live)

- **Modal/dialog**: `role="dialog"` + `aria-modal`, focus moved in and trapped, Escape closes, focus returns to trigger, background inert.
- **Dropdown menu / combobox / tabs / accordion**: follow the ARIA Authoring Practices keyboard model (arrow keys, Home/End, expected roles). Don't invent your own.
- **Carousel**: pause control, keyboard-navigable, slides announced, doesn't auto-advance without control.
- **Tables**: real `<th>` with `scope`, `<caption>`; not layout tables.

## Report format

Shared audit structure, with each finding tagged by **WCAG success criterion** (e.g. "1.4.3 Contrast (Minimum)"), its **POUR principle**, and **who it blocks** (keyboard users / screen reader users / low vision / cognitive). Severity by how completely it blocks a task — a keyboard trap on checkout is critical; a missing decorative alt is trivial. Route fixes through **website-fix** (the accessibility recipe), and prefer native-semantics fixes over piling on ARIA.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
