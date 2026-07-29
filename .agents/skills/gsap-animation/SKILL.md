---
name: gsap-animation
description: Implement or review GSAP animation with correct lifecycle cleanup, sequencing, ScrollTrigger behavior, responsive rules, and performance. Activate when GSAP code is requested or present; do not activate for CSS-only motion that needs no GSAP.
---

# GSAP animation

Use the `gsap-animation` profile.

1. Confirm that animation supports a user or narrative goal and define reduced-motion behavior.
2. Prefer transforms and opacity; avoid repeated layout reads/writes.
3. Scope selectors and clean up animations, contexts, listeners, and ScrollTriggers on unmount.
4. Use timelines for coordinated sequences and match-media rules for breakpoint-specific behavior.
5. Register only required plugins and treat premium-plugin availability as an explicit dependency.

Output implementation, cleanup behavior, responsive and reduced-motion behavior, and visual/performance verification. Do not copy third-party examples without license and attribution review.
