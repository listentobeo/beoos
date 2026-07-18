import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "BeoOS",
    short_name: "BeoOS",
    description:
      "AI-powered business command center for inbox, WhatsApp, CRM, quotations, pricing, and follow-up automation.",
    start_url: "/dashboard/inbox",
    scope: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#ed633f",
    icons: [
      {
        src: "/favicon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
      {
        src: "/favicon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "maskable",
      },
    ],
  };
}
