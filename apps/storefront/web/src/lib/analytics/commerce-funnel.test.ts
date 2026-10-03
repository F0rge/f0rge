import { describe, expect, it } from "vitest";
import { confirmedPaymentStep } from "./commerce-events";
import { sanitizeAnalyticsEvent } from "./events";
import { ANALYTICS_POLICY, POSTHOG_EU_INGEST_HOST } from "./policy";
import { POSTHOG_EU_HOST, createPostHogBrowserProvider, type PostHogCapturePayload } from "./posthog-browser";
import { OutcomeLedger, planConfirmationOutcomes, planPaymentFailure, stableRefundAnalyticsId } from "./outcomes";
import { publishConfirmationOutcomes, publishPaymentFailure } from "./posthog-server";
import { DASHBOARD_IDS, consentedCommerceDashboards } from "./dashboards";
import { CONSENTED_MEASUREMENT_DISCLAIMER } from "./reports";
import { decideReplay, isReplaySampled, replayConfigAllowsCapture, replayRouteAllowed, replaySampleBucket, REPLAY_SAMPLE_THRESHOLD, REPLAY_VENDOR_CONFIG } from "./replay";
import { applyReplayDecision, startMaskedReplay, type ReplayRoot } from "./replay-recorder";

const canary = {
  email: "ada@example.com",
  token: "phc_secret_token_value",
  personalToken: "phx_personal_secret",
  address: "12 Long Street Cape Town",
  card: "4242424242424242",
  search: "walnut sideboard",
  note: "leave at the back gate",
  url: "https://shop.example/checkout?access=secret-token&email=ada@example.com",
};

function confirmationPayload(refunds?: { amount_minor: number; currency_code: string; status: string; provider_refund_id?: string }[]) {
  return {
    status: "captured",
    order: {
      id: "order_opaque_1",
      analytics_order_id: "order_opaque_1",
      reference: 42,
      email: canary.email,
      currency_code: "zar",
      total: 1150,
      captured_amount_minor: 115000,
      address: { address_1: canary.address, postal_code: "8001" },
      notes: canary.note,
      items: [{ title: "Sola chair", quantity: 1, total: 1150 }],
      refund_status: {
        items: refunds ?? [
          { amount_minor: 40000, currency_code: "ZAR", status: "succeeded", provider_refund_id: canary.token },
          { amount_minor: 40000, currency_code: "ZAR", status: "succeeded", provider_refund_id: "refund-again" },
          { amount_minor: 1500, currency_code: "ZAR", status: "pending" },
        ],
      },
    },
  };
}

