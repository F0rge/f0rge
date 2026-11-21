import type { MetadataRoute } from "next";
import { canonicalUrl, storefrontIndexable } from "@/lib/launch-indexing";

// Read the indexing switch at request time; the image is built once for every environment.
export const dynamic = "force-dynamic";

export default function robots(): MetadataRoute.Robots {
  const base = process.env.NEXT_PUBLIC_BASE_URL;
  if (!storefrontIndexable() || !base) return { rules: { userAgent: "*", disallow: "/" } };
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/account", "/checkout", "/bag", "/sign-in", "/sign-up", "/order", "/api"],
    },
    sitemap: canonicalUrl(base, "/sitemap.xml"),
  };
}
