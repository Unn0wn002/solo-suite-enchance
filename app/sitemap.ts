import type { MetadataRoute } from "next";

// Single-page site today, so a single-entry sitemap is honest rather than
// listing in-page anchor sections (#system, #workflow, #rooms, #proof) as if
// they were independently indexable routes. Extend this array if/when the
// site grows real sub-routes. See .solo/tasks.md T3.
export default function sitemap(): MetadataRoute.Sitemap {
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

  return [
    {
      url: siteUrl,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 1,
    },
  ];
}
