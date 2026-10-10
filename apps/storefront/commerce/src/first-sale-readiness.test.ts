import { assessFirstSaleReadiness, runPrivateCapacityProbe } from "./first-sale-readiness";

function purchase(patch: Record<string, unknown> = {}) {
  return {
    hosted: true,
    buyer: "guest",
    goods: "stocked",
    fulfilment: "gauteng_delivery",
    payment: "verified",
    commerce_order_id: "order_guest_delivery",
    amount_minor_zar: 1840000,
    firstout: {
      sales_order_count: 1,
      payment_journal_count: 1,
      payment_source: "storefront",
      ops_status: "imported",
      captured_minor_zar: 1840000,
      currency: "ZAR",
    },
    ...patch,
  };
}

function coveringPurchases() {
  return [
    purchase(),
    purchase({
      buyer: "clerk",
      goods: "confirmed_lead_time",
      fulfilment: "collection",
      commerce_order_id: "order_clerk_collection",
      amount_minor_zar: 920000,
      firstout: {
        sales_order_count: 1,
        payment_journal_count: 1,
        payment_source: "storefront",
        ops_status: "imported",
        captured_minor_zar: 920000,
        currency: "ZAR",
      },
    }),
  ];
}

test("an empty record is the same no-go as absent evidence", () => {
  expect(assessFirstSaleReadiness({})).toEqual(assessFirstSaleReadiness(undefined));
});

test("absent evidence is a no-go and leaves public selling off", () => {
  const result = assessFirstSaleReadiness(undefined);

  expect(result).toEqual({
    decision: "no_go",
    public_selling: false,
    public_selling_changed: false,
    release_gate: "open",
    post_launch_follow_up: "Plan five real orders across at least 14 days after an authorized launch. This is not a prelaunch requirement.",
    cost: null,
    capacity: null,
    missing: [
      "Owner catalogue pack is absent.",
      "Reviewed policies are absent.",
      "Provider credentials, callbacks, allowed origins, and sender records are absent.",
      "Named launch operator is absent.",
      "Hosted guest and Clerk purchases were not recorded.",
      "Operator fulfilment, refund, return, and recovery were not recorded.",
      "Consented, rejected, and withdrawn analytics journeys were not recorded.",
      "Private capacity rehearsal was not recorded.",
      "Measured monthly Storefront cost was not recorded.",
      "Environment identity, backups, restore evidence, and alerts were not recorded.",
      "Owner authorization for public selling is absent.",
      "Owner authorization for a real-money rehearsal is absent.",
    ],
  });
});

test("hosted guest and Clerk purchases that cover stocked, lead-time, delivery, and collection close only that gate", () => {
  const result = assessFirstSaleReadiness({ purchases: coveringPurchases() });
  expect(result.decision).toBe("no_go");
  expect(result.public_selling).toBe(false);
  expect(result.release_gate).toBe("open");
  expect(result.missing).not.toContain("Hosted guest and Clerk purchases were not recorded.");
  expect(result.missing).toEqual([
    "Owner catalogue pack is absent.",
    "Reviewed policies are absent.",
    "Provider credentials, callbacks, allowed origins, and sender records are absent.",
    "Named launch operator is absent.",
    "Operator fulfilment, refund, return, and recovery were not recorded.",
    "Consented, rejected, and withdrawn analytics journeys were not recorded.",
    "Private capacity rehearsal was not recorded.",
    "Measured monthly Storefront cost was not recorded.",
    "Environment identity, backups, restore evidence, and alerts were not recorded.",
    "Owner authorization for public selling is absent.",
    "Owner authorization for a real-money rehearsal is absent.",
  ]);
});

function readyOperations() {
  return {
    delivery_progressed: true,
    collection_progressed: true,
    partial_refund: {
      commerce_order_id: "order_guest_delivery",
      captured_minor_zar: 1840000,
      amount_minor_zar: 10000,
      remaining_captured_minor_zar: 1830000,
      restocked: false,
    },
    full_refund: {
      commerce_order_id: "order_clerk_collection",
      captured_minor_zar: 920000,
      amount_minor_zar: 920000,
      remaining_captured_minor_zar: 0,
      restocked: false,
    },
    separate_return: {
      commerce_order_id: "order_guest_delivery",
      restocked: true,
      refund_id: null,
    },
    customer_status_converged: true,
    notifications_converged: true,
    reconciliation_converged: true,
    recovery: {
      closed_browser: { payment_verified: true, commerce_order_id: "order_closed_browser" },
      duplicate_callback: { attempts: 2, commerce_order_ids: ["order_guest_delivery"] },
      firstout_outage: { paid_order_retained: true, handoff_queued: true },
      unknown_outcome: { repeated_financial_action: false, reconciled: true },
    },
  };
}

