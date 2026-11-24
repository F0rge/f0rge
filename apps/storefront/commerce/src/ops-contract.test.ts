import { medusaPrice, parseOpsProducts, shouldApplyRevision } from "./ops-contract";

const contract = {
  company_id: "6ba7b814-9dad-453f-9a1f-e66ece58b89b",
  products: [{
    source_sku_id: "e4653558-60c7-4be7-a416-76fc2c055b8f",
    product_group_id: "f6c64903-48ad-4202-a918-7903a40020ce",
    product_title: "Arc sofa",
    options: { Colour: "Sand" },
    sku: "ARC-001",
    name: "Arc sofa",
    price_minor_zar: 1150000,
    available_quantity: 2,
    revision: "2026-09-22T09:14:32.000001",
    observed_at: "2026-09-22T09:14:32.000001",
    acknowledged_commitment_ids: [],
    made_to_order_offer: null,
    photo_token: null,
  }],
};

test("validates a provider-neutral private product snapshot", () => {
  expect(parseOpsProducts(contract, contract.company_id).products[0].sku).toBe("ARC-001");
  expect(() => parseOpsProducts(contract, "912f8c83-777f-4485-9ddd-f1d709db18f6")).toThrow();
  expect(() => parseOpsProducts({ ...contract, products: [...contract.products, contract.products[0]] }, contract.company_id)).toThrow();
  expect(() => parseOpsProducts({ ...contract, products: [{ ...contract.products[0], supplier_ref: "private" }] }, contract.company_id)).toThrow();
  expect(parseOpsProducts({ ...contract, products: [{ ...contract.products[0], photo_token: "a".repeat(64) }] }, contract.company_id)
    .products[0].photo_token).toBe("a".repeat(64));
  const { photo_token: _omitted, ...withoutPhotoToken } = contract.products[0];
  expect(parseOpsProducts({ ...contract, products: [withoutPhotoToken] }, contract.company_id).products[0].photo_token).toBeUndefined();
  for (const malformed of ["", "A".repeat(64), "a".repeat(65), "../photo"]) {
    expect(() => parseOpsProducts({ ...contract, products: [{ ...contract.products[0], photo_token: malformed }] }, contract.company_id)).toThrow();
  }
});

test("v2 accepts ordered catalogue fields without internal notes or zero prices", () => {
  const row = {
    ...contract.products[0], dimensions_cm: { width: null, depth: null, height: 74, diameter: 150 },
    piece_count: 2, gallery_photo_tokens: ["a", "b", "c"].map((letter) => letter.repeat(64)),
  };
  const request = (product: unknown) => parseOpsProducts({
    ...contract, curated_catalogue: true, products: [product],
  }, contract.company_id);
  expect(request(row)).toMatchObject({ curated_catalogue: true, products: [row] });
  expect(request({ ...row, dimensions_cm: null, piece_count: null })).toMatchObject({
    products: [{ dimensions_cm: null, piece_count: null }],
  });
  expect(() => request({ ...row, gallery_photo_tokens: row.gallery_photo_tokens.slice(0, 2) })).toThrow();
  expect(() => request({ ...row, gallery_photo_tokens: Array(3).fill("a".repeat(64)) })).toThrow();
  expect(() => request({ ...row, dimensions_cm: { ...row.dimensions_cm, height: -1 } })).toThrow();
  expect(() => request({ ...row, piece_count: 0 })).toThrow();
  expect(() => request({ ...row, price_minor_zar: 0 })).toThrow();
  expect(() => request({ ...row, notes: "internal" })).toThrow();
});

test("an opted-in setting photo has its own token after the three distinct studio photos", () => {
  const row = contract.products[0];
  const studio = ["a", "b", "c"].map((letter) => letter.repeat(64));
  const setting = "d".repeat(64);
  const read = (overrides: Record<string, unknown>) => parseOpsProducts({
    ...contract, products: [{ ...row, ...overrides }],
  }, contract.company_id).products[0];

  expect(read({ gallery_photo_tokens: studio, setting_photo_token: setting }).setting_photo_token).toBe(setting);
  expect(read({ gallery_photo_tokens: studio }).setting_photo_token).toBeUndefined();
  expect(read({ setting_photo_token: null }).setting_photo_token).toBeNull();
  expect(() => read({ setting_photo_token: setting })).toThrow();
  expect(() => read({ gallery_photo_tokens: studio, setting_photo_token: studio[0] })).toThrow();
  expect(() => read({ gallery_photo_tokens: studio, setting_photo_token: "unverified" })).toThrow();
  expect(() => read({ gallery_photo_tokens: [...studio, setting] })).toThrow();
});

