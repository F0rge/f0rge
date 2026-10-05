import { directPurchase, loadApprovedLaunchPack, publishedCustomerPolicies, summarizeLaunchLoad, type LaunchShelf } from "./launch-load";

const now = new Date("2026-10-05T12:00:00.000Z");

const business = {
  legal_name: "Northwind Furnishings (Pty) Ltd",
  trading_name: "Northwind",
  contact_address: "12 Commerce Road, Kramerville, Johannesburg, 2090",
  vat_registered: true,
  vat_number: "4123456789",
  support_mailbox: "support@northwind.co.za",
  daily_operator_name: "Naledi Dlamini",
  escalation_availability: "The owner answers the same business day.",
  confirmed_by: "Naledi Dlamini",
  confirmed_on: "2026-10-05",
};

function variant(index: number, patch: Record<string, unknown> = {}) {
  const n = String(index + 1).padStart(2, "0");
  return {
    sku: `NW-${n}`,
    product_group_id: `group-${n}`,
    options: { Finish: "Oak" },
    price_zar_incl_vat: "18400.00",
    length_cm: 180,
    width_cm: 90,
    height_cm: 78,
    material: "Solid oak and linen",
    care: "Dust weekly and blot spills with a dry cloth.",
    copy: "A dining piece milled from solid oak, sized for a Gauteng dining room, with a linen-upholstered seat and a finish that can be repaired.",
    licensed_photos: [1, 2, 3].map((photo) => ({
      url: `https://images.northwind.co.za/nw-${n}-${photo}.jpg`,
      license: "owner_licensed",
    })),
    wrong_finish_assets: [],
    availability: { kind: "stocked", quantity: 2 },
    ...patch,
  };
}

function readyPack(patch: Record<string, unknown> = {}) {
  const variants = Array.from({ length: 30 }, (_, index) => variant(index));
  variants[2] = variant(2, {
    availability: { kind: "made_to_order", allowance: 4, min_lead_time_days: 21, max_lead_time_days: 35, expires_at: "2026-12-01T00:00:00.000Z" },
  });
  return {
    business,
    catalogue: { approved_by: "Naledi Dlamini", approved_on: "2026-10-05", variants },
    fulfilment: {
      approved_by: "Naledi Dlamini",
      approved_on: "2026-10-05",
      gauteng_zones: [{ name: "Johannesburg", rate_zar_incl_vat: "950.00" }],
      collection: {
        location: "Kramerville showroom, 12 Commerce Road, Johannesburg",
        instructions: "Collect from the showroom desk on weekdays between 09:00 and 16:00.",
      },
      mixed_cart: { promise: "single_promise_slowest_line", approved: true },
    },
    policies: {
      reviewed_by: "Naledi Dlamini",
      reviewed_on: "2026-10-05",
      delivery: "Delivery is available in the approved Gauteng zones at the stated VAT-inclusive rate. Collection from the showroom is the alternative.",
      cancellation_returns_refund: "Standard made to order pieces keep the confirmed lead time on the order. Bespoke commissions are not offered on the storefront and use a separate agreement.",
      privacy: "We use contact details to fulfil the order and to provide support. Optional analytics stay off until the visitor accepts them.",
      information_officer_name: "Naledi Dlamini",
      information_officer_responsibilities: "Receives privacy questions and PAIA requests sent to the support mailbox.",
      paia_baseline: "The information officer publishes the PAIA manual and acknowledges requests received at the support mailbox.",
      collector_skin: "Oxblood / citron",
    },
    provisioning: {
      checked_by: "Naledi Dlamini",
      checked_on: "2026-10-05",
      channels: ["clerk", "peach", "email", "posthog", "railway", "temporary_hostname"].map((channel) => ({
        channel,
        authorized_access: false,
        test_and_live_separated: true,
        remaining_onboarding: "Owner still has to grant this channel.",
      })),
    },
    ...patch,
  };
}

const paidOrder = {
  id: "ord_paid_1",
  paid: true as const,
  lines: [{ sku: "NW-01", quantity: 1, amount_cents: 1_840_000 }],
};

function shelf(orders = [paidOrder]): LaunchShelf {
  return { variants: [], orders };
}

test("an absent pack publishes nothing and leaves paid orders unchanged", () => {
  const current = shelf();
  const result = loadApprovedLaunchPack(current, undefined, now);

  expect(result.loaded).toBe(false);
  expect(result.public_selling).toBe(false);
  expect(result.shelf.variants).toEqual([]);
  expect(result.shelf.orders).toEqual([paidOrder]);
  expect(result.shelf.orders).not.toBe(current.orders);
  expect(directPurchase(result.shelf, "NW-01")).toEqual({
    allowed: false,
    reason: "This piece is not published.",
  });
  expect(publishedCustomerPolicies(undefined, now)).toBeNull();
});

test("an incomplete variant stays unpublished and cannot be bought directly", () => {
  const pack = readyPack();
  const variants = pack.catalogue.variants;
  variants[0] = variant(0, { licensed_photos: variant(0).licensed_photos.slice(0, 2) });
  const result = loadApprovedLaunchPack(shelf(), { ...pack, catalogue: { ...pack.catalogue, variants } }, now);

  expect(result.loaded).toBe(false);
  expect(result.shelf.variants.find((item) => item.sku === "NW-01")).toBeUndefined();
  expect(directPurchase(result.shelf, "NW-01")).toEqual({
    allowed: false,
    reason: "This piece is not published.",
  });
  expect(result.shelf.orders).toEqual([paidOrder]);
});

