import { allowsFiniteBackorder, groupOpsProducts } from "./sync-firstout";
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
