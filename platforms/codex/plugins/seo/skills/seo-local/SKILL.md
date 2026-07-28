---
name: seo-local
description: Local SEO analysis covering business-type detection (brick-and-mortar, service-area, hybrid) and industry-vertical detection, then scored checks across Google Business Profile signals, reviews and reputation, local on-page SEO and location-page quality, NAP consistency and citations, LocalBusiness schema correctness, and local link/authority signals. Use for "local SEO", "Google Business Profile", "GBP", "map pack", "NAP consistency", "citations", or "multi-location" requests.
---

# Local SEO Analysis

Scored local-SEO audit covering Google Business Profile signals, reviews, on-page local signals, NAP/citation consistency, local schema, and local authority — with business-type and industry-vertical detection driving which checks actually apply.

## Key stats

| Metric | Value | Source |
|---|---|---|
| GBP signals share of local-pack weight | 32% | Whitespark 2026 |
| Proximity share of ranking variance | 55.2% | Search Atlas ML study |
| Review signals share | ~20% (up from 16%) | Whitespark 2026 |
| Searches seeking local info | 46% | Industry data |
| Mobile "near me" -> visit within 24h | 76% | Google |
| AI usage for local recommendations | 45% (up from 6%) | BrightLocal LCRS 2026 |
| ChatGPT local conversion rate | 15.9% vs 1.76% Google organic | Seer Interactive |
| Local pack ad share (Jan25 to Jan26) | 1% to 22% | Sterling Sky |

## Business type detection

Detect before scoring, since it changes which checks apply:

- **Brick-and-mortar**: visible street address, embedded map with pin/directions, "visit us at" language, structured `address` in schema. Gets full NAP + map checks.
- **Service-area business (SAB)**: no visible address, "serving [region]"/"we come to you" language, `areaServed` without `streetAddress`. Skips embedded-map and physical-address checks.
- **Hybrid**: both patterns present ("visit our showroom" + "we also serve...").

## Industry vertical detection

Route to industry-specific checks (schema subtype, citation sources) based on page signals:

| Vertical | Signals |
|---|---|
| Restaurant | Menu, reservations, cuisine, "dine-in"/"takeout" |
| Healthcare | Insurance, patients, NPI, "Dr.", HIPAA notice |
| Legal | Attorney, practice areas, bar admission, "free consultation" |
| Home services | Service area, "free estimate", "licensed/insured/bonded", "24/7" |
| Real estate | MLS listings, agent bio, brokerage, "open house" |
| Automotive | Inventory, VIN, dealership, "new/used/certified" |

Fall back to generic `LocalBusiness` analysis if nothing matches.

## Scoring dimensions

**1. GBP signals (25%).** Primary category is the single strongest local-pack factor (Whitespark's #1); a wrong primary category is the #1 negative factor. Check for a detectable GBP embed/place-ID/reviews widget, category alignment with page content, evidence of active GBP posts, photo/video presence (45% more direction requests with photos), and visible business hours (open-at-search-time ranks higher). Do **not** recommend linking the GBP profile to the site's strongest organic page — Sterling Sky's research found this risks suppressing that page's own rankings.

**2. Reviews & reputation (20%).** Review velocity beats raw count — Sterling Sky's "18-day rule" holds that a 3-week gap without a new review is a ranking risk. Check total review count against the ~10-review credibility threshold, star rating against consumer cutoffs (31% only trust 4.5+, 68% only trust 4+), recency (74% of consumers only weight the last 3 months), `aggregateRating` schema, third-party review presence, and owner-response rate (88% of consumers say they'd use a business that responds). Flag any sign of review gating (pre-screening customers before directing them to leave a review) as a policy violation, not a growth tactic — it breaches Google's fake-engagement policy and carries FTC penalties.

**3. Local on-page SEO (20%).** Dedicated service pages are simultaneously the #1 local organic factor and the #2 AI-visibility factor (Whitespark 2026). Check city+service keywords in title/H1, visible NAP, one page per core service, and for multi-location sites apply the **swap test**: if you can swap the city name and the page still reads fine, it's a doorway page — one real HVAC company lost 80% of rankings and 63% of traffic to this pattern after a Core Update. Target >60-70% unique content per location page (industry consensus, not a Google-confirmed number), local photos/testimonials/FAQs, a lazy-loaded embedded map, a `tel:` click-to-call link, and hub-and-spoke internal linking (everything within 3 clicks of home, 2-5 contextual links per 1,000 words). Multi-location sites should use crawlable subdirectory URLs (`/locations/city-name/`) over query params, each with its own `LocalBusiness` schema `@id`.

