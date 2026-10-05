import type { MetadataRoute } from "next";
import { canonicalUrl, storefrontIndexable } from "@/lib/launch-indexing";

export default function robots(): MetadataRoute.Robots {
  const base = process.env.NEXT_PUBLIC_BASE_URL;
  if (!storefrontIndexable() || !base) return { rules: { userAgent: "*", disallow: "/" } };
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/account", "/checkout", "/bag", "/sign-in", "/sign-up", "/order", "/api", "/study"],
    },
    sitemap: canonicalUrl(base, "/sitemap.xml"),
  };
}
