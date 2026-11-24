import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, Modules } from "@medusajs/framework/utils";
import * as flows from "@medusajs/medusa/core-flows";
import { createHash } from "node:crypto";
import { allowsFiniteBackorder, catalogueExternalIds, groupOpsProducts, isCatalogueRow, missingTaxInclusiveZarPrice, syncFirstout } from "./sync-firstout";
import type { OpsProduct } from "./ops-contract";

jest.mock("./storefront-order-handoff", () => ({ reconcileStorefrontHandoffs: jest.fn() }));
jest.mock("./storefront-commerce-exceptions", () => ({ recordOpsCheckoutHealth: jest.fn(), refreshOpsCheckoutHealth: jest.fn() }));
jest.mock("@medusajs/medusa/core-flows", () => Object.fromEntries([
  "createCollectionsWorkflow", "createInventoryLevelsWorkflow", "createProductCategoriesWorkflow", "createProductsWorkflow",
  "createProductVariantsWorkflow", "deleteProductVariantsWorkflow", "updateCollectionsWorkflow", "updateInventoryLevelsWorkflow",
  "updateProductVariantsWorkflow", "updateProductsWorkflow", "uploadFilesWorkflow", "batchVariantImagesWorkflow", "deleteFilesWorkflow",
  "batchLinkProductsToCategoryWorkflow", "linkProductsToSalesChannelWorkflow",
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
  expect(catalogueExternalIds([stocked, madeToOrder, empty, base, mixedOut], true)).toEqual([
    `firstout-${stocked.source_sku_id}`,
    `firstout-${madeToOrder.source_sku_id}`,
    `firstout-group-${base.product_group_id}`,
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
// The four shop categories and one staff category the sync must never touch.
const CATEGORIES = [
  { id: "pcat_sofas", handle: "sofas-armchairs" }, { id: "pcat_dining", handle: "dining-room" },
  { id: "pcat_bedroom", handle: "bedroom" }, { id: "pcat_tables", handle: "coffee-console-tables" },
  { id: "pcat_featured", handle: "featured" },
];
const jpeg = (bytes = new Uint8Array([0xff, 0xd8, 0xff])) => new Response(bytes, { headers: { "content-type": "image/jpeg" } });
const [TOKEN_SOFA_1, TOKEN_TABLE_1, TOKEN_TABLE_2] = ["a", "b", "c"].map((digit) => digit.repeat(64));

/**
 * A Medusa stand-in: every workflow call is recorded, and product, image and
 * variant writes are applied to the in-memory catalogue so a second run sees them.
 */
function fakeMedusa(products: FakeProduct[], feed: OpsProduct[]) {
  const calls: { workflow: string; input: WorkflowInput }[] = [];
  const state = { feed, curated: false, photo: (_sourceSkuId: string, _slot: number | null): Response => jpeg() };
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
      const update = input.update as { images?: Partial<FakeImage>[]; thumbnail?: string; title?: string; metadata?: Record<string, unknown> };
      for (const product of byIds(input.selector as { id: string })) {
        if (update.title) product.title = update.title;
        if ("status" in update) product.status = Reflect.get(update, "status");
        if ("collection_id" in update) product.collection_id = Reflect.get(update, "collection_id");
        if (update.metadata) product.metadata = { ...(product.metadata as Record<string, unknown>), ...update.metadata };
        if (update.images) {
          product.images = update.images.map((image) => image.id
            ? product.images!.find((current) => current.id === image.id)!
            : { ...image, id: `img_${(sequence += 1)}` } as FakeImage);
        }
        if (update.thumbnail) product.thumbnail = update.thumbnail;
      }
      return [];
    },
    batchLinkProductsToCategoryWorkflow: (input) => {
      for (const product of byIds({ id: [...input.add as string[], ...input.remove as string[]] })) {
        const current = (product.categories || []) as { id: string }[];
        product.categories = (input.remove as string[]).includes(product.id)
          ? current.filter((category) => category.id !== input.id) : [...current, { id: input.id }];
      }
      return [];
    },
    linkProductsToSalesChannelWorkflow: (input) => {
      for (const product of byIds({ id: [...((input.add || []) as string[]), ...((input.remove || []) as string[])] })) {
        const current = (product.sales_channels || []) as { id: string }[];
        product.sales_channels = ((input.remove || []) as string[]).includes(product.id)
          ? current.filter((channel) => channel.id !== input.id) : [...current, { id: input.id }];
      }
      return [];
    },
    batchVariantImagesWorkflow: (input) => {
      const variant = products.flatMap((product) => product.variants || []).find((candidate) => candidate.id === input.variant_id);
      if (variant) variant.images = [
        ...(variant.images || []).filter(({ id }) => !(input.remove as string[] | undefined)?.includes(id)),
        ...(input.add as string[]).map((id) => ({ id })),
      ];
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
  const graph = jest.fn(async ({ entity, filters }: { entity: string; filters?: { id?: string; handle?: string[] } }) => {
    if (entity === "product_category") return { data: CATEGORIES.filter((category) => filters?.handle?.includes(category.handle)) };
    if (entity === "product_variant") return { data: [{ id: filters?.id, inventory_items: [{ inventory_item_id: `iitem_${filters?.id}` }] }] };
    if (entity === "product") return { data: filters?.id ? byIds({ id: filters.id }) : products };
    return { data: rows[entity] || [] };
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
    const photo = /\/products\/([^/]+)\/photo(?:\?slot=(\d+))?$/.exec(url);
    if (photo) return state.photo(photo[1], photo[2] ? Number(photo[2]) : null);
    return new Response(JSON.stringify({ company_id: process.env.FIRSTOUT_OPS_COMPANY_ID, products: state.feed,
      ...(state.curated ? { curated_catalogue: true } : {}),
    }));
  });
  global.fetch = fetchMock as unknown as typeof fetch;
  const photoFetches = () => fetchMock.mock.calls.filter(([url]) => url.endsWith("/photo")).map(([url]) => url.split("/").at(-2));
  return { calls, logger, rows, state, photoFetches, container: { resolve: (key: string) => services[key] } as unknown as MedusaContainer };
}

test("curated projection verifies and orders three SKU images, stores typed details, and withdraws all other products", async () => {
  const bytes = [1, 2, 3].map((slot) => new Uint8Array([0xff, 0xd8, 0xff, slot]));
  const tokens = bytes.map((body) => createHash("sha256").update(body).digest("hex"));
  const existing = stagedTable();
  const outside: FakeProduct = {
    id: "prod_manual", external_id: "staff", status: "published", collection_id: "pcol_staff",
    sales_channels: [{ id: "sc_1" }, { id: "sc_other" }],
  };
  const review: OpsProduct = { ...table, name: "Approved table", shop_category: "coffee-console-tables",
    dimensions_cm: { width: null, depth: null, height: 74, diameter: 150 }, piece_count: 2,
    gallery_photo_tokens: tokens };
  const { calls, state, container } = fakeMedusa([existing, outside], [review]);
  state.curated = true;
  const photo = jest.fn((_sku: string, slot: number | null) => jpeg(bytes[(slot || 0) - 1]));
  state.photo = photo;
  await syncFirstout(container);
  expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/products?catalogue_version=2&include_setting_photo=true&include_detail_photo=true"), expect.anything());
  expect(existing.status).toBe("published");
  expect(existing.title).toBe("Approved table");
  expect(outside).toMatchObject({ status: "published", collection_id: "pcol_staff", sales_channels: [{ id: "sc_other" }] });
  const variants = existing.variants!;
  const gallery = variants[0].metadata?.suitable_image_urls as string[];
  expect(gallery.map((url) => url.slice(-6))).toEqual(["-1.jpg", "-2.jpg", "-3.jpg"]);
  expect(variants[0].thumbnail).toEqual(gallery[0]);
  expect(existing.thumbnail).toEqual(gallery[0]);
  expect(variants[0].metadata).toMatchObject({ dimensions_cm: review.dimensions_cm, piece_count: 2 });
  expect(photo.mock.calls.map(([, slot]) => slot)).toEqual([1, 2, 3]);
  await syncFirstout(container);
  expect(photo).toHaveBeenCalledTimes(3);
  expect(calls.filter((call) => call.workflow === "uploadFilesWorkflow")).toHaveLength(1);
  bytes[1] = new Uint8Array([0xff, 0xd8, 0xff, 0x23]);
  state.feed = [{ ...review, gallery_photo_tokens: [tokens[0], createHash("sha256").update(bytes[1]).digest("hex"), tokens[2]] }];
  await syncFirstout(container);
  expect(photo.mock.calls.map(([, slot]) => slot)).toEqual([1, 2, 3, 2]);
  expect(variants[0].metadata?.suitable_image_urls).toEqual([gallery[0], expect.not.stringMatching(gallery[1]), gallery[2]]);
  expect(existing.images?.map((image) => image.url)).not.toContain(gallery[1]);
  expect(existing.images).toHaveLength(4); // Three approved views and the untouched staff image.
});

test("a curated product waits for a verified gallery and recovers on the next consistent snapshot", async () => {
  const bytes = [1, 2, 3, 4].map((slot) => new Uint8Array([0xff, 0xd8, 0xff, slot]));
  const tokens = bytes.map((body) => createHash("sha256").update(body).digest("hex"));
  const existing = stagedTable();
  const studio = { ...table, gallery_photo_tokens: tokens.slice(0, 3) };
  const { calls, state, container, logger } = fakeMedusa([existing], [{ ...studio, setting_photo_token: tokens[3] }]);
  state.curated = true;
  const photo = jest.fn((_id: string, slot: number | null) => jpeg(bytes[slot === 4 ? 0 : (slot || 0) - 1]));
  state.photo = photo;
  await syncFirstout(container);
  expect(existing.status).toBe("draft");
  expect(logger.warn).toHaveBeenCalledWith(expect.stringContaining("Firstout gallery changed during download"));
  expect(calls.filter((call) => call.workflow === "uploadFilesWorkflow")).toHaveLength(0);
  photo.mockImplementation((_id, slot) => jpeg(bytes[(slot || 0) - 1]));
  await syncFirstout(container);
  expect(existing.status).toBe("published");
  const variant = existing.variants![0];
  const gallery = variant.metadata?.suitable_image_urls as string[];
  expect(gallery.map((url) => url.slice(-6))).toEqual(["-1.jpg", "-2.jpg", "-3.jpg", "-4.jpg"]);
  expect(existing.thumbnail).toBe(gallery[0]);
  expect(variant.thumbnail).toBe(gallery[0]);
  expect(photo.mock.calls.map(([, slot]) => slot)).toEqual([1, 2, 3, 4, 1, 2, 3, 4]);

  state.feed = [studio];
  await syncFirstout(container);
  expect(variant.metadata?.suitable_image_urls).toEqual(gallery);
  expect(photo).toHaveBeenCalledTimes(8);

  state.feed = [{ ...studio, setting_photo_token: null }];
  await syncFirstout(container);
  expect(variant.metadata?.suitable_image_urls).toEqual(gallery.slice(0, 3));
  expect(existing.images?.map((image) => image.url)).not.toContain(gallery[3]);
  expect(photo).toHaveBeenCalledTimes(8);
});

test("reconciles a slot-five detail independently from setting photos and preserves the hero", async () => {
  const bytes = [1, 2, 3, 4, 5].map((slot) => new Uint8Array([0xff, 0xd8, 0xff, slot]));
  const tokens = bytes.map((body) => createHash("sha256").update(body).digest("hex"));
  const existing = stagedTable();
  const studio = { ...table, gallery_photo_tokens: tokens.slice(0, 3) };
  const detail = { ...studio, detail_photo_token: tokens[4] };
  const { state, container } = fakeMedusa([existing], [detail]);
  state.curated = true;
  const photo = jest.fn((_id: string, slot: number | null) => jpeg(bytes[(slot || 0) - 1]));
  state.photo = photo;
  await syncFirstout(container);

  const variant = existing.variants![0];
  const gallery = variant.metadata?.suitable_image_urls as string[];
  expect(gallery.map((url) => url.slice(-6))).toEqual(["-1.jpg", "-2.jpg", "-3.jpg", "-5.jpg"]);
  expect(variant.metadata?.firstout_gallery_photo_tokens).toEqual([...tokens.slice(0, 3), null, tokens[4]]);
  expect(photo.mock.calls.map(([, slot]) => slot)).toEqual([1, 2, 3, 5]);

  state.feed = [{ ...studio, setting_photo_token: tokens[3] }];
  await syncFirstout(container);
  const withSetting = variant.metadata?.suitable_image_urls as string[];
  expect(withSetting.map((url) => url.slice(-6))).toEqual(["-1.jpg", "-2.jpg", "-3.jpg", "-4.jpg", "-5.jpg"]);
  expect(withSetting[4]).toBe(gallery[3]);
  expect(variant.metadata?.firstout_gallery_photo_tokens).toEqual(tokens);
  expect(photo.mock.calls.map(([, slot]) => slot)).toEqual([1, 2, 3, 5, 4]);

  state.feed = [studio]; // An older provider cannot refer to either supplemental slot.
  await syncFirstout(container);
  expect(variant.metadata?.suitable_image_urls).toEqual(withSetting);
  expect(photo).toHaveBeenCalledTimes(5);

  state.feed = [{ ...studio, setting_photo_token: null }];
  await syncFirstout(container);
  expect(variant.metadata?.suitable_image_urls).toEqual(gallery);
  expect(existing.images?.map((image) => image.url)).not.toContain(withSetting[3]);

  bytes[4] = new Uint8Array([0xff, 0xd8, 0xff, 0x25]);
  state.feed = [{ ...studio, detail_photo_token: createHash("sha256").update(bytes[4]).digest("hex") }];
  await syncFirstout(container);
  const replaced = variant.metadata?.suitable_image_urls as string[];
  expect(replaced.slice(0, 3)).toEqual(gallery.slice(0, 3));
  expect(replaced[3]).not.toBe(gallery[3]);
  expect(existing.images?.map((image) => image.url)).not.toContain(gallery[3]);
  expect(photo.mock.calls.map(([, slot]) => slot)).toEqual([1, 2, 3, 5, 4, 5]);

  state.feed = [{ ...studio, detail_photo_token: null }];
  await syncFirstout(container);
  expect(variant.metadata?.suitable_image_urls).toEqual(gallery.slice(0, 3));
  expect(existing.images?.map((image) => image.url)).not.toContain(replaced[3]);
  expect(existing.images?.map((image) => image.id)).toContain("img_staff");
  expect(variant.thumbnail).toBe(gallery[0]);
  expect(existing.thumbnail).toBe(gallery[0]);
});

test("a failed supplemental download keeps a verified studio gallery published while the sync retries", async () => {
  const bytes = [1, 2, 3, 4, 5].map((slot) => new Uint8Array([0xff, 0xd8, 0xff, slot]));
  const tokens = bytes.map((body) => createHash("sha256").update(body).digest("hex"));
  const existing = stagedTable();
  const studio = { ...table, gallery_photo_tokens: tokens.slice(0, 3) };
  const { calls, state, container, logger } = fakeMedusa([existing], [studio]);
  state.curated = true;
  const photo = jest.fn((_id: string, slot: number | null) => jpeg(bytes[(slot || 0) - 1]));
  state.photo = photo;
  await syncFirstout(container);
  const variant = existing.variants![0];
  const gallery = variant.metadata?.suitable_image_urls;
  expect(existing.status).toBe("published");

  state.feed = [{ ...studio, detail_photo_token: tokens[4] }];
  photo.mockImplementationOnce(() => jpeg(bytes[0]));
  await syncFirstout(container);
  expect(logger.warn).toHaveBeenCalledWith(expect.stringContaining("Firstout gallery changed during download"));
  expect(existing.status).toBe("published");
  expect(variant.metadata?.suitable_image_urls).toEqual(gallery);
  expect(calls.filter((call) => call.workflow === "uploadFilesWorkflow")).toHaveLength(1);

  await syncFirstout(container);
  expect(existing.status).toBe("published");
  expect(photo.mock.calls.map(([, slot]) => slot)).toEqual([1, 2, 3, 5, 5]);
  expect(variant.metadata?.suitable_image_urls).toEqual([...(gallery as string[]), expect.stringMatching(/-5\.jpg$/)]);
});

test("a selected legacy-only product keeps its custom title and images while an omitted unpriced SKU stays off the shop", async () => {
  const retained = stagedTable();
  retained.title = "Showroom display stand";
  retained.metadata = { firstout_title: "Old source display stand" };
  const omitted: FakeProduct = { id: "prod_omitted", external_id: "firstout-f493d366-0284-42e9-a8d8-e7fb19bb4c06", status: "published" };
  const { container, state } = fakeMedusa([retained, omitted], [{ ...table, shop_category: "coffee-console-tables" }]);
  state.curated = true;
  await syncFirstout(container);
  expect(retained).toMatchObject({ title: "Showroom display stand", status: "published", thumbnail: "https://cdn.example.com/staff-hero.jpg" });
  expect(omitted.status).toBe("draft");
  expect(retained.variants?.[0].metadata).not.toHaveProperty("dimensions_cm");
});

test("curated regrouping blocks when a captured order still depends on the old Medusa variant", async () => {
  const existing = stagedTable();
  const grouped = { ...table, product_group_id: base.product_group_id, product_title: base.product_title, options: base.options };
  const { rows, calls, container, state } = fakeMedusa([existing], [grouped]);
  state.curated = true;
  rows.order_line_item = [{ id: "line_1" }];
  rows.order_item = [{ item_id: "line_1", order_id: "order_1" }];
  const captured = { items: [{ id: "line_1" }], payment_collections: [{ payments: [{ captured_at: "2026-10-01" }] }] };
  const metadata = { storefront_confirmation_sha256: "approved" };
  rows.order = [{ ...captured, metadata }];
  await expect(syncFirstout(container)).rejects.toThrow("waits for the paid-order handoff snapshot");
  expect(calls).toEqual([]);
  const outbox = { status: "imported", payload: {
    lines: [{ external_line_id: "line_1", source_sku_id: table.source_sku_id, sku: table.sku }],
  } };
  rows.order = [{ ...captured, metadata: { ...metadata, storefront_handoff_outbox: outbox } }];
  await expect(syncFirstout(container)).rejects.toThrow("waits for a paid order to finish");
  expect(calls).toEqual([]);
  rows.order = [{ ...captured, metadata: { ...metadata, storefront_handoff_outbox: outbox, storefront_fulfillment_status: { status: "delivered" } } }];
  await expect(syncFirstout(container)).resolves.toBeUndefined();
  expect(calls.some((entry) => entry.workflow === "deleteProductVariantsWorkflow")).toBe(true);
});

test("without a shop category in the feed, a sync run writes no room metadata and never sends categories", async () => {
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
  // Without shop_category nothing is renamed either: no update carries a title.
  expect(calls.filter((call) => call.workflow === "updateProductsWorkflow" && "title" in (call.input.update as object))).toEqual([]);
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

const categoryIds = (product: FakeProduct) => ((product.categories || []) as { id: string }[]).map((category) => category.id).sort();
const linkCalls = (calls: { workflow: string; input: WorkflowInput }[]) => calls.filter((call) => call.workflow === "batchLinkProductsToCategoryWorkflow");

test("the shop category moves a product between the four only and leaves other categories alone", async () => {
  const existing: FakeProduct = { ...stagedTable(), categories: [{ id: "pcat_featured" }, { id: "pcat_bedroom" }] };
  const { calls, state, container } = fakeMedusa([existing], [
    { ...base, shop_category: "sofas-armchairs" }, { ...table, shop_category: "dining-room" },
  ]);

  await syncFirstout(container);
  expect(categoryIds(existing)).toEqual(["pcat_dining", "pcat_featured"]);
  const sofa = (await (container.resolve(ContainerRegistrationKeys.QUERY) as { graph: (q: object) => Promise<{ data: FakeProduct[] }> })
    .graph({ entity: "product" })).data.find((product) => product.external_id === `firstout-group-${base.product_group_id}`)!;
  expect(categoryIds(sofa)).toEqual(["pcat_sofas"]);
  expect(linkCalls(calls).map((call) => call.input)).toEqual(expect.arrayContaining([
    { id: "pcat_dining", add: ["prod_table"], remove: [] },
    { id: "pcat_bedroom", add: [], remove: ["prod_table"] },
  ]));
  expect(linkCalls(calls).map((call) => call.input.id)).not.toContain("pcat_featured");

  // Already placed: nothing is written again.
  const written = linkCalls(calls).length;
  await syncFirstout(container);
  expect(linkCalls(calls)).toHaveLength(written);

  // No shop category in the feed: categories are left exactly as they are.
  state.feed = [base, table];
  await syncFirstout(container);
  expect(linkCalls(calls)).toHaveLength(written);
  expect(categoryIds(existing)).toEqual(["pcat_dining", "pcat_featured"]);
});

test("a Firstout rename reaches the title only while staff have not edited it", async () => {
  const placed = { ...table, shop_category: "coffee-console-tables" };
  const existing: FakeProduct = { ...stagedTable(), title: table.name };
  const { calls, state, container } = fakeMedusa([existing], [{ ...table, name: "Renamed while off" }]);

  // Auto-publish off (no shop_category): names are not touched at all.
  await syncFirstout(container);
  expect(existing.title).toBe(table.name);
  expect(existing.metadata).toEqual({});

  // Synced before names were recorded, still showing the Firstout name: adopted.
  state.feed = [placed, { ...base, shop_category: "sofas-armchairs" }];
  await syncFirstout(container);
  expect(existing.title).toBe(table.name);
  expect(existing.metadata).toMatchObject({ firstout_title: table.name });
  // A product created from a placed row records its Firstout name at creation.
  const created = calls.find((call) => call.workflow === "createProductsWorkflow")?.input as { products: { title: string; metadata: unknown }[] };
  expect(created.products[0]).toMatchObject({ title: "Arc sofa", metadata: { firstout_title: "Arc sofa" } });

  state.feed = [{ ...placed, name: "Carrara coffee table" }];
  await syncFirstout(container);
  expect(existing.title).toBe("Carrara coffee table");
  expect(existing.metadata).toMatchObject({ firstout_title: "Carrara coffee table" });

  existing.title = "Carrara marble table, honed";
  state.feed = [{ ...placed, name: "Carrara table" }];
  await syncFirstout(container);
  expect(existing.title).toBe("Carrara marble table, honed");
  expect(existing.metadata).toMatchObject({ firstout_title: "Carrara coffee table" });

  // A product with an unrecorded name that differs from Firstout's is treated as edited.
  const legacy: FakeProduct = { ...stagedTable(), title: "Staff name", metadata: {} };
  const second = fakeMedusa([legacy], [placed]);
  await syncFirstout(second.container);
  expect(legacy.title).toBe("Staff name");
  expect(legacy.metadata).toEqual({});
});

test("a published piece that leaves the feed is withdrawn", async () => {
  const existing = stagedTable();
  const { calls, container } = fakeMedusa([existing], [base]);

  await syncFirstout(container);
  expect(calls).toContainEqual({ workflow: "updateProductsWorkflow", input: {
    selector: { id: ["prod_table"] }, update: { status: "draft", collection_id: null },
  } });
});