**4. NAP consistency & citations (15%).** Citation weight is declining for classic pack rankings, but 3 of the top 5 AI-visibility factors are citation-related (Whitespark 2026). Cross-check Name/Address/Phone across visible page HTML, `LocalBusiness` schema, and any visible GBP data, flagging discrepancies. Check Tier 1 presence (Yelp, BBB, Facebook via `site:` search patterns), note Apple Maps/Business listing claim status (verify any "Apple Business" launch/rename claim against an Apple primary source before repeating it), and recommend claiming Bing Places (it powers ChatGPT, Copilot, and Alexa) plus data-aggregator submission (Data Axle, Foursquare, Neustar/TransUnion).

**5. Local schema (10%).** Not a direct ranking factor (Mueller-confirmed) but drives rich-result CTR lift (43% in one case study) and helps AI systems parse the business. Check for the correct industry subtype rather than generic `LocalBusiness` — `Restaurant`, `LegalService` (not deprecated `Attorney`), `AutoDealer` (not deprecated `VehicleListing`), `MedicalClinic`/`Hospital`/`Dentist` (not generic `MedicalBusiness`) — plus `geo` at 5+ decimal places, `openingHoursSpecification`, `telephone`, `priceRange` under 100 characters, and `aggregateRating` where real review data backs it. Multi-location: each location gets its own `LocalBusiness` `@id` linked to the homepage `Organization` via `branchOf`.

**6. Local link & authority signals (10%).** Links are ~26% of local organic ranking (Whitespark's #2 factor group) even as their weight declines; "best of" list placement is the #1 AI-visibility citation factor. Check for Chamber of Commerce mentions, BBB accreditation, local press coverage, and community-involvement signals (sponsorships, events, partnerships). Brand mentions correlate roughly 3x more strongly with AI visibility than backlinks (Ahrefs).

## AI search overlap

Don't duplicate **seo-geo**'s analysis here — note that AI Overviews appear on up to 68% of local searches, that ChatGPT doesn't read GBP directly (it sources from Bing's index, Yelp, TripAdvisor, BBB, Reddit), and that Bing Places is therefore load-bearing for AI visibility even though it's not for the classic Google local pack. Recommend `$seo-geo` for the full AI-search picture.

## Output

Score 0-100 with a per-dimension breakdown, business type, detected vertical, a GBP checklist (detected vs missing), a review-health snapshot, a NAP consistency audit across all three sources, citation presence, local-schema status with a ready-to-use fix, location-page quality (unique-content %, doorway risk, store-locator status) for multi-location sites, and a Critical-to-Low prioritized action list. Always disclose what couldn't be assessed without live data — geo-grid position, Domain Authority, comprehensive backlinks, GBP Insights, real-time pack position — and point to **seo-maps** for the tiers that can fill those gaps.

## Quick wins / medium / high impact

- **Quick**: claim/verify Apple Maps and Bing Places listings; fix NAP mismatches; add correctly-typed LocalBusiness schema; add 5+ decimal `geo`; use a `tel:` link; add city+service to title/H1.
- **Medium**: build a dedicated page per core service; build a review-generation cadence that respects the 18-day rule; submit to the three major data aggregators; claim vertical-specific directories; add industry-specific schema (Menu, Physician, etc.).
- **High**: local digital PR targeting "best of" lists; genuinely unique (>60%) location-page content; presence on the platforms ChatGPT actually sources from (Yelp, TripAdvisor, BBB, Reddit); Chamber/BBB membership; community-involvement content.

## Connector mode (optional)

If a DataForSEO-style business-listings connector is available, use it for live GBP/citation-directory data and real-time local-pack position instead of the page-only inference above — say so explicitly. Without one, run every check from the live page HTML, schema, and manual `site:` searches, and mark anything requiring live map-pack data as "unknown, requires a connector" rather than guessing.

## Error handling

| Scenario | Action |
|---|---|
| URL unreachable | Report the error; don't guess; ask the user to verify. |
| No local signals detected | Report it plainly; ask the user to confirm this is a local business and provide a GBP URL if one exists. |
| NAP not found in HTML | Check schema/meta as a fallback; if still absent, flag Critical and recommend adding it to the footer and contact page. |
| Vertical unclear | Present the top two candidate verticals with supporting signals and ask the user to confirm before applying vertical-specific recommendations. |
| 50+ location pages | Apply the orchestrator's sitemap quality gates: warn at 30+ pages (enforce 60%+ unique content), hard-stop at 50+ pages pending user justification. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.

## Explicit workflow behavior

When explicitly invoked as `$seo-local`, apply this entrypoint behavior:

If no URL was provided, ask for it. Detect business type and industry
vertical, then score GBP signals, reviews, on-page local SEO, NAP/citation
consistency, local schema, and local authority signals.

## Output
See the seo-local skill's Output section, then close with the seo
orchestrator's evidence-based footer.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
