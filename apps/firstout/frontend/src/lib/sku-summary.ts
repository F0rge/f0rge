/** Plain-language lines the SKU panel, full view and search preview show. Pure, so they are tested. */

import type { components } from "./generated/api-schema";

type Schema = components["schemas"];
type Sku = Schema["SkuResponse"];
type Overview = Schema["SkuOverviewResponse"];

export const SKU_SECTION_IDS = ["overview", "stock", "pricing", "supply", "shop", "kit", "activity"] as const;
export type SkuSectionId = (typeof SKU_SECTION_IDS)[number];
export const SKU_SECTION_NAMES: Record<SkuSectionId, string> = {
  overview: "Overview",
  stock: "Stock",
  pricing: "Pricing",
  supply: "Supply",
  shop: "Shop",
  kit: "Kit",
  activity: "Activity",
};

export function formatRand(value: number): string {
  return `R ${value.toFixed(2)}`;
}

function amount(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(4)));
}

/** "sold in pairs" / "sold in sets of 6"; empty when sold singly. */
export function soldIn(multiple: number): string {
  if (multiple <= 1) return "";
  return multiple === 2 ? "sold in pairs" : `sold in sets of ${multiple}`;
}

/**
 * What a customer reads about price and batch, as in the shop:
 * "R 2450.00 each · sold in pairs · R 4900.00 per pair", "… · minimum 4 · from R 9800.00", "… · sold singly".
 */
export function customersSee(retailIncVat: string | null | undefined, multiple: number, minimum: number): string {
  const step = Math.max(1, Math.floor(multiple) || 1);
  const least = Math.max(step, Math.floor(minimum) || step);
  const price = amount(retailIncVat);
  const parts: string[] = [price === null ? "No retail price" : `${formatRand(price)} each`];
  if (step > 1) parts.push(soldIn(step));
  if (least > step) {
    parts.push(`minimum ${least}`);
    if (price !== null) parts.push(`from ${formatRand(price * least)}`);
  } else if (step > 1) {
    if (price !== null) parts.push(`${formatRand(price * step)} per ${step === 2 ? "pair" : "set"}`);
  } else parts.push("sold singly");
  return parts.join(" · ");
}

/** "W 52 × D 56 × H 80 cm", "Ø 90 cm", or "" when no dimension is stored. */
export function dimensionsText(sku: Pick<Sku, "width_cm" | "depth_cm" | "height_cm" | "diameter_cm">): string {
  const sides = (
    [
      ["W", sku.width_cm],
      ["D", sku.depth_cm],
      ["H", sku.height_cm],
    ] as const
  )
    .filter(([, value]) => value !== null && value !== undefined)
    .map(([key, value]) => `${key} ${formatCount(Number(value))}`);
  const parts = [
    ...(sku.diameter_cm !== null && sku.diameter_cm !== undefined ? [`Ø ${formatCount(Number(sku.diameter_cm))}`] : []),
    ...(sides.length ? [sides.join(" × ")] : []),
  ];
  return parts.length ? `${parts.join(" · ")} cm` : "";
}

export function categoryText(sku: Pick<Sku, "category" | "subcategory">): string {
  if (!sku.category) return "";
  return sku.subcategory ? `${sku.category} › ${sku.subcategory}` : sku.category;
}

/** Number of photos the API serves for this SKU (slots 1..n of `/skus/{id}/photo`). */
export function photoCount(sku: Pick<Sku, "gallery_photo_count" | "photo_storage_key">): number {
  return sku.gallery_photo_count > 0 ? sku.gallery_photo_count : sku.photo_storage_key ? 1 : 0;
}

export interface ReadinessCheck {
  key: "photo" | "shop_section" | "retail" | "dimensions";
  label: string;
  /** null while the category list is still loading. */
  ok: boolean | null;
}

