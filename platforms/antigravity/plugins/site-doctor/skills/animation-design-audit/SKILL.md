---
name: animation-design-audit
description: Audit motion design and animation implementation across GSAP, CSS animations, the Web Animations API, and framework animation libraries. Check lifecycle cleanup, ScrollTrigger hygiene, duplicate loading, rendering performance, prefers-reduced-motion behavior, keyboard and scroll usability, and visual consistency. Use for animation audits, motion reviews, janky transitions, GSAP cleanup checks, reduced-motion accessibility, scroll-animation problems, or questions about whether a site's motion is purposeful and performant. Deeper than the code-hygiene section of website-audit.
---

# Animation & Motion Design Audit

Audit motion on four axes: correctness, performance, accessibility, and design purpose. The bundled scanner specializes in GSAP because that is this suite's default animation engine. Apply the same axes manually to CSS animations, the Web Animations API, Framer Motion, Motion One, or another library. A no-GSAP scanner result means the automated portion is not applicable, not that the project has no motion.

If the companion `gsap-*` skills are installed, use the relevant one for implementation guidance. If they are unavailable, still provide a concrete fix plan and identify the GSAP API or framework lifecycle that must change.

## Audit workflow

1. Read `.solo/handoff.md`, `.solo/tasks.md`, and `.solo/stack.md` when present.
2. Identify the framework, animation libraries, package-loading path, and routes or components in scope.
3. Run the bundled scanner against local source when GSAP may be present.
4. Inspect every reported file before classifying a finding. A regex hit is evidence to review, not proof of a defect.
5. Manually inspect behavior the scanner cannot establish: animation purpose, focus order, scroll behavior, timing consistency, runtime jank, and non-GSAP motion.
6. Separate confirmed findings from warnings and unverified areas. Never infer runtime behavior from source alone.
7. Prioritize by user harm and blast radius: accessibility and broken interaction first, lifecycle leaks and severe jank next, consistency improvements last.

## Run the bundled scanner

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/animation-design-audit/scripts/animation_check.py" /path/to/project
```

If `python3` is unavailable, use `python`.

The scanner is local and makes no network requests. It checks for GSAP loading, layout-triggering tween properties, missing lifecycle-cleanup signals, ScrollTrigger refresh or cleanup awareness, and project-level `prefers-reduced-motion` handling in JavaScript, component, and CSS-family files.

It is a bounded heuristic grep, not control-flow or browser analysis. Treat every hit as "inspect this file."

Exit codes are evidence, not the final audit verdict:

- `0`: GSAP found and no heuristic gaps flagged.
- `1`: one or more warnings or failures flagged.
- `2`: invalid invocation or project path.
- `3`: no GSAP usage detected; continue manually if another motion system is present.

## 1. Correctness

- **Lifecycle cleanup:** require teardown for tweens, timelines, and ScrollTriggers created in components that mount and unmount. Accept `gsap.context()` with `.revert()`, `useGSAP()`, or manual `.kill()` on stored references. `overwrite: true` or `"auto"` resolves tween conflicts; it is not lifecycle cleanup.
- **ScrollTrigger freshness:** inspect triggers whose positions depend on images, fonts, accordions, route transitions, or other late layout changes. Require a refresh at the correct lifecycle point when automatic refresh is insufficient.
- **Loading path:** flag CDN and package loading in the same application because duplicate GSAP instances can split plugin registration and global state.
- **Timeline ownership:** identify timelines that compete for the same properties, magic offsets that should be labels, and animations created repeatedly by render or event loops.
- **Framework lifecycle:** verify client-only initialization, stable selectors or refs, and cleanup behavior appropriate to React, Vue, Nuxt, Svelte, or the detected framework.

Do not report missing cleanup as confirmed merely because the scanner found no signal in one file. First establish that the animation belongs to a remounting lifecycle rather than a one-shot static page.

## 2. Performance

- Prefer transforms (`x`, `y`, `scale`, `rotation`) and opacity over layout-triggering properties such as `width`, `height`, `top`, `left`, margin, and padding. Treat exceptions as review points, not automatic failures.
- Look for unbounded tweens, listeners, tickers, and ScrollTriggers; off-screen animations that continue indefinitely; and per-frame work that reads and writes layout.
- Check whether a stagger or batched trigger can replace large loops of individual animations.
- Use bounded `will-change`; persistent promotion across many elements can consume memory.
- When installed, the external companion `gsap-performance` provides batching, `quickTo()`, scrub-tuning, and implementation guidance.
- Route Core Web Vitals questions to **performance-tuning**. Hidden entrance content can damage perceived speed and may delay LCP recognition; layout-changing motion can cause CLS. Do not label every entrance animation as a layout shift.

## 3. Accessibility

- Respect `prefers-reduced-motion` for non-essential parallax, large entrances, autoplay loops, zooming, and other spatial motion. Reduced mode should reveal content immediately and preserve meaning.
- Never gate primary copy, navigation, forms, or CTAs on an animation completing.
- Flag large, fast, full-viewport movement, rapid flashing, and unexpected autoplay even when a reduced-motion branch exists.
- Verify that pinning, snapping, smooth scrolling, and scroll hijacking do not trap keyboard navigation, disrupt screen-reader order, or break anchor links and browser history.
- Confirm that focus indicators are not hidden or displaced by transforms.
- Distinguish decorative motion that may be disabled from essential state-change feedback that needs a reduced alternative.

## 4. Design

- Require a job for each significant motion pattern: direct attention, confirm an action, explain spatial change, or preserve continuity.
- Identify decorative motion whose noise, delay, or implementation cost exceeds its value.
- Look for a small duration and easing system rather than unrelated values in each component.
- Treat roughly 150–300 ms as a review heuristic for common micro-interactions, not a universal rule. Evaluate distance, scale, input method, and product tone.
- Check interruption behavior: repeated clicks, route changes, resize, and fast scrolling should not leave the interface between states.
- Confirm that content remains readable and interactive during transitions.

## Evidence and severity

For each finding, record:

- file or component;
- inspected code or observed behavior;
- why it matters;
- confidence: Confirmed, Likely, or Unverified;
- severity: Critical, High, Medium, or Low;
- smallest safe fix;
- verification step.

Use Critical only for severe user harm or loss of control. Use High for inaccessible core flows, broken interaction, or leaks with broad impact. Use Medium for repeatable jank, stale triggers, or inconsistent behavior. Use Low for local polish and consistency issues.

## Report format

Use the exact output contract from the invoking command. When invoked directly, report:

1. **Status** — PASS, WARNING, or FAIL.
2. **Evidence Checked** — inspected files, scanner output, and runtime checks; say "not checked" where evidence is missing.
3. **Findings** — bucket under Correctness, Performance, Accessibility, and Design.
4. **Risk Level** — Low, Medium, High, or Critical.
5. **Required Fixes** — ordered by user harm and dependency.
6. **Suggested Tasks** — stable T-IDs suitable for `.solo/tasks.md`.
7. **Verification Steps** — exact checks that prove each fix.

Add **Next Recommended Command** when the invoking command requires it.

## Project memory integration

**AgentRoom proposal mode:** when a trusted seat lists a memory target under `proposes`, write the intended target, proposed entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write.

If `.solo/` exists, read its session context before auditing. Propose stable task entries and significant decision updates in the report. Write them into `.solo/` only when the active session workflow or the user authorizes memory updates. If `.solo/` does not exist, proceed normally.

## Session lifecycle

This skill works inside a session bookended by `/solo:start-session` and `/solo:end-session`. `/solo:run-cycle` may invoke it as one step of a larger delivery cycle.
