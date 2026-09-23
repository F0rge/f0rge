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
          const sourceSkuId = product.handle.replace(/^firstout-/, "");
          return (
            <Link href={`/product/${sourceSkuId}`} key={product.id} className="product-card">
              <div className="product-image" aria-hidden="true">Object study</div>
              <div className="product-meta">
                <strong>{product.title}</strong>
                <span>{priceLabel(product)}</span>
              </div>
            </Link>
          );
        })}
      </div>
      {products.length === 0 && <p>No pieces are published yet.</p>}
    </section>
  );
}