/** The four checks a SKU needs before the shop can show it. */
export function shopReadiness(sku: Sku, shopSection: string | null | undefined): ReadinessCheck[] {
  const retail = amount(sku.retail_inc_vat);
  return [
    { key: "photo", label: "Photo", ok: photoCount(sku) > 0 },
    { key: "shop_section", label: "Category has a shop section", ok: shopSection === undefined ? null : Boolean(shopSection) },
    { key: "retail", label: "Retail price", ok: retail !== null && retail > 0 },
    { key: "dimensions", label: "Dimensions", ok: dimensionsText(sku) !== "" },
  ];
}

export function nextArrivalText(arrival: Overview["stock"]["next_arrival"]): string {
  if (!arrival) return "Nothing on order";
  const status = { open: "open", on_water: "on the water", landed: "landed" }[arrival.status];
  const when = arrival.expected_on ? `, expected ${formatDay(arrival.expected_on)}` : "";
  return `${arrival.po_number} (${status}), ${formatCount(arrival.qty)}${when}`;
}

export function formatDay(iso: string): string {
  const date = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleDateString("en-ZA", { day: "numeric", month: "short", year: "numeric" });
}

/** The one-line summary a collapsed panel group shows. */
export function sectionSummary(id: SkuSectionId, overview: Overview, extra: { shopSection?: string | null } = {}): string {
  const { sku, stock } = overview;
  switch (id) {
    case "overview":
      return [categoryText(sku) || "No category", sku.colour_name, dimensionsText(sku)].filter(Boolean).join(" · ");
    case "stock":
      return overview.is_kit
        ? `Kit · ${formatCount(stock.available)} available`
        : `${formatCount(stock.on_hand)} on hand · ${formatCount(stock.available)} available · ${formatCount(stock.on_order)} on order`;
    case "pricing": {
      const retail = amount(sku.retail_inc_vat);
      return [
        retail === null ? "No retail price" : `Retail ${formatRand(retail)}`,
        soldIn(sku.sell_multiple),
        sku.min_sell_qty > sku.sell_multiple ? `minimum ${sku.min_sell_qty}` : "",
      ].filter(Boolean).join(" · ");
    }
    case "supply": {
      if (overview.is_kit) return "Built from its parts, never bought in";
      const rule = sku.do_not_reorder
        ? "do not reorder"
        : sku.reorder_min === null
          ? "no reorder minimum"
          : `reorder at ${sku.reorder_min}, up to ${sku.order_up_to ?? sku.reorder_min}`;
      return `${sku.preferred_supplier_name ?? "No preferred supplier"} · ${rule}`;
    }
    case "shop": {
      const checks = shopReadiness(sku, extra.shopSection);
      const ready = checks.filter((check) => check.ok).length;
      return `${sku.storefront_hidden ? "Hidden from the shop" : "Shown in the shop"} · ${ready} of ${checks.length} ready`;
    }
    case "kit":
      if (overview.is_kit) return "Kit built from other SKUs";
      return overview.used_in_kits.length
        ? `Not a kit · used in ${overview.used_in_kits.map((use) => `${use.our_ref} × ${formatCount(use.qty)}`).join(", ")}`
        : "Not a kit";
    case "activity": {
      const last = overview.activity[0];
      return last ? `Last: ${formatDay(last.created_at)}, ${last.source_label.toLowerCase()}` : "No activity recorded";
    }
  }
}

export interface SkuStatusTag {
  label: string;
  type: "green" | "blue" | "gray" | "teal" | "red";
}

export function skuStatusTags(sku: Pick<Sku, "is_archived" | "is_sellable" | "is_kit" | "do_not_reorder">): SkuStatusTag[] {
  if (sku.is_archived) return [{ label: "Archived", type: "gray" }];
  return [
    { label: "Active", type: "green" },
    sku.is_sellable ? { label: "Sellable", type: "blue" } : { label: "Not for sale", type: "gray" },
    ...(sku.is_kit ? [{ label: "Kit", type: "gray" } as const] : []),
    ...(sku.do_not_reorder ? [{ label: "Do not reorder", type: "teal" } as const] : []),
  ];
}