describe("purchase attribution, privacy, and deduplication", () => {
  it("joins a consented guest to a verified customer without copying personal fields", async () => {
    const sent: PostHogCapturePayload[] = [];
    const provider = createPostHogBrowserProvider({
      projectToken: "phc_test_fixture",
      createDistinctId: () => "anonvisitor01",
      fetcher: async (_input, init) => {
        sent.push(JSON.parse(String(init?.body)) as PostHogCapturePayload);
        return new Response("ok");
      },
    });
    provider.capture({
      name: "storefront_page_viewed",
      properties: { page_key: "shop", utm_source: "spring_news", utm_campaign: "bedroom-sale" },
    });
    provider.identify("ada@example.com");
    provider.identify(canary.token);
    provider.identify("cus_verified_1");
    provider.resetIdentity();
    provider.capture({ name: "storefront_product_viewed", properties: { product_id: "prod_chair" } });
    await Promise.resolve();

    expect(sent.map((payload) => payload.event)).toEqual([
      "storefront_page_viewed",
      "storefront_account_signed_in",
      "storefront_product_viewed",
    ]);
    expect(sent[1]).toMatchObject({
      distinct_id: "cus_verified_1",
      properties: { anonymous_id: "anonvisitor01", method: "passwordless", $anon_distinct_id: "anonvisitor01" },
    });
    expect(sent[2]?.distinct_id).not.toBe("cus_verified_1");
    expect(JSON.stringify(sent)).not.toContain(canary.email);
    expect(JSON.stringify(sent)).not.toContain("phc_secret");
    expect(JSON.stringify(sent)).not.toContain("phx_");
  });

  it("emits each purchase and refund once and drops canaries from the server payload", async () => {
    const bodies: string[] = [];
    let calls = 0;
    const ledger = new OutcomeLedger();
    const fetcher = async (_input: RequestInfo | URL, init?: RequestInit) => {
      calls += 1;
      bodies.push(String(init?.body));
      return new Response("ok");
    };
    const headers = { get: (name: string) => name === "x-storefront-analytics-id" ? "anonvisitor01" : name === "x-storefront-customer-type" ? "guest" : null };
    const input = { headers, cartId: "cart_opaque_1", payload: confirmationPayload(), projectToken: "phc_test_fixture", fetcher, ledger };

    const first = await publishConfirmationOutcomes(input);
    const refresh = await publishConfirmationOutcomes(input);
    expect(first).toEqual(["sent", "sent", "sent"]);
    expect(refresh).toEqual(["duplicate", "duplicate", "duplicate"]);
    expect(calls).toBe(3);
    const payload = confirmationPayload();
    const viaCart = planConfirmationOutcomes({ cartId: "cart_opaque_1", customerType: "guest", payload });
    const viaEmail = planConfirmationOutcomes({ orderId: "order_email_route", customerType: "returning", payload });
    const firstRefund = stableRefundAnalyticsId(canary.token);
    const secondRefund = stableRefundAnalyticsId("refund-again");
    expect(firstRefund && secondRefund).toBeTruthy();
    expect(firstRefund).not.toContain("phc_");
    expect(firstRefund).not.toContain(canary.token);
    expect(viaCart.map((item) => item.insertId)).toEqual(viaEmail.map((item) => item.insertId));
    expect(viaCart.map((item) => item.insertId)).toEqual([
      "storefront_order_completed:order_opaque_1",
      `storefront_order_refunded:order_opaque_1:${firstRefund}`,
      `storefront_order_refunded:order_opaque_1:${secondRefund}`,
    ]);
    expect(viaCart.map((item) => item.insertId).join(" ")).not.toMatch(/rf_\d+_/);
    const reordered = confirmationPayload([
      { amount_minor: 40000, currency_code: "ZAR", status: "succeeded", provider_refund_id: "refund-again" },
      { amount_minor: 40000, currency_code: "ZAR", status: "succeeded", provider_refund_id: canary.token },
      { amount_minor: 1500, currency_code: "ZAR", status: "pending" },
    ]);
    expect(planConfirmationOutcomes({ cartId: "cart_other", payload: reordered }).map((item) => item.insertId).sort())
      .toEqual([...viaCart.map((item) => item.insertId)].sort());
    const repeated = confirmationPayload([
      { amount_minor: 40000, currency_code: "ZAR", status: "succeeded", provider_refund_id: "refund-again" },
      { amount_minor: 40000, currency_code: "ZAR", status: "succeeded", provider_refund_id: "refund-again" },
    ]);
    expect(planConfirmationOutcomes({ payload: repeated }).map((item) => item.insertId)).toEqual([
      "storefront_order_completed:order_opaque_1",
      `storefront_order_refunded:order_opaque_1:${secondRefund}`,
    ]);
    const { analytics_order_id: _orderAlias, id: _orderId, ...orderWithoutId } = confirmationPayload().order;
    expect(planConfirmationOutcomes({
      cartId: "cart_opaque_1",
      orderId: "order_other",
      payload: { status: "captured", order: orderWithoutId },
    })).toEqual([]);
    expect(_orderAlias).toBe("order_opaque_1");
    expect(_orderId).toBe("order_opaque_1");
    expect(confirmedPaymentStep({ status: "prepared", analyticsOrderId: "order_opaque_1", customerType: "guest" })).toBeNull();
    expect(confirmedPaymentStep({ status: "captured", analyticsOrderId: "order_opaque_1", customerType: "new" })).toEqual({
      name: "storefront_checkout_step_completed",
      properties: { cart_id: "order_opaque_1", step: "payment", checkout_type: "account" },
    });
    const serialized = bodies.join("\n");
    for (const secret of Object.values(canary)) expect(serialized).not.toContain(secret);
    expect(serialized).not.toContain("Sola chair");
    expect(serialized).toContain("\"value_minor\":115000");
    expect(serialized).toContain("\"$geoip_disable\":true");
    expect(serialized).toContain("\"$insert_id\":");
    expect(bodies.length).toBe(3);
  });

  it("does not capture when consent is missing and still returns after an ingestion outage", async () => {
    let calls = 0;
    const ledger = new OutcomeLedger();
    const outage = async () => {
      calls += 1;
      throw new Error("offline");
    };
    const headers = { get: () => null };
    expect(await publishConfirmationOutcomes({
      headers, cartId: "cart_opaque_1", payload: confirmationPayload(), projectToken: "phc_test_fixture", fetcher: outage, ledger,
    })).toEqual([]);
    expect(calls).toBe(0);
    const consented = { get: (name: string) => name === "x-storefront-analytics-id" ? "anonvisitor01" : null };
    expect(await publishPaymentFailure({
      headers: consented, cartId: "cart_opaque_1", outcome: "declined", projectToken: "phc_test_fixture", fetcher: outage, ledger,
    })).toBe("failed");
    expect(await publishPaymentFailure({
      headers: consented, cartId: "cart_opaque_1", outcome: "declined", projectToken: "phc_test_fixture", fetcher: async () => new Response("ok"), ledger,
    })).toBe("sent");
    expect(await publishPaymentFailure({
      headers: consented, cartId: "cart_opaque_1", outcome: "success", projectToken: "phc_test_fixture", fetcher: async () => { calls += 1; return new Response("ok"); }, ledger,
    })).toBe("skipped");
    expect(planPaymentFailure({ cartId: "cart_opaque_1", outcome: "declined" })?.insertId).toBe("storefront_payment_failed:cart_opaque_1:declined");
  });

  it("keeps personal data and server purchase events off the browser allowlist", () => {
    expect(sanitizeAnalyticsEvent({
      name: "storefront_order_completed",
      properties: { analytics_order_id: "cart_opaque_1", value_minor: 100, item_count: 1, currency: "ZAR", email: canary.email },
    })).toBeNull();
    expect(sanitizeAnalyticsEvent({
      name: "storefront_checkout_started",
      properties: {
        cart_id: "cart_opaque_1", item_count: 1, value_minor: 115000, checkout_type: "guest",
        email: canary.email, address: canary.address, card: canary.card, search_query: canary.search, current_url: canary.url, token: canary.token,
      },
    })).toEqual({
      name: "storefront_checkout_started",
      properties: { schema_version: 1, currency: "ZAR", cart_id: "cart_opaque_1", item_count: 1, value_minor: 115000, checkout_type: "guest" },
    });
    expect(sanitizeAnalyticsEvent({
      name: "storefront_search_results_viewed",
      properties: { query_present: true, result_count: 0, search_query: canary.search, current_url: canary.url },
    })?.properties).not.toHaveProperty("search_query");
  });
});

