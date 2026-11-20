// Pure availability and dimension facts shared by the product page and the spec tiles.
// Type-only imports keep this module free of the server-only Medusa client.
import type { MadeToOrderOffer, MedusaVariant, StoreProduct } from "./medusa";

const OFFER_MAX_AGE_MS = 5 * 60_000;
const OFFER_CLOCK_SKEW_MS = 60_000;

export type OfferState = "none" | "available" | "stale" | "exhausted";

/** A made-to-order offer is usable only while freshly observed, with capacity left and before it expires. */
export function offerState(offer: MadeToOrderOffer | null | undefined, now = Date.now()): OfferState {
  if (!offer) return "none";
  const observedAt = offer.observed_at ? Date.parse(offer.observed_at) : NaN;
  const fresh = Number.isFinite(observedAt) && now - observedAt <= OFFER_MAX_AGE_MS && observedAt <= now + OFFER_CLOCK_SKEW_MS;
  if (!fresh) return "stale";
  return offer.remaining_capacity > 0 && Date.parse(offer.expires_at) > now ? "available" : "exhausted";
}

export type PieceAvailability =
  | { kind: "in_stock" }
  | { kind: "made_to_order"; minDays: number; maxDays: number }
  | { kind: "unconfirmed" }
  | { kind: "unavailable" };

/** Availability across the variants a tile shows: stock wins, then live offers (widest window), then honest unknown/unavailable. */
export function pieceAvailability(variants: MedusaVariant[], now = Date.now()): PieceAvailability {
  if (variants.some((variant) => (variant.inventory_quantity ?? 0) > 0)) return { kind: "in_stock" };
  const offers = variants.map((variant) => variant.metadata?.made_to_order_offer);
  const live = offers.filter((offer): offer is MadeToOrderOffer => offerState(offer, now) === "available");
  if (live.length) return {
    kind: "made_to_order",
    minDays: Math.min(...live.map((offer) => offer.min_lead_time_days)),
    maxDays: Math.max(...live.map((offer) => offer.max_lead_time_days)),
  };
  if (offers.some((offer) => offerState(offer, now) === "stale")) return { kind: "unconfirmed" };
  return { kind: "unavailable" };
}

export function availabilityLabel(availability: PieceAvailability): string {
  switch (availability.kind) {
    case "in_stock": return "In stock";
    case "made_to_order": return `Made to order · ${availability.minDays === availability.maxDays ? availability.minDays : `${availability.minDays}–${availability.maxDays}`} days`;
    case "unconfirmed": return "Availability being confirmed";
    case "unavailable": return "Currently unavailable";
  }
}

export type PieceDimensions = { length: number | null; width: number | null; height: number | null; unit: string };

const measured = (value: number | null | undefined) => value != null && Number.isFinite(value) && value > 0 ? value : null;

/** One variant's dimensions, falling back to the product's. Missing or non-positive values are null. */
export function pieceDimensions(product: StoreProduct, variant?: MedusaVariant): PieceDimensions {
  return {
    length: measured(variant?.length ?? product.length),
    width: measured(variant?.width ?? product.width),
    height: measured(variant?.height ?? product.height),
    unit: product.metadata?.dimension_unit ?? "",
  };
}

/** Dimensions every listed variant agrees on; a value that differs between variants is null rather than guessed. */
export function sharedDimensions(product: StoreProduct, variants: MedusaVariant[]): PieceDimensions {
  const all = variants.length ? variants.map((variant) => pieceDimensions(product, variant)) : [pieceDimensions(product)];
  const agreed = (key: "length" | "width" | "height") => all.every((dims) => dims[key] === all[0][key]) ? all[0][key] : null;
  return { length: agreed("length"), width: agreed("width"), height: agreed("height"), unit: all[0].unit };
}

/** "L 200 × W 90 × H 80 cm" when all three are known; otherwise null so the row is omitted. */
export function sizeLabel(dims: PieceDimensions): string | null {
  if (dims.length == null || dims.width == null || dims.height == null) return null;
  return `L ${dims.length} × W ${dims.width} × H ${dims.height}${dims.unit ? ` ${dims.unit}` : ""}`;
}

/** "Fill: Soft / Firm" from the option values present in the listed variants; null for a single-variant product. */
export function optionsLabel(product: StoreProduct, variants: MedusaVariant[]): string | null {
  if (product.variants.length < 2) return null;
  const choices = (product.options || []).filter((option) => (option.values?.length || 0) > 1).flatMap((option) => {
    const present = new Set(variants.flatMap((variant) => variant.options?.filter((value) => (value.option_id || value.option?.id) === option.id).map((value) => value.value) || []));
    const values = option.values!.map(({ value }) => value).filter((value) => present.has(value));
    return values.length ? [`${option.title}: ${values.join(" / ")}`] : [];
  });
  return choices.length ? choices.join("; ") : null;
}

/** Variant material over product material, as on the product page; when listed variants disagree, nothing is shown. */
export function pieceMaterial(product: StoreProduct, variants: MedusaVariant[]): string | null {
  const materials = new Set((variants.length ? variants : [undefined]).map((variant) => variant?.material || product.material || null));
  return materials.size === 1 ? [...materials][0] : null;
}
