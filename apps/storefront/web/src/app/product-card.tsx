import Link from "next/link";
import { lowestPricedVariant, priceLabel, productPath, type MedusaVariant, type StoreProduct } from "@/lib/medusa";

export function ProductCard({ product, hero = false, variants }: { product: StoreProduct; hero?: boolean; variants?: MedusaVariant[] }) {
  const image = product.thumbnail || product.images?.[0]?.url;
  const shownVariants = variants ?? product.variants;
  const prices = shownVariants.map((variant) => variant.calculated_price?.calculated_amount).filter((value): value is number => value != null);
  return <Link href={productPath(product)} className={hero ? "product-card hero-card" : "product-card"}>
    <div className="product-image">{image ? <img src={image} alt="" /> : <span className="image-placeholder" aria-hidden="true">The Collector</span>}</div>
    <div className="product-meta"><strong>{product.title}</strong><span>{new Set(prices).size > 1 ? "From " : ""}{priceLabel(lowestPricedVariant(shownVariants))}</span></div>
  </Link>;
}
