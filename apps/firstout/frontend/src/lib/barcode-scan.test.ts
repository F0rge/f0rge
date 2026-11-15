import { describe, expect, it } from "vitest";

import type { Sku } from "@/lib/api";

import { resolveTillScan, tillScanErrorMessage } from "./barcode-scan";

const sku: Sku = {
  id: "sku-fixture",
  our_ref: "EXAMPLE-CHAIR",
  our_barcode: "EXAMPLE-CHAIR-BARCODE",
  name: "Example chair",
  design: "Example",
  fabric: "Example",
  category: null,
  supplier_ref: null,
  preferred_supplier_id: null,
  preferred_supplier_name: null,
  lead_time_days: null,
  made_to_order_capacity: null,
  made_to_order_lead_time_min_days: null,
  made_to_order_lead_time_max_days: null,
  made_to_order_expires_at: null,
  made_to_order_offer_id: null,
  reorder_min: null,
  last_landed_cost_zar: null,
  photo_storage_key: null,
  stockist_ex_vat: null,
  stockist_inc_vat: null,
  wholesale_ex_vat: null,
  wholesale_inc_vat: null,
  decorator_ex_vat: null,
  decorator_inc_vat: null,
  retail_ex_vat: "100.00",
  retail_inc_vat: "115.00",
  carton_count: 1,
  is_kit: false,
  is_archived: false,
  is_sellable: true,
  created_at: "2026-11-14T00:00:00Z",
  updated_at: "2026-11-14T00:00:00Z",
};

function scan(item: Sku, code = item.our_barcode) {
  return resolveTillScan({
    code,
    skus: [item],
    allowOurRef: true,
    addQty: 1,
    floorOnHand: () => 3,
    cartQty: () => 0,
  });
}

describe("till sellable stock", () => {
  it("allows a sellable SKU with stock and a valid price", () => {
    expect(scan(sku)).toEqual({ ok: true, sku, qty: 1 });
  });

  it("rejects not-for-sale stock even when it has stock and a valid price", () => {
    const notForSale = { ...sku, is_sellable: false };
    expect(scan(notForSale)).toEqual({ ok: false, error: "not_sellable" });
    expect(scan(notForSale, notForSale.our_ref)).toEqual({ ok: false, error: "not_sellable" });
    expect(tillScanErrorMessage("not_sellable")).toBe("This SKU is not for sale.");
  });
});

it("does not add an archived SKU through the normal scanner even if passed in a lookup list", () => {
  const result = resolveTillScan({ code: sku.our_barcode, skus: [{ ...sku, is_archived: true, is_sellable: true }], allowOurRef: false, addQty: 1, floorOnHand: () => 10, cartQty: () => 0 });
  expect(result).toEqual({ ok: false, error: "not_sellable" });
});