test("operator delivery, collection, refunds, a separate return, and recovery close only that gate", () => {
  const result = assessFirstSaleReadiness({ operations: readyOperations() });
  expect(result.public_selling).toBe(false);
  expect(result.missing.some((line) => line.startsWith("Operator fulfilment"))).toBe(false);
  expect(result.missing).toContain("Hosted guest and Clerk purchases were not recorded.");
});

test("a refund that restocks, or a duplicate callback with two orders, keeps recovery open", () => {
  const restocked = readyOperations();
  restocked.partial_refund.restocked = true;
  const duplicated = readyOperations();
  duplicated.recovery.duplicate_callback.commerce_order_ids = ["order_guest_delivery", "order_extra"];

  expect(assessFirstSaleReadiness({ operations: restocked }).missing).toContain(
    "The partial refund put goods back into sellable stock.",
  );
  expect(assessFirstSaleReadiness({ operations: duplicated }).missing).toContain(
    "A duplicate callback created another commerce order.",
  );
});

test("measured Storefront spend of 42.00 dollars fits the 50 dollar envelope and leaves fees outside it", () => {
  const result = assessFirstSaleReadiness({
    cost: {
      measured: true,
      usage_assumptions: "One private web service, one Medusa service, Postgres, Redis, and object storage for a month of rehearsal traffic.",
      lines: [
        { category: "compute", usd_cents: 1200, class: "storefront" },
        { category: "staging", usd_cents: 800, class: "storefront" },
        { category: "media", usd_cents: 400, class: "storefront" },
        { category: "backups", usd_cents: 300, class: "storefront" },
        { category: "saas", usd_cents: 1500, class: "storefront" },
        { category: "peach", usd_cents: 250, class: "payment_fee" },
        { category: "courier", usd_cents: 95000, class: "carrier" },
        { category: "firstout", usd_cents: 2000, class: "firstout_hosting" },
      ],
    },
  });

  expect(result.missing.some((line) => line.startsWith("Measured monthly"))).toBe(false);
  expect(result.cost).toEqual({
    storefront_usd_cents: 4200,
    fits_budget: true,
    pending_owner_decision: false,
    disclosed_separately_usd_cents: { payment_fee: 250, carrier: 95000, firstout_hosting: 2000 },
  });
});

test("Storefront spend of 52.00 dollars stays a no-go pending an owner decision", () => {
  const result = assessFirstSaleReadiness({
    cost: {
      measured: true,
      usage_assumptions: "Same private stack, with SaaS raised until the recorded total exceeds the envelope.",
      lines: [
        { category: "compute", usd_cents: 1200, class: "storefront" },
        { category: "staging", usd_cents: 800, class: "storefront" },
        { category: "media", usd_cents: 400, class: "storefront" },
        { category: "backups", usd_cents: 300, class: "storefront" },
        { category: "saas", usd_cents: 2500, class: "storefront" },
      ],
    },
  });
  expect(result.decision).toBe("no_go");
  expect(result.cost).toMatchObject({ storefront_usd_cents: 5200, fits_budget: false, pending_owner_decision: true });
  expect(result.missing).toContain("Measured monthly Storefront cost is above USD 50 and remains a no-go pending an owner decision.");
});

test("a private hosted capacity rehearsal at the proposed profile closes only that gate", () => {
  const samples = [...Array(19).fill(400), 900];
  const result = assessFirstSaleReadiness({
    capacity: {
      source: "hosted_private",
      private_environment: true,
      simulator_public: false,
      concurrent_shoppers: 20,
      duration_minutes: 30,
      simulator_completions_per_minute: 5,
      stock_sync_enabled: true,
      cart_checkout_samples_ms: samples,
      unexpected_errors: 0,
      requests: 200,
      oom: false,
      backlog_start: 4,
      backlog_end: 4,
      duplicate_effects: 0,
    },
  });
  expect(result.missing.some((line) => line.startsWith("Private capacity"))).toBe(false);
  expect(result.capacity).toEqual({
    p95_ms: 400,
    unexpected_error_rate: 0,
    meets_profile: true,
    hosted: true,
  });
  expect(result.public_selling).toBe(false);
});

test("the in-process probe refuses a publicly reachable simulator", () => {
  expect(runPrivateCapacityProbe({
    publiclyReachable: true,
    simulatorPublic: true,
    completions: [{ effectId: "pay_1", latencyMs: 100, unexpectedError: false }],
  })).toEqual({
    refused: true,
    reason: "simulator_public",
    source: "in_process",
    meets_hosted_profile: false,
  });
});

