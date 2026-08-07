import type { MetadataRoute } from "next";

// Reuses the exact same env var app/layout.tsx already uses for
// metadataBase/OG/Twitter URLs, so there is one source of truth for the
// production domain instead of a second, possibly-drifting hardcoded one.
// See .solo/tasks.md T3.
export default function robots(): MetadataRoute.Robots {
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

  return {
    rules: {
      userAgent: "*",
      allow: "/",
    },
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
