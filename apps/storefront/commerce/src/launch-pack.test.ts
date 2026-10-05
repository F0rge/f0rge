import { assessLaunchPack } from "./launch-pack";

const confirmedBusiness = {
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

function codes(pack: unknown): string[] {
  return assessLaunchPack(pack).findings.map((finding) => finding.code);
}

test("an absent launch pack is not ready and names every owner input", () => {
  const assessment = assessLaunchPack(undefined);
  expect(assessment.ready).toBe(false);
  expect(assessment.findings.map((finding) => finding.code)).toEqual([
    "business_identity_unconfirmed",
    "catalogue_not_approved",
    "availability_unconfirmed",
    "policies_unreviewed",
    "provisioning_incomplete",
  ]);
  expect(assessment.findings.every((finding) => !/secret|password|token/i.test(finding.detail))).toBe(true);
});

test("owner-confirmed business particulars clear only the identity finding", () => {
  expect(codes({ business: confirmedBusiness })).toEqual([
    "catalogue_not_approved",
    "availability_unconfirmed",
    "policies_unreviewed",
    "provisioning_incomplete",
  ]);
});

test("the software name Firstout is not a confirmed retail identity", () => {
  expect(codes({ business: { ...confirmedBusiness, legal_name: "Firstout" } })).toContain("business_identity_unconfirmed");
  expect(codes({ business: { ...confirmedBusiness, trading_name: "firstout" } })).toContain("business_identity_unconfirmed");
});

test("a support mailbox on a reserved domain is not a dedicated mailbox", () => {
  expect(codes({ business: { ...confirmedBusiness, support_mailbox: "support@shop.example" } })).toContain(
    "business_identity_unconfirmed",
  );
});

test("an unregistered VAT position is explicit and a short VAT number is not", () => {
  expect(codes({ business: { ...confirmedBusiness, vat_registered: false, vat_number: "" } })).not.toContain(
    "business_identity_unconfirmed",
  );
  expect(codes({ business: { ...confirmedBusiness, vat_number: "412345678" } })).toContain("business_identity_unconfirmed");
});

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

function catalogue(count: number, patch: Record<string, unknown> = {}) {
  return {
    approved_by: "Naledi Dlamini",
    approved_on: "2026-10-05",
    variants: Array.from({ length: count }, (_, index) => variant(index)),
    ...patch,
  };
}

test("an empty catalogue object is not an approved 30 to 80 variant pack", () => {
  expect(codes({ business: confirmedBusiness, catalogue: {} })).toContain("catalogue_not_approved");
});

test("twenty nine otherwise complete variants stay below the launch range", () => {
  const assessment = assessLaunchPack({ business: confirmedBusiness, catalogue: catalogue(29) });
  expect(assessment.findings).toContainEqual({
    section: "catalogue",
    code: "catalogue_not_approved",
    detail: "Approved sellable variants must number between 30 and 80. This pack has 29.",
  });
});

test("a variant needs three licensed photos and must flag a wrong-finish asset", () => {
  const shortPhotos = catalogue(30).variants;
  shortPhotos[0] = variant(0, { licensed_photos: variant(0).licensed_photos.slice(0, 2) });
  expect(assessLaunchPack({ catalogue: catalogue(30, { variants: shortPhotos }) }).findings).toContainEqual({
    section: "catalogue",
    code: "catalogue_not_approved",
    detail: "SKU NW-01 needs at least three licensed photos of its own finish.",
  });
  const shared = "https://images.northwind.co.za/nw-01-walnut.jpg";
  const crossed = catalogue(30).variants;
  crossed[0] = variant(0, {
    licensed_photos: [...variant(0).licensed_photos.slice(0, 2), { url: shared, license: "owner_licensed" }],
    wrong_finish_assets: [{ url: shared, finish: "Walnut" }],
  });
  expect(assessLaunchPack({ catalogue: catalogue(30, { variants: crossed }) }).findings).toContainEqual({
    section: "catalogue",
    code: "catalogue_not_approved",
    detail: "SKU NW-01 lists a wrong-finish asset as a suitable photo.",
  });
});

const now = new Date("2026-10-05T12:00:00.000Z");

const approvedFulfilment = {
  approved_by: "Naledi Dlamini",
  approved_on: "2026-10-05",
  gauteng_zones: [{ name: "Johannesburg", rate_zar_incl_vat: "950.00" }],
  collection: {
    location: "Kramerville showroom, 12 Commerce Road, Johannesburg",
    instructions: "Collect from the showroom desk on weekdays between 09:00 and 16:00.",
  },
  mixed_cart: { promise: "single_promise_slowest_line", approved: true },
};

test("an empty fulfilment object does not confirm stock, delivery, or the mixed-cart promise", () => {
  expect(codes({ business: confirmedBusiness, catalogue: catalogue(30), fulfilment: {} })).toContain("availability_unconfirmed");
});

test("made-to-order allowances must be finite and unexpired, and the mixed-cart promise must be approved", () => {
  const variants = catalogue(30).variants;
  variants[1] = variant(1, {
    availability: { kind: "made_to_order", allowance: 4, min_lead_time_days: 21, max_lead_time_days: 35, expires_at: "2026-10-01T00:00:00.000Z" },
  });
  expect(assessLaunchPack({
    catalogue: catalogue(30, { variants }),
    fulfilment: approvedFulfilment,
  }, now).findings).toContainEqual({
    section: "availability_and_fulfilment",
    code: "availability_unconfirmed",
    detail: "SKU NW-02 made-to-order allowance is missing, exhausted, or expired.",
  });
  expect(assessLaunchPack({
    catalogue: catalogue(30),
    fulfilment: { ...approvedFulfilment, mixed_cart: { promise: "single_promise_slowest_line", approved: false } },
  }, now).findings).toContainEqual({
    section: "availability_and_fulfilment",
    code: "availability_unconfirmed",
    detail: "The mixed-cart promise is not approved.",
  });
});

const reviewedPolicies = {
  reviewed_by: "Naledi Dlamini",
  reviewed_on: "2026-10-05",
  delivery: "Delivery is available in the approved Gauteng zones at the stated VAT-inclusive rate. Collection from the showroom is the alternative.",
  cancellation_returns_refund: "Standard made to order pieces keep the confirmed lead time on the order. Bespoke commissions are not offered on the storefront and use a separate agreement.",
  privacy: "We use contact details to fulfil the order and to provide support. Optional analytics stay off until the visitor accepts them.",
  information_officer_name: "Naledi Dlamini",
  information_officer_responsibilities: "Receives privacy questions and PAIA requests sent to the support mailbox.",
  paia_baseline: "The information officer publishes the PAIA manual and acknowledges requests received at the support mailbox.",
  collector_skin: "Oxblood / citron",
};

test("policy text must distinguish made to order from bespoke and name one Collector skin", () => {
  expect(codes({ policies: {} })).toContain("policies_unreviewed");
  expect(assessLaunchPack({ policies: { ...reviewedPolicies, collector_skin: "development default" } }).findings).toContainEqual({
    section: "policies_and_skin",
    code: "policies_unreviewed",
    detail: "The final Collector D font and palette is not selected.",
  });
  const undifferentiated = reviewedPolicies.cancellation_returns_refund.replace("Bespoke commissions", "Custom work");
  expect(assessLaunchPack({ policies: { ...reviewedPolicies, cancellation_returns_refund: undifferentiated } }).findings).toContainEqual({
    section: "policies_and_skin",
    code: "policies_unreviewed",
    detail: "Cancellation terms do not distinguish standard made to order from bespoke goods.",
  });
});

const provisioningChannels = ["clerk", "peach", "email", "posthog", "railway", "temporary_hostname"].map((channel) => ({
  channel,
  authorized_access: false,
  test_and_live_separated: true,
  remaining_onboarding: "Owner still has to grant this channel.",
}));

test("the provisioning checklist names each channel without storing a secret or a customer export", () => {
  const secret = "sk_live_do_not_print_this_value";
  const leaked = assessLaunchPack({
    provisioning: { checked_by: "Naledi Dlamini", checked_on: "2026-10-05", channels: provisioningChannels, peach_api_key: secret },
  });
  expect(leaked.ready).toBe(false);
  expect(JSON.stringify(leaked)).not.toContain(secret);
  expect(leaked.findings).toEqual([{
    section: "provisioning",
    code: "provisioning_incomplete",
    detail: "Launch pack must not contain secrets.",
  }]);
  const exported = assessLaunchPack({ customers: [{ email: "buyer@northwind.co.za" }] });
  expect(JSON.stringify(exported)).not.toContain("buyer@northwind.co.za");
  expect(exported.findings).toContainEqual({
    section: "provisioning",
    code: "provisioning_incomplete",
    detail: "Customer exports are not part of the launch pack.",
  });
  expect(codes({ provisioning: { checked_by: "Naledi Dlamini", checked_on: "2026-10-05", channels: provisioningChannels.slice(0, 5) } })).toContain(
    "provisioning_incomplete",
  );
  expect(codes({ provisioning: { checked_by: "Naledi Dlamini", checked_on: "2026-10-05", channels: provisioningChannels } })).not.toContain(
    "provisioning_incomplete",
  );
});

test("SKU identity and option combinations stay unique", () => {
  const repeatedSku = catalogue(30).variants;
  repeatedSku[1] = { ...repeatedSku[1], sku: "NW-01" };
  expect(assessLaunchPack({ catalogue: catalogue(30, { variants: repeatedSku }) }).findings).toContainEqual({
    section: "catalogue",
    code: "catalogue_not_approved",
    detail: "SKU NW-01 is used more than once.",
  });
  const repeatedOptions = catalogue(30).variants;
  repeatedOptions[1] = { ...repeatedOptions[1], product_group_id: "group-01", options: { Finish: "Oak" } };
  expect(assessLaunchPack({ catalogue: catalogue(30, { variants: repeatedOptions }) }).findings).toContainEqual({
    section: "catalogue",
    code: "catalogue_not_approved",
    detail: "Group group-01 repeats the Finish: Oak combination.",
  });
});

test("a complete fictional pack is ready and eighty one variants are not", () => {
  const variants = catalogue(30).variants;
  variants[2] = variant(2, {
    availability: { kind: "made_to_order", allowance: 4, min_lead_time_days: 21, max_lead_time_days: 35, expires_at: "2026-12-01T00:00:00.000Z" },
  });
  const pack = {
    business: confirmedBusiness,
    catalogue: catalogue(30, { variants }),
    fulfilment: approvedFulfilment,
    policies: reviewedPolicies,
    provisioning: { checked_by: "Naledi Dlamini", checked_on: "2026-10-05", channels: provisioningChannels },
  };
  expect(assessLaunchPack(pack, now)).toEqual({ ready: true, findings: [] });
  expect(assessLaunchPack({ ...pack, catalogue: catalogue(81) }, now).findings).toContainEqual({
    section: "catalogue",
    code: "catalogue_not_approved",
    detail: "Approved sellable variants must number between 30 and 80. This pack has 81.",
  });
});
