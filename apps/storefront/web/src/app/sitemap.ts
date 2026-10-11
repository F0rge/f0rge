import type { MetadataRoute } from "next";
import { canonicalUrl, sitemapPaths, storefrontIndexable } from "@/lib/launch-indexing";
import { merchandisingCollections } from "@/lib/catalogue-collections";
import { listStoreProducts, productPath } from "@/lib/medusa";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = process.env.NEXT_PUBLIC_BASE_URL;
  if (!storefrontIndexable() || !base) return [];
  let products: { path: string }[] = [];
  let collections: { handle: string }[] = [];
  try {
    const listed = await listStoreProducts();
    products = listed.map((product) => ({ path: productPath(product) }));
    collections = merchandisingCollections(listed).map((collection) => ({ handle: collection.handle }));
  } catch {
    products = [];
    collections = [];
  }
  return sitemapPaths({ indexable: true, products, collections }).map((path) => ({
    url: canonicalUrl(base, path),
  }));
}