test("the private in-process probe counts a repeated effect and stays short of the hosted profile", () => {
  expect(runPrivateCapacityProbe({
    publiclyReachable: false,
    simulatorPublic: false,
    completions: [
      { effectId: "pay_1", latencyMs: 120, unexpectedError: false },
      { effectId: "pay_1", latencyMs: 80, unexpectedError: false },
      { effectId: "pay_2", latencyMs: 400, unexpectedError: true },
    ],
    backlogStart: 1,
    backlogEnd: 2,
    oom: false,
  })).toEqual({
    refused: false,
    reason: null,
    source: "in_process",
    meets_hosted_profile: false,
    duplicate_effects: 1,
    p95_ms: 400,
    unexpected_errors: 1,
    requests: 3,
    backlog_grew: true,
    oom: false,
  });
});

const MARROW_RAILWAY_PROJECT_ID = "a633a271-5bb0-461e-8eb5-1acb9e126a59";

function readyEnvironment() {
  return {
    railway_project_id: "11111111-1111-4111-8111-111111111111",
    railway_project_name: "F0rge Storefront Preview",
    private_access: true,
    indexing_enabled: false,
    public_selling_enabled: false,
    backup_evidence_id: "backup_2026_10_05",
    restore_evidence_id: "restore_2026_10_05",
    alerts: ["backup_stale", "payment_unknown"],
  };
}

test("provider evidence without recorded allowed origins stays open", () => {
  const result = assessFirstSaleReadiness({
    providers: {
      clerk_callback_recorded: true,
      peach_callback_recorded: true,
      email_sender_recorded: true,
      posthog_eu_recorded: true,
    },
  });
  expect(result.missing.some((line) => line.startsWith("Provider credentials"))).toBe(true);
});

test("a private Storefront environment, recorded callbacks, and a named operator close those gates", () => {
  const result = assessFirstSaleReadiness({
    environment: readyEnvironment(),
    operator: { name: "Naledi Dlamini" },
    providers: {
      clerk_callback_recorded: true,
      peach_callback_recorded: true,
      email_sender_recorded: true,
      posthog_eu_recorded: true,
      allowed_origins_recorded: true,
    },
  });
  expect(result.missing.some((line) => line.startsWith("Environment identity"))).toBe(false);
  expect(result.missing.some((line) => line.startsWith("Provider credentials"))).toBe(false);
  expect(result.missing.some((line) => line.startsWith("Named launch operator"))).toBe(false);
  expect(result.public_selling).toBe(false);
});

test("Marrow project identity and a pasted secret keep the environment gate open without echoing the secret", () => {
  const result = assessFirstSaleReadiness({
    environment: {
      ...readyEnvironment(),
      railway_project_id: MARROW_RAILWAY_PROJECT_ID,
      peach_secret: "sk_live_should_not_print",
    },
  });
  expect(JSON.stringify(result)).not.toContain("sk_live_should_not_print");
  expect(result.missing).toContain("Environment identity points at the Marrow Railway project.");
  expect(result.missing).toContain("Evidence contains a secret and was not accepted.");
});

const DASHBOARDS = [
  "store_health",
  "acquisition",
  "product_performance",
  "purchase_funnel",
  "search_merchandising",
  "friction_quality",
  "accounts",
];

function readyAnalytics() {
  return {
    consented: true,
    rejected_stopped: true,
    withdrawn_stopped: true,
    replay_excludes_sensitive_routes: true,
    dashboards: DASHBOARDS,
    personal_information_exposed: false,
    commerce_blocked: false,
  };
}

test("consented, rejected, and withdrawn analytics with seven dashboards close only that gate", () => {
  const result = assessFirstSaleReadiness({ analytics: readyAnalytics() });
  expect(result.missing.some((line) => line.startsWith("Consented, rejected"))).toBe(false);
  expect(result.public_selling).toBe(false);
});

test("analytics that expose personal information or block commerce stay open", () => {
  const exposed = assessFirstSaleReadiness({
    analytics: { ...readyAnalytics(), personal_information_exposed: true },
  });
  const blocked = assessFirstSaleReadiness({
    analytics: { ...readyAnalytics(), commerce_blocked: true },
  });
  expect(exposed.missing).toContain("Analytics exposed personal information.");
  expect(blocked.missing).toContain("Analytics blocked commerce.");
});

test("an empty launch pack stays a no-go and reports the missing catalogue", () => {
  const result = assessFirstSaleReadiness({ launch_pack: {} });
  expect(result.decision).toBe("no_go");
  expect(result.public_selling).toBe(false);
  expect(result.missing).toContain(
    "Owner has not approved a 30 to 80 variant catalogue with SKU mapping, VAT-inclusive ZAR prices, dimensions, material, care, copy, and licensed photos.",
  );
});

