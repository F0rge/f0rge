import { describe, expect, it } from "vitest";
import { catalogueCsv } from "./catalogue-export";
import type { Sku } from "./api";

const row = {
  id: "s1", our_ref: "DC-1", name: "Chair", is_archived: false, category: "Dining", subcategory: "Chairs", colour_name: "Oat",
  main_material: { id: "m", name: "Bouclé", family: "fabric", is_archived: false },
  other_materials: [{ id: "a", name: "Ash", family: "wood", is_archived: false }, { id: "b", name: "Brass", family: "metal", is_archived: false }],
  carton_count: 2, preferred_supplier_name: "Nordhaus", lead_time_days: 84, reorder_min: 8, order_up_to: 24, do_not_reorder: true,
  sell_multiple: 2, min_sell_qty: 4, stockist_inc_vat: "1", wholesale_inc_vat: "2", decorator_inc_vat: "3", retail_inc_vat: "4", our_barcode: "600",
} as unknown as Sku;

describe("catalogue CSV", () => {
  it("exports the new catalogue columns", () => {
    const csv = catalogueCsv([row]);
    const value = (name: string) => csv.rows[0][csv.header.indexOf(name)];
    expect(csv.header).not.toContain("Cost (ZAR)");
    expect(value("Sub-category")).toBe("Chairs");
    expect(value("Colour")).toBe("Oat");
    expect(value("Main material")).toBe("Bouclé");
    expect(value("Other materials")).toBe("Ash; Brass");
    expect(value("Order up to")).toBe("24");
    expect(value("Do not reorder")).toBe("Yes");
    expect(value("Sold in multiples of")).toBe("2");
    expect(value("Minimum quantity")).toBe("4");
    expect(value("Cartons")).toBe("2");
    expect(csv.rows[0]).toHaveLength(csv.header.length);
  });
  it("adds cost only for users who may see it, and says when it failed", () => {
    expect(catalogueCsv([row], new Map([["s1", "99.00"]])).rows[0]).toContain("99.00");
    const failed = catalogueCsv([row], null);
    expect(failed.rows[0][failed.header.indexOf("Cost (ZAR)")]).toBe("Unavailable");
  });
});
