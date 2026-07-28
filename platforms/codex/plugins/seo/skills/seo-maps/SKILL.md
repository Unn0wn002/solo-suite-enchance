---
name: seo-maps
description: Maps-platform intelligence for local businesses — geo-grid rank simulation, Google Business Profile completeness scoring, cross-platform review intelligence (velocity, sentiment, fake-review signals), competitor radius mapping, cross-platform NAP verification across Google/Bing/Apple/OSM, and LocalBusiness JSON-LD generation, running in free-source mode by default and upgrading automatically when a maps/business-data connector is available. Use for "maps", "geo-grid", "rank tracking", "GBP audit", "review velocity", or "competitor radius" requests.
---

# Maps Intelligence

Analyzes how a local business appears on maps *platforms* (Google Maps, Bing Places, Apple Maps, OpenStreetMap) via APIs — a different layer from **seo-local**, which audits local-SEO signals on the *website* itself via HTML. Don't duplicate seo-local's on-page checks here; recommend `$seo-local` for those.

## Commands

| Command | What it does | Needs a connector? |
|---|---|---|
| `$seo-maps <url>` | Full maps-presence audit, auto-detects capability tier | No (degrades gracefully) |
| `$seo-maps grid <keyword> <location>` | Geo-grid rank scan (7x7 default) | Yes |
| `$seo-maps reviews <business> <location>` | Cross-platform review intelligence | Yes |
| `$seo-maps competitors <keyword> <location>` | Competitor radius mapping | No (Overpass fallback) |
| `$seo-maps nap <business-name>` | Cross-platform NAP verification | No |
| `$seo-maps schema <business-name>` | Generate LocalBusiness JSON-LD | No |
| `$seo-maps gbp <business> <location>` | GBP completeness audit | Preferred, has a manual fallback |

## Capability tiers

Detect and **always state** which tier is running before presenting results:

- **Free tier** (no maps/business-data connector): Overpass API for competitor discovery, Geoapify/Nominatim for geocoding and POI search, a static GBP checklist filled from whatever's visible on the site, and schema generation from collected data. This is the default and is fully usable on its own.
- **Connector tier** (a DataForSEO-style business-listings/SERP connector is available): adds geo-grid rank tracking, a live GBP profile pull, review-velocity/sentiment intelligence, GBP post/Q&A activity, and Tripadvisor/Trustpilot review data.
- **Connector + Maps API tier** (the above plus a Google Maps Platform key in the environment): adds live Places details, real-time business status, and photo analysis. Google's ToS restricts storage to `place_id` only — any cached lat/lng must be dropped within 30 days.

## Geo-grid rank tracking (connector tier)

Simulates Maps searches from a grid of coordinates around the business to show rank variation across its service area. Workflow: geocode the address to a center point, generate a grid (default 7x7, 5km radius) via Haversine offsets, **display an estimated cost and get explicit confirmation before firing any paid calls**, run the ranking query at each grid point, locate the target business's rank at each, and compute Share of Local Voice: `(points where rank is top-3) / (total points) * 100`. Render the result as an ASCII heatmap alongside the average rank. Always show the cost warning first:

```
Geo-Grid Scan: [keyword] at [location]
Grid: 7x7 (49 points) | Keywords: [N] | Est. cost: $[amount]
This will consume connector credits. Proceed?
```

## GBP profile audit

Score across the roughly 25 fields that affect GBP quality and ranking (category correctness, hours, attributes, photos, posts, Q&A, messaging, products/services, description). With a connector, pull the profile directly, map fields to the checklist, score Present+Optimized=2 / Present=1 / Missing=0 with industry weight multipliers, and normalize to 0-100. Without one, extract whatever GBP signals are visible on the website itself (Maps embed, place references, review widgets), apply the static checklist, and mark anything undetectable as "unknown — requires a connector," rather than guessing at live profile data.

Recent GBP surface changes worth checking for: review-media URLs, recurring local-post scheduling, review reply/moderation state, and invitation Place ID — and be aware Google is rolling out conversational Maps assistance and agentic booking/calling for select local-service categories, which raises the stakes on GBP data completeness beyond pure ranking.

