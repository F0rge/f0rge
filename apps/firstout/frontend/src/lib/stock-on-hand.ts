import type { WorkspaceField } from "@/components/record-workspace/types";
import type { WorkspaceSkuRow } from "./api";

/** Columns, in order. All sortable but By location (a list, not one number). Costs never appear here. */
export const STOCK_ON_HAND_COLUMNS = [
  { key: "name", label: "Product / SKU", sortable: true },
  { key: "category", label: "Category", sortable: true },
  { key: "on_hand", label: "On hand", numeric: true, sortable: true },
  { key: "held", label: "Held", numeric: true, sortable: true },
  { key: "available", label: "Available", numeric: true, sortable: true },
  { key: "on_order", label: "On order", numeric: true, sortable: true },
  { key: "stock_locations", label: "By location", sortable: false },
] as const;

type Option = { value: string; label: string };

/** Quick filters Category and Location ("has stock at this location"), then the Advanced filters. */
export function stockOnHandFilters(lists: {
  categories: readonly string[];
  subcategories: readonly string[];
  suppliers: readonly Option[];
  locations: readonly string[];
}): WorkspaceField[] {
  const option = (value: string) => ({ value, label: value });
  return [
    { key: "category", label: "Category", type: "enum", quick: true, allLabel: "All categories", options: lists.categories.map(option) },
    { key: "stocked_at", label: "Location", type: "enum", quick: true, allLabel: "All locations", options: lists.locations.map(option) },
    { key: "subcategory", label: "Sub-category", type: "enum", options: lists.subcategories.map(option) },
    { key: "preferred_supplier_id", label: "Supplier", type: "enum", options: lists.suppliers },
    { key: "on_hand", label: "On hand", type: "number" },
    { key: "held", label: "Held", type: "number" },
    { key: "available", label: "Available", type: "number" },
    { key: "on_order", label: "On order", type: "number" },
    { key: "below_reorder_min", label: "Below reorder minimum", type: "boolean" },
    { key: "do_not_reorder", label: "Do not reorder", type: "boolean" },
    { key: "is_kit", label: "Kit", type: "boolean" },
    { key: "name", label: "Product name", type: "text" },
    { key: "our_ref", label: "SKU", type: "text" },
    { key: "our_barcode", label: "Barcode", type: "text" },
  ];
}

/** "Kramerville 10 · Bedfordview 4"; only locations with stock above zero are listed. */
export function byLocation(row: Pick<WorkspaceSkuRow, "stock_locations">, format: (value: string) => string = String): string {
  return row.stock_locations.map((item) => `${item.location_name} ${format(item.on_hand)}`).join(" · ");
}

export function stockOnHandCsv(rows: readonly WorkspaceSkuRow[]): { header: string[]; rows: string[][] } {
  return {
    header: [
      "Our ref", "Name", "Archived", "Category", "Sub-category", "Preferred supplier",
      "On hand", "Held", "Available", "On order", "Reorder min", "Below reorder minimum", "By location",
    ],
    rows: rows.map((row) => [
      row.our_ref, row.name, row.is_archived ? "Yes" : "No", row.category ?? "", row.subcategory ?? "", row.preferred_supplier_name ?? "",
      row.on_hand, row.held, row.available, row.on_order,
      row.reorder_min === null ? "" : String(row.reorder_min), row.below_reorder_min ? "Yes" : "No", byLocation(row),
    ]),
  };
}