describe("replay gate", () => {
  it("samples at most ten percent and stops on sensitive routes and overlays", () => {
    expect(REPLAY_VENDOR_CONFIG.session_recording.sampleRate).toBe(0.1);
    expect(REPLAY_VENDOR_CONFIG.session_recording.maskAllInputs).toBe(true);
    expect(REPLAY_VENDOR_CONFIG.session_recording.maskTextSelector).toBe("*");
    expect(REPLAY_VENDOR_CONFIG.session_recording.recordBody).toBe(false);
    expect(REPLAY_VENDOR_CONFIG.session_recording.recordHeaders).toBe(false);
    expect(REPLAY_VENDOR_CONFIG.enable_recording_console_log).toBe(false);
    expect(REPLAY_VENDOR_CONFIG.autocapture).toBe(false);
    expect(REPLAY_VENDOR_CONFIG.ip).toBe(false);
    expect(REPLAY_VENDOR_CONFIG.api_host).toBe(POSTHOG_EU_HOST);

    const keys = Array.from({ length: 400 }, (_value, index) => `session-${index}`);
    expect(REPLAY_SAMPLE_THRESHOLD / 1000).toBe(0.1);
    expect(keys.every((key) => isReplaySampled(key) === (replaySampleBucket(key) < REPLAY_SAMPLE_THRESHOLD))).toBe(true);
    const sampled = keys.find((key) => isReplaySampled(key));
    const unsampled = keys.find((key) => !isReplaySampled(key));
    expect(sampled && unsampled).toBeTruthy();

    const allowed = decideReplay({ consent: "accepted", sessionKey: sampled || "", pathname: "/shop?q=secret", sensitiveOverlay: false });
    expect(allowed.record).toBe(true);
    expect(allowed.config).toBe(REPLAY_VENDOR_CONFIG);
    expect(JSON.stringify(allowed)).not.toContain("secret");

    const journey = ["/shop", "/product/prod_chair", "/bag", "/checkout", "/order/confirmation", "/bag"];
    const reasons = journey.map((pathname) => decideReplay({ consent: "accepted", sessionKey: sampled || "", pathname, sensitiveOverlay: false }).reason);
    expect(reasons).toEqual(["consented_sample", "consented_sample", "consented_sample", "blocked_route", "blocked_route", "consented_sample"]);
    for (const pathname of ["/sign-in", "/sign-up", "/account", "/account/orders/order_1", "/checkout", "/order/confirmation"]) {
      expect(replayRouteAllowed(pathname)).toBe(false);
    }
    expect(decideReplay({ consent: "accepted", sessionKey: sampled || "", pathname: "/shop", sensitiveOverlay: true }).reason).toBe("sensitive_overlay");
    expect(decideReplay({ consent: "rejected", sessionKey: sampled || "", pathname: "/shop", sensitiveOverlay: false }).record).toBe(false);
    expect(decideReplay({ consent: null, sessionKey: sampled || "", pathname: "/bag", sensitiveOverlay: false }).record).toBe(false);
    expect(decideReplay({ consent: "accepted", sessionKey: unsampled || "", pathname: "/shop", sensitiveOverlay: false }).record).toBe(false);

    const root = fakeReplayRoot(canary.email);
    const open = decideReplay({ consent: "accepted", sessionKey: sampled || "", pathname: "/shop", sensitiveOverlay: false });
    let recording = applyReplayDecision(null, open, root);
    expect(recording?.recording).toBe(true);
    expect(root.subscribed).toBe(true);
    const kept = applyReplayDecision(recording, open, root);
    expect(kept).toBe(recording);
    root.emit();
    expect(recording?.frames()).toEqual([{ kind: "input", masked: "*" }]);
    expect(JSON.stringify(recording?.frames())).not.toContain(canary.email);
    expect(JSON.stringify(recording?.frames())).not.toContain(canary.token);

    recording = applyReplayDecision(recording, decideReplay({
      consent: "rejected", sessionKey: sampled || "", pathname: "/shop", sensitiveOverlay: false,
    }), root);
    expect(recording).toBeNull();
    expect(root.subscribed).toBe(false);

    recording = applyReplayDecision(null, open, root);
    recording = applyReplayDecision(recording, decideReplay({
      consent: "accepted", sessionKey: sampled || "", pathname: "/shop", sensitiveOverlay: true,
    }), root);
    expect(recording).toBeNull();

    recording = applyReplayDecision(null, open, root);
    recording = applyReplayDecision(recording, decideReplay({
      consent: "accepted", sessionKey: sampled || "", pathname: "/checkout", sensitiveOverlay: false,
    }), root);
    expect(recording).toBeNull();

    const unrestricted = {
      ...REPLAY_VENDOR_CONFIG,
      autocapture: true,
      capture_pageview: true,
      enable_recording_console_log: true,
      session_recording: {
        ...REPLAY_VENDOR_CONFIG.session_recording,
        maskAllInputs: false,
        maskTextSelector: "",
        recordHeaders: true,
        recordBody: true,
      },
    };
    expect(replayConfigAllowsCapture(unrestricted)).toBe(false);
    const quiet = fakeReplayRoot(canary.address);
    expect(startMaskedReplay(unrestricted as typeof REPLAY_VENDOR_CONFIG, quiet).recording).toBe(false);
    expect(quiet.subscribed).toBe(false);
  });
});

