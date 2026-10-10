import type { Metadata } from "next";
import Link from "next/link";
import { listStoreProducts, publicCollections } from "@/lib/medusa";
import { ProductCard } from "../product-card";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Collections", description: "Explore furniture collections from The Collector.", alternates: { canonical: "/collections" } };

export default async function CollectionsPage() {
  const products = await listStoreProducts();
  const collections = publicCollections(products);
  return <div className="content collections-page"><p className="eyebrow">The Collector / collections</p><h1>Explore by collection.</h1>
    {collections.length ? collections.map((collection) => {
      const pieces = products.filter((product) => product.collection?.handle === collection.handle);
      return <section key={collection.id} className="collection-section"><div className="section-heading"><h2>{collection.title}</h2><Link href={`/shop?collection=${encodeURIComponent(collection.handle)}`} className="text-link">View {pieces.length} {pieces.length === 1 ? "piece" : "pieces"} ↗</Link></div><div className="product-grid">{pieces.slice(0, 3).map((product) => <ProductCard key={product.id} product={product} />)}</div></section>;
    }) : <div className="empty-state"><h2>No collections are published yet.</h2><p>Published collections will appear here.</p><Link href="/shop" className="text-link">Shop all pieces →</Link></div>}
  </div>;
}
