import Link from "next/link";
import { listStoreProducts, publicCollections } from "@/lib/medusa";
import { ProductCard } from "./product-card";
import { InteractiveStudy } from "./study/interactive-study";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const products = await listStoreProducts();
  const featured = products.slice(0, 3);
  const collections = publicCollections(products);
  return <>
    <section className="hero">
      <div className="hero-heading"><p className="eyebrow">The Collector · considered interiors</p><h1>Objects for a <em>life in colour.</em></h1><Link className="text-link light" href="/shop">Explore the collection <span aria-hidden="true">↗</span></Link></div>
      <div className="hero-grid">{featured.map((product, index) => <ProductCard key={product.id} product={product} hero priority={index === 0} />)}</div>
      {featured.length === 0 && <p className="hero-empty">No pieces are published yet.</p>}
      <div className="hero-footer"><span>Furniture selected for everyday living</span><span>{products.length} {products.length === 1 ? "piece" : "pieces"}</span></div>
    </section>
    <section className="content home-intro"><p className="eyebrow">An edited point of view</p><h2>Pieces to keep close.</h2><p>Explore furniture that brings warmth, shape and character to a room.</p><Link href="/shop" className="text-link">Shop all pieces <span aria-hidden="true">↗</span></Link></section>
    <InteractiveStudy />
    {collections.length > 0 && <section className="content collection-feature" id="collection"><div><p className="eyebrow">Find your place</p><h2>Collections</h2></div><div className="collection-links">{collections.map((collection) => <Link key={collection.id} href={`/shop?collection=${encodeURIComponent(collection.handle)}`}>{collection.title}<span aria-hidden="true">↗</span></Link>)}</div></section>}
    <section className="content featured-section" id={collections.length === 0 ? "collection" : undefined}><div className="section-heading"><div><p className="eyebrow">The edit</p><h2>Discover the pieces</h2></div><Link href="/shop" className="text-link">View all <span aria-hidden="true">↗</span></Link></div><div className="product-grid">{products.slice(0, 6).map((product) => <ProductCard key={product.id} product={product} />)}</div>{products.length === 0 && <p>No pieces are published yet.</p>}</section>
  </>;
}
