import { notFound } from "next/navigation";
import Link from "next/link";
import { getStoreProduct, priceLabel } from "@/lib/medusa";

export const dynamic = "force-dynamic";

export default async function ProductPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;
  const product = await getStoreProduct(sku);
  if (!product) notFound();
  const quantity = product.variants[0]?.inventory_quantity ?? 0;

  return (
    <article className="content product-page">
      <div className="product-image hero-study" aria-hidden="true">Object study</div>
      <div>
        <Link href="/" className="back-link">← All pieces</Link>
        <p className="eyebrow">The Collector / furniture</p>
        <h1>{product.title}</h1>
        <p className="price">{priceLabel(product)}</p>
        <p>{product.description || "A considered addition to your living space."}</p>
        <p className="availability" role="status">
          {quantity > 0 ? `${quantity} available` : "Currently unavailable"}
        </p>
        <p className="preview-note">Checkout is being prepared. This is a private catalogue preview.</p>
      </div>
    </article>
  );
}
