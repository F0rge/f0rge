import type { components } from "./generated/api-schema";
import { skuCartonCount } from "./carton-helpers";

type Sku = components["schemas"]["SkuResponse"];

const leadDays = (days: number | null) => (days === null ? "—" : `${days} days`);
const count = (value: number | null) => (value === null ? "" : String(value));

/**
 * Header and rows for the catalogue CSV. `costs` is null when the cost report failed
 * ("Unavailable"), undefined when the user may not see costs (no column).
 */
export function catalogueCsv(rows: readonly Sku[], costs?: ReadonlyMap<string, string | null> | null): { header: string[]; rows: string[][] } {
  const withCost = costs !== undefined;
  return {
    header: [
      "Our ref", "Name", "Archived", "Category", "Sub-category", "Colour", "Main material", "Other materials",
      "Cartons", "Preferred supplier", "Lead time", "Reorder min", "Order up to", "Do not reorder",
      "Sold in multiples of", "Minimum quantity",
      ...(withCost ? ["Cost (ZAR)"] : []),
      "Stockist inc VAT", "Wholesale inc VAT", "Decorator inc VAT", "Retail inc VAT", "Our barcode",
    ],
    rows: rows.map((sku) => [
      sku.our_ref, sku.name, sku.is_archived ? "Yes" : "No", sku.category ?? "", sku.subcategory ?? "",
      sku.colour_name ?? "", sku.main_material?.name ?? "", sku.other_materials.map((item) => item.name).join("; "),
      String(skuCartonCount(sku)), sku.preferred_supplier_name ?? "", leadDays(sku.lead_time_days),
      count(sku.reorder_min), count(sku.order_up_to), sku.do_not_reorder ? "Yes" : "No",
      String(sku.sell_multiple), String(sku.min_sell_qty),
      ...(withCost ? [costs === null ? "Unavailable" : (costs.get(sku.id) ?? "")] : []),
      sku.stockist_inc_vat ?? "", sku.wholesale_inc_vat ?? "", sku.decorator_inc_vat ?? "", sku.retail_inc_vat ?? "", sku.our_barcode,
    ]),
  };
}
