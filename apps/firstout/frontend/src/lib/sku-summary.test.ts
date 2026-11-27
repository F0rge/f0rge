import { describe, expect, it } from "vitest";
import type { components } from "./generated/api-schema";
import {
  customersSee,
  dimensionsText,
  nextArrivalText,
  photoCount,
  sectionSummary,
  shopReadiness,
  skuStatusTags,
  soldIn,
} from "./sku-summary";

type Overview = components["schemas"]["SkuOverviewResponse"];
type Sku = Overview["sku"];

function sku(patch: Partial<Sku> = {}): Sku {
  return {
    id: "11111111-1111-4111-8111-111111111111", our_ref: "DC-OSLO-OAT", our_barcode: "600", name: "Oslo dining chair",
    design: "Oslo", fabric: "Oat Bouclé", width_cm: 52, depth_cm: 56, height_cm: 80, diameter_cm: null, notes: null,
    piece_count: null, is_archived: false, archived_at: null, archived_by_id: null, is_sellable: true, till_no_stock_required: false,
    exclude_from_commission: false, storefront_hidden: false, supplier_ref: null, preferred_supplier_id: null,
    preferred_supplier_name: "Nordhaus", lead_time_days: 84, made_to_order_capacity: null, made_to_order_lead_time_min_days: null,
    made_to_order_lead_time_max_days: null, made_to_order_expires_at: null, made_to_order_offer_id: null, reorder_min: 8,
    last_landed_cost_zar: null, category: "Dining", category_id: "c", subcategory_id: null, subcategory: null, colour_name: "Oat",
    main_material_id: null, main_material: null, other_material_ids: [], other_materials: [], sell_multiple: 2, min_sell_qty: 2,
    order_up_to: 24, do_not_reorder: false, swatch_hex: "#e6dccb", photo_storage_key: null, gallery_photo_count: 0,
    stockist_ex_vat: null, stockist_inc_vat: null, wholesale_ex_vat: null, wholesale_inc_vat: null, decorator_ex_vat: null,
    decorator_inc_vat: null, retail_ex_vat: "2130.43", retail_inc_vat: "2450.00", average_unit_cost_zar: null,
    stockist_below_cost: false, wholesale_below_cost: false, decorator_below_cost: false, retail_below_cost: false,
    carton_count: 1, is_kit: false, created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z",
    ...patch,
  };
}

function overview(patch: Partial<Sku> = {}, rest: Partial<Overview> = {}): Overview {
  return {
    sku: sku(patch),
    stock: { on_hand: 14, held: 2, held_documents: [], available: 12, on_order: 24, next_arrival: null, unit_cost_zar: null, locations: [] },
    supplier_prices: [], is_kit: false, used_in_kits: [], activity: [],
    ...rest,
  };
}

describe("Customers see", () => {
  it("names pairs and sets with their batch price", () => {
    expect(soldIn(1)).toBe("");
    expect(soldIn(2)).toBe("sold in pairs");
    expect(soldIn(6)).toBe("sold in sets of 6");
    expect(customersSee("2450.00", 2, 2)).toBe("R 2450.00 each · sold in pairs · R 4900.00 per pair");
    expect(customersSee("100", 6, 6)).toBe("R 100.00 each · sold in sets of 6 · R 600.00 per set");
  });
  it("leads with the minimum when it is above the multiple", () => {
    expect(customersSee("2450.00", 2, 4)).toBe("R 2450.00 each · sold in pairs · minimum 4 · from R 9800.00");
    expect(customersSee("10", 1, 3)).toBe("R 10.00 each · minimum 3 · from R 30.00");
  });
  it("says sold singly, and copes without a retail price", () => {
    expect(customersSee("10", 1, 1)).toBe("R 10.00 each · sold singly");
    expect(customersSee(null, 2, 4)).toBe("No retail price · sold in pairs · minimum 4");
  });
});

