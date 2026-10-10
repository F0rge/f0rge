import { allowsFiniteBackorder, catalogueExternalIds, groupOpsProducts, isCatalogueRow, missingTaxInclusiveZarPrice } from "./sync-firstout";
import type { OpsProduct } from "./ops-contract";

const base: OpsProduct = {
  source_sku_id: "e4653558-60c7-4be7-a416-76fc2c055b8f",
  product_group_id: "f6c64903-48ad-4202-a918-7903a40020ce",
  product_title: "Arc sofa", options: { Colour: "Sand" },
  sku: "ARC-SAND", name: "Arc sofa Sand", price_minor_zar: 1150000,
  available_quantity: 2, revision: "2026-09-22T09:14:32.000001Z", observed_at: "2026-09-22T09:14:32.000001Z", acknowledged_commitment_ids: [], made_to_order_offer: null,
};

test("projects two SKUs into one stable group identity, retaining standalone identities", () => {
  const groups = groupOpsProducts([
    base,
    { ...base, source_sku_id: "da9cdb14-9126-408d-a3bd-ab8352d2d810", sku: "ARC-CHAR", options: { Colour: "Charcoal" } },
    { ...base, source_sku_id: "627a41f1-9892-4bbc-bcfb-b4149474235d", product_group_id: null, product_title: null, options: {}, sku: "SIDE-1" },
  ]);
  expect(groups).toHaveLength(2);
  expect(groups[0].externalId).toBe("firstout-group-f6c64903-48ad-4202-a918-7903a40020ce");
  expect(groups[0].rows.map((row) => row.sku)).toEqual(["ARC-SAND", "ARC-CHAR"]);
  expect(groups[1].externalId).toBe("firstout-627a41f1-9892-4bbc-bcfb-b4149474235d");
});

test("the shop collection keeps in-stock rows and a live made-to-order offer, and drops an empty group", () => {
  const offer = {
    id: "46ce043c-b680-4b87-8833-4d169ddad492",
    capacity: 2,
    min_lead_time_days: 21,
    max_lead_time_days: 28,
    expires_at: new Date(Date.now() + 86_400_000).toISOString(),
  };
  const expired = { ...offer, expires_at: new Date(Date.now() - 1_000).toISOString() };
  const stocked = { ...base, product_group_id: null, product_title: null, options: {}, sku: "SIDE-1", source_sku_id: "627a41f1-9892-4bbc-bcfb-b4149474235d" };
  const madeToOrder = { ...stocked, source_sku_id: "da9cdb14-9126-408d-a3bd-ab8352d2d810", sku: "SIDE-2", available_quantity: 0, made_to_order_offer: offer };
  const empty = { ...stocked, source_sku_id: "11111111-1111-4111-8111-111111111111", sku: "SIDE-0", available_quantity: 0, made_to_order_offer: expired };
  const mixedOut = { ...base, source_sku_id: "22222222-2222-4222-8222-222222222222", sku: "ARC-OUT", available_quantity: 0, made_to_order_offer: null };
  expect(isCatalogueRow(stocked)).toBe(true);
  expect(isCatalogueRow(madeToOrder)).toBe(true);
  expect(isCatalogueRow(empty)).toBe(false);
  expect(catalogueExternalIds([stocked, madeToOrder, empty, base, mixedOut])).toEqual([
    `firstout-${stocked.source_sku_id}`,
    `firstout-${madeToOrder.source_sku_id}`,
  ]);
});

test("a missing tax-inclusive ZAR price is the only publication rejection the sync continues past", () => {
  const price = new Error("Variant variant_01M48YWEX49XJCTR3EWVMNVM88 cannot be published: tax-inclusive ZAR price is missing");
  const wrapped = new Error("wrapped");
  Reflect.set(wrapped, "cause", price);
  expect(missingTaxInclusiveZarPrice(price)).toBe(true);
  expect(missingTaxInclusiveZarPrice(wrapped)).toBe(true);
  expect(missingTaxInclusiveZarPrice(new Error("Variant variant_x cannot be published: stock or a positive lead time is required"))).toBe(false);
  expect(missingTaxInclusiveZarPrice(new Error("connection reset"))).toBe(false);
});

test("Medusa backorder is available only while a finite source offer is live", () => {
  expect(allowsFiniteBackorder(base)).toBe(false);
  const offer = {
    id: "46ce043c-b680-4b87-8833-4d169ddad492",
    capacity: 2,
    min_lead_time_days: 21,
    max_lead_time_days: 28,
    expires_at: new Date(Date.now() + 86_400_000).toISOString(),
  };
  expect(allowsFiniteBackorder({ ...base, available_quantity: 0, made_to_order_offer: offer })).toBe(true);
  expect(allowsFiniteBackorder({ ...base, available_quantity: 0, made_to_order_offer: {
    ...offer, expires_at: new Date(Date.now() - 1_000).toISOString(),
  } })).toBe(false);
});