test("an approved pack loads each variant once under a stable group and option mapping", () => {
  const result = loadApprovedLaunchPack(shelf(), readyPack(), now);
  const first = result.shelf.variants.find((item) => item.sku === "NW-01");
  const madeToOrder = result.shelf.variants.find((item) => item.sku === "NW-03");

  expect(result.loaded).toBe(true);
  expect(result.public_selling).toBe(false);
  expect(result.shelf.variants).toHaveLength(30);
  expect(first).toMatchObject({
    sku: "NW-01",
    product_group_id: "group-01",
    option_key: "Finish: Oak",
    mapping_id: "launch:group-01:NW-01",
    published: true,
    price_zar_incl_vat: "18400.00",
    photo_urls: [
      "https://images.northwind.co.za/nw-01-1.jpg",
      "https://images.northwind.co.za/nw-01-2.jpg",
      "https://images.northwind.co.za/nw-01-3.jpg",
    ],
    promise: { kind: "stocked", quantity: 2 },
  });
  expect(madeToOrder?.promise).toEqual({
    kind: "made_to_order",
    allowance: 4,
    min_lead_time_days: 21,
    max_lead_time_days: 35,
    expires_at: "2026-12-01T00:00:00.000Z",
  });
  expect(directPurchase(result.shelf, "NW-01")).toEqual({ allowed: true, mapping_id: "launch:group-01:NW-01" });
  expect(directPurchase(result.shelf, "NW-99")).toEqual({ allowed: false, reason: "This piece is not published." });
});

test("loading the same pack again does not duplicate products or rewrite a paid order", () => {
  const first = loadApprovedLaunchPack(shelf(), readyPack(), now);
  const repriced = readyPack();
  repriced.catalogue.variants[0] = variant(0, { price_zar_incl_vat: "19000.00" });
  const second = loadApprovedLaunchPack(first.shelf, repriced, now);
  const kept = second.shelf.variants.filter((item) => item.sku === "NW-01");

  expect(second.loaded).toBe(true);
  expect(second.shelf.variants).toHaveLength(30);
  expect(kept).toHaveLength(1);
  expect(kept[0].mapping_id).toBe("launch:group-01:NW-01");
  expect(kept[0].price_zar_incl_vat).toBe("19000.00");
  expect(second.shelf.orders).toEqual([paidOrder]);
});

test("a later approved pack unpublishes a removed sku without touching its paid line", () => {
  const first = loadApprovedLaunchPack(shelf(), readyPack(), now);
  const next = readyPack();
  next.catalogue.variants[0] = variant(30);
  const second = loadApprovedLaunchPack(first.shelf, next, now);
  const removed = second.shelf.variants.find((item) => item.sku === "NW-01");

  expect(second.shelf.variants.filter((item) => item.published)).toHaveLength(30);
  expect(removed).toMatchObject({ published: false, mapping_id: "launch:group-01:NW-01" });
  expect(directPurchase(second.shelf, "NW-01")).toEqual({ allowed: false, reason: "This piece is not published." });
  expect(directPurchase(second.shelf, "NW-31")).toEqual({ allowed: true, mapping_id: "launch:group-31:NW-31" });
  expect(second.shelf.orders).toEqual([paidOrder]);
});

test("a rejected reload does not unpublish pieces from the last approved load", () => {
  const first = loadApprovedLaunchPack(shelf(), readyPack(), now);
  const second = loadApprovedLaunchPack(first.shelf, undefined, now);

  expect(second.loaded).toBe(false);
  expect(second.shelf.variants).toEqual(first.shelf.variants);
  expect(directPurchase(second.shelf, "NW-01").allowed).toBe(true);
  expect(second.shelf.orders).toEqual([paidOrder]);
});

test("reviewed support, delivery, returns and privacy are copied only from an approved pack", () => {
  expect(publishedCustomerPolicies(readyPack(), now)).toEqual({
    legal_name: "Northwind Furnishings (Pty) Ltd",
    trading_name: "Northwind",
    contact_address: "12 Commerce Road, Kramerville, Johannesburg, 2090",
    support_mailbox: "support@northwind.co.za",
    delivery: "Delivery is available in the approved Gauteng zones at the stated VAT-inclusive rate. Collection from the showroom is the alternative.",
    collection_location: "Kramerville showroom, 12 Commerce Road, Johannesburg",
    collection_instructions: "Collect from the showroom desk on weekdays between 09:00 and 16:00.",
    gauteng_zones: [{ name: "Johannesburg", rate_zar_incl_vat: "950.00" }],
    cancellation_returns_refund: "Standard made to order pieces keep the confirmed lead time on the order. Bespoke commissions are not offered on the storefront and use a separate agreement.",
    privacy: "We use contact details to fulfil the order and to provide support. Optional analytics stay off until the visitor accepts them.",
    information_officer_name: "Naledi Dlamini",
    information_officer_responsibilities: "Receives privacy questions and PAIA requests sent to the support mailbox.",
    paia_baseline: "The information officer publishes the PAIA manual and acknowledges requests received at the support mailbox.",
    collector_skin: "Oxblood / citron",
    distinguishes_standard_made_to_order_from_bespoke: true,
  });
  const undifferentiated = readyPack();
  undifferentiated.policies.cancellation_returns_refund = undifferentiated.policies.cancellation_returns_refund.replace("Bespoke commissions", "Custom work");
  expect(publishedCustomerPolicies(undifferentiated, now)).toBeNull();
});

test("the load summary reports an absent pack without echoing a secret", () => {
  const secret = "sk_live_do_not_print_this_value";
  const summary = summarizeLaunchLoad({ provisioning: { peach_api_key: secret } }, now);
  expect(summary).toMatchObject({ loaded: false, public_selling: false, published_variants: 0 });
  expect(JSON.stringify(summary)).not.toContain(secret);
  expect(summary.findings.map((finding) => finding.code)).toEqual(["provisioning_incomplete"]);
});
