---
name: seo-ecommerce
description: E-commerce SEO — product-page on-page audit (title/meta/headings/images/internal links/content), Product schema validation and generation against Google Merchant requirements, and marketplace intelligence (Google Shopping/Amazon pricing and seller landscape, organic-vs-Shopping keyword gaps) where a data connector is available. Use for "ecommerce SEO", "product SEO", "Google Shopping", "product schema", "Amazon SEO", or "merchant SEO" requests.
---

# E-commerce SEO Analysis

Two tiers: an on-page product audit that works standalone against any fetched page, and marketplace intelligence (Shopping/Amazon pricing, seller landscape, keyword gaps) that needs a commerce-data connector.

## 1. Product page audit (works standalone)

Fetch and parse the product page, then check:

**Title tag** — primary product keyword present, brand included, under 60 characters, roughly `[Product Name] - [Key Feature] | [Brand]`.

**Meta description** — keyword plus benefit, price or "from $XX" (draws rich-snippet interest), a call to action, under 155 characters.

**Headings** — single H1 matching the product name, H2s for Features/Specifications/Reviews/Related Products, no duplicate H1s across variant pages.

**Images** — alt text names the product plus its distinguishing feature, descriptive filenames (not `IMG_001.jpg`), WebP with a JPEG fallback, at least 3 images (hero/detail/lifestyle), ≥800px for Shopping eligibility, lazy-loading only below the fold.

**Internal linking** — breadcrumb trail (Home > Category > Subcategory > Product), a related/cross-sell section, a keyword-rich link back to the category page, reviews linking to a full review page if one exists separately.

**Content** — a genuinely unique description (not manufacturer boilerplate), ≥200 words in the body description, a specs table rather than prose-only specs, on-page user reviews as a UGC signal.

**Scoring weights**: schema completeness 25%, title/meta 15%, image optimization 20%, content quality 20%, internal linking 10%, technical (speed/mobile/canonical) 10%.

## 2. Product schema

Confirmed-required fields for Google Merchant: `name`, `image`, `offers` (use `Offer`, not `AggregateOffer`, for a single merchant listing).

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "",
  "image": [""],
  "offers": {
    "@type": "Offer",
    "url": "",
    "priceCurrency": "USD",
    "price": "0.00",
    "availability": "https://schema.org/InStock"
  }
}
```

Recommended additions that unlock richer results: `sku`, `description`/`brand`/`offers.seller`, `gtin13`/`gtin14`/`mpn`, `aggregateRating`, `review` (at least one), variant attributes (`color`/`material`/`size`), `shippingDetails` (a `ShippingDetails` block, or set shipping/returns directly in Search Console without a Merchant Center account), `hasMerchantReturnPolicy`. For adult-oriented products, `hasAdultConsideration` with the value `https://schema.org/SexualContentConsideration` is required by Google Search.

**Validation rules**: `price` is a bare number string, never `"$29.99"`; `availability` uses the full Schema.org URL enum; `image` is an array with at least one high-res URL; `priceCurrency` is ISO 4217; a present `brand.name` must not be empty or `"N/A"`; `priceValidUntil` is ISO 8601; if `aggregateRating` is present, `ratingValue` and `reviewCount` are both required.

**Completeness scoring**: required fields alone = 50/100; + aggregateRating = 65; + sku/gtin/mpn = 75; + shippingDetails = 85; + merchantReturnPolicy = 90; + 3 or more reviews = 100.

## 3. Marketplace intelligence (needs a connector)

**Pricing intelligence**: price distribution (min/max/median/P25/P75), outliers beyond 2 standard deviations from median, price-to-rating correlation.

**Seller landscape**: top sellers by listing count, merchant rating distribution, free-shipping prevalence, new-vs-established seller mix.

**Listing quality**: title keyword patterns among top listings, rating/review-count benchmarks, image counts, availability-status distribution.

**Cross-marketplace comparison** (Google Shopping vs Amazon): average price, median rating, average review count, top-seller share, free-shipping percentage, side by side.

**Keyword gaps**: cross-reference organic rankings against Shopping/marketplace presence for the same keywords.

| Gap type | Meaning | Action |
|---|---|---|
| Organic only | Ranks organically, no Shopping presence | Get a Merchant Center feed live, bid these keywords |
| Shopping only | Shopping visibility, weak/no organic | Build content (buying guides, comparisons) for these keywords |
| Both | Visible in both channels | Optimize — keep price consistent, enhance schema |
| Neither | No visibility either way | Low priority unless volume is high |

## 4. Universal Commerce Protocol (UCP)

Google-initiated open standard (co-developed with Shopify, Etsy, Wayfair, Target, Walmart; payment partners including Visa/Mastercard/Stripe/Adyen/Amex) letting AI agents discover, negotiate, and transact with merchants without bespoke integrations. Confirmed live with a first reference implementation for conversational buying in Google's AI Mode; uses date-based versioning (not semver — a literal `"version": "1.0"` in a profile is invalid), with Native and Embedded (approved-merchant) integration paths. Pairs with the Agent Payments Protocol (AP2). Canonical references: developers.google.com/merchant/ucp and ucp.dev.

For a merchant already on Google Merchant Center with clean Product schema, check for a UCP profile at `/.well-known/ucp` declaring capabilities (e.g. `dev.ucp.shopping.checkout`, `.fulfillment`, `.discount`). A missing profile is an opportunity to flag, not a defect — broad adoption is still early even though the standard itself is live.

## Cross-skill routing

| Area | Hand off to |
|---|---|
| Product schema generation details | **seo-schema** |
| Product image audit | **seo-images** |
| Description uniqueness/E-E-A-T | **seo-content** |
| Core Web Vitals on product pages (LCP on the hero image) | **seo-technical** |
| Indexation/performance for product URLs | **seo-google** |

## Output

```
## E-commerce SEO Report: [URL or keyword]

### Overall Score: XX/100
- Schema Completeness: XX/100
- Title & Meta: XX/100
- Image Optimization: XX/100
- Content Quality: XX/100
- Internal Linking: XX/100

### Marketplace Intelligence (if a connector is available)
- Listings found, price range/median, top seller, cross-marketplace comparison

### Top Recommendations
1. [Critical] …
2. [High] …
3. [Medium] …
```

## Connector mode (optional)

Marketplace intelligence (section 3) requires a commerce-data MCP connector (DataForSEO Merchant-API-class tooling or equivalent) — without one, skip that section entirely and say plainly that Shopping/Amazon competitive data wasn't checked, rather than guessing at prices or seller share. The on-page audit (section 1) and schema validation (section 2) work fully standalone via `${CLAUDE_PLUGIN_ROOT}/lib/url_guard.py`-guarded fetches.

## Error handling

| Scenario | Action |
|---|---|
| No Product schema found | Analyze the page content and generate a recommended schema from scratch. |
| No commerce connector available | Run the on-page and schema sections only; note marketplace intelligence was skipped. |
| Non-product URL given | Detect the actual page type (category/home) and suggest schema-only analysis instead. |
| Invalid/unreachable URL | Report the fetch error, don't guess at page content. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.
