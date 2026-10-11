import Link from "next/link";
import { Button } from "@f0rge/ui";
import { TrackedProductLink } from "@/components/analytics/tracked-product-link";
import { listStoreProducts, lowestPricedVariant, priceLabel, productPath, publicCollections } from "@/lib/medusa";
import { ProductCard } from "./product-card";
import { InteractiveStudy } from "./study/interactive-study";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const products = await listStoreProducts();
  const heroProduct = products.find((product) => product.thumbnail || product.images?.[0]?.url);
  const heroImage = heroProduct?.thumbnail || heroProduct?.images?.[0]?.url;
  const heroPrices = heroProduct?.variants.map((variant) => variant.calculated_price?.calculated_amount).filter((price): price is number => price != null) || [];
  const collections = publicCollections(products);

  return <>
    <section className="home-hero" aria-labelledby="hero-title">
      <div className="hero-copy">
        <p className="eyebrow">Vellano · considered furniture</p>
        <h1 id="hero-title">Room to<br /><em>live well.</em></h1>
        <p className="hero-description">Good furniture makes room for life. Discover pieces that bring quiet character to the everyday.</p>
        <Button className="hero-shop-button" nativeButton={false} render={<Link href="/shop" />}>Explore the collection <span aria-hidden="true">↗</span></Button>
        <p className="hero-footnote">A little less. A little better.</p>
      </div>
      {heroProduct && heroImage ? <TrackedProductLink href={productPath(heroProduct)} productId={heroProduct.id} className="hero-image-link">
        <img className="hero-photograph" src={heroImage} alt={heroProduct.title} width={1400} height={1200} fetchPriority="high" loading="eager" />
        <div className="hero-product-caption"><div><p className="eyebrow">In the collection</p><strong>{heroProduct.title}</strong><span>{new Set(heroPrices).size > 1 ? "From " : ""}{priceLabel(lowestPricedVariant(heroProduct.variants))}</span></div><span className="hero-product-arrow" aria-hidden="true">↗</span></div>
      </TrackedProductLink> : <div className="hero-no-image"><span className="wordmark">VELLANO</span><p>Considered pieces.<br />Everyday living.</p><span className="eyebrow">Explore our furniture collection</span></div>}
    </section>
    <section className="content featured-section" id={collections.length === 0 ? "collection" : undefined}>
      <div className="section-heading"><div><p className="eyebrow">The Vellano edit</p><h2>Find your next piece.</h2></div><Link href="/shop" className="text-link">Shop all furniture <span aria-hidden="true">↗</span></Link></div>
      <div className="product-grid">{products.slice(0, 6).map((product) => <ProductCard key={product.id} product={product} />)}</div>
      {products.length === 0 && <div className="empty-state"><h3>A collection in the making.</h3><p>Our furniture will appear here as pieces become available.</p></div>}
    </section>
    {collections.length > 0 && <section className="collection-feature" id="collection">
      <div className="content"><div className="section-heading"><div><p className="eyebrow">A considered collection</p><h2>Make it your own.</h2></div><Link href="/collections" className="text-link">Explore collections <span aria-hidden="true">↗</span></Link></div>
        <div className="collection-cards">{collections.slice(0, 3).map((collection) => {
          const pieces = products.filter((product) => product.collection?.id === collection.id);
          const cover = pieces.find((product) => product.thumbnail || product.images?.[0]?.url);
          const image = cover?.thumbnail || cover?.images?.[0]?.url;
          return <Link key={collection.id} href={`/shop?collection=${encodeURIComponent(collection.handle)}`} className="collection-card">
            <div className="collection-image">{image ? <img src={image} alt="" width={800} height={600} loading="lazy" /> : <span className="wordmark">VELLANO</span>}</div>
            <div className="collection-card-copy"><div><h3>{collection.title}</h3><p>{pieces.length} {pieces.length === 1 ? "piece" : "pieces"} to explore</p></div><span aria-hidden="true">↗</span></div>
          </Link>;
        })}</div>
      </div>
    </section>}
    <section className="content home-intro" id="our-approach"><p className="eyebrow">Our point of view</p><div><h2>A home is built<br /><em>around living.</em></h2><p>Warmth in the materials. Clarity in the shapes. Space for your own story. Our collection brings together furniture that feels at home in everyday life.</p><Link href="/shop" className="text-link">Discover the collection <span aria-hidden="true">↗</span></Link></div></section>
    <details className="home-study"><summary><span className="study-summary-copy"><span className="eyebrow">An illustrative exploration</span><span className="study-summary-title">A study in form.</span></span><span className="study-summary-action">Explore a study in form <span aria-hidden="true">+</span></span></summary><InteractiveStudy /></details>
    <section className="content home-support"><div><p className="eyebrow">Here to help</p><h2>A considered purchase.</h2></div><p>Take a closer look at materials, dimensions and availability on each piece. Find delivery, collection and returns information before you decide.</p><Link href="/support" className="text-link">Get in touch <span aria-hidden="true">↗</span></Link></section>
  </>;
}
