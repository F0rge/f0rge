import type { SkuProductDetails } from "./api";

export const SKU_DIMENSION_FIELDS = {
  width_cm: "Width (cm)",
  depth_cm: "Depth (cm)",
  height_cm: "Height (cm)",
  diameter_cm: "Diameter (cm)",
} as const;
type DimensionField = keyof typeof SKU_DIMENSION_FIELDS;
export const SKU_DIMENSIONS = Object.keys(SKU_DIMENSION_FIELDS) as DimensionField[];
export type SkuDetailsForm = Record<keyof SkuProductDetails, string>;
export type SkuDetailsErrors = Partial<Record<keyof SkuDetailsForm, string>>;
export const SKU_NOTES_LIMIT = 4000;
/** The DasKasas finish dot: lowercase #rrggbb, or blank for none. */
export const SKU_SWATCH_PATTERN = /^#[0-9a-f]{6}$/;

export function skuDetailsFormFromSku(sku: SkuProductDetails): SkuDetailsForm {
  return {
    width_cm: sku.width_cm == null ? "" : String(sku.width_cm),
    depth_cm: sku.depth_cm == null ? "" : String(sku.depth_cm),
    height_cm: sku.height_cm == null ? "" : String(sku.height_cm),
    diameter_cm: sku.diameter_cm == null ? "" : String(sku.diameter_cm),
    piece_count: sku.piece_count == null ? "" : String(sku.piece_count),
    notes: sku.notes ?? "",
    swatch_hex: sku.swatch_hex ?? "",
  };
}

export function validateSkuDetails(form: SkuDetailsForm): SkuDetailsErrors {
  const errors: SkuDetailsErrors = {};
  for (const field of SKU_DIMENSIONS) {
    const value = form[field].trim();
    if (value && (!/^\d+(?:\.\d{1,2})?$/.test(value) || Number(value) <= 0 || Number(value) >= 1000000)) {
      errors[field] = "Enter a positive measurement in centimetres with up to 2 decimals.";
    }
  }
  const pieces = form.piece_count.trim();
  if (pieces && (!/^\d+$/.test(pieces) || Number(pieces) < 1 || Number(pieces) > 2_147_483_647)) {
    errors.piece_count = "Enter the number of pieces as a positive whole number.";
  }
  if (form.notes.trim().length > SKU_NOTES_LIMIT) errors.notes = "Use no more than 4000 characters.";
  const swatch = form.swatch_hex.trim().toLowerCase();
  if (swatch && !SKU_SWATCH_PATTERN.test(swatch)) errors.swatch_hex = "Enter a colour as # and six hex digits, such as #9b9592, or leave it blank.";
  return errors;
}

export function skuDetailsPayload(form: SkuDetailsForm, original: SkuProductDetails = {}): SkuProductDetails {
  const payload: SkuProductDetails = {};
  for (const field of [...SKU_DIMENSIONS, "piece_count"] as const) {
    const value = form[field].trim() ? Number(form[field]) : null;
    if (value !== (original[field] ?? null)) payload[field] = value;
  }
  const notes = form.notes.trim() || null;
  if (notes !== (original.notes ?? null)) payload.notes = notes;
  const swatch = form.swatch_hex.trim().toLowerCase() || null;
  if (swatch !== (original.swatch_hex ?? null)) payload.swatch_hex = swatch;
  return payload;
}
