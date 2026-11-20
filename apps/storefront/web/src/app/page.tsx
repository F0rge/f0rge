import Link from "next/link";
import { StorefrontMotion } from "@/components/storefront-motion";
import { TrackedProductLink } from "@/components/analytics/tracked-product-link";
import { merchandisingCollections, productInCollection } from "@/lib/catalogue-collections";
import { listStoreProducts, lowestPricedVariant, priceLabel, productPath } from "@/lib/medusa";
import { sharedDimensions } from "@/lib/piece-spec";
import { selectedImages } from "@/lib/product-images";
import { Wordmark } from "@/components/wordmark";
import { ProductCard } from "./product-card";
import { InteractiveStudy } from "./study/interactive-study";

export const dynamic = "force-dynamic";

const arrow = <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M4 12h16M14 6l6 6-6 6" /></svg>;

const steps = [
  { title: "Choose a piece", body: <>Each listing states the price, the available options and whether the piece is in stock or made to order, with its dimensions where they are recorded.</> },
  { title: "Check out as a guest", body: <>An account is not required. All prices are in rand and include VAT.</> },
  { title: "Delivery or collection", body: <>Orders are delivered in selected Gauteng areas or collected. Made-to-order pieces show their lead time on each listing and before checkout.</> },
  { title: "Returns", body: <>If a piece is not suitable, <Link href="/policies/returns">the returns policy</Link> sets out the procedure.</> },
];

const terms = [
  ["Delivery", "Selected Gauteng areas"],
  ["Collection", "Available"],
  ["Made to order", "Lead time shown on each piece"],
  ["Checkout", "As a guest; no account required"],
  ["Prices", "Rand, VAT included"],
];

