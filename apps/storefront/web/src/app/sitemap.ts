import type { MetadataRoute } from "next";
import { canonicalUrl, sitemapPaths, storefrontIndexable } from "@/lib/launch-indexing";
import { listStoreProducts, productPath, publicCollections } from "@/lib/medusa";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  if (!storefrontIndexable()) return [];
  const base = process.env.NEXT_PUBLIC_BASE_URL || "https://collector.example";
  let products: { path: string }[] = [];
  let collections: { handle: string }[] = [];
  try {
    const listed = await listStoreProducts();
    products = listed.map((product) => ({ path: productPath(product) }));
    collections = publicCollections(listed).map((collection) => ({ handle: collection.handle }));
  } catch {
    products = [];
    collections = [];
  }
  return sitemapPaths({ indexable: true, products, collections }).map((path) => ({
    url: canonicalUrl(base, path),
  }));
}
