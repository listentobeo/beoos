import type { MetadataRoute } from "next";

const siteUrl = "https://beoos.com.ng";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: [
        "/",
        "/features",
        "/pricing",
        "/how-it-works",
        "/about",
        "/support",
        "/privacy",
        "/terms",
        "/cookies",
        "/data-deletion",
      ],
      disallow: [
        "/api/",
        "/dashboard/",
        "/sign-in",
        "/sign-up",
        "/quotes/",
      ],
    },
    sitemap: `${siteUrl}/sitemap.xml`,
    host: siteUrl,
  };
}
