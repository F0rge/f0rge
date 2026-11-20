import { lowestPricedVariant, priceLabel, productPath, type MedusaVariant, type StoreProduct } from "@/lib/medusa";
import { availabilityLabel, optionsLabel, pieceAvailability, pieceMaterial, sharedDimensions, sizeLabel } from "@/lib/piece-spec";
import { TrackedProductLink } from "@/components/analytics/tracked-product-link";

export function ProductCard({ product, hero = false, variants, priority = false }: { product: StoreProduct; hero?: boolean; variants?: MedusaVariant[]; priority?: boolean }) {
  const image = product.thumbnail || product.images?.[0]?.url;
  const shownVariants = variants ?? product.variants;
  const prices = shownVariants.map((variant) => variant.calculated_price?.calculated_amount).filter((value): value is number => value != null);
  const size = sizeLabel(sharedDimensions(product, shownVariants));
  const availability = pieceAvailability(shownVariants);
  const options = optionsLabel(product, shownVariants);
  const material = pieceMaterial(product, shownVariants);
  return <TrackedProductLink href={productPath(product)} productId={product.id} className={hero ? "product-card hero-card" : "product-card"}>
    <div className="product-image">{image ? <img src={image} alt="" width={800} height={600} loading={priority ? "eager" : "lazy"} fetchPriority={priority ? "high" : "auto"} /> : <span className="image-placeholder" aria-hidden="true">DasKasas</span>}</div>
    <div className="product-card-body">
      <div className="product-meta"><strong>{product.title}</strong><span className="product-card-price">{new Set(prices).size > 1 ? "From " : ""}{priceLabel(lowestPricedVariant(shownVariants))}</span></div>
      <dl className="spec-rows">
        {size && <><dt>Size</dt><dd>{size}</dd></>}
        <dt>Availability</dt><dd><span className={`availability-chip availability-${availability.kind.replaceAll("_", "-")}`}>{availabilityLabel(availability)}</span></dd>
        {options && <><dt>Options</dt><dd>{options}</dd></>}
        {material && <><dt>Material</dt><dd>{material}</dd></>}
      </dl>
    </div>
  </TrackedProductLink>;
}