## Review intelligence (connector tier)

Pull Google reviews sorted newest-first, compute monthly review velocity over the trailing 6 months, check for any 3-week gap (the 18-day-rule ranking risk), assess rating-distribution shape (healthy = skewed toward 5-star, not uniform), compute owner-response rate, and cross-reference Tripadvisor/Trustpilot where available.

**Fake-review signals** — flag any review matching 2 or more: uniform same-day/hour timing, reviewer accounts with a single review or no history, geographic mismatch between reviewer and business location, a 5-star volume spike with no matching marketing activity, or near-identical text across reviews.

## Competitor radius mapping

Free tier: geocode the business, query Overpass for same-category businesses within radius, sort by distance. Connector tier: use the maps SERP API for the keyword+location, pull full profile data for the top ~20 (rating, review count, categories, photos, attributes), and compute a competitive-density score (competitors per km²).

## Cross-platform NAP verification

Search for the business on Google (from GBP/Maps SERP data), Bing (`bing.com/maps` query), Apple (no public API — verify claim status manually; treat any "Apple Business" rename/launch claim as third-party-sourced until confirmed by an Apple primary source), and OSM (Overpass/Nominatim). Extract Name/Address/Phone from each and flag: Critical for a name mismatch, High for an address mismatch, Medium for a phone mismatch. Recommend claiming any unclaimed profile.

## Schema generation

Pick the most specific `LocalBusiness` subtype for the detected industry (see **seo-local**'s vertical table), populate required properties (`@type`, `name`, `address`, `image`) plus recommended ones (`telephone`, `url`, `geo`, `openingHoursSpecification`, `priceRange`), add multi-location properties (`branchOf`, `areaServed`, `sameAs`) where relevant, and include `aggregateRating` only when backed by real review data collected above. Never fabricate self-serving review markup — Google ignores `LocalBusiness` review markup sourced from the business itself; only mark up third-party reviews actually visible on the page.

## Output

Maps Health Score (0-100) with a per-dimension breakdown, the detected capability tier and what it unlocked, a geo-grid heatmap with SoLV and average rank (connector tier only), the GBP field-by-field audit, review intelligence (velocity, distribution, response rate, cross-platform comparison), the competitor landscape (count in radius, top 5, density score), cross-platform presence status (Google/Bing/Apple/OSM), a generated LocalBusiness JSON-LD block if one was missing or incomplete, a Critical-to-Low action list, a credit/cost report for any connector calls made, and an explicit statement of what couldn't be assessed at the current tier.

## Cross-skill delegation

Website on-page local signals: `$seo-local`. Full AI-search visibility: `$seo-geo`. Schema validation/fixes: `$seo-schema`.

## Connector mode (optional)

This skill's value scales directly with connector availability — say explicitly which tier ran. The free tier (Overpass/Geoapify/Nominatim, static checklists) always works standalone. If a DataForSEO-style connector becomes available mid-session, offer to re-run the connector-only sections (geo-grid, live GBP, review intelligence) rather than silently upgrading without telling the user.

## Error handling

| Scenario | Action |
|---|---|
| No maps/business-data connector | Run free tier; tell the user explicitly what's unavailable (geo-grid, live GBP, review intelligence) and that a connector would unlock it. |
| Business not found in Maps SERP | Retry by business name/keyword; if still not found, report it plainly rather than guessing at a profile. |
| Geocoding fails | Ask the user for coordinates or a more specific address. |
| Connector rate limit hit | Report the limit; suggest waiting or falling back to a non-live/queued method. |
| No reviews found | Report the zero-review state and recommend a review-generation strategy targeting the 18-day cadence. |
| Multi-location business | Ask which location to analyze, or offer a batch run with a per-location cost estimate. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.

## Explicit workflow behavior

When explicitly invoked as `$seo-maps`, apply this entrypoint behavior:

If no URL was provided, ask for it. Audit maps-platform presence (Google,
Bing, Apple, OSM), running in free-tier mode unless a maps/business-data
connector is available, and state which tier ran.

## Output
See the seo-maps skill's Output section, then close with the seo
orchestrator's evidence-based footer.

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
