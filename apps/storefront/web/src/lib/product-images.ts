import type { MedusaVariant, StoreProduct } from "./medusa";

/** Gallery for a variant: the merchant-approved `suitable_image_urls` when set, otherwise every variant and product image. */
export function selectedImages(product: StoreProduct, variant?: MedusaVariant): string[] {
  const all = [...(variant?.images?.map((image) => image.url) || []), ...(product.images?.map((image) => image.url) || [])];
  const suitableValue = variant?.metadata?.suitable_image_urls;
  let suitable: string[] = [];
  if (Array.isArray(suitableValue)) suitable = suitableValue;
  else if (typeof suitableValue === "string") {
    try {
      const parsed: unknown = JSON.parse(suitableValue);
      if (Array.isArray(parsed)) suitable = parsed.filter((url): url is string => typeof url === "string");
    } catch { /* Invalid merchant metadata falls back to the product gallery. */ }
  }
  if (suitable?.length) return Array.from(new Set(all.filter((url) => suitable.includes(url))));
  return Array.from(new Set(all.length ? all : variant?.thumbnail ? [variant.thumbnail] : product.thumbnail ? [product.thumbnail] : []));
}
