---
name: animation-design-audit
description: Audit motion design and animation implementation — GSAP correctness (cleanup, ScrollTrigger hygiene, duplicate loading), performance (layout-triggering properties vs transform/opacity), accessibility (prefers-reduced-motion), and design consistency (purposeful motion, consistent easing/duration). Use whenever the user wants an animation audit, motion review, "does my site feel janky", GSAP cleanup check, or asks whether their site's animations are accessible/performant. Deeper than the code-hygiene section of website-audit.
---

# Animation & Motion Design Audit

Animation is judged on three axes that all have to hold at once: it has to **run smoothly** (performance), it has to **respect the user** (accessibility — not everyone wants motion), and it has to **mean something** (design — motion that's there because it was easy to add, not because it helps, is a liability not a feature).

This skill audits GSAP specifically, since it's the animation engine this suite defaults to (see the companion `gsap-*` skills — `gsap-core`, `gsap-timeline`, `gsap-scrolltrigger`, `gsap-plugins`, `gsap-react`, `gsap-frameworks`, `gsap-utils`, `gsap-performance` — for implementation and fixes; this skill finds the problems, those skills write the code). If the project uses CSS animations, the Web Animations API, or another library instead, apply the same three axes manually — the checklist below still applies conceptually even where the GSAP-specific script doesn't.

## Run the bundled scanner first

```bash
python3 "<skill-root>/scripts/animation_check.py" /path/to/project
```
> If `python3` isn't on PATH, use `python` instead.

It statically scans the local source tree (no network involved) for GSAP usage and flags: duplicate CDN+npm loading, layout-triggering properties passed directly to tweens, tween/timeline creation with no cleanup signal anywhere in the file, ScrollTrigger usage with no refresh/kill awareness, and whether `prefers-reduced-motion` is handled anywhere at all. It's a heuristic grep, not real control-flow analysis — treat every hit as "go look at this file," not as a confirmed defect, and read the actual code before reporting a finding.

## 1. Correctness — is the animation actually working the way it's meant to?

- **Cleanup**: every tween/timeline/ScrollTrigger created in a component that mounts and unmounts (SPA route changes, React/Vue/Svelte component lifecycle) needs an explicit teardown — `gsap.context()` + `.revert()`, the `useGSAP()` hook, or manual `.kill()` on stored refs. Missing cleanup means animations keep running against DOM nodes that no longer exist, and — worse — keep re-triggering on every subsequent mount, compounding over a session.
- **ScrollTrigger staleness**: trigger positions are computed from layout at creation/refresh time. Anything that changes layout after that (images finishing load, content toggling open, fonts swapping in) needs an explicit `ScrollTrigger.refresh()` or triggers fire at the wrong scroll position.
- **Duplicate loading**: GSAP loaded both via a CDN `<script>` tag and the npm package in the same project risks two separate instances with inconsistent global state (plugin registration, `matchMedia` contexts). Pick one loading path.
- **Timeline/label sanity**: labels used consistently instead of magic time offsets; nested timelines don't fight each other for the same properties on the same element (last-write-wins silently overrides earlier tweens).

## 2. Performance

- Prefer **transform** (`x`, `y`, `scale`, `rotation`) and **opacity** over layout-triggering properties (`width`, `height`, `top`, `left`, `margin`, `padding`) — the scanner flags direct use of the latter inside a tween. Not every layout-property animation is wrong (sometimes there's no transform equivalent), but each one is worth a second look.
- Large numbers of simultaneous tweens/ScrollTriggers, especially on lower-end devices, are a real jank source — check whether `stagger` replaces a loop of individual tweens, and whether off-screen/inactive animations get paused or killed rather than running invisibly forever.
- For fixes and the full performance checklist (batching, `will-change`, `gsap.quickTo()` for high-frequency updates like mouse-followers, `scrub` tuning), hand off to the separately-installed `gsap-performance` skill (from GreenSock's own plugin, not part of this suite) rather than re-deriving it here.

## 3. Accessibility

- **`prefers-reduced-motion`** must be respected for any non-essential motion — parallax, large-scale entrance animations, autoplaying decorative loops. `gsap.matchMedia()` is the standard way to branch behavior on it; the scanner flags a project with zero references to reduced-motion anywhere.
- **Motion that blocks content**: nothing essential (primary CTA, form, core copy) should be gated behind an animation finishing — a slow page-load animation that delays interactivity is a UX and a11y problem, not just a performance one.
- **Vestibular triggers**: large, fast, full-viewport motion (parallax, spinning, rapid flashing) is a known trigger for some users regardless of stated preference — flag it even when `prefers-reduced-motion` is otherwise handled, since the media query is opt-in, not universal coverage.
- **Focus and scroll hijacking**: scroll-triggered pinning/snapping shouldn't trap keyboard or screen-reader navigation, and shouldn't override the browser's native scroll-to-anchor/hash behavior without a deliberate reason.

## 4. Design — is the motion doing a job?

- **Purposeful vs decorative**: good motion directs attention (what changed, what's now interactive, what just loaded), confirms an action (button press, form submit), or orients (where did this panel come from, where did it go). Motion that's just "because it looks cool" on every element adds noise and cost for no functional payoff — call this out even when it's technically well-implemented.
- **Consistency**: easing curves and durations should read as a small, deliberate set (e.g. one "enter" ease, one "exit" ease, a couple of duration tiers) rather than every component picking its own. Inconsistent easing is the single most common reason a site "feels off" without an obvious bug.
- **Timing feel**: UI micro-interactions (hover, toggle, tooltip) generally read best fast (~150–300ms); larger transitions (page/section changes) can run longer, but anything that makes the user wait to act starts costing more than it adds.
- **Respect the content**: entrance animations that delay text/images becoming visible/interactive are a common self-inflicted CLS and perceived-performance problem — audit against **performance-tuning**'s Core Web Vitals checks too, since a "smooth" animation that pushes LCP past 2.5s isn't actually smooth.

## Report format

Shared audit structure (Summary → Scorecard → Findings → Fix order), findings bucketed under Correctness / Performance / Accessibility / Design so the pattern behind them is visible, each tagged with the file/component it applies to. Route implementation fixes to the relevant **gsap-\*** skill for the specific GSAP mechanism involved, and to **performance-tuning** for anything that's really a Core Web Vitals issue wearing an animation costume.

## Project memory integration (solo-team)

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. If `.solo/` doesn't exist, proceed normally.

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `$solo-start-session` restores project context at the start, and `$solo-end-session` saves progress at the end. `$solo-run-cycle` may invoke this skill as one step of a complete task cycle.

## Stack awareness

Read `.solo/stack.md` if it exists before auditing, so recommendations account for the project's real framework — the separately-installed `gsap-react` and `gsap-frameworks` skills (from GreenSock's own plugin) cover React/Vue/Nuxt/Svelte-specific patterns like `useGSAP` and SSR-safety — rather than giving generic vanilla-JS advice to a framework project.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
