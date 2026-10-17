import Link from "next/link";
import { Button } from "@f0rge/ui";
import { StorefrontMotion } from "@/components/storefront-motion";
import { TrackedProductLink } from "@/components/analytics/tracked-product-link";
import { listStoreProducts, lowestPricedVariant, priceLabel, productPath, publicCollections } from "@/lib/medusa";
import { Wordmark } from "@/components/wordmark";
import { ProductCard } from "./product-card";
import { InteractiveStudy } from "./study/interactive-study";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const products = await listStoreProducts();
  const heroProduct = products.find((product) => product.thumbnail || product.images?.[0]?.url);
  const heroImage = heroProduct?.thumbnail || heroProduct?.images?.[0]?.url;
  const heroPrices = heroProduct?.variants.map((variant) => variant.calculated_price?.calculated_amount).filter((price): price is number => price != null) || [];
  const collections = publicCollections(products);

  return <StorefrontMotion>
    <section data-reveal className="home-hero" aria-labelledby="hero-title">
      <div className="hero-copy">
        <div className="hero-heading"><p className="eyebrow">Furniture for everyday life</p><h1 id="hero-title">Make room<br />for living.</h1></div>
        <div className="hero-details"><p className="hero-description">Find pieces for living and dining. Explore materials and dimensions, then choose what works for your space.</p>
          <div className="hero-actions"><Button className="hero-shop-button" nativeButton={false} render={<Link href="/shop" />}>Shop furniture</Button><Link className="text-link" href="/collections">Explore collections <span aria-hidden="true">›</span></Link></div>
        </div>
      </div>
      {heroProduct && heroImage ? <TrackedProductLink href={productPath(heroProduct)} productId={heroProduct.id} className="hero-image-link">
        <div className="hero-product-visual"><img className="hero-photograph" src={heroImage} alt={heroProduct.title} width={1400} height={1200} fetchPriority="high" loading="eager" /></div>
        <div className="hero-product-caption"><div><p className="eyebrow">Featured piece</p><strong>{heroProduct.title}</strong><span>{new Set(heroPrices).size > 1 ? "From " : ""}{priceLabel(lowestPricedVariant(heroProduct.variants))}</span></div><span className="hero-product-arrow">Explore piece <span aria-hidden="true">›</span></span></div>
      </TrackedProductLink> : <div className="hero-no-image"><span className="wordmark"><Wordmark /></span><p>Your next piece starts here.</p><span className="eyebrow">Explore our furniture collection</span></div>}
    </section>
    <section data-reveal className="content featured-section" id={collections.length === 0 ? "collection" : undefined}>
      <div className="section-heading"><div><p className="eyebrow">Explore the lineup</p><h2>Find your next piece.</h2></div><Link href="/shop" className="text-link">Shop all furniture <span aria-hidden="true">↗</span></Link></div>
      <div className="product-grid">{products.slice(0, 6).map((product) => <ProductCard key={product.id} product={product} />)}</div>
      {products.length === 0 && <div className="empty-state"><h3>A collection in the making.</h3><p>Our furniture will appear here as pieces become available.</p></div>}
    </section>
    {collections.length > 0 && <section data-reveal className="collection-feature" id="collection">
      <div className="content"><div className="section-heading"><div><p className="eyebrow">Collections</p><h2>Find your space.</h2></div><Link href="/collections" className="text-link">Explore collections <span aria-hidden="true">↗</span></Link></div>
        <div className="collection-cards">{collections.slice(0, 3).map((collection) => {
          const pieces = products.filter((product) => product.collection?.id === collection.id);
          const cover = pieces.find((product) => product.thumbnail || product.images?.[0]?.url);
          const image = cover?.thumbnail || cover?.images?.[0]?.url;
          return <Link key={collection.id} href={`/shop?collection=${encodeURIComponent(collection.handle)}`} className="collection-card">
            <div className="collection-image">{image ? <img src={image} alt="" width={800} height={600} loading="lazy" /> : <span className="wordmark"><Wordmark /></span>}</div>
            <div className="collection-card-copy"><div><h3>{collection.title}</h3><p>{pieces.length} {pieces.length === 1 ? "piece" : "pieces"} to explore</p></div><span aria-hidden="true">↗</span></div>
          </Link>;
        })}</div>
      </div>
    </section>}
    <section data-reveal className="content home-intro" id="our-approach"><p className="eyebrow">Our approach</p><div><h2>Good design.<br />Room for you.</h2><p>Explore materials and dimensions. Choose the shapes that work in your space. Furniture for the way you live.</p><Link href="/shop" className="text-link">Discover the collection <span aria-hidden="true">↗</span></Link></div></section>
    <details className="home-study"><summary><span className="study-summary-copy"><span className="eyebrow">An illustrative exploration</span><span className="study-summary-title">A study in form.</span></span><span className="study-summary-action">Explore a study in form <span aria-hidden="true">+</span></span></summary><InteractiveStudy /></details>
    <section data-reveal className="content home-support" id="after-study" tabIndex={-1}><div><p className="eyebrow">Here to help</p><h2>Choose with confidence.</h2></div><p>Explore materials, dimensions and availability. Get delivery, collection and returns information before you decide.</p><Link href="/contact" className="text-link">Get in touch <span aria-hidden="true">↗</span></Link></section>
  </StorefrontMotion>;
}
