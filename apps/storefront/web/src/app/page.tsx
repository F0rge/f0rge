import Link from "next/link";
import { listStoreProducts, priceLabel } from "@/lib/medusa";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const products = await listStoreProducts();
  return (
    <section className="content">
      <p className="eyebrow">A study in living well</p>
      <h1>Furniture with a point of view.</h1>
      <p className="intro">A first glimpse of the pieces coming to our new store.</p>
      <div className="product-grid">
        {products.map((product) => {
          const slug = product.handle.replace(/^firstout-(?!group-)/, "");
          const image = product.thumbnail || product.images?.[0]?.url;
          const prices = product.variants.map((variant) => variant.calculated_price?.calculated_amount).filter((price): price is number => price != null);
          const lowest = product.variants.find((variant) => variant.calculated_price?.calculated_amount === Math.min(...prices));
          return <Link href={`/product/${slug}`} key={product.id} className="product-card">
            <div className="product-image">{image ? <img src={image} alt={product.title} /> : <span aria-hidden="true">Object study</span>}</div>
            <div className="product-meta"><strong>{product.title}</strong><span>{prices.length > 1 && new Set(prices).size > 1 ? "From " : ""}{priceLabel(lowest)}</span></div>
          </Link>;
        })}
      </div>
      {products.length === 0 && <p>No pieces are published yet.</p>}
    </section>
  );
}
