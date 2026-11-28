import type { MedusaVariant, StoreProduct } from "./medusa";

type Axis = "width" | "depth" | "height" | "diameter" | "length";
export type Measurement = { axis: Axis; value: number; unit: "cm" | "mm" };

function positive(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

/** Older records publish a full L × W × H tuple. Keep its axes and units as supplied. */
function legacyValues(product: StoreProduct, variant?: MedusaVariant) {
  const length = variant?.length ?? product.length;
  const width = variant?.width ?? product.width;
  const height = variant?.height ?? product.height;
  if (!positive(length) || !positive(width) || !positive(height)) return null;
  return { length, width, height };
}

export function publishedDimensions(product: StoreProduct, variant?: MedusaVariant): Measurement[] {
  const measured = variant?.metadata?.dimensions_cm;
  if (measured) {
    const axes = ["diameter", "width", "depth", "height"] as const;
    return axes.flatMap((axis) => {
      const value = measured[axis];
      return positive(value) ? [{ axis, value, unit: "cm" as const }] : [];
    });
  }
  const unit = product.metadata?.dimension_unit;
  if (unit !== "cm" && unit !== "mm") return [];
  const legacy = legacyValues(product, variant);
  return legacy ? [
    { axis: "length", value: legacy.length, unit },
    { axis: "width", value: legacy.width, unit },
    { axis: "height", value: legacy.height, unit },
  ] : [];
}

/** Preserve the old visible size text when its unit cannot support a measurement guide. */
export function unqualifiedLegacySize(product: StoreProduct, variant?: MedusaVariant): string | null {
  const unit = product.metadata?.dimension_unit;
  if (variant?.metadata?.dimensions_cm || unit === "cm" || unit === "mm") return null;
  const legacy = legacyValues(product, variant);
  return legacy ? [Object.values(legacy).join(" × "), unit].filter(Boolean).join(" ") : null;
}
