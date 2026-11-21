import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, Modules } from "@medusajs/framework/utils";
import * as flows from "@medusajs/medusa/core-flows";
import { allowsFiniteBackorder, catalogueExternalIds, groupOpsProducts, isCatalogueRow, missingTaxInclusiveZarPrice, syncFirstout } from "./sync-firstout";
import type { OpsProduct } from "./ops-contract";

jest.mock("./storefront-order-handoff", () => ({ reconcileStorefrontHandoffs: jest.fn() }));
jest.mock("./storefront-commerce-exceptions", () => ({ recordOpsCheckoutHealth: jest.fn(), refreshOpsCheckoutHealth: jest.fn() }));
jest.mock("@medusajs/medusa/core-flows", () => Object.fromEntries([
  "createCollectionsWorkflow", "createInventoryLevelsWorkflow", "createProductCategoriesWorkflow", "createProductsWorkflow",
  "createProductVariantsWorkflow", "deleteProductVariantsWorkflow", "updateCollectionsWorkflow", "updateInventoryLevelsWorkflow",
  "updateProductVariantsWorkflow", "updateProductsWorkflow",
].map((name) => [name, jest.fn()])));

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

type FakeProduct = Record<string, unknown> & { id: string; external_id: string };

/** A Medusa stand-in: every workflow call is recorded, and product creation is reflected in the catalogue. */
function fakeMedusa(products: FakeProduct[], feed: OpsProduct[]) {
  const calls: { workflow: string; input: unknown }[] = [];
  for (const [name, mock] of Object.entries(flows).filter(([, value]) => jest.isMockFunction(value))) {
    (mock as jest.Mock).mockImplementation(() => ({ run: async ({ input }: { input: Record<string, unknown> }) => {
      calls.push({ workflow: name, input });
      if (name !== "createProductsWorkflow") return { result: [] };
      const [product] = input.products as { external_id: string; variants: { sku: string }[] }[];
      const created = { ...product, id: `prod_${products.length}`, variants: product.variants.map((variant) => ({ ...variant, id: `variant_${variant.sku}` })) };
      products.push(created as unknown as FakeProduct);
      return { result: [created] };
    } }));
  }
  const rows: Record<string, unknown[]> = {
    product: products, sales_channel: [{ id: "sc_1" }], stock_location: [{ id: "sloc_1" }], shipping_profile: [{ id: "sp_1" }],
    inventory_level: [], product_collection: [{ id: "pcol_sale", handle: "on-sale", title: "On Sale" }],
  };
  const graph = jest.fn(async ({ entity, filters }: { entity: string; filters?: { id?: string } }) => entity === "product_variant"
    ? { data: [{ id: filters?.id, inventory_items: [{ inventory_item_id: `iitem_${filters?.id}` }] }] }
    : { data: rows[entity] });
  const services: Record<string, unknown> = {
    [ContainerRegistrationKeys.QUERY]: { graph },
    [ContainerRegistrationKeys.LOGGER]: { info: jest.fn(), warn: jest.fn(), error: jest.fn() },
    [Modules.LOCKING]: { execute: async (_key: string, job: () => Promise<unknown>) => job() },
    [Modules.INVENTORY]: { listReservationItems: async () => [] },
  };
  process.env.FIRSTOUT_OPS_URL = "https://firstout.test/api/v1/ops-commerce/v1";
  process.env.FIRSTOUT_OPS_TOKEN = "ops-token";
  process.env.FIRSTOUT_OPS_COMPANY_ID = "5b2f8c3e-4a1d-4c55-9a7e-0d1c2b3a4f5e";
  global.fetch = jest.fn(async () => new Response(JSON.stringify({ company_id: process.env.FIRSTOUT_OPS_COMPANY_ID, products: feed })));
  return { calls, container: { resolve: (key: string) => services[key] } as unknown as MedusaContainer };
}

test("a sync run writes no room metadata and never sends categories", async () => {
  const table = { ...base, source_sku_id: "627a41f1-9892-4bbc-bcfb-b4149474235d", product_group_id: null, product_title: null, options: {}, sku: "TABLE-1", name: "Carrara marble coffee table" };
  const existing: FakeProduct = {
    id: "prod_table", external_id: `firstout-${table.source_sku_id}`, status: "published", collection_id: "pcol_sale",
    metadata: { storefront_room_collections: ["sofas"] }, categories: [{ id: "pcat_staff" }], options: [{ title: "Item" }],
    variants: [{ id: "variant_table", sku: "TABLE-1", allow_backorder: false, options: [{ value: "Standard", option: { title: "Item" } }],
      metadata: { source_sku_id: table.source_sku_id, source_revision: "2026-09-01T00:00:00.000000Z" } }],
  };
  const { calls, container } = fakeMedusa([existing], [base, table]);

  await syncFirstout(container);

  const created = calls.find((call) => call.workflow === "createProductsWorkflow")?.input as { products: { metadata: unknown }[] };
  expect(created.products[0].metadata).toEqual({ source_product_group_id: base.product_group_id });
  expect(calls.map((call) => call.workflow)).not.toContain("createProductCategoriesWorkflow");
  const written = JSON.stringify(calls.map((call) => call.input));
  expect(written).not.toContain("storefront_room_collections");
  expect(written).not.toMatch(/categor/);
  expect(calls.filter((call) => call.workflow === "updateProductVariantsWorkflow")).toHaveLength(1);
});
