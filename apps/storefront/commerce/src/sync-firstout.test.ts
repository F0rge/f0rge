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
  "updateProductVariantsWorkflow", "updateProductsWorkflow", "uploadFilesWorkflow", "batchVariantImagesWorkflow", "deleteFilesWorkflow",
].map((name) => [name, jest.fn()])));

const base: OpsProduct = {
  source_sku_id: "e4653558-60c7-4be7-a416-76fc2c055b8f",
  product_group_id: "f6c64903-48ad-4202-a918-7903a40020ce",
  product_title: "Arc sofa", options: { Colour: "Sand" },
  sku: "ARC-SAND", name: "Arc sofa Sand", price_minor_zar: 1150000,
  available_quantity: 2, revision: "2026-09-22T09:14:32.000001Z", observed_at: "2026-09-22T09:14:32.000001Z", acknowledged_commitment_ids: [], made_to_order_offer: null, photo_token: null,
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

type FakeImage = { id: string; url: string; metadata?: Record<string, unknown> | null };
type FakeVariant = {
  id: string; sku: string; thumbnail?: string | null; metadata: Record<string, unknown> | null; images?: { id: string }[];
} & Record<string, unknown>;
type FakeProduct = Record<string, unknown> & {
  id: string; external_id: string; thumbnail?: string | null; images?: FakeImage[]; variants?: FakeVariant[];
};
type WorkflowInput = Record<string, unknown>;
const jpeg = (bytes = new Uint8Array([0xff, 0xd8, 0xff])) => new Response(bytes, { headers: { "content-type": "image/jpeg" } });
const [TOKEN_SOFA_1, TOKEN_TABLE_1, TOKEN_TABLE_2] = ["a", "b", "c"].map((digit) => digit.repeat(64));

/**
 * A Medusa stand-in: every workflow call is recorded, and product, image and
 * variant writes are applied to the in-memory catalogue so a second run sees them.
 */
function fakeMedusa(products: FakeProduct[], feed: OpsProduct[]) {
  const calls: { workflow: string; input: WorkflowInput }[] = [];
  const state = { feed, photo: (_sourceSkuId: string): Response => jpeg() };
  let sequence = 0;
  const byIds = (selector: { id: string | string[] }) => products.filter((product) => [selector.id].flat().includes(product.id));
  const apply: Record<string, (input: WorkflowInput) => unknown[]> = {
    createProductsWorkflow: (input) => {
      const [product] = input.products as (FakeProduct & { variants: FakeVariant[] })[];
      // Stored in Medusa's read shape, so a later run maps the created product back.
      const created = { ...product, id: `prod_${products.length}`, variants: product.variants.map((variant) => ({
        ...variant, id: `variant_${variant.sku}`,
        options: Object.entries(variant.options as Record<string, string>).map(([title, value]) => ({ value, option: { title } })),
      })) };
      products.push(created);
      return [created];
    },
    uploadFilesWorkflow: (input) => (input.files as { filename: string }[]).map((file) => {
      sequence += 1;
      return { id: `file_${sequence}`, url: `https://commerce.example.com/static/${sequence}-${file.filename}` };
    }),
    updateProductsWorkflow: (input) => {
      const update = input.update as { images?: Partial<FakeImage>[]; thumbnail?: string };
      for (const product of byIds(input.selector as { id: string })) {
        if (update.images) {
          product.images = update.images.map((image) => image.id
            ? product.images!.find((current) => current.id === image.id)!
            : { ...image, id: `img_${(sequence += 1)}` } as FakeImage);
        }
        if (update.thumbnail) product.thumbnail = update.thumbnail;
      }
      return [];
    },
    batchVariantImagesWorkflow: (input) => {
      const variant = products.flatMap((product) => product.variants || []).find((candidate) => candidate.id === input.variant_id);
      if (variant) variant.images = [...(variant.images || []), ...(input.add as string[]).map((id) => ({ id }))];
      return [];
    },
    updateProductVariantsWorkflow: (input) => {
      for (const update of input.product_variants as { id: string; thumbnail?: string; metadata?: Record<string, unknown> }[]) {
        const variant = products.flatMap((product) => product.variants || []).find((candidate) => candidate.id === update.id);
        if (!variant) continue;
        if (update.thumbnail) variant.thumbnail = update.thumbnail;
        if (update.metadata) variant.metadata = { ...variant.metadata, ...update.metadata };
      }
      return [];
    },
  };
  for (const [name, mock] of Object.entries(flows).filter(([, value]) => jest.isMockFunction(value))) {
    (mock as jest.Mock).mockImplementation(() => ({ run: async ({ input }: { input: WorkflowInput }) => {
      calls.push({ workflow: name, input: JSON.parse(JSON.stringify(input)) });
      return { result: apply[name]?.(input) || [] };
    } }));
  }
  const rows: Record<string, unknown[]> = {
    sales_channel: [{ id: "sc_1" }], stock_location: [{ id: "sloc_1" }], shipping_profile: [{ id: "sp_1" }],
    inventory_level: [], product_collection: [{ id: "pcol_sale", handle: "on-sale", title: "On Sale" }],
  };
  const graph = jest.fn(async ({ entity, filters }: { entity: string; filters?: { id?: string } }) => {
    if (entity === "product_variant") return { data: [{ id: filters?.id, inventory_items: [{ inventory_item_id: `iitem_${filters?.id}` }] }] };
    if (entity === "product") return { data: filters?.id ? byIds({ id: filters.id }) : products };
    return { data: rows[entity] };
  });
  const logger = { info: jest.fn(), warn: jest.fn(), error: jest.fn() };
  const services: Record<string, unknown> = {
    [ContainerRegistrationKeys.QUERY]: { graph },
    [ContainerRegistrationKeys.LOGGER]: logger,
    [Modules.LOCKING]: { execute: async (_key: string, job: () => Promise<unknown>) => job() },
    [Modules.INVENTORY]: { listReservationItems: async () => [] },
  };
  process.env.FIRSTOUT_OPS_URL = "https://firstout.test/api/v1/ops-commerce/v1";
  process.env.FIRSTOUT_OPS_TOKEN = "ops-token";
  process.env.FIRSTOUT_OPS_COMPANY_ID = "5b2f8c3e-4a1d-4c55-9a7e-0d1c2b3a4f5e";
  const fetchMock = jest.fn(async (url: string) => {
    const photo = /\/products\/([^/]+)\/photo$/.exec(url);
    if (photo) return state.photo(photo[1]);
    return new Response(JSON.stringify({ company_id: process.env.FIRSTOUT_OPS_COMPANY_ID, products: state.feed }));
  });
  global.fetch = fetchMock as unknown as typeof fetch;
  const photoFetches = () => fetchMock.mock.calls.filter(([url]) => url.endsWith("/photo")).map(([url]) => url.split("/").at(-2));
  return { calls, logger, state, photoFetches, container: { resolve: (key: string) => services[key] } as unknown as MedusaContainer };
}

test("a sync run writes no room metadata and never sends categories", async () => {
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

const table = { ...base, source_sku_id: "627a41f1-9892-4bbc-bcfb-b4149474235d", product_group_id: null, product_title: null, options: {}, sku: "TABLE-1", name: "Carrara marble coffee table" };
function stagedTable(): FakeProduct {
  return {
    id: "prod_table", external_id: `firstout-${table.source_sku_id}`, status: "published", collection_id: "pcol_sale",
    metadata: {}, options: [{ title: "Item" }], thumbnail: "https://cdn.example.com/staff-hero.jpg",
    images: [{ id: "img_staff", url: "https://cdn.example.com/staff-hero.jpg", metadata: null }],
    variants: [{ id: "variant_table", sku: "TABLE-1", allow_backorder: false, options: [{ value: "Standard", option: { title: "Item" } }],
      metadata: { source_sku_id: table.source_sku_id, source_revision: table.revision, source_observed_at: table.observed_at } }],
  };
}

test("a Firstout photo downloads once per token, beside staff images, and a SKU without a photo is left alone", async () => {
  const existing = stagedTable();
  const { calls, state, photoFetches, container } = fakeMedusa([existing], [{ ...base, photo_token: TOKEN_SOFA_1 }, { ...table, photo_token: TOKEN_TABLE_1 }]);
  const uploads = () => calls.filter((call) => call.workflow === "uploadFilesWorkflow");

  await syncFirstout(container);
  expect(photoFetches().sort()).toEqual([base.source_sku_id, table.source_sku_id].sort());
  expect(uploads().map((call) => call.input)).toContainEqual({ files: [{
    filename: `firstout-${table.source_sku_id}.jpg`, mimeType: "image/jpeg", content: "/9j/", access: "public",
  }] });
  // Staff own the table's hero image and thumbnail; the synced photo is added beside them.
  const synced = existing.images!.find((image) => image.metadata?.firstout_source_sku_id === table.source_sku_id)!;
  expect(existing.images!.map((image) => image.id)).toEqual(["img_staff", synced.id]);
  expect(existing.thumbnail).toBe("https://cdn.example.com/staff-hero.jpg");
  expect(existing.variants![0].thumbnail).toBe(synced.url);
  expect(existing.variants![0].metadata?.firstout_photo_token).toBe(TOKEN_TABLE_1);
  expect(calls).toContainEqual({ workflow: "batchVariantImagesWorkflow", input: { variant_id: "variant_table", add: [synced.id] } });
  // The new sofa had no images, so its photo becomes the product thumbnail.
  const sofa = (await (container.resolve(ContainerRegistrationKeys.QUERY) as { graph: (q: object) => Promise<{ data: FakeProduct[] }> })
    .graph({ entity: "product" })).data.find((product) => product.external_id === `firstout-group-${base.product_group_id}`)!;
  expect(sofa.thumbnail).toBe(sofa.images![0].url);

  await syncFirstout(container);
  expect(photoFetches()).toHaveLength(2);
  expect(uploads()).toHaveLength(2);

  // A new token replaces only the sync's own image; the staff image stays first.
  state.feed = [{ ...base, photo_token: TOKEN_SOFA_1 }, { ...table, photo_token: TOKEN_TABLE_2 }];
  await syncFirstout(container);
  expect(photoFetches()).toHaveLength(3);
  const replaced = existing.images!.find((image) => image.metadata?.firstout_source_sku_id === table.source_sku_id)!;
  expect(existing.images!.map((image) => image.id)).toEqual(["img_staff", replaced.id]);
  expect(replaced.url).not.toBe(synced.url);
  expect(existing.thumbnail).toBe("https://cdn.example.com/staff-hero.jpg");
  expect(existing.variants![0].thumbnail).toBe(replaced.url);

  // No photo in Firstout: nothing is fetched and nothing the product has is touched.
  state.feed = [{ ...base, photo_token: TOKEN_SOFA_1 }, { ...table, photo_token: null }];
  await syncFirstout(container);
  expect(photoFetches()).toHaveLength(3);
  expect(existing.images!.map((image) => image.id)).toEqual(["img_staff", replaced.id]);

  // An older Firstout without the field: no photo info, so photos are left alone.
  const { photo_token: _absent, ...olderFirstout } = table;
  state.feed = [olderFirstout];
  await syncFirstout(container);
  expect(photoFetches()).toHaveLength(3);
  expect(existing.images!.map((image) => image.id)).toEqual(["img_staff", replaced.id]);
  expect(existing.variants![0].metadata?.firstout_photo_token).toBe(TOKEN_TABLE_2);
});

test("a failed photo download is logged and retried without failing the stock sync", async () => {
  const existing = stagedTable();
  const { calls, logger, state, photoFetches, container } = fakeMedusa([existing], [{ ...table, photo_token: TOKEN_TABLE_1 }]);
  state.photo = () => new Response("unavailable", { status: 503 });

  await expect(syncFirstout(container)).resolves.toBeUndefined();
  expect(calls.map((call) => call.workflow)).toContain("createInventoryLevelsWorkflow");
  expect(calls.map((call) => call.workflow)).not.toContain("uploadFilesWorkflow");
  expect(logger.warn).toHaveBeenCalledWith(expect.stringContaining(`Firstout photo for SKU ${table.source_sku_id} was not synced`));
  expect(existing.variants![0].metadata?.firstout_photo_token).toBeUndefined();

  state.photo = () => jpeg();
  await syncFirstout(container);
  expect(photoFetches()).toHaveLength(2);
  expect(existing.variants![0].metadata?.firstout_photo_token).toBe(TOKEN_TABLE_1);
});

test("a photo Medusa refuses to attach is deleted from the volume instead of piling up", async () => {
  const existing = stagedTable();
  const { calls, logger, container } = fakeMedusa([existing], [{ ...table, photo_token: TOKEN_TABLE_1 }]);
  const update = flows.updateProductsWorkflow as unknown as jest.Mock;
  const normal = update.getMockImplementation()!;
  update.mockImplementation(() => ({ run: async ({ input }: { input: WorkflowInput }) => {
    if ((input.update as { images?: unknown }).images) throw new Error("Variant variant_table cannot be published: attested gallery photos must be public images on this variant");
    return normal().run({ input });
  } }));

  await syncFirstout(container);
  expect(calls).toContainEqual({ workflow: "deleteFilesWorkflow", input: { ids: ["file_1"] } });
  expect(existing.images!.map((image) => image.id)).toEqual(["img_staff"]);
  expect(existing.variants![0].metadata?.firstout_photo_token).toBeUndefined();
  expect(logger.warn).toHaveBeenCalled();
});

test("a photo that fails after upload is linked on the next run without uploading again", async () => {
  const existing = stagedTable();
  const { calls, logger, photoFetches, container } = fakeMedusa([existing], [{ ...table, photo_token: TOKEN_TABLE_1 }]);
  const batch = flows.batchVariantImagesWorkflow as unknown as jest.Mock;
  const normal = batch.getMockImplementation()!;
  batch.mockImplementationOnce(() => ({ run: async () => { throw new Error("variant link failed"); } }));

  await syncFirstout(container);
  expect(logger.warn).toHaveBeenCalledWith(expect.stringContaining("variant link failed"));
  expect(existing.variants![0].metadata?.firstout_photo_token).toBeUndefined();
  const synced = existing.images!.find((image) => image.metadata?.firstout_source_sku_id === table.source_sku_id)!;
  expect(synced.metadata?.firstout_photo_token).toBe(TOKEN_TABLE_1);

  batch.mockImplementation(normal);
  await syncFirstout(container);
  // The gallery image is reused: one download, one upload, no deleted or dropped file.
  expect(photoFetches()).toHaveLength(1);
  expect(calls.filter((call) => call.workflow === "uploadFilesWorkflow")).toHaveLength(1);
  expect(calls.map((call) => call.workflow)).not.toContain("deleteFilesWorkflow");
  expect(existing.images!.map((image) => image.id)).toEqual(["img_staff", synced.id]);
  expect(existing.variants![0].images).toEqual([{ id: synced.id }]);
  expect(existing.variants![0].thumbnail).toBe(synced.url);
  expect(existing.variants![0].metadata?.firstout_photo_token).toBe(TOKEN_TABLE_1);

  // Already linked: a later retry of the variant write does not link it twice (the failed call is unrecorded).
  existing.variants![0].metadata = { ...existing.variants![0].metadata, firstout_photo_token: undefined };
  await syncFirstout(container);
  expect(calls.filter((call) => call.workflow === "batchVariantImagesWorkflow")).toHaveLength(1);
  expect(existing.variants![0].metadata?.firstout_photo_token).toBe(TOKEN_TABLE_1);
});

test.each([
  ["an HTML page", () => new Response("<html>login</html>", { headers: { "content-type": "text/html" } })],
  ["a JPEG-labelled non-JPEG", () => jpeg(new Uint8Array([0x3c, 0x68, 0x74]))],
  ["a declared oversized body", () => new Response(new Uint8Array([0xff, 0xd8, 0xff]), {
    headers: { "content-type": "image/jpeg", "content-length": String(5 * 1024 * 1024 + 1) },
  })],
  ["an undeclared oversized body", () => jpeg(new Uint8Array(5 * 1024 * 1024 + 1).fill(0xff))],
])("%s from Firstout is refused: no upload, no token, a warning", async (_label, photo) => {
  const existing = stagedTable();
  const { calls, logger, state, container } = fakeMedusa([existing], [{ ...table, photo_token: TOKEN_TABLE_1 }]);
  state.photo = photo;

  await syncFirstout(container);
  expect(calls.map((call) => call.workflow)).not.toContain("uploadFilesWorkflow");
  expect(existing.variants![0].metadata?.firstout_photo_token).toBeUndefined();
  expect(logger.warn).toHaveBeenCalledWith(expect.stringContaining(`Firstout photo for SKU ${table.source_sku_id} was not synced`));
});

test("Ops requests refuse redirects", async () => {
  const { container } = fakeMedusa([], [base]);
  await syncFirstout(container);
  for (const [, init] of (global.fetch as jest.Mock).mock.calls) expect(init).toMatchObject({ redirect: "error" });
});
