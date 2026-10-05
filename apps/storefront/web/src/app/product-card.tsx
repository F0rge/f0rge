import { lowestPricedVariant, priceLabel, productPath, type MedusaVariant, type StoreProduct } from "@/lib/medusa";
import { TrackedProductLink } from "@/components/analytics/tracked-product-link";

export function ProductCard({ product, hero = false, variants, priority = false }: { product: StoreProduct; hero?: boolean; variants?: MedusaVariant[]; priority?: boolean }) {
  const image = product.thumbnail || product.images?.[0]?.url;
  const shownVariants = variants ?? product.variants;
  const prices = shownVariants.map((variant) => variant.calculated_price?.calculated_amount).filter((value): value is number => value != null);
  return <TrackedProductLink href={productPath(product)} productId={product.id} className={hero ? "product-card hero-card" : "product-card"}>
    <div className="product-image">{image ? <img src={image} alt="" width={800} height={1000} loading={priority ? "eager" : "lazy"} fetchPriority={priority ? "high" : "auto"} /> : <span className="image-placeholder" aria-hidden="true">The Collector</span>}</div>
    <div className="product-meta"><strong>{product.title}</strong><span>{new Set(prices).size > 1 ? "From " : ""}{priceLabel(lowestPricedVariant(shownVariants))}</span></div>
  </TrackedProductLink>;
}