function readyLaunchPack() {
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
  const variants = Array.from({ length: 30 }, (_, index) => {
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
      availability: index === 2
        ? { kind: "made_to_order", allowance: 4, min_lead_time_days: 21, max_lead_time_days: 35, expires_at: "2026-12-01T00:00:00.000Z" }
        : { kind: "stocked", quantity: 2 },
    };
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
  };
}

function hostedCapacity() {
  return {
    source: "hosted_private",
    private_environment: true,
    simulator_public: false,
    concurrent_shoppers: 20,
    duration_minutes: 30,
    simulator_completions_per_minute: 5,
    stock_sync_enabled: true,
    cart_checkout_samples_ms: [...Array(19).fill(400), 900],
    unexpected_errors: 0,
    requests: 200,
    oom: false,
    backlog_start: 4,
    backlog_end: 4,
    duplicate_effects: 0,
  };
}

function fittingCost() {
  return {
    measured: true,
    usage_assumptions: "One private web service, one Medusa service, Postgres, Redis, and object storage for a month of rehearsal traffic.",
    lines: [
      { category: "compute", usd_cents: 1200, class: "storefront" },
      { category: "staging", usd_cents: 800, class: "storefront" },
      { category: "media", usd_cents: 400, class: "storefront" },
      { category: "backups", usd_cents: 300, class: "storefront" },
      { category: "saas", usd_cents: 1500, class: "storefront" },
      { category: "peach", usd_cents: 250, class: "payment_fee" },
    ],
  };
}

function completeEvidence(authorization: Record<string, boolean>) {
  return {
    launch_pack: readyLaunchPack(),
    purchases: coveringPurchases(),
    operations: readyOperations(),
    analytics: readyAnalytics(),
    capacity: hostedCapacity(),
    cost: fittingCost(),
    environment: readyEnvironment(),
    operator: { name: "Naledi Dlamini" },
    providers: {
      clerk_callback_recorded: true,
      peach_callback_recorded: true,
      email_sender_recorded: true,
      posthog_eu_recorded: true,
      allowed_origins_recorded: true,
    },
    owner_decision: authorization,
  };
}

test("complete evidence without owner authorization stays an open no-go and does not enable selling", () => {
  const result = assessFirstSaleReadiness(completeEvidence({
    public_selling_authorized: false,
    real_money_rehearsal_authorized: false,
  }));
  expect(result.decision).toBe("no_go");
  expect(result.public_selling).toBe(false);
  expect(result.release_gate).toBe("open");
  expect(result.missing).toEqual([
    "Owner authorization for public selling is absent.",
    "Owner authorization for a real-money rehearsal is absent.",
  ]);
});

test("a launch pack whose made-to-order allowance has expired stays open", () => {
  const result = assessFirstSaleReadiness(
    { launch_pack: readyLaunchPack() },
    new Date("2027-01-01T00:00:00.000Z"),
  );
  expect(result.decision).toBe("no_go");
  expect(result.missing).toContain("SKU NW-03 made-to-order allowance is missing, exhausted, or expired.");
});

test("cart and checkout p95 above one second keeps the capacity gate open", () => {
  const result = assessFirstSaleReadiness({
    capacity: {
      ...hostedCapacity(),
      cart_checkout_samples_ms: [...Array(18).fill(400), 1500, 1500],
    },
  });
  expect(result.capacity).toMatchObject({ p95_ms: 1500, meets_profile: false, hosted: true });
  expect(result.missing).toContain("First-party cart and checkout p95 was above 1 second.");
});

test("an unexpected error rate of 1 percent does not pass the capacity rehearsal", () => {
  const result = assessFirstSaleReadiness({
    capacity: { ...hostedCapacity(), unexpected_errors: 2, requests: 200 },
  });
  expect(result.capacity?.unexpected_error_rate).toBe(0.01);
  expect(result.missing).toContain("Unexpected server errors were not under 1 percent.");
});

test("authorized complete evidence is a go while public selling stays off", () => {
  const result = assessFirstSaleReadiness(completeEvidence({
    public_selling_authorized: true,
    real_money_rehearsal_authorized: true,
  }));
  expect(result.decision).toBe("go");
  expect(result.public_selling).toBe(false);
  expect(result.public_selling_changed).toBe(false);
  expect(result.release_gate).toBe("closed");
  expect(result.missing).toEqual([]);
  expect(result.post_launch_follow_up).toBe(
    "Plan five real orders across at least 14 days after an authorized launch. This is not a prelaunch requirement.",
  );
});
