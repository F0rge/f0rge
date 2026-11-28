import { describe, expect, it } from "vitest";
import type { WorkspaceSkuRow } from "./api";
import { STOCK_ON_HAND_COLUMNS, byLocation, stockOnHandCsv, stockOnHandFilters } from "./stock-on-hand";

const row = {
  id: "s1", our_ref: "DC-OSLO-OAT", name: "Oslo dining chair", is_archived: false, category: "Dining", subcategory: "Chairs",
  preferred_supplier_name: "Oslo Works", on_hand: "14", held: "2", available: "12", on_order: "24", reorder_min: 10,
  below_reorder_min: false, average_unit_cost_zar: "999.00", last_landed_cost_zar: "999.00",
  stock_locations: [
    { location_id: "k", location_name: "Kramerville", on_hand: "10" },
    { location_id: "b", location_name: "Bedfordview", on_hand: "4" },
  ],
} as unknown as WorkspaceSkuRow;

describe("Stock on hand", () => {
  it("has the standard columns, all sortable but By location", () => {
    expect(STOCK_ON_HAND_COLUMNS.map((column) => [column.label, column.sortable])).toEqual([
      ["Product / SKU", true], ["Category", true], ["On hand", true], ["Held", true],
      ["Available", true], ["On order", true], ["By location", false],
    ]);
  });

  it("offers Category and Location as quick filters and the rest as advanced filters, against the workspace keys", () => {
    const filters = stockOnHandFilters({ categories: ["Dining"], subcategories: ["Chairs"], suppliers: [{ value: "id", label: "Oslo Works" }], locations: ["Kramerville"] });
    expect(filters.filter((field) => field.quick).map((field) => field.key)).toEqual(["category", "stocked_at"]);
    expect(filters.map((field) => [field.key, field.type])).toEqual([
      ["category", "enum"], ["stocked_at", "enum"], ["subcategory", "enum"], ["preferred_supplier_id", "enum"],
      ["on_hand", "number"], ["held", "number"], ["available", "number"], ["on_order", "number"],
      ["below_reorder_min", "boolean"], ["do_not_reorder", "boolean"], ["is_kit", "boolean"],
      ["name", "text"], ["our_ref", "text"], ["our_barcode", "text"],
    ]);
    expect(filters.find((field) => field.key === "stocked_at")?.options).toEqual([{ value: "Kramerville", label: "Kramerville" }]);
  });

  it("lists stock by location", () => {
    expect(byLocation(row)).toBe("Kramerville 10 · Bedfordview 4");
    expect(byLocation({ stock_locations: [] })).toBe("");
  });

  it("exports quantities without costs", () => {
    const csv = stockOnHandCsv([row]);
    expect(csv.header).toEqual([
      "Our ref", "Name", "Archived", "Category", "Sub-category", "Preferred supplier",
      "On hand", "Held", "Available", "On order", "Reorder min", "Below reorder minimum", "By location",
    ]);
    expect(csv.rows).toEqual([[
      "DC-OSLO-OAT", "Oslo dining chair", "No", "Dining", "Chairs", "Oslo Works",
      "14", "2", "12", "24", "10", "No", "Kramerville 10 · Bedfordview 4",
    ]]);
    expect(csv.rows.flat()).not.toContain("999.00");
  });
});
