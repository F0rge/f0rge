import { describe, expect, it } from "vitest";

import { ApiError, type Sku } from "./api";
import type { SkuSupplierPrice } from "./catalogue-lists";
import {
  cardSaveFailure,
  formChanged,
  newSupplierRow,
  overviewFormFromSku,
  overviewPayload,
  pricingFormFromSku,
  pricingPayload,
  supplierRowsPayload,
  supplyFormFromSku,
  supplyPayload,
  validateOverview,
  validatePricing,
  validateSupply,
  withSellMultiple,
} from "./catalogue-editor";

function sku(patch: Partial<Sku> = {}): Sku {
  return {
    id: "11111111-1111-4111-8111-111111111111", our_ref: "DC-OSLO-OAT", our_barcode: "600", name: "Oslo dining chair",
    design: "Oslo", fabric: "Oat Bouclé", width_cm: 52, depth_cm: 56, height_cm: 80, diameter_cm: null, notes: null,
    piece_count: null, is_archived: false, archived_at: null, archived_by_id: null, is_sellable: true, till_no_stock_required: false,
    exclude_from_commission: false, storefront_hidden: false, supplier_ref: "NH-1", preferred_supplier_id: "s1",
    preferred_supplier_name: "Nordhaus", lead_time_days: 84, made_to_order_capacity: null, made_to_order_lead_time_min_days: null,
    made_to_order_lead_time_max_days: null, made_to_order_expires_at: null, made_to_order_offer_id: null, reorder_min: 8,
    last_landed_cost_zar: null, category: "Dining", category_id: "c1", subcategory_id: "sub1", subcategory: "Chairs", colour_name: "Oat",
    main_material_id: "m1", main_material: null, other_material_ids: ["m2"], other_materials: [], sell_multiple: 2, min_sell_qty: 2,
    order_up_to: 24, do_not_reorder: false, swatch_hex: "#e6dccb", photo_storage_key: null, gallery_photo_count: 0,
    stockist_ex_vat: "1000.00", stockist_inc_vat: "1150.00", wholesale_ex_vat: null, wholesale_inc_vat: null, decorator_ex_vat: null,
    decorator_inc_vat: null, retail_ex_vat: "2130.43", retail_inc_vat: "2450.00", average_unit_cost_zar: null,
    stockist_below_cost: false, wholesale_below_cost: false, decorator_below_cost: false, retail_below_cost: false,
    carton_count: 1, is_kit: false, created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z",
    ...patch,
  };
}

const row = (patch: Partial<SkuSupplierPrice> = {}): SkuSupplierPrice => ({
  id: "r1", supplier_id: "s1", supplier_name: "Nordhaus", supplier_is_archived: false, is_preferred: true,
  supplier_sku: "NH-OSLO", latest_price: "380.00", fixed_price: null, min_order_qty: 4, pack_multiple: 2,
  updated_at: "2026-11-01T00:00:00Z", ...patch,
});

describe("overview card", () => {
  it("sends nothing for an untouched form and only the changed fields otherwise", () => {
    const base = sku();
    expect(overviewPayload(base, overviewFormFromSku(base))).toEqual({});
    expect(overviewPayload(base, { ...overviewFormFromSku(base), name: "  Oslo chair ", do_not_reorder: true }))
      .toEqual({ name: "Oslo chair", do_not_reorder: true });
  });

  it("clears nullable fields with null and sends the sub-category with a new category", () => {
    const base = sku();
    const form = { ...overviewFormFromSku(base), colour_name: " ", main_material_id: "", category_id: "c2", subcategory_id: "" };
    expect(overviewPayload(base, form)).toEqual({ colour_name: null, main_material_id: null, category_id: "c2", subcategory_id: null });
  });

  it("sends the whole ordered list when other materials change", () => {
    const base = sku();
    expect(overviewPayload(base, { ...overviewFormFromSku(base), other_material_ids: ["m3", "m2"] }))
      .toEqual({ other_material_ids: ["m3", "m2"] });
  });

  it("requires identity fields and whole cartons", () => {
    const errors = validateOverview({ ...overviewFormFromSku(sku()), our_ref: " ", carton_count: "0", swatch_hex: "red" });
    expect(Object.keys(errors).sort()).toEqual(["carton_count", "our_ref", "swatch_hex"]);
  });
});

describe("pricing card", () => {
  it("lets the minimum follow the multiple until the minimum is edited", () => {
    const form = pricingFormFromSku(sku());
    expect(withSellMultiple(form, "3", false)).toMatchObject({ sell_multiple: "3", min_sell_qty: "3" });
    expect(withSellMultiple({ ...form, min_sell_qty: "6" }, "3", true)).toMatchObject({ sell_multiple: "3", min_sell_qty: "6" });
  });

  it("refuses a minimum that is not a multiple", () => {
    expect(validatePricing({ ...pricingFormFromSku(sku()), sell_multiple: "2", min_sell_qty: "3" }, "0.15"))
      .toEqual({ min_sell_qty: "Must be a multiple of 2." });
    expect(validatePricing({ ...pricingFormFromSku(sku()), sell_multiple: "0" }, "0.15").sell_multiple).toBeTruthy();
  });

  it("sends the minimum with a new multiple, the changed price and the commission flag", () => {
    const base = sku();
    const form = { ...withSellMultiple(pricingFormFromSku(base), "4", false), retail_inc_vat: "2500", earns_commission: false };
    expect(pricingPayload(base, form)).toEqual({ retail_inc_vat: "2500", sell_multiple: 4, min_sell_qty: 4, exclude_from_commission: true });
    expect(pricingPayload(base, pricingFormFromSku(base))).toEqual({});
  });
});

