import type { MetadataRoute } from "next";
import { canonicalUrl, sitemapPaths, storefrontIndexable } from "@/lib/launch-indexing";
import { listStoreProducts, productPath } from "@/lib/medusa";

// Read the indexing switch at request time; the image is built once for every environment.
export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = process.env.NEXT_PUBLIC_BASE_URL;
  if (!storefrontIndexable() || !base) return [];
  let products: { path: string }[] = [];
  try {
    products = (await listStoreProducts()).map((product) => ({ path: productPath(product) }));
  } catch {
    products = [];
  }
  return sitemapPaths({ indexable: true, products }).map((path) => ({
    url: canonicalUrl(base, path),
  }));
}
