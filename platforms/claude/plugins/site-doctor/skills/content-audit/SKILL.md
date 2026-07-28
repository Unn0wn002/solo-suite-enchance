---
name: content-audit
description: Audit the content of a website — broken or missing media, stale and outdated content, readability and clarity, tone and terminology consistency, placeholder/lorem-ipsum left in production, spelling and grammar, duplicate content, and content structure. Use whenever the user wants a content review, editorial audit, "check my copy", find outdated or broken content, readability check, or wants site content polished and consistent before or after launch. Complements seo-optimization (search-facing content) with an editorial lens.
---

# Content Audit

Great engineering wrapped around stale, broken, or sloppy content still reads as an unfinished site. This audit looks at content as a reader and an editor: is it current, correct, clear, consistent, and complete? Distinct from SEO (which optimizes content for search) — here the lens is editorial quality and trustworthiness.

## Setup

Get the site (crawl key pages) and/or the content source (CMS export, markdown files, templates). Ask what the content is *for* and who the audience is — the right reading level and tone for developer docs differs from a consumer landing page. Prioritize the pages that matter most (home, product, pricing, high-traffic content), then sample deeper pages.

## 1. Broken & missing content (fix first — it's the most visibly broken)

- **Broken media**: images that 404, videos that don't load, missing icons, broken embeds. (The `check_links.py` script from website-audit catches broken asset URLs — reuse it.)
- **Broken links** within content: dead internal links, external links to pages that no longer exist or moved (link rot accumulates over time).
- **Placeholder content in production**: `lorem ipsum`, "TODO", "coming soon" that never came, `[INSERT X HERE]`, sample/dummy data, "Your Company Name" boilerplate, test content. Grep for these — they're embarrassing and surprisingly common. Search patterns: `lorem ipsum`, `TODO`, `FIXME`, `placeholder`, `insert `, `xxxx`, `sample text`, `test test`.
- **Empty states**: pages/sections that render blank or with no meaningful content; "no results" states that look broken rather than intentional.
- Missing alt text on images (overlaps accessibility-review, but here as a content-completeness issue).

## 2. Stale & outdated content

- **Dated information**: copyright year, "as of [old year]", outdated statistics, old pricing, references to discontinued products/features, team members who've left, events that already passed still shown as upcoming.
- **Outdated claims**: "the leading X", version numbers, "new" features that are years old, roadmap items long since shipped or abandoned.
- **Broken time-sensitivity**: blog posts with no date (readers can't judge relevance), or dates revealing the site looks abandoned (last post 3 years ago).
- Legal/policy pages with old "last updated" dates that may no longer match reality (ties to compliance-check).

## 3. Readability & clarity

- **Reading level fits the audience**: sentences not needlessly long/dense; jargon defined or avoided for general audiences; active voice; scannable structure (headings, short paragraphs, lists) rather than walls of text.
- **Clear and concrete**: says what it means; avoids vague filler and hype without substance; leads with the point. Value propositions are specific, not generic ("we deliver innovative solutions").
- **Structure**: logical heading hierarchy that outlines the content (overlaps SEO/accessibility but here for reader comprehension); important information above the fold / early; clear calls to action.
- **Actionability**: instructions are complete and followable; nothing assumes context the reader doesn't have.

## 4. Consistency (the thing that signals polish or its absence)

- **Terminology**: the same thing called the same name throughout (not "sign in" here and "log in" there, "cart" vs "basket", product name spelled/capitalized consistently). Build a quick term list and check adherence.
- **Tone & voice**: consistent register across pages — not formal on one page and casual on the next; consistent person (you/we) and point of view.
- **Formatting conventions**: consistent capitalization (title case vs sentence case for headings), date formats, number formats, button label style, oxford comma or not — pick a convention and check it holds.
- **Brand consistency**: name, tagline, key messaging consistent; no leftover references to an old name/brand after a rename.

## 5. Correctness

- **Spelling & grammar**: typos, grammatical errors, punctuation. (Read carefully — automated checks miss context-dependent errors like their/there, its/it's, homophones.)
- **Factual accuracy** where checkable: internal consistency (the same number stated differently on different pages — e.g. "10,000 customers" vs "over 5,000"), claims that contradict each other.
- **Working examples**: code samples that actually run, commands that are correct, links in examples that resolve.

## 6. Duplication & gaps

- **Duplicate content**: the same text copy-pasted across pages (also an SEO issue — see seo-optimization), near-duplicate pages that should be consolidated.
- **Content gaps**: expected pages missing (no about/contact/pricing/privacy), questions the content raises but doesn't answer, dead ends with no next step.
- **Orphaned content**: pages with no links pointing to them (nobody can find them — overlaps SEO architecture).

## Report format

Shared audit structure (Summary → Scorecard → Findings → Fix order), grouped **Broken/Missing / Stale / Readability / Consistency / Correctness / Duplication**. Each finding names the specific page and text, quotes the problem, and gives the fix (the corrected copy, the term to standardize on, the media to replace). Rank by visibility and trust impact — lorem ipsum on the homepage or a broken hero image outranks an inconsistent oxford comma. For search-facing content optimization, hand off to seo-optimization; for broken asset detection, reuse website-audit's link checker.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
