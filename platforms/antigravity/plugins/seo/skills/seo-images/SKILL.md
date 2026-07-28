---
name: seo-images
description: Image SEO and optimization audit covering alt text quality, file-size budgets by image role, format choice (WebP/AVIF/JPEG/PNG/SVG) with picture-element fallback chains, responsive srcset/sizes, lazy-loading correctness across native and JS-driven lazy-loaders, CLS-safe dimensions, fetchpriority/decoding hints, descriptive file naming, CDN usage, and IPTC/XMP metadata including the AI-generated-image DigitalSourceType label Google Merchant Center requires. Use for "image optimization", "alt text", "image SEO", "image audit", "convert to webp", or "image metadata" requests.
---

# Image SEO & Optimization Audit

Covers on-page image signals (alt text, dimensions, formats, loading strategy) plus the off-page metadata that affects Google Images display and Merchant Center eligibility.

## Alt text

Every `<img>` needs alt text unless it's genuinely decorative (`role="presentation"` or an intentional empty `alt=""`). Good alt text describes the image content in roughly 10-125 characters, uses keywords only where they'd occur naturally, and never repeats the filename or stuffs terms. "Red 2024 Toyota Camry sedan front view" passes; "image.jpg" or "plumber plumbing plumber services" fails.

## File-size budgets by role

Judge size against the image's role on the page, not one flat number:

| Role | Target | Warning | Critical |
|---|---|---|---|
| Thumbnails | <50KB | >100KB | >200KB |
| Content images | <100KB | >200KB | >500KB |
| Hero/banner | <200KB | >300KB | >700KB |

## Format and the `<picture>` fallback chain

Recommend WebP as the default (97%+ browser support), AVIF where maximum compression matters (92%+ support), with a JPEG/PNG/SVG fallback for photos, transparency, and icons respectively. Chain formats so the browser picks the best one it supports:

```html
<picture>
  <source srcset="image.avif" type="image/avif">
  <source srcset="image.webp" type="image/webp">
  <img src="image.jpg" alt="Descriptive alt text" width="800" height="600" loading="lazy" decoding="async">
</picture>
```

JPEG XL isn't reliable enough to depend on yet — third-party reporting describes a Rust-based decoder shipping behind a disabled-by-default Chrome flag, with no Google-owned confirmation of default support. Keep serving AVIF/WebP with a JPEG fallback and revisit if that changes.

## Responsive images and loading strategy

Check `srcset`/`sizes` against real layout breakpoints. On loading: native `loading="lazy"` belongs on below-fold images only — applying it to the hero/LCP image actively hurts LCP. Give the LCP image `fetchpriority="high"` instead, and add `decoding="async"` to everything else so decode work stays off the main thread.

Many sites use a JS-driven lazy-loader instead of the native attribute, and treating that as a defect is a false finding. Look for these signals before flagging anything as "not lazy-loaded":

| Signal in markup | Likely stack |
|---|---|
| `loading="lazy"` attribute | Native, no plugin |
| `data-perfmatters-src`/`-srcset`, class `perfmatters-lazy` | WordPress + Perfmatters |
| `data-ewww-src`/`data-eio`, class `lazyload-eio` | WordPress + EWWW |
| `data-src`/`data-lazy-src`/`data-original`/`data-srcset`, class `lazyload`/`lazy` | Lazysizes, vanilla-lazyload, jQuery plugins |
| None of the above | Genuinely not lazy-loading this image |

Report the detected mechanism next to the native `loading` value so a JS-driven site doesn't get flagged incorrectly.

## CLS prevention

Every `<img>` needs `width`/`height` attributes or an `aspect-ratio` CSS fallback so the browser reserves layout space before the image loads. Flag any image with neither.

## File names and CDN

Descriptive, hyphenated, lowercase filenames (`blue-running-shoes.webp`, not `IMG_1234.jpg`) help both users and image search. Note whether images are served from a CDN/edge-cache domain and recommend one for image-heavy sites that lack it.

## What actually moves Google Images

