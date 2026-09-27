import type { Metadata } from "next";
import Link from "next/link";
import { listStoreProducts, publicCollections, type MedusaVariant, type StoreProduct } from "@/lib/medusa";
import { ProductCard } from "../product-card";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Shop furniture", description: "Discover The Collector's considered furniture collection.", alternates: { canonical: "/shop" } };

type Search = { q?: string; category?: string; collection?: string; availability?: string; min?: string; max?: string; sort?: string };
type Props = { searchParams: Promise<Record<keyof Search, string | string[] | undefined>> };

function qualifyingVariants(product: StoreProduct, params: Search): MedusaVariant[] {
  const minimum = params.min && Number.isFinite(Number(params.min)) && Number(params.min) >= 0 ? Number(params.min) : null;
  const maximum = params.max && Number.isFinite(Number(params.max)) && Number(params.max) >= 0 ? Number(params.max) : null;
  return product.variants.filter((variant) => {
    const price = variant.calculated_price?.calculated_amount;
    return (params.availability !== "in-stock" || (variant.inventory_quantity || 0) > 0)
      && (minimum == null || (price != null && price >= minimum))
      && (maximum == null || (price != null && price <= maximum));
  });
}

function filteredProducts(products: StoreProduct[], params: Search): StoreProduct[] {
  const query = (params.q || "").trim().toLocaleLowerCase("en-ZA");
  const qualifyingPrice = (product: StoreProduct) => {
    const prices = qualifyingVariants(product, params).map((variant) => variant.calculated_price?.calculated_amount).filter((price): price is number => price != null);
    return prices.length ? Math.min(...prices) : null;
  };
  const results = products.filter((product) => {
    return (!query || `${product.title} ${product.description || ""} ${product.material || ""} ${product.variants.map((variant) => `${variant.sku || ""} ${variant.material || ""}`).join(" ")}`.toLocaleLowerCase("en-ZA").includes(query))
      && (!params.category || product.categories?.some((category) => category.handle === params.category))
      && (!params.collection || product.collection?.handle === params.collection)
      && qualifyingVariants(product, params).length > 0;
  });
  return results.sort((a, b) => {
    if (params.sort === "price-asc" || params.sort === "price-desc") {
      const aPrice = qualifyingPrice(a);
      const bPrice = qualifyingPrice(b);
      if (aPrice == null) return bPrice == null ? 0 : 1;
      if (bPrice == null) return -1;
      return params.sort === "price-asc" ? aPrice - bPrice : bPrice - aPrice;
    }
    return a.title.localeCompare(b.title);
  });
}

export default async function ShopPage({ searchParams }: Props) {
  const params = Object.fromEntries(Object.entries(await searchParams).map(([key, value]) => [key, typeof value === "string" ? value : ""])) as Search;
  const products = await listStoreProducts();
  const categories = [...new Map(products.flatMap((product) => product.categories?.map((category) => [category.handle, category] as const) || [])).values()].sort((a, b) => a.name.localeCompare(b.name));
  const collections = publicCollections(products).sort((a, b) => a.title.localeCompare(b.title));
  const results = filteredProducts(products, params);
  return <div className="content shop-page">
    <p className="eyebrow">The Collector / shop</p><h1>Explore the collection.</h1>
    <p className="intro">Thoughtfully chosen pieces for rooms made to be lived in.</p>
    <form action="/shop" method="get" className="catalogue-filters" role="search">
      <div className="search-field"><label htmlFor="catalogue-search">Search furniture</label><input id="catalogue-search" name="q" type="search" defaultValue={params.q || ""} placeholder="Search pieces or materials" /></div>
      {categories.length > 0 && <div><label htmlFor="category">Category</label><select id="category" name="category" defaultValue={params.category || ""}><option value="">All categories</option>{categories.map((category) => <option key={category.id} value={category.handle}>{category.name}</option>)}</select></div>}
      {collections.length > 0 && <div><label htmlFor="collection">Collection</label><select id="collection" name="collection" defaultValue={params.collection || ""}><option value="">All collections</option>{collections.map((collection) => <option key={collection.id} value={collection.handle}>{collection.title}</option>)}</select></div>}
      <div><label htmlFor="availability">Availability</label><select id="availability" name="availability" defaultValue={params.availability || ""}><option value="">All pieces</option><option value="in-stock">In stock</option></select></div>
      <div><label htmlFor="min-price">Minimum price (R)</label><input id="min-price" name="min" type="number" min="0" step="1" defaultValue={params.min || ""} /></div>
      <div><label htmlFor="max-price">Maximum price (R)</label><input id="max-price" name="max" type="number" min="0" step="1" defaultValue={params.max || ""} /></div>
      <div><label htmlFor="sort">Sort by</label><select id="sort" name="sort" defaultValue={params.sort || "title"}><option value="title">Name A–Z</option><option value="price-asc">Price: low to high</option><option value="price-desc">Price: high to low</option></select></div>
      <div className="filter-actions"><button type="submit">Show pieces</button><Link href="/shop">Clear filters</Link></div>
    </form>
    <div className="results-heading" role="status" aria-live="polite">{results.length} {results.length === 1 ? "piece" : "pieces"}</div>
    {results.length ? <div className="product-grid">{results.map((product) => <ProductCard key={product.id} product={product} variants={qualifyingVariants(product, params)} />)}</div> : <div className="empty-state"><h2>No pieces found.</h2><p>Try a different search or clear your filters.</p><Link href="/shop" className="text-link">See all pieces →</Link></div>}
  </div>;
}
