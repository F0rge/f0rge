import { describe, expect, it, vi } from "vitest";
import { normalizePick } from "./picks";
import type { Sku } from "./api";
import { canResumeArchivedTillPick, isPendingTillPick, restoreTillCartSkus } from "./till-archive";

const sku: Sku = {
  id: "kit", our_ref: "KIT", our_barcode: "KIT", name: "Kit", design: "Kit", fabric: "None", category: null,
  category_id: null, subcategory_id: null, subcategory: null, colour_name: null, main_material_id: null, main_material: null, other_material_ids: [], other_materials: [], sell_multiple: 1, min_sell_qty: 1, order_up_to: null, do_not_reorder: false,
  width_cm: null, depth_cm: null, height_cm: null, diameter_cm: null, notes: null, piece_count: null, swatch_hex: null, gallery_photo_count: 0,
  supplier_ref: null, preferred_supplier_id: null, preferred_supplier_name: null, lead_time_days: null,
  made_to_order_capacity: null, made_to_order_lead_time_min_days: null, made_to_order_lead_time_max_days: null,
  made_to_order_expires_at: null, made_to_order_offer_id: null, reorder_min: null, last_landed_cost_zar: null,
  photo_storage_key: null, stockist_ex_vat: null, stockist_inc_vat: null, wholesale_ex_vat: null, wholesale_inc_vat: null,
  decorator_ex_vat: null, decorator_inc_vat: null, retail_ex_vat: "100.00", retail_inc_vat: "115.00", carton_count: 1,
  is_kit: true, is_sellable: true, is_archived: true, archived_at: "2026-11-15T10:00:00Z", archived_by_id: null,
  till_no_stock_required: false, exclude_from_commission: false, storefront_hidden: false, average_unit_cost_zar: null,
  stockist_below_cost: false, wholesale_below_cost: false, decorator_below_cost: false, retail_below_cost: false, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-11-15T10:00:00Z",
};
const pick = normalizePick({ id: "pick", source_type: "till", kit_sku_id: "kit", kit_qty: 2, status: "staged", invoice_id: null, customer_id: "buyer", created_at: "2026-11-15T09:00:00Z" });
const snapshot = { locationId: "showroom", customerId: "buyer", pickId: "pick", linkedPickIds: { kit: "pick" }, lines: [{ skuId: "kit", qty: 2, discountPercent: 0 }] };

describe("archived kit checkout through an existing till pick", () => {
  it("preserves the exact source fields instead of accepting display SKU fallbacks", () => {
    expect(pick).toMatchObject({ source_type: "till", kit_sku_id: "kit", kit_qty: 2 });
    const legacy = normalizePick({ id: "legacy", sku_id: "kit", qty: 2, status: "confirmed" });
    expect(legacy.sku_id).toBe("kit");
    expect(isPendingTillPick(legacy)).toBe(false);
  });
  it.each(["confirmed", "picking", "staged"])("permits an unconsumed prearchive %s pick at the exact quantity and customer", (status) => {
    expect(canResumeArchivedTillPick(sku, normalizePick({ ...pick, status }), 2, "buyer")).toBe(true);
  });
  it("rejects new quantities, wrong customer, consumed picks, wrong source, postarchive picks and not-for-sale SKUs", () => {
    expect(canResumeArchivedTillPick(sku, pick, 3, "buyer")).toBe(false);
    expect(canResumeArchivedTillPick(sku, pick, 1, "buyer")).toBe(false);
    expect(canResumeArchivedTillPick(sku, pick, 2, "other")).toBe(false);
    expect(canResumeArchivedTillPick(sku, { ...pick, invoice_id: "invoice" }, 2, "buyer")).toBe(false);
    expect(canResumeArchivedTillPick(sku, { ...pick, source_type: "sales_order" }, 2, "buyer")).toBe(false);
    expect(canResumeArchivedTillPick(sku, { ...pick, status: "draft" }, 2, "buyer")).toBe(false);
    expect(canResumeArchivedTillPick(sku, { ...pick, created_at: "2026-11-15T11:00:00Z" }, 2, "buyer")).toBe(false);
    expect(canResumeArchivedTillPick({ ...sku, is_sellable: false }, pick, 2, "buyer")).toBe(false);
    expect(canResumeArchivedTillPick({ ...sku, archived_at: null }, pick, 2, "buyer")).toBe(false);
  });
  it("treats timezone-free server times as UTC across the Luxembourg spring DST gap", () => {
    const archived = { ...sku, archived_at: "2026-03-29T03:00:00" };
    expect(canResumeArchivedTillPick(archived, { ...pick, created_at: "2026-03-29T02:30:00" }, 2, "buyer")).toBe(true);
    expect(canResumeArchivedTillPick(archived, { ...pick, created_at: "2026-03-29T03:30:00" }, 2, "buyer")).toBe(false);
  });
  it("preserves explicit Z and numeric offsets when comparing instants", () => {
    const archived = { ...sku, archived_at: "2026-03-29T03:00:00Z" };
    expect(canResumeArchivedTillPick(archived, { ...pick, created_at: "2026-03-29T04:30:00+02:00" }, 2, "buyer")).toBe(true);
    expect(canResumeArchivedTillPick(archived, { ...pick, created_at: "2026-03-29T05:30:00+0200" }, 2, "buyer")).toBe(false);
    expect(canResumeArchivedTillPick({ ...sku, archived_at: "2026-03-29T03:00:00+02:00" }, { ...pick, created_at: "2026-03-29T01:30:00Z" }, 2, "buyer")).toBe(false);
  });
  it("fails closed for absent or invalid server timestamps", () => {
    expect(canResumeArchivedTillPick({ ...sku, archived_at: "not a timestamp" }, pick, 2, "buyer")).toBe(false);
    expect(canResumeArchivedTillPick(sku, { ...pick, created_at: "not a timestamp" }, 2, "buyer")).toBe(false);
    expect(canResumeArchivedTillPick(sku, { ...pick, created_at: "" }, 2, "buyer")).toBe(false);
  });
  it("hydrates a valid saved archived line by its specific pick without adding it to the active catalogue", async () => {
    const lookup = vi.fn(async () => sku);
    const active: Sku[] = [];
    const restored = await restoreTillCartSkus(snapshot, active, [pick], lookup);
    expect(lookup).toHaveBeenCalledExactlyOnceWith("kit");
    expect(restored.get("kit")).toBe(sku);
    expect(active).toEqual([]);
  });
  it("does not fetch an arbitrary archived SKU through an absent pick or a changed saved quantity", async () => {
    const lookup = vi.fn(async () => sku);
    expect((await restoreTillCartSkus(snapshot, [], [], lookup)).has("kit")).toBe(false);
    expect((await restoreTillCartSkus({ ...snapshot, lines: [{ ...snapshot.lines[0], qty: 3 }] }, [], [pick], lookup)).has("kit")).toBe(false);
    expect(lookup).not.toHaveBeenCalled();
  });
  it("keeps a lookup failure visible to the caller instead of silently dropping a committed cart line", async () => {
    await expect(restoreTillCartSkus(snapshot, [], [pick], async () => { throw new Error("Offline"); })).rejects.toThrow("Offline");
  });
});