| Factor | Impact | Where it lives |
|---|---|---|
| Alt text | Critical (ranking) | `<img alt="">` |
| Filename | High (ranking) | Filesystem |
| Surrounding page context | High (ranking) | Page HTML |
| File size/speed | Medium (via Core Web Vitals) | Compression, format |
| IPTC Creator/Copyright | Low (display only) | File metadata |
| EXIF camera data | None | — |
| IPTC Keywords | None (Google ignores) | — |

Image discovery increasingly runs through visual-search fan-out (Lens, AI Mode, Circle to Search) rather than alt text alone — there's no distinct optimization lever for this yet beyond clean alt text and clean structured data.

## IPTC/XMP metadata and AI-image labeling

IPTC/XMP fields (Creator, Credit, Copyright) are a display-only signal for Google Images, not a ranking factor. If the site sells or displays AI-generated product imagery, flag the **Merchant Center policy requirement** separately from SEO: feeds are checked for IPTC `DigitalSourceType` on AI-generated product images (Google Merchant Center's AI-generated-content policy), and a missing label can get a feed disapproved. Vocabulary: `trainedAlgorithmicMedia` (fully AI-generated), `compositeSynthetic` (mixed captured + AI), `algorithmicMedia` (purely algorithmic, not trained on sampled data), `compositeWithTrainedAlgorithmicMedia` (AI inpainting/outpainting over real media), `digitalCapture` (real photograph, not on Google's extracted list but a valid IPTC value). AI-generated product titles/descriptions carry a parallel feed-level labeling requirement — cross-reference **seo-ecommerce** for that.

If the business wants Google's Licensable-image badge, it needs either `ImageObject` structured data with a `license` property plus `acquireLicensePage` (see **seo-schema**) or embedded IPTC licensor metadata — either path qualifies.

Treat SynthID watermarking and C2PA Content Credentials as emerging, forward-looking provenance signals worth noting, not as a currently-required field.

## Output

### Image Audit Summary

| Metric | Status | Count |
|---|---|---|
| Total Images | - | XX |
| Missing Alt Text | fail | XX |
| Oversized | warn | XX |
| Wrong Format | warn | XX |
| No Dimensions | warn | XX |
| Not Lazy Loaded | warn | XX |

### Prioritized fix list

Sorted by estimated file-size savings, largest first: image, current size, format, issues, estimated savings.

### Recommendations

Numbered, concrete: format conversions with estimated savings, missing-alt-text count, missing-dimension count, lazy-loading gaps, compression targets.

## Connector mode (optional)

If a DataForSEO-style SERP connector is available, cross-reference on-page images against Google Images rankings for the target keyword(s): pull top image results, extract domain dominance, common alt-text patterns, and format distribution in the top set, and flag keywords where the page ranks in text search but has no image presence. State explicitly that this used live SERP data.

Without a connector, skip the competitive image-SERP comparison and say it requires one — everything else in this skill (the on-page audit and format/metadata guidance) runs standalone.

For actual file work (format conversion, compression, metadata injection), this skill produces the audit and concrete recommendations only — hand off `exiftool`/`cwebp`/ImageMagick/FFmpeg commands as manual steps for the user or their build pipeline rather than executing them, since none of those tools ship with this plugin.

## Error handling

| Scenario | Action |
|---|---|
| URL unreachable | Report the connection error and status code; suggest verifying the URL and checking for an auth wall. |
| No images found | Report that no `<img>` elements were detected; note images may load via JS or CSS `background-image`. |
| Images behind CDN/auth | Note file sizes couldn't be verified directly; report markup-derived metadata (alt, dimensions, format) and flag inaccessible assets. |
| No image-SERP connector | Skip the competitive section and say so explicitly. |

## Project memory & stack awareness

Same conventions as the **seo** orchestrator skill: read `.solo/handoff.md`/`tasks.md`/`stack.md` first when `.solo/` exists, write findings back to `.solo/tasks.md` and `.solo/decisions.md`, respect AgentRoom proposal mode.