export default async function HomePage() {
  const products = await listStoreProducts();
  const heroProduct = products.find((product) => product.thumbnail || product.images?.[0]?.url);
  const heroImage = heroProduct?.thumbnail || heroProduct?.images?.[0]?.url;
  const heroPrices = heroProduct?.variants.map((variant) => variant.calculated_price?.calculated_amount).filter((price): price is number => price != null) || [];
  const heroDims = heroProduct ? sharedDimensions(heroProduct, heroProduct.variants) : null;
  const unit = heroDims?.unit ? ` ${heroDims.unit}` : "";
  // "Our approach" figures are further merchant-approved gallery images of the hero piece; fewer than two means text only.
  const gallery = heroProduct ? selectedImages(heroProduct, heroProduct.variants[0]) : [];
  const figures = gallery.filter((url) => url !== heroImage).slice(0, 2);
  const collections = merchandisingCollections(products)
    .map((collection) => ({ ...collection, count: products.filter((product) => productInCollection(product, collection.handle)).length }))
    .sort((a, b) => a.title.localeCompare(b.title));

  return <StorefrontMotion>
    <section data-reveal className="home-hero" aria-labelledby="hero-title">
      <div className="hero-copy">
        <div className="hero-heading">
          <p className="section-number">00 — DasKasas</p>
          <h1 id="hero-title">Furniture for living and dining rooms.</h1>
          <p className="hero-description">Each piece is listed with its price, its options and its availability, and with its dimensions where they are recorded, so that you can check the fit and the lead time before you order.</p>
        </div>
        <table className="terms-table">
          <caption>Terms of purchase</caption>
          <tbody>{terms.map(([term, value]) => <tr key={term}><th scope="row">{term}</th><td>{value}</td></tr>)}</tbody>
        </table>
        <div className="hero-actions">
          <Link className="button-solid" href="/shop">Shop all furniture {arrow}</Link>
          {heroProduct && heroImage ? <TrackedProductLink href={productPath(heroProduct)} productId={heroProduct.id} className="button-outline" trackImpression={false}>View the {heroProduct.title}</TrackedProductLink> : <Link className="button-outline" href="/collections">Browse collections</Link>}
        </div>
      </div>
      {heroProduct && heroImage ? <figure className="hero-figure">
        <div className={`hero-drawing${heroDims?.length ? " has-horizontal" : ""}${heroDims?.height ? " has-vertical" : ""}`}>
          {heroDims?.length && <div className="dimension dimension-horizontal" aria-hidden="true"><span>L {heroDims.length}{unit}</span></div>}
          {heroDims?.height && <div className="dimension dimension-vertical" aria-hidden="true"><span>H {heroDims.height}{unit}</span></div>}
          <TrackedProductLink href={productPath(heroProduct)} productId={heroProduct.id} className="hero-image-link">
            <img className="hero-photograph" src={heroImage} alt={heroProduct.title} width={1200} height={900} fetchPriority="high" loading="eager" />
          </TrackedProductLink>
        </div>
        <figcaption>
          <span>{heroProduct.title}</span>
          <span>
            {heroDims?.length && <span className="sr-only">Length {heroDims.length}{unit}. </span>}
            {heroDims?.height && <span className="sr-only">Height {heroDims.height}{unit}. </span>}
            {heroDims?.width && <>W {heroDims.width}{unit} · </>}{new Set(heroPrices).size > 1 ? "From " : ""}{priceLabel(lowestPricedVariant(heroProduct.variants))}
          </span>
        </figcaption>
      </figure> : <div className="hero-no-image"><span className="wordmark"><Wordmark /></span><p>{products.length === 0 ? "Pieces will appear here as they become available." : "Your next piece starts here."}</p></div>}
    </section>

    <section data-reveal className="ledger-section" aria-labelledby="buy-title">
      <div className="ledger-heading"><p className="section-number">01 — Purchasing</p><h2 id="buy-title">How to buy</h2></div>
      <ol className="lattice steps">{steps.map((step, index) => <li key={step.title}><span className="section-number">Step {index + 1}</span><h3>{step.title}</h3><p>{step.body}</p></li>)}</ol>
    </section>

    <section data-reveal className="ledger-section featured-section" id={collections.length === 0 ? "collection" : undefined} aria-labelledby="feat-title">
      <div className="ledger-heading"><p className="section-number">02 — Featured</p><div className="ledger-heading-end"><h2 id="feat-title">Selected pieces</h2><Link href="/shop" className="text-link">View all furniture</Link></div></div>
      {products.length > 0 ? <div className="product-grid lattice">{products.slice(0, 6).map((product) => <ProductCard key={product.id} product={product} />)}</div>
        : <div className="empty-state"><h3>No pieces are listed yet.</h3><p>Furniture will appear here as pieces become available.</p></div>}
    </section>

    {collections.length > 0 && <section data-reveal className="ledger-section" id="collection" aria-labelledby="collections-title">
      <div className="ledger-heading"><p className="section-number">03 — Collections</p><h2 id="collections-title">Shop by collection</h2></div>
      <nav aria-label="Shop by collection" className="index-rows">{collections.map((collection, index) => <Link key={collection.handle} className="index-row" href={`/shop?collection=${encodeURIComponent(collection.handle)}`}>
        <span className="section-number">{String(index + 1).padStart(2, "0")}</span>
        <span className="index-row-title"><span>{collection.title}</span><span className="index-count">{collection.count} {collection.count === 1 ? "piece" : "pieces"}</span></span>
        <svg className="index-arrow" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25" aria-hidden="true"><path d="M3 12h18M15 6l6 6-6 6" /></svg>
      </Link>)}</nav>
    </section>}

    <section data-reveal className="ledger-section home-intro" id="our-approach" aria-labelledby="approach-title">
      <p className="section-number">{collections.length > 0 ? "04" : "03"} — Our approach</p>
      <div className="approach-copy">
        <h2 id="approach-title">Clear terms before you order.</h2>
        <div>
          <p>Every piece states its price and its availability: in stock, or made to order within a stated lead time. Options, dimensions and materials are listed wherever they are recorded.</p>
          <p>Where a piece is made to order, the lead time is shown before checkout.</p>
        </div>
      </div>
      {heroProduct && figures.length === 2 && <div className="approach-figures">{figures.map((url, index) => <figure key={url}>
        <img src={url} alt={`Photograph of the ${heroProduct.title}, view ${gallery.indexOf(url) + 1} of ${gallery.length}`} width={1200} height={800} loading="lazy" />
        <figcaption>Fig. {index + 1}</figcaption>
      </figure>)}</div>}
    </section>

    <details className="home-study"><summary><span className="study-summary-copy"><span className="eyebrow">An illustrative exploration</span><span className="study-summary-title">A study in form.</span></span><span className="study-summary-action">Explore a study in form <span aria-hidden="true">+</span></span></summary><InteractiveStudy /></details>
    <section data-reveal className="ledger-section home-support" id="after-study" tabIndex={-1} aria-labelledby="support-title"><div><p className="section-number">Help</p><h2 id="support-title">Choose with confidence.</h2></div><p>Availability is listed with each piece, with materials and dimensions where they are recorded. Delivery, collection and returns information is available before you decide.</p><Link href="/contact" className="text-link">Get in touch</Link></section>
  </StorefrontMotion>;
}