function fakeReplayRoot(secret: string): ReplayRoot & { secret: string; subscribed: boolean; emit(): void } {
  let listener: (() => void) | null = null;
  return {
    secret,
    subscribed: false,
    subscribe(next) {
      listener = next;
      this.subscribed = true;
      return () => {
        listener = null;
        this.subscribed = false;
      };
    },
    emit() { listener?.(); },
  };
}

describe("seven commerce dashboards", () => {
  it("uses consent-scoped denominators and server revenue only", () => {
    const dashboards = consentedCommerceDashboards([
      { event: "storefront_page_viewed", distinct_id: "anonvisitor01", properties: { page_key: "shop", utm_source: "spring_news", utm_campaign: "bedroom-sale" } },
      { event: "storefront_product_viewed", distinct_id: "anonvisitor01", properties: { product_id: "prod_chair" } },
      { event: "storefront_product_viewed", distinct_id: "anonvisitor01", properties: { product_id: "prod_chair" } },
      { event: "storefront_search_results_viewed", distinct_id: "anonvisitor01", properties: { query_present: true, result_count: 2, availability: "all", sort_order: "default", price_filter_active: false, search_query: canary.search } },
      { event: "storefront_cart_item_added", distinct_id: "anonvisitor01", properties: { variant_id: "variant_1", product_id: "prod_chair", quantity: 1, value_minor: 115000 } },
      { event: "storefront_cart_viewed", distinct_id: "anonvisitor01", properties: { cart_id: "cart_opaque_1", item_count: 1, value_minor: 115000 } },
      { event: "storefront_checkout_started", distinct_id: "anonvisitor01", properties: { cart_id: "cart_opaque_1", item_count: 1, value_minor: 999999, checkout_type: "guest", email: canary.email } },
      { event: "storefront_shipping_method_selected", distinct_id: "anonvisitor01", properties: { cart_id: "cart_opaque_1", method_id: "delivery" } },
      { event: "storefront_checkout_step_completed", distinct_id: "anonvisitor01", properties: { cart_id: "cart_opaque_1", step: "payment", checkout_type: "guest" } },
      { event: "storefront_account_signed_in", distinct_id: "cus_verified_1", properties: { method: "passwordless", anonymous_id: "anonvisitor01" } },
      { event: "storefront_account_created", distinct_id: "cus_verified_1", properties: { method: "passwordless", anonymous_id: "anonvisitor01" } },
      { event: "storefront_order_completed", distinct_id: "cus_verified_1", properties: { analytics_order_id: "cart_opaque_1", value_minor: 115000, item_count: 1, currency: "ZAR", customer_type: "new", email: canary.email } },
      { event: "storefront_order_refunded", distinct_id: "cus_verified_1", properties: { analytics_order_id: "cart_opaque_1", refund_id: "rf_0_40000", refund_minor: 40000, currency: "ZAR", address: canary.address } },
      { event: "storefront_payment_failed", distinct_id: "anonvisitor02", properties: { analytics_order_id: "cart_other", provider: "test_simulator", reason_family: "declined", card: canary.card } },
      { event: "storefront_friction_noted", distinct_id: "anonvisitor02", properties: { surface: "checkout", kind: "reservation_expired", note: canary.note } },
      { name: "arbitrary_event", properties: { token: canary.token, current_url: canary.url } },
    ]);

    expect(Object.keys(dashboards)).toEqual([...DASHBOARD_IDS]);
    for (const dashboard of Object.values(dashboards)) {
      expect(dashboard.scope).toBe("consented_visitors");
      expect(dashboard.disclaimer).toBe(CONSENTED_MEASUREMENT_DISCLAIMER);
      expect(dashboard.denominators).toBe("matching_consent_scope");
    }
    expect(dashboards.store_health.revenue_authority).toBe("server_confirmed_orders_and_refunds");
    expect(dashboards.store_health.rows).toEqual(expect.arrayContaining([
      { metric: "orders", value: 1 },
      { metric: "revenue_minor", value: 115000 },
      { metric: "refunded_minor", value: 40000 },
      { metric: "net_revenue_minor", value: 75000 },
    ]));
    expect(dashboards.acquisition.rows).toEqual([
      { utm_source: "spring_news", utm_campaign: "bedroom-sale", visitors: 1, orders: 1, revenue_minor: 115000 },
    ]);
    expect(dashboards.product_performance.rows).toEqual([
      { product_id: "prod_chair", viewers: 1, active_seconds: 0, selections: 0, add_to_cart: 1 },
    ]);
    expect(dashboards.purchase_funnel.rows.map((row) => row.visitors)).toEqual([1, 1, 1, 1, 1, 1, 1]);
    expect(dashboards.search_merchandising.rows).toEqual(expect.arrayContaining([{ metric: "orders_after_search", value: 1 }]));
    expect(dashboards.friction_quality.rows).toEqual(expect.arrayContaining([
      { metric: "replay_sample_rate", value: 0.1 },
      { kind: "declined", value: 1 },
      { kind: "reservation_expired", value: 1 },
    ]));
    expect(dashboards.accounts.rows).toEqual(expect.arrayContaining([
      { metric: "account_created", value: 1 },
      { metric: "account_signed_in", value: 1 },
      { customer_type: "new", orders: 1 },
    ]));
    expect(JSON.stringify(dashboards)).not.toContain(canary.email);
    expect(JSON.stringify(dashboards)).not.toContain(canary.search);
    expect(JSON.stringify(dashboards)).not.toContain(canary.card);
    expect(JSON.stringify(dashboards)).not.toContain("999999");
  });
});