test("a material detail photo can follow the studio gallery even without a setting photo", () => {
  const studio = ["a", "b", "c"].map((letter) => letter.repeat(64));
  const setting = "d".repeat(64);
  const detail = "e".repeat(64);
  const read = (fields: Record<string, unknown>) => parseOpsProducts({
    ...contract, products: [{ ...contract.products[0], ...fields }],
  }, contract.company_id).products[0];

  expect(read({ gallery_photo_tokens: studio, detail_photo_token: detail }).detail_photo_token).toBe(detail);
  expect(read({ gallery_photo_tokens: studio, setting_photo_token: setting, detail_photo_token: detail }))
    .toMatchObject({ setting_photo_token: setting, detail_photo_token: detail });
  expect(read({ gallery_photo_tokens: studio }).detail_photo_token).toBeUndefined();
  expect(read({ detail_photo_token: null }).detail_photo_token).toBeNull();
  expect(() => read({ detail_photo_token: detail })).toThrow();
  expect(() => read({ gallery_photo_tokens: studio, detail_photo_token: studio[2] })).toThrow();
  expect(() => read({ gallery_photo_tokens: studio, setting_photo_token: setting, detail_photo_token: setting })).toThrow();
  expect(() => read({ gallery_photo_tokens: studio, detail_photo_token: "unverified" })).toThrow();
});

test("validates finite made-to-order offers and rejects an inverted promise range", () => {
  const offer = {
    id: "bcd2f5d4-237b-43fb-a152-bef10a6a3eaa",
    capacity: 4,
    min_lead_time_days: 28,
    max_lead_time_days: 42,
    expires_at: "2026-10-15T12:00:00Z",
  };
  expect(parseOpsProducts({ ...contract, products: [{ ...contract.products[0], made_to_order_offer: offer }] }, contract.company_id)
    .products[0].made_to_order_offer?.capacity).toBe(4);
  expect(() => parseOpsProducts({ ...contract, products: [{ ...contract.products[0], made_to_order_offer: { ...offer, max_lead_time_days: 27 } }] }, contract.company_id)).toThrow();
  expect(() => parseOpsProducts({ ...contract, products: [{ ...contract.products[0], made_to_order_offer: { ...offer, secret: "supplier" } }] }, contract.company_id)).toThrow();
});

test("rejects duplicate option combinations and inconsistent group definitions", () => {
  const second = { ...contract.products[0], source_sku_id: "da9cdb14-9126-408d-a3bd-ab8352d2d810", sku: "ARC-002" };
  expect(() => parseOpsProducts({ ...contract, products: [contract.products[0], second] }, contract.company_id)).toThrow();
  expect(() => parseOpsProducts({ ...contract, products: [contract.products[0], { ...second, options: { Size: "Large" } }] }, contract.company_id)).toThrow();
  expect(() => parseOpsProducts({ ...contract, products: [contract.products[0], { ...second, product_title: "Other sofa" }] }, contract.company_id)).toThrow();
  expect(() => parseOpsProducts({ ...contract, products: [{ ...contract.products[0], product_group_id: null }] }, contract.company_id)).toThrow();
});

test("accepts an optional shop category from the four, consistent across a group", () => {
  const product = contract.products[0];
  expect(parseOpsProducts({ ...contract, products: [{ ...product, shop_category: "dining-room" }] }, contract.company_id)
    .products[0].shop_category).toBe("dining-room");
  expect(parseOpsProducts(contract, contract.company_id).products[0].shop_category).toBeUndefined();
  for (const unknown of ["featured", "Dining Room", "", null]) {
    expect(() => parseOpsProducts({ ...contract, products: [{ ...product, shop_category: unknown }] }, contract.company_id)).toThrow();
  }
  const second = { ...product, source_sku_id: "da9cdb14-9126-408d-a3bd-ab8352d2d810", sku: "ARC-002", options: { Colour: "Charcoal" } };
  expect(() => parseOpsProducts({ ...contract, products: [
    { ...product, shop_category: "bedroom" }, { ...second, shop_category: "dining-room" },
  ] }, contract.company_id)).toThrow("inconsistent shop categories");
  expect(() => parseOpsProducts({ ...contract, products: [{ ...product, shop_category: "bedroom" }, second] }, contract.company_id)).toThrow();
});

test("converts exact ZAR cents to Medusa v2 major units", () => {
  expect(medusaPrice(1150000)).toBe(11500);
  expect(medusaPrice(115001)).toBe(1150.01);
  expect(() => medusaPrice(-1)).toThrow();
});

test("applies only newer source observations", () => {
  expect(shouldApplyRevision("2026-09-22T09:15:00.000000", "2026-09-22T09:14:32.000001")).toBe(true);
  expect(shouldApplyRevision("2026-09-22T09:14:32.000001", "2026-09-22T09:14:32.000001")).toBe(false);
  expect(shouldApplyRevision("2026-09-22T09:14:00.000000", "2026-09-22T09:14:32.000001")).toBe(false);
});