describe("shop readiness", () => {
  it("checks photo, shop section, retail price and dimensions", () => {
    const checks = shopReadiness(sku({ photo_storage_key: "k" }), "dining");
    expect(checks.map((check) => check.ok)).toEqual([true, true, true, true]);
  });
  it("flags what is missing and leaves the section unknown while categories load", () => {
    const bare = sku({ retail_inc_vat: null, width_cm: null, depth_cm: null, height_cm: null });
    expect(shopReadiness(bare, null).map((check) => check.ok)).toEqual([false, false, false, false]);
    expect(shopReadiness(bare, undefined)[1].ok).toBeNull();
    expect(shopReadiness(sku({ retail_inc_vat: "0.00" }), "x")[2].ok).toBe(false);
  });
  it("counts every served photo slot", () => {
    expect(photoCount(sku())).toBe(0);
    expect(photoCount(sku({ photo_storage_key: "k" }))).toBe(1);
    expect(photoCount(sku({ photo_storage_key: "k", gallery_photo_count: 5 }))).toBe(5);
  });
});

describe("summary lines", () => {
  it("summarises each section in one line", () => {
    const data = overview();
    expect(sectionSummary("overview", data)).toBe("Dining · Oat · W 52 × D 56 × H 80 cm");
    expect(sectionSummary("stock", data)).toBe("14 on hand · 12 available · 24 on order");
    expect(sectionSummary("pricing", data)).toBe("Retail R 2450.00 · sold in pairs");
    expect(sectionSummary("supply", data)).toBe("Nordhaus · reorder at 8, up to 24");
    expect(sectionSummary("shop", data, { shopSection: "dining" })).toBe("Shown in the shop · 3 of 4 ready");
    expect(sectionSummary("kit", data)).toBe("Not a kit");
    expect(sectionSummary("activity", data)).toBe("No activity recorded");
  });
  it("covers kits, do-not-reorder, sub-categories and kit membership", () => {
    expect(sectionSummary("overview", overview({ subcategory: "Chairs", colour_name: null }))).toBe("Dining › Chairs · W 52 × D 56 × H 80 cm");
    expect(sectionSummary("supply", overview({ do_not_reorder: true, preferred_supplier_name: null }))).toBe("No preferred supplier · do not reorder");
    expect(sectionSummary("pricing", overview({ min_sell_qty: 4 }))).toBe("Retail R 2450.00 · sold in pairs · minimum 4");
    const kit = overview({ is_kit: true }, { is_kit: true });
    expect(sectionSummary("stock", kit)).toBe("Kit · 12 available");
    expect(sectionSummary("supply", kit)).toBe("Built from its parts, never bought in");
    const used = overview({}, { used_in_kits: [{ parent_sku_id: "p", our_ref: "KIT-OSLO-6", name: "Set", qty: 6, parent_is_archived: false }] });
    expect(sectionSummary("kit", used)).toBe("Not a kit · used in KIT-OSLO-6 × 6");
  });
  it("formats dimensions, arrivals and status tags", () => {
    expect(dimensionsText({ width_cm: null, depth_cm: null, height_cm: null, diameter_cm: 90 })).toBe("Ø 90 cm");
    expect(dimensionsText({ width_cm: null, depth_cm: null, height_cm: null, diameter_cm: null })).toBe("");
    expect(nextArrivalText(null)).toBe("Nothing on order");
    expect(nextArrivalText({ purchase_order_id: "p", po_number: "PO-0142", status: "on_water", qty: 24, expected_on: null, expected_on_basis: null }))
      .toBe("PO-0142 (on the water), 24");
    expect(skuStatusTags(sku({ do_not_reorder: true })).map((tag) => tag.label)).toEqual(["Active", "Sellable", "Do not reorder"]);
    expect(skuStatusTags(sku({ is_archived: true })).map((tag) => tag.label)).toEqual(["Archived"]);
  });
});
