import type { MedusaVariant, StoreProduct } from "./medusa";

export function variantChoices(variant: MedusaVariant | undefined): Record<string, string> {
  return Object.fromEntries((variant?.options ?? []).flatMap((option) => {
    const id = option.option_id || option.option?.id;
    return id ? [[id, option.value]] : [];
  }));
}

export function productVariantOptions(product: StoreProduct) {
  const choices = product.variants.map(variantChoices);
  return (product.options ?? []).flatMap((option) => {
    const present = Array.from(new Set(choices.flatMap((row) => row[option.id] ? [row[option.id]] : [])));
    if (present.length < 2) return [];
    const ordered = (option.values ?? []).map(({ value }) => value).filter((value) => present.includes(value));
    return [{ ...option, availableValues: Array.from(new Set([...ordered, ...present])) }];
  });
}

/** Keep the other selections when possible, then pick the closest existing SKU. */
export function pickVariant(
  variants: MedusaVariant[],
  active: MedusaVariant | undefined,
  optionId: string,
  value: string,
): MedusaVariant | undefined {
  const selected = variantChoices(active);
  const otherOptions = Object.entries(selected).filter(([id]) => id !== optionId);
  let bestScore = -1;
  let bestMatch: MedusaVariant | undefined;
  for (const variant of variants) {
    const choices = variantChoices(variant);
    if (choices[optionId] !== value) continue;
    const score = otherOptions.filter(([id, current]) => choices[id] === current).length;
    if (score > bestScore) {
      bestScore = score;
      bestMatch = variant;
    }
  }
  return bestMatch;
}

function imageUrls(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((url): url is string => typeof url === "string");
  if (typeof value !== "string") return [];
  try { return imageUrls(JSON.parse(value)); } catch { return []; }
}

export function selectedImages(product: StoreProduct, variant?: MedusaVariant): string[] {
  const variantImages = variant?.images?.map((image) => image.url) ?? [];
  const all = [...variantImages, ...(product.images?.map((image) => image.url) ?? [])];
  const preferred = imageUrls(variant?.metadata?.suitable_image_urls);
  if (preferred.length) {
    const attached = new Set(all);
    return [...new Set(preferred.filter((url) => attached.has(url)))];
  }
  if (variantImages.length) return [...new Set(variantImages)];
  if (variant?.thumbnail) return [variant.thumbnail];
  if (product.variants.length > 1) return [];
  if (all.length) return [...new Set(all)];
  return product.thumbnail ? [product.thumbnail] : [];
}