describe("supply card", () => {
  it("clears values with null and leaves untouched ones out", () => {
    const base = sku();
    const form = { ...supplyFormFromSku(base, []), reorder_min: "", supplier_ref: "NH-1", order_up_to: "30" };
    expect(supplyPayload(base, form)).toEqual({ reorder_min: null, order_up_to: 30 });
  });

  it("checks order up to against the reorder minimum and made to order as a set", () => {
    const errors = validateSupply({ ...supplyFormFromSku(sku(), []), reorder_min: "10", order_up_to: "5", mto_capacity: "3" });
    expect(errors.order_up_to).toBe("Must be at least the reorder minimum (10).");
    expect(errors.mto_min_days).toBeTruthy();
    expect(errors.mto_capacity).toBeUndefined();
  });

  it("flags a repeated supplier and a bad quantity on its row", () => {
    const form = supplyFormFromSku(sku(), [row()]);
    form.rows.push({ ...newSupplierRow("new-1", "s1"), pack_multiple: "0" });
    expect(validateSupply(form)).toMatchObject({ "rows.1.supplier_id": "This supplier already has a row.", "rows.1.pack_multiple": expect.any(String) });
  });

  it("builds the replace-all rows only when they changed", () => {
    const saved = [row()];
    const form = supplyFormFromSku(sku(), saved);
    expect(supplierRowsPayload(saved, form.rows, true)).toBeNull();
    const edited = [{ ...form.rows[0], latest_price: "400.00", min_order_qty: "" }, { ...newSupplierRow("new-1", "s2"), pack_multiple: "6" }];
    expect(supplierRowsPayload(saved, edited, true)).toEqual({ rows: [
      { supplier_id: "s1", supplier_sku: "NH-OSLO", latest_price: "400.00", fixed_price: null, min_order_qty: null, pack_multiple: 2 },
      { supplier_id: "s2", supplier_sku: null, latest_price: null, fixed_price: null, min_order_qty: null, pack_multiple: 6 },
    ] });
  });

  it("never sends prices without cost access, so the stored ones are kept", () => {
    const saved = [row({ latest_price: null })];
    const rows = [{ ...supplyFormFromSku(sku(), saved).rows[0], supplier_sku: "NH-2", latest_price: "99" }];
    expect(supplierRowsPayload(saved, rows, false)?.rows[0]).toMatchObject({ supplier_sku: "NH-2", latest_price: null, fixed_price: null });
  });
});

describe("dirty detection", () => {
  it("compares the draft with the form the edit started from", () => {
    const start = overviewFormFromSku(sku());
    expect(formChanged(start, { ...start })).toBe(false);
    expect(formChanged(start, { ...start, notes: "x" })).toBe(true);
  });
});

describe("save failures", () => {
  it("maps 422 locations, including legacy names and supplier rows", () => {
    const error = new ApiError(422, "Unprocessable", [
      { loc: ["body", "min_sell_qty"], msg: "Minimum quantity must be a multiple of 2" },
      { loc: ["body", "category"], msg: "Unknown category 'X'. Add it in Settings first." },
      { loc: ["body", "rows", 1, "supplier_id"], msg: "Value error, Supplier not found" },
    ]);
    expect(cardSaveFailure(error).fields).toEqual({
      min_sell_qty: "Minimum quantity must be a multiple of 2",
      category_id: "Unknown category 'X'. Add it in Settings first.",
      "rows.1.supplier_id": "Supplier not found",
    });
  });

  it("puts the duplicate finish 409 on design and colour, and reference clashes on their field", () => {
    const finish = cardSaveFailure(new ApiError(409, "Another SKU already has this design, colour and material."));
    expect(finish.fields.design).toBe("Another SKU already has this design, colour and material.");
    expect(finish.fields.colour_name).toBeTruthy();
    expect(cardSaveFailure(new ApiError(409, "A SKU with this our_barcode already exists")).fields)
      .toEqual({ our_barcode: "Another SKU already uses this barcode." });
  });

  it("explains a refused price change and keeps unknown failures readable", () => {
    expect(cardSaveFailure(new ApiError(403, "Changing supplier prices needs stock.cost.view")).message).toMatch(/cost access/);
    expect(cardSaveFailure(new ApiError(409, "Restore the SKU before editing it")).message).toBe("Restore the SKU before editing it");
    expect(cardSaveFailure(new TypeError("fetch")).message).toMatch(/connection/);
  });
});
