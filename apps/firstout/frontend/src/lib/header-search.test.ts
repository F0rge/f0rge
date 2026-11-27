import { describe, expect, it } from "vitest";
import { moveHighlight, searchGroups, skuIds } from "./header-search";

const hit = (id: string) => ({
  id, our_ref: "R-" + id, our_barcode: "6", name: "Chair " + id, category: "Dining", has_photo: false,
  retail_inc_vat: "10.00", available: 1, is_kit: false, sell_multiple: 1, min_sell_qty: 1,
});

describe("header search shaping", () => {
  const results = {
    q: "o",
    skus: [hit("a"), hit("b")],
    purchase_orders: [{ id: "p", po_number: "PO-1", status: "on_water", supplier_name: "Nordhaus" }],
    invoices: [{ id: "i", invoice_number: "INV-1", customer_name: "Ann" }],
  };
  it("flattens groups in order with stable indexes", () => {
    const { groups, options } = searchGroups(results, [{ href: "/users", label: "Team members", description: "Staff" }]);
    expect(groups.map((group) => group.label)).toEqual(["Administration", "SKUs", "Purchase orders", "Invoices"]);
    expect(options.map((option) => option.href)).toEqual(["/users", "/catalogue/a", "/catalogue/b", "/purchase-orders/p", "/invoices/i"]);
    expect(groups[2].options[0]).toMatchObject({ index: 3, option: { label: "PO-1 · Nordhaus", meta: "on water" } });
  });
  it("drops empty groups and gives SKU ids as the stepping context", () => {
    const { groups, options } = searchGroups({ ...results, purchase_orders: [], invoices: [] }, []);
    expect(groups.map((group) => group.label)).toEqual(["SKUs"]);
    expect(skuIds(options)).toEqual(["a", "b"]);
    expect(searchGroups(undefined, []).options).toEqual([]);
  });
  it("moves the highlight with wrapping", () => {
    expect(moveHighlight(-1, 1, 3)).toBe(0);
    expect(moveHighlight(-1, -1, 3)).toBe(2);
    expect(moveHighlight(2, 1, 3)).toBe(0);
    expect(moveHighlight(0, -1, 3)).toBe(2);
    expect(moveHighlight(0, 1, 0)).toBe(-1);
  });
});