describe("analytics policy baseline", () => {
  it("records the one-year event retention, 30-day replay retention, and a real billing limit", () => {
    expect(ANALYTICS_POLICY.projectId).toBe("292683");
    expect(ANALYTICS_POLICY.ingestHost).toBe(POSTHOG_EU_INGEST_HOST);
    expect(POSTHOG_EU_INGEST_HOST).toBe(POSTHOG_EU_HOST);
    expect(ANALYTICS_POLICY.analyticsRetention).toBe("P1Y");
    expect(ANALYTICS_POLICY.replayRetention).toBe("P30D");
    expect(ANALYTICS_POLICY.retentionIsNotDeletion).toBe(true);
    expect(ANALYTICS_POLICY.analyticsBillingLimitUsd).toBe(5);
    expect(ANALYTICS_POLICY.platformBudgetUsd).toBe(50);
    expect(ANALYTICS_POLICY.billingAlertIsHardCap).toBe(false);
    expect(ANALYTICS_POLICY.billingLimitDropsIngestion).toBe(true);
    expect(ANALYTICS_POLICY.geoipEnrichment).toBe("disabled");
    expect(ANALYTICS_POLICY.ipRetention).toBe("disabled");
    expect(ANALYTICS_POLICY.replaySampleRate).toBeLessThanOrEqual(0.1);
  });
});
